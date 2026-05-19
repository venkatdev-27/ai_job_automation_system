import os
os.environ['MONGO_URI'] = 'mongodb://kosurivenky:venkyyamuna@ac-rn1zxqy-shard-00-00.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-01.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-02.uhbfag1.mongodb.net:27017/?ssl=true&replicaSet=atlas-rmuasr-shard-0&authSource=admin&appName=JobAutomation'

import sys
sys.path.insert(0, '/app')

from pymongo import MongoClient

client = MongoClient(os.environ['MONGO_URI'])
db = client['ai_bot_resumes']

doc = db.students.find_one({'student_id': 'student_4443c80f', 'active': True})
if doc:
    print("Fields in MongoDB document:")
    for k in sorted(doc.keys()):
        v = doc[k]
        if k == '_id':
            v = str(v)
        print(f"  {k}: {type(v).__name__} = {v}")