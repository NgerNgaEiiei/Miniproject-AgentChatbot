import re
from agent.decision import check_prerequisite, count_courses
from llm.llm_helper import classify_intent, explain_result, chat_freely, explain_curriculum


completed_courses = ["CS101"]

print("🎓 Mini CS Advisor Agent")
print("พิมพ์ 'exit' เพื่อออก\n")

def extract_course_id(text):
    match = re.search(r'CS\d+', text.upper())
    if match:
        return match.group()
    return None

while True:
    user_input = input("คุณ: ")

    if user_input.lower() == "exit":
        break

    intent = classify_intent(user_input)
    print("DEBUG INTENT:", intent)


    if intent == "check_prerequisite":

        course_id = extract_course_id(user_input)

        if not course_id:
            print("Agent: กรุณาระบุรหัสวิชา เช่น CS201")
            continue

        ok, missing = check_prerequisite(course_id, completed_courses)
        response = explain_result(course_id, ok, missing)

        print("Agent:", response)
    
    elif intent == "ask_curriculum_overview":
        total = count_courses()
        response = explain_curriculum(total)
        print("Agent:", response)



    else:
        response = chat_freely(user_input)
        print("Agent:", response)
