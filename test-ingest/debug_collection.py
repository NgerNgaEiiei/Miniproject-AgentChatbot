"""
debug_collection.py — ตรวจสอบว่า collection rebuild ถูกต้องหรือเปล่า
รัน: python test-ingest/debug_collection.py
"""
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

COLLECTION_NAME = "course_chunks_collection"
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
client = QdrantClient("localhost", port=6333)

# 1. นับจำนวน chunk ทั้งหมดใน collection
info = client.get_collection(COLLECTION_NAME)
print(f"✅ Collection: {COLLECTION_NAME}")
print(f"   จำนวน vectors: {info.points_count}")
print()

# 2. ดู payload ของ chunk 5 (CS111/OOP) ว่า metadata ถูกต้องไหม
chunk5 = client.retrieve(COLLECTION_NAME, ids=[5])[0]
print(f"chunk_id=5 payload:")
print(f"  en_code : {chunk5.payload.get('en_code')}")
print(f"  th_name : {chunk5.payload.get('th_name')}")
print(f"  text    : {chunk5.payload.get('text', '')[:100]}...")
print()

# 3. ทดสอบ query "OOP" ดูว่า top-3 คือวิชาอะไร
queries = [
    "อยากเรียนเรื่อง OOP ต้องลงวิชาอะไร?",
    "วิชา CS102 เรียนอะไร",
    "วิชาไหนสอนเรื่อง sorting และ searching?",
    "วิชาไหนเกี่ยวกับ algorithm บ้าง?",
]

print("=" * 60)
for q in queries:
    vec = model.encode(q)
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vec,
        limit=3,
    ).points
    ids = [r.id for r in results]
    names = [f"[{r.id}] {r.payload.get('en_code','?')} {r.payload.get('th_name','?')}" for r in results]
    print(f"Query: {q}")
    print(f"  Retrieved: {ids}")
    for n in names:
        print(f"    {n}")
    print()
