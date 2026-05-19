from ai_job_auto_apply.utils.student_mongodb import get_mongo_connection
import json

def check_student():
    client = get_mongo_connection()
    db = client['ai_bot_resumes']
    student = db['students'].find_one({'student_id': 'student_06f6e1f3'})
    
    if not student:
        print("Student not found!")
        return

    print(f"Student: {student.get('full_name', 'N/A')}")
    print("\nCustom Roles and Keywords:")
    roles = student.get('custom_roles', {})
    for key, data in roles.items():
        print(f"\nBucket: {key}")
        print(f"Title: {data.get('title')}")
        print(f"Keywords: {', '.join(data.get('keywords', []))}")

if __name__ == '__main__':
    check_student()
