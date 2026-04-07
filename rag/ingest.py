#import pdfplumber # อ่านไฟล์ PDF ดึงข้อความออกมา
import fitz 
import re
# from langchain_text_splitters import RecursiveCharacterTextSplitter # แบ่งข้อความยาว → เป็น chunk เล็ก ๆ
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

def split_by_course(text):
    pattern = r'(?=\d+\.\s+[^\d])'                      # pattern จับบรรทัดที่ขึ้นต้นด้วยตัวเลขตาม เช่น 1. CS102
    parts = re.split(pattern, text)                     # ตัดข้อความทุกตำแหน่งที่ pattern ตรงกัน

    chunks = [p.strip() for p in parts if p.strip()]    # .strip() → ตัด whitespace หัว-ท้ายของแต่ละชิ้น

    return chunks

def extract_metadata(chunk):  # ดึงข้อมูลเมตาดาต้าของรายวิชา จากข้อความ chunk

    # re.findall ค้นหาทุกตำแหน่งที่ตรงกับ pattern แล้วคืนค่าเป็น list
    th_code = re.findall(r'คพ\s*\.\s*\d+', chunk)                           # จับได้: คพ.101, คพ . 101, คพ.2101
    en_code = re.findall(r'CS\d+', chunk)                                   # จับได้: CS101, CS2101
    en_name = re.findall(r'CS\d+\s+([A-Za-z][A-Za-z\s\-]+)\)', chunk)       # จับได้: CS101 Introduction to Python) → ได้ "Introduction to Python"
    th_name = re.findall(r'คพ\s*\.\s*\d+\s+([\u0E00-\u0E7F][^\(]+)', chunk) # จับได้: คพ.101 การเขียนโปรแกรม ( → ได้ "การเขียนโปรแกรม "

    return {
        "th_code": th_code[0] if th_code else None,
        "en_code": en_code[0] if en_code else None,
        "en_name": en_name[0].strip() if en_name else None,
        "th_name": th_name[0].strip() if th_name else None,
    }


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
        metadata = extract_metadata(chunk)
        points.append(                      # เพิ่มข้อมูลลง list
            PointStruct(
                id=i,                       # กำหนด id 0, 1, 2, 3,...
                vector=emb,                 # vector ของ chunk นั้น
                payload={
                    "text": chunk,
                    "th_code": metadata["th_code"],
                    "en_code": metadata["en_code"],
                    "en_name": metadata["en_name"],
                    "th_name": metadata["th_name"],
                    "chunk_index": i,
                }     
            )
        )

    client.upsert(                          # update + insert ข้อมูลลง database
        collection_name="coursesdetail",
        points=points                       # เอา list vectors ที่เราสร้างมาเก็บ
    )


if __name__ == "__main__":

    text = load_pdf("data/coursesdetail.pdf")  # เรียก load_pdf() แปลงไฟล์ pdf เป็น text
    
    chunks = split_by_course(text)               # แบ่ง text เป็น chunk

    embeddings = create_embeddings(chunks)  # แปลง chunk text → vectors

    store_vectors(chunks, embeddings)       # เก็บ vectors ลง Qdrant

    print("✅ Ingest Complete")