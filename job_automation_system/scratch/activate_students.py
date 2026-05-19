import os
from pymongo import MongoClient
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation"))
db = client['ai_bot_resumes']
result = db.students.update_many({}, {'$set': {'active': True}})
print(f'Updated {result.modified_count} students to active=True')
client.close()
