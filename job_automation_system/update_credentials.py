from pymongo import MongoClient

client = MongoClient('mongodb://kosurivenky:venkyyamuna@ac-rn1zxqy-shard-00-00.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-01.uhbfag1.mongodb.net:27017,ac-rn1zxqy-shard-00-02.uhbfag1.mongodb.net:27017/?ssl=true&replicaSet=atlas-rmuasr-shard-0&authSource=admin&appName=JobAutomation')
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