import re
from agent.decision import check_prerequisite
from llm.llm_helper import classify_intent, explain_result

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

    if intent == "check_prerequisite":

        course_id = extract_course_id(user_input)

        if not course_id:
            print("Agent: กรุณาระบุรหัสวิชา เช่น CS201")
            continue

        ok, missing = check_prerequisite(course_id, completed_courses)

        if ok:
            result = f"คุณสามารถลงทะเบียนวิชา {course_id} ได้"
        else:
            result = f"คุณยังไม่สามารถลงทะเบียนวิชา {course_id} ได้\nขาด prerequisite: {missing}"

        print("Agent:", explain_result(result))

    else:
        print("Agent: ขออภัย ยังไม่เข้าใจคำถามนี้")
