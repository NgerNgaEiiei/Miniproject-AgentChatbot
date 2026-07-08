import re
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

COLLECTION_NAME = "course_chunks_collection"  # ชื่อ collection ใน Qdrant (ตรงกับ ingest_course_chunks.py)

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")  # multilingual model รองรับภาษาไทย-อังกฤษ

client = QdrantClient("localhost", port=6333)


def normalize_query(query: str) -> str:
    """
    Normalize รหัสวิชาใน query ให้ตรงกับ format ใน collection
    เช่น "CS216" → "CS 216", "cs271" → "CS 271"
    ป้องกัน format mismatch ระหว่าง query กับ header ที่ embed ไว้
    """
    return re.sub(r'([A-Za-z]+)(\d+)', lambda m: m.group(1).upper() + ' ' + m.group(2), query)


def extract_code(query: str) -> str | None:
    """ดึงรหัสวิชา EN จากคำถาม เช่น 'CS271' หรือ 'CS 271' → 'CS 271'"""
    match = re.search(r"CS\s*\d{3}", query, re.IGNORECASE)
    if match:
        raw = match.group(0).upper()
        return re.sub(r"CS(\d)", r"CS \1", raw)  # normalize เป็น "CS 271"
    return None


def rerank_with_code_boost(query: str, docs: list) -> list:
    """
    จัดอันดับ docs ใหม่หลัง vector search
    ถ้าคำถามระบุรหัสวิชาตรงๆ เช่น "CS 271 คืออะไร"
    → boost score ของวิชานั้น +1.0 เพื่อให้ขึ้นมาอยู่อันดับแรก
    """
    code = extract_code(query)

    def score(doc):
        base = doc["score"]
        if code and doc.get("en_code") == code:
            base += 1.0
        return base

    return sorted(docs, key=score, reverse=True)


def search_doc_with_id(query: str, top_k: int = 3) -> list:
    """
    ค้นหาเอกสารที่เกี่ยวข้องกับคำถามจาก Qdrant
    คืน list ของ dict พร้อม metadata (en_code, th_name ฯลฯ)
    เพื่อให้ rag_tool.py นำไปสร้าง context ให้ LLM

    ขั้นตอน:
      1. แปลงคำถามเป็น vector ด้วย embedding model
      2. ค้นหา top_k chunks ที่ใกล้เคียงที่สุดใน Qdrant
      3. rerank โดย boost วิชาที่ตรงกับรหัสในคำถาม
    """
    query = normalize_query(query)
    query_vector = model.encode(query)

    # ดึง candidate pool ใหญ่กว่า top_k เพื่อให้ rerank มีตัวเลือกมากขึ้น
    # กรณีที่ query ระบุรหัสวิชาตรงๆ chunk ที่ตรงอาจไม่ติด top-k แรกของ vector search
    # แต่จะถูก boost ขึ้นมาได้ใน rerank_with_code_boost
    candidate_pool = max(top_k * 5, 15)
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=candidate_pool,
    ).points

    docs = []
    for r in results:
        docs.append({
            "id":      r.id,
            "text":    r.payload["text"],
            "th_code": r.payload.get("th_code"),
            "en_code": r.payload.get("en_code"),
            "th_name": r.payload.get("th_name"),
            "en_name": r.payload.get("en_name"),
            "score":   r.score,
        })

    docs = rerank_with_code_boost(query, docs)

    return docs[:top_k]