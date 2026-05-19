from pymongo import MongoClient
client = MongoClient('mongodb+srv://kosurivenky:venkyyamuna@cluster0.uhbfag1.mongodb.net/ai_bot_resumes?appName=Cluster0')
db = client['ai_bot_resumes']
result = db.students.update_many({}, {'$set': {'active': True}})
print(f'Updated {result.modified_count} students to active=True')
client.close()
