from pymongo import MongoClient
import os

MONGO_URI = 'mongodb://kosurivenky:venkyyamuna@ac-rn1zxqy-shard-00-00.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-01.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-02.uhbfag1.mongodb.net:27017/?ssl=true&replicaSet=atlas-rmuasr-shard-0&authSource=admin&appName=JobAutomation'
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
