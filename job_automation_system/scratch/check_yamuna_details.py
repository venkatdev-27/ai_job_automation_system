import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(".env")

client = MongoClient(os.getenv("MONGO_URI"))
db = client.get_database(os.getenv("MONGO_DB", "ai_bot_resumes"))

student = db.students.find_one({"student_id": "student_06f6e1f3"})

if student:
    print(f"Name: {student.get('name')}")
    print(f"ID: {student.get('student_id')}")
    print(f"Active: {student.get('active')}")
    creds = student.get('credentials', {})
    if creds:
        print(f"Platforms configured: {list(creds.keys())}")
    else:
        print("No credentials configured.")
else:
    print("Student 'yamuna' (student_06f6e1f3) not found.")
