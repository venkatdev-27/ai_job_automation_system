import os
from pymongo import MongoClient
import json
from bson import json_util

mongo_uri = 'mongodb://kosurivenky:venkyyamuna@ac-rn1zxqy-shard-00-00.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-01.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-02.uhbfag1.mongodb.net:27017/?ssl=true&replicaSet=atlas-rmuasr-shard-0&authSource=admin&appName=JobAutomation'
client = MongoClient(mongo_uri)
db = client['ai_bot_resumes']

student = db.students.find_one({'student_id': 'student_2b4359c4'})
if student:
    print(json.dumps(student, indent=2, default=json_util.default))
else:
    print("Student not found")
