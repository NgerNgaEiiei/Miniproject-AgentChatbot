import pdfplumber # อ่านไฟล์ PDF ดึงข้อความออกมา
from langchain_text_splitters import RecursiveCharacterTextSplitter # แบ่งข้อความยาว → เป็น chunk เล็ก ๆ
from sentence_transformers import SentenceTransformer # แปลง text → vector (embedding)
from qdrant_client import QdrantClient # เชื่อมต่อกับ Qdrant Vector Database
from qdrant_client.models import VectorParams, Distance, PointStruct # ใช้กำหนดโครงสร้างของ vector database

def load_pdf(path):
    text = ""

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    return text


def split_text(text):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, # แต่ละ chunk ~500 ตัวอักษร
        chunk_overlap=100 # chunk จะทับกัน 100 ตัวอักษร
        # Chunk 1
            # [ 0 ----------- 500 ]

        # Chunk 2
                    # [400 ----------- 900]
    )

    chunks = splitter.split_text(text)

    return chunks


model = SentenceTransformer("all-MiniLM-L6-v2")

def create_embeddings(chunks):
    embeddings = model.encode(chunks)

    return embeddings


client = QdrantClient(path="qdrant_db")         # เชื่อมต่อ Qdrant

# ลบ collection เก่า ป้องกันข้อมูลซ้ำ
try:
    client.delete_collection("curriculum")
except:
    pass

client.create_collection(               # สร้าง collection ใหม่ใน vector database
    collection_name="curriculum",       # ตั้งชื่อ
    vectors_config=VectorParams(        
        size=384,                       # vector dimension ต้องตรงกับ embedding model
        distance=Distance.COSINE        # ใช้ Cosine similarity สำหรับวัดว่า vector ไหนคล้ายกัน
    )
)

def store_vectors(chunks, embeddings):

    points = []     # สร้าง list ไว้เก็บข้อมูล

    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        points.append(                      # เพิ่มข้อมูลลง list
            PointStruct(
                id=i,                       # กำหนด id 0, 1, 2, 3,...
                vector=emb,                 # vector ของ chunk นั้น
                payload={"text": chunk}     # เก็บ text จริงไว้ด้วย เวลาค้นหา vector จะได้ vector → text
            )
        )

    client.upsert(                          # update + insert ข้อมูลลง database
        collection_name="curriculum",
        points=points                       # เอา list vectors ที่เราสร้างมาเก็บ
    )


if __name__ == "__main__":

    text = load_pdf("data/curriculum.pdf")  # เรียก load_pdf() แปลงไฟล์ pdf เป็น text

    chunks = split_text(text)               # แบ่ง text เป็น chunk

    embeddings = create_embeddings(chunks)  # แปลง chunk text → vectors

    store_vectors(chunks, embeddings)       # เก็บ vectors ลง Qdrant

    print("✅ Ingest Complete")