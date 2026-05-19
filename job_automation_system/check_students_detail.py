import pymongo
import os

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
client = pymongo.MongoClient(mongo_uri)
db = client['ai_bot_resumes']

student_ids = ['student_2b4359c4', 'student_65a834b8', 'student_4443c80f']

for sid in student_ids:
    s = db.students.find_one({'student_id': sid})
    if s:
        print(f"ID: {sid} | Name: {s.get('name')} | Email: {s.get('email')}")
    else:
        print(f"ID: {sid} | Not found")
