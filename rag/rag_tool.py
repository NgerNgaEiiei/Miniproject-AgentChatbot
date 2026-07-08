from rag.search import search_doc_with_id

def get_rag_context(query):
    """
    ค้นหาเอกสารที่เกี่ยวข้องจาก Qdrant แล้วคืนเป็น string context
    ใช้ search_doc_with_id เพื่อได้ metadata + rerank ตาม course code
    """
    docs = search_doc_with_id(query)

    parts = []
    for doc in docs:
        # ใส่ชื่อวิชาไว้ด้านบนเพื่อให้ LLM รู้ว่าข้อความนี้เป็นของวิชาไหน
        header = f"[{doc['en_code']} | {doc['th_name']}]"
        parts.append(f"{header}\n{doc['text']}")

    return "\n\n".join(parts)
