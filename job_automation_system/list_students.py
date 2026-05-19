import os
from pymongo import MongoClient

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
client = MongoClient(mongo_uri)
db = client['ai_bot_resumes']

print("All Students in MongoDB:")
for student in db.students.find({}):
    print(f"- ID: {student.get('student_id')} | Name: {student.get('full_name')} | Status: {student.get('status')} | Active: {student.get('active')}")
