from sentence_transformers import SentenceTransformer # Library สำหรับสร้าง embedding
from qdrant_client import QdrantClient   # เชื่อมต่อกับ Qdrant Vector DB

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2") # model ที่แปลง text → embedding vector

client = QdrantClient("localhost", port=6333)

def search_docs(query, top_k=3):        # query:คำถามผู้ใข้, top_k=3 : ดึงเอกสารที่ใกล้ที่สุด 3 ชิ้น

    query_vector = model.encode(query)  # แปลงคำถามเป็น vector

    results = client.query_points(      # ค้นหาใน Vector Database
        collection_name="coursesdetail",   # ค้นหาใน collection curriculum
        query=query_vector,             # ใช้ vector ของคำถามเป็นตัวค้นหา
        limit=top_k                     # เอาผลลัพธ์ top_k ชิ้น (3)
    ).points                            # Qdrant จะคืนข้อมูลแบบ object เอาเฉพาะ points

    docs = []                           # สร้าง list ว่าง เพื่อเก็บ text ของเอกสาร

    for r in results:
        docs.append(r.payload["text"])  # ดึง text จาก payload (ดึงข้อความจริงจาก PDF)

    return docs