import os
os.environ['MONGO_URI'] = 'mongodb://kosurivenky:venkyyamuna@ac-rn1zxqy-shard-00-00.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-01.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-02.uhbfag1.mongodb.net:27017/?ssl=true&replicaSet=atlas-rmuasr-shard-0&authSource=admin&appName=JobAutomation'

import sys
sys.path.insert(0, '/app')

from pymongo import MongoClient

client = MongoClient(os.environ['MONGO_URI'])
db = client['ai_bot_resumes']

# Deactivate all other students, keep only our test student
result = db.students.update_many(
    {'student_id': {'$ne': 'student_4443c80f'}, 'active': True},
    {'$set': {'active': False}}
)
print(f"Deactivated {result.modified_count} other students")

# Verify
doc = db.students.find_one({'student_id': 'student_4443c80f'})
print(f"Student {doc['student_id']}: active={doc['active']}, full_name={doc['full_name']}")