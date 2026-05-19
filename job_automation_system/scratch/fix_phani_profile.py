from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
client = MongoClient(MONGO_URI)
db = client['ai_bot_resumes']

student_id = 'student_2b4359c4'
update_data = {
    'full_name': 'phani krishna',
    'resumeData.name': 'phani krishna',
    'resumeData.email': 'venky90@gmail.com',
    'resumeData.phone': '+91 7013269473'
}

result = db.students.update_one(
    {'student_id': student_id},
    {'$set': update_data}
)

if result.modified_count > 0:
    print(f'Successfully updated {student_id} to Phani Krishna!')
else:
    print(f'No changes made to {student_id}.')
