import os
import json

base_dir = os.path.dirname(os.path.dirname(__file__))
file_path = os.path.join(base_dir, "data", "courses.json")

with open(file_path, "r", encoding="utf-8") as f:
    courses = json.load(f)


def count_courses():
    return {"total_courses": len(courses["courses"])}


def get_course_detail(course_id):
    for course in courses["courses"]:   
        if course["course_id"] == course_id:
            return course
    return {"error": "Course not found"}


def check_prerequisite(course_id, completed_courses=None):
    if completed_courses is None:
        completed_courses = []

    for course in courses["courses"]:
        if course["course_id"] == course_id:
            missing = [
                pre for pre in course.get("prerequisites", [])
                if pre not in completed_courses
            ]
            return {
                "eligible": len(missing) == 0,
                "missing": missing
            }

    return {"error": "Course not found"}