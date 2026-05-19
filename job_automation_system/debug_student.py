import os
os.environ['MONGO_URI'] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")

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