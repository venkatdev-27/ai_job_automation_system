from utils.student_mongodb import get_mongo_connection

client = get_mongo_connection()
db = client['ai_bot_resumes']
db.students.update_one(
    {'student_id': 'student_4443c80f'},
    {'$set': {'warmup_complete': True, 'warmup_resumes_generated': 6}}
)
print('Done')
