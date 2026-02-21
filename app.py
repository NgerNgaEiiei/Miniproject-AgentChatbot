from agent.decision import count_courses, get_course_detail, check_prerequisite
from llm.llm_helper import decide_action, generate_response

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

        if action_name not in TOOLS:
            final_answer = generate_response({}, user_input)
            print("Agent:", final_answer)
            continue

        # 2️⃣ Execute tool
        observation = TOOLS[action_name](**action_input)

        # 3️⃣ Generate final response
        final_answer = generate_response(observation, user_input)

        print("Agent:", final_answer)

    except Exception as e:
        print("Agent Error:", e)