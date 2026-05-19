import os
from pymongo import MongoClient
import sys

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
client = MongoClient(mongo_uri)
db = client['ai_bot_resumes']

student_id = sys.argv[1] if len(sys.argv) > 1 else 'student_2b4359c4'

print(f"Applications for {student_id}:")
for app in db.applications.find({'student_id': student_id}).sort('applied_at', -1).limit(5):
    print(f"- Job: {app.get('job_title')} | Company: {app.get('company')} | Platform: {app.get('platform')} | Status: {app.get('status')} | Date: {app.get('applied_at')}")
