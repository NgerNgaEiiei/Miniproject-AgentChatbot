from agent.decision import count_courses, get_course_detail, check_prerequisite
from llm.llm_helper import decide_action, generate_response
from rag.rag_tool import get_rag_context

TOOLS = {
    "count_courses": count_courses,
    "get_course_detail": get_course_detail,
    "check_prerequisite": check_prerequisite,
}

print("🎓 Mini CS Advisor Agent (Agent Version)")
print("พิมพ์ 'exit' เพื่อออก\n")

while True:
    user_input = input("คุณ: ")

    if user_input.lower() == "exit":
        break

    try:

        # 1️⃣ Agent decides action
        action_data = decide_action(user_input)

        if not action_data:
            print("Agent: ขออภัย ฉันไม่เข้าใจคำถามนี้")
            continue

        action_name = action_data["action"]
        action_input = action_data.get("input", {})

        observation = None

        # 2️⃣ Execute tool if exists
        if action_name in TOOLS:
            observation = TOOLS[action_name](**action_input)

        # 3️⃣ RAG search
        rag_context = get_rag_context(user_input)

        # 4️⃣ Combine context
        context = {
            "tool_result": observation,
            "rag_docs": rag_context
        }

        # 5️⃣ Generate final response
        final_answer = generate_response(context, user_input)

        print("Agent:", final_answer)

    except Exception as e:
        print("Agent Error:", e)