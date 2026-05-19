import os
from pymongo import MongoClient
import json
from bson import json_util

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
client = MongoClient(mongo_uri)
db = client['ai_bot_resumes']

student = db.students.find_one({'student_id': 'student_2b4359c4'})
if student:
    print(json.dumps(student, indent=2, default=json_util.default))
else:
    print("Student not found")
