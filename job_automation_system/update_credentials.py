import os
from pymongo import MongoClient

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation"))
db = client['ai_bot_resumes']

db.students.update_one(
    {'student_id': 'student_2b4359c4'},
    {'$set': {
        'credentials.naukri.username': 'k.venky5678@gmail.com',
        'credentials.naukri.password': 'Venkyyamuna@143322',
        'credentials.linkedin.username': 'k.venky5678@gmail.com',
        'credentials.linkedin.password': 'Venkyyamuna@1433',
        'credentials.foundit.username': 'k.venky5678@gmail.com',
        'credentials.foundit.password': 'Venky@143322'
    }}
)

print('SUCCESS: Credentials updated for student_2b4359c4')