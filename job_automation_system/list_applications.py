import os
from pymongo import MongoClient
import sys

mongo_uri = 'mongodb://kosurivenky:venkyyamuna@ac-rn1zxqy-shard-00-00.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-01.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-02.uhbfag1.mongodb.net:27017/?ssl=true&replicaSet=atlas-rmuasr-shard-0&authSource=admin&appName=JobAutomation'
client = MongoClient(mongo_uri)
db = client['ai_bot_resumes']

student_id = sys.argv[1] if len(sys.argv) > 1 else 'student_2b4359c4'

print(f"Applications for {student_id}:")
for app in db.applications.find({'student_id': student_id}).sort('applied_at', -1).limit(5):
    print(f"- Job: {app.get('job_title')} | Company: {app.get('company')} | Platform: {app.get('platform')} | Status: {app.get('status')} | Date: {app.get('applied_at')}")
