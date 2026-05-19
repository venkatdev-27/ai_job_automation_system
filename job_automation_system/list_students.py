import os
from pymongo import MongoClient

mongo_uri = 'mongodb://kosurivenky:venkyyamuna@ac-rn1zxqy-shard-00-00.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-01.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-02.uhbfag1.mongodb.net:27017/?ssl=true&replicaSet=atlas-rmuasr-shard-0&authSource=admin&appName=JobAutomation'
client = MongoClient(mongo_uri)
db = client['ai_bot_resumes']

print("All Students in MongoDB:")
for student in db.students.find({}):
    print(f"- ID: {student.get('student_id')} | Name: {student.get('full_name')} | Status: {student.get('status')} | Active: {student.get('active')}")
