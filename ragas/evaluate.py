from search import search_doc_with_id 

# Pipeline: 
# Query → search_doc_with_id → ได้ docs → เทียบกับ ground truth → คำนวณ metrics

test_data = [ 
    { 
        "query": "วิชา CS102 เรียนอะไร", 
        "relevant_ids": [1] 
    }, 
    { 
        "query": "อยากเรียนเรื่อง OOP ต้องลงวิชาอะไร?",
        "relevant_ids": [2] 
    }, 
    { 
        "query": "วิชาไหนสอนเรื่อง sorting และ searching?", 
        "relevant_ids": [3] 
    }, 
    { 
        "query": "วิชาไหนเกี่ยวกับ algorithm บ้าง?", 
        "relevant_ids": [3] 
    }, 
] 


# -------------------------
# Metrics
# -------------------------

def recall_at_k(retrieved_ids, relevant_ids, k): 
    hit_count = 0  # จำนวน id ที่ตรงกัน
    
    for r in retrieved_ids[:k]: 
        if r in relevant_ids: 
            hit_count += 1 
    
    return hit_count / len(relevant_ids) if relevant_ids else 0


def precision_at_k(retrieved_ids, relevant_ids, k):
    hit_count = 0
    
    for r in retrieved_ids[:k]:
        if r in relevant_ids:
            hit_count += 1
    
    return hit_count / len(retrieved_ids[:k]) if retrieved_ids else 0


def mrr_at_k(retrieved_ids, relevant_ids):
    for i, r in enumerate(retrieved_ids):
        if r in relevant_ids:
            return 1 / (i + 1)
    return 0


# -------------------------
# Evaluation Functions
# -------------------------

def evaluate_recall(top_k=3): 
    total = 0 
    
    for item in test_data: 
        results = search_doc_with_id(item["query"], top_k) 
        retrieved_ids = [r["id"] for r in results] 

        score = recall_at_k(retrieved_ids, item["relevant_ids"], top_k)

        print("Query:", item["query"])
        print("Retrieved IDs:", retrieved_ids)
        print("Expected IDs:", item["relevant_ids"])
        print("Recall:", score)
        print("------")
        
        total += score 
    
    return total / len(test_data) 


def evaluate_precision(top_k=3):
    total = 0
    
    for item in test_data:
        results = search_doc_with_id(item["query"], top_k)
        retrieved_ids = [r["id"] for r in results]

        score = precision_at_k(retrieved_ids, item["relevant_ids"], top_k)

        print("Query:", item["query"])
        print("Retrieved IDs:", retrieved_ids)
        print("Expected IDs:", item["relevant_ids"])
        print("Precision:", score)
        print("------")
        
        total += score
    
    return total / len(test_data)


def evaluate_mrr(top_k=3):
    total = 0
    
    for item in test_data:
        results = search_doc_with_id(item["query"], top_k)
        retrieved_ids = [r["id"] for r in results]

        score = mrr_at_k(retrieved_ids, item["relevant_ids"])

        print("Query:", item["query"])
        print("Retrieved IDs:", retrieved_ids)
        print("MRR :", score)
        print("------")
        
        total += score
    
    return total / len(test_data)


# -------------------------
# Main
# -------------------------

if __name__ == "__main__": 
    recall = evaluate_recall(top_k=3) 
    print("Recall@3 เจอของถูกไหม =", recall)

    precision = evaluate_precision(top_k=3)
    print("Precision@3 ของที่เอามา มั่วไหม =", precision)

    mrr = evaluate_mrr(top_k=3)
    print("MRR@3 คำตอบที่ถูก อยู่ลำดับที่เท่าไหร่ =", mrr)

    print("===== สรุปผล =====")
    print("Recall@3 =", recall)
    print("Precision=", precision)
    print("MRR@3 =", mrr)