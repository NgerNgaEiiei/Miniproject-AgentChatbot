import json
import os
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

def load_json_chunks(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# กำหนดชื่อ Collection ใหม่ได้เลย
COLLECTION_NAME = "course_chunks_collection"

# Model สำหรับทำ embedding แบบเดียวกับที่ใช้ใน ingest.py
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

def create_embeddings(texts):
    embeddings = model.encode(texts)
    return embeddings


def build_embed_text(item: dict) -> str:
    """
    สร้าง augmented text สำหรับ embed โดยรวม:
      - รหัสวิชา (EN + TH) และชื่อวิชา (EN + TH) เป็น header
      - content คำอธิบายวิชาต่อท้าย
    เพื่อให้ embedding จับ course identity ได้
    เช่น query "OOP" จะ match กับ header "Object-Oriented Concepts แนวคิดเชิงวัตถุ"
    และ query "CS 102" จะ match กับ header "CS 102 คพ.102"
    """
    meta = item.get("metadata", {})
    en_code  = meta.get("en_code", "") or ""
    th_code  = meta.get("th_code", "") or ""
    en_name  = meta.get("en_name", "") or ""
    th_name  = meta.get("th_name", "") or ""
    content  = item.get("content", "") or ""

    header = f"วิชา {en_code} {th_code} {th_name} {en_name}"
    return f"{header}\n{content}"

client = QdrantClient("localhost", port=6333)       # เชื่อมต่อ Qdrant

# ลบ collection เก่า (ถ้ามี) ป้องกันข้อมูลซ้ำ
try:
    client.delete_collection(COLLECTION_NAME)
    print(f"Deleted existing collection: {COLLECTION_NAME}")
except:
    pass

client.create_collection(               # สร้าง collection ใหม่ใน vector database
    collection_name=COLLECTION_NAME,       
    vectors_config=VectorParams(        
        size=384,                       # vector dimension ต้องตรงกับ embedding model
        distance=Distance.COSINE        # ใช้ Cosine similarity
    )
)

def store_vectors(items, embeddings):
    points = []     

    for i, (item, emb) in enumerate(zip(items, embeddings)):
        content = item.get("content", "")
        metadata = item.get("metadata", {})
        
        points.append(
            PointStruct(
                id=i,                       
                vector=emb,                 
                payload={
                    "text": content,
                    "th_code": metadata.get("th_code"),
                    "en_code": metadata.get("en_code"),
                    "en_name": metadata.get("en_name"),
                    "th_name": metadata.get("th_name"),
                    "sentence_count": item.get("sentence_count"),
                    "chunk_index": i,
                }     
            )
        )

    # ทยอย upsert ทีละ batch ถ้าข้อมูลมีเยอะไป, แต่ปกติไซส์เท่านี้หลักร้อย upsert ได้เลย
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i+batch_size]
        client.upsert(                          
            collection_name=COLLECTION_NAME,
            points=batch                       
        )

if __name__ == "__main__":
    # ไฟล์ course_chunks.json เก็บอยู่ใน test-ingest/result/
    json_path = os.path.join(os.path.dirname(__file__), "result", "course_chunks.json")
    
    print(f"Loading data from {json_path} ...")
    items = load_json_chunks(json_path)

    # สร้าง augmented text (header + content) สำหรับ embed
    # payload.text ยังเก็บ content เดิมไว้ใช้ตอนสร้างคำตอบ
    text_chunks = [build_embed_text(item) for item in items]
    
    print("Creating Embeddings (may take a moment) ...")
    embeddings = create_embeddings(text_chunks)  

    print(f"Storing into Qdrant collection '{COLLECTION_NAME}' ...")
    store_vectors(items, embeddings)       

    print("✅ Ingest Complete")
