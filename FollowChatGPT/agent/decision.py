import json

def load_courses():
    with open("data/courses.json", "r", encoding="utf-8") as f:
        return json.load(f)

def check_prerequisite(course_id, completed_courses):
    courses = load_courses()

    course = next((c for c in courses if c["course_id"] == course_id), None)
    if not course:
        return False, ["Course not found"]

    missing = []
    for prereq in course["prerequisite"]:
        if prereq not in completed_courses:
            missing.append(prereq)

    if missing:
        return False, missing

    return True, []

def count_courses():
    courses = load_courses()
    return len(courses)

