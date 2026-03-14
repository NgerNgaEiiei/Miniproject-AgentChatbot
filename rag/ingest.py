#import pdfplumber # อ่านไฟล์ PDF ดึงข้อความออกมา
import fitz 
import re
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter # แบ่งข้อความยาว → เป็น chunk เล็ก ๆ
from sentence_transformers import SentenceTransformer # แปลง text → vector (embedding)
from qdrant_client import QdrantClient # เชื่อมต่อกับ Qdrant Vector Database
from qdrant_client.models import VectorParams, Distance, PointStruct # ใช้กำหนดโครงสร้างของ vector database


def load_pdf(path):
    text = ""
    doc = fitz.open(path)
    for page in doc:
        extracted = page.get_text("text")
        if extracted:
            cleaned = re.sub(r'\n', ' ', extracted)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            text += cleaned + "\n"

    return text 


def split_text(text): # หาเพิ่ม
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,     # แต่ละ chunk 500 ตัวอักษร
        chunk_overlap=50,   # chunk จะทับกัน 100 ตัวอักษร
        separators=["\n\d+\.", "\n", " ", ""],
    )

    chunks = splitter.split_text(text)

    return chunks


model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2") # Model สำหรับทำ embedding

def create_embeddings(chunks):
    embeddings = model.encode(chunks)

    return embeddings


client = QdrantClient("localhost", port=6333)       # เชื่อมต่อ Qdrant

# ลบ collection เก่า ป้องกันข้อมูลซ้ำ
try:
    client.delete_collection("coursesdetail")
except:
    pass

client.create_collection(               # สร้าง collection ใหม่ใน vector database
    collection_name="coursesdetail",       # ตั้งชื่อ
    vectors_config=VectorParams(        
        size=384,                       # vector dimension ต้องตรงกับ embedding model
        distance=Distance.COSINE        # ใช้ Cosine similarity สำหรับวัดว่า vector ไหนคล้ายกัน
    )
)

def store_vectors(chunks, embeddings):

    points = []     # สร้าง list ไว้เก็บข้อมูล

    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        # ลองดึงรหัสวิชา เช่น คพ.xxx หรือ CSxxx ออกมาเป็น metadata
        # course_code = re.findall(r'[คพCS]+\.?\s?\d+', chunk)
        
        points.append(                      # เพิ่มข้อมูลลง list
            PointStruct(
                id=i,                       # กำหนด id 0, 1, 2, 3,...
                vector=emb,                 # vector ของ chunk นั้น
                payload={
                    "text": chunk,
                    # "course_codes": course_code
                }     
            )
        )

    client.upsert(                          # update + insert ข้อมูลลง database
        collection_name="coursesdetail",
        points=points                       # เอา list vectors ที่เราสร้างมาเก็บ
    )


if __name__ == "__main__":

    text = load_pdf("data/coursesdetail.pdf")  # เรียก load_pdf() แปลงไฟล์ pdf เป็น text
    
    chunks = split_text(text)               # แบ่ง text เป็น chunk

    embeddings = create_embeddings(chunks)  # แปลง chunk text → vectors

    store_vectors(chunks, embeddings)       # เก็บ vectors ลง Qdrant

    print("✅ Ingest Complete")