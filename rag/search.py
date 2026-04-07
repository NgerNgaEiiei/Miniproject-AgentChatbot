import re
from sentence_transformers import SentenceTransformer # Library สำหรับสร้าง embedding
from qdrant_client import QdrantClient   # เชื่อมต่อกับ Qdrant Vector DB

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2") # model ที่แปลง text → embedding vector

client = QdrantClient("localhost", port=6333)

def search_docs(query, top_k=3):        # query:คำถามผู้ใข้, top_k=3 : ดึงเอกสารที่ใกล้ที่สุด 3 ชิ้น

    query_vector = model.encode(query)  # แปลงคำถามเป็น vector

    results = client.query_points(      # ค้นหาใน Vector Database
        collection_name="coursesdetail",   # ค้นหาใน collection curriculum, coursesdetail
        query=query_vector,             # ใช้ vector ของคำถามเป็นตัวค้นหา
        limit=top_k                     # เอาผลลัพธ์ top_k ชิ้น (3)
    ).points                            # Qdrant จะคืนข้อมูลแบบ object เอาเฉพาะ points

    docs = []                           # สร้าง list ว่าง เพื่อเก็บ text ของเอกสาร

    for r in results:
        docs.append(r.payload["text"])  # ดึง text จาก payload (ดึงข้อความจริงจาก PDF)

    return docs


# ========== Code for evaluate ===============
def extract_code(query):                       # ดึงรหัสวิชาจาก query
    match = re.search(r"CS\d+", query)
    return match.group(0) if match else None


def rerank_with_code_boost(query, docs):       # เอาผลลัพธ์ที่ retrieve มาแล้วจัดอันดับใหม่
    code = extract_code(query)

    def score(doc):                            # scoring function ที่จะใช้ในการ sort
        base = doc["score"]

        # ⭐ boost ถ้ามี code ตรง +1.0 boost score
        if code and doc["en_code"] == code:
            base += 1.0

        return base

    return sorted(docs, key=score, reverse=True) # เอา doc ทีละตัวไปคำนวณ “คะแนนใหม่”


def search_doc_with_id(query, top_k=3):
    query_vector = model.encode(query)

    results = client.query_points(
        collection_name="coursesdetail",
        query=query_vector,
        limit=top_k
    ).points

    docs = []
    for r in results:
        docs.append({
            "id": r.id,
            "text": r.payload["text"],
            "th_code": r.payload.get("th_code"),
            "en_code": r.payload.get("en_code"),
            "score": r.score   # ⭐ สำคัญ
        })

    # ⭐ rerank ตรงนี้
    docs = rerank_with_code_boost(query, docs)

    # เอา top_k หลัง rerank
    return docs[:top_k]