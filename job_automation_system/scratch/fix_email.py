import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')
from pymongo import MongoClient
from config.settings import settings

client = MongoClient(settings.mongo_uri)
db = client[settings.mongo_db]
students = db['students']

# Find who has kosurivenky50@gmail.com
print("=== Student with kosurivenky50@gmail.com ===")
dup = students.find_one({'email': 'kosurivenky50@gmail.com'})
if dup:
    print(f"  student_id: {dup.get('student_id')}")
    print(f"  full_name: {dup.get('full_name')}")
    print(f"  name: {dup.get('name')}")

# Check phani krishna email
print("\n=== Phani Krishna ===")
phani = students.find_one({'student_id': 'student_2b4359c4'})
if phani:
    print(f"  email: {phani.get('email')}")
    print(f"  full_name: {phani.get('full_name')}")
    print(f"  name: {phani.get('name')}")
    print(f"  resumeData: {phani.get('resumeData')}")

# Update phani with unique email
new_email = "phani_krishna_2b4359c4@test.com"
print(f"\n=== Updating Phani email to: {new_email} ===")
result = students.update_one(
    {'student_id': 'student_2b4359c4'},
    {'$set': {'email': new_email, 'full_name': 'Phani Krishna'}}
)
print(f"  Modified: {result.modified_count}")

# Verify
phani = students.find_one({'student_id': 'student_2b4359c4'})
print(f"  New email: {phani.get('email')}")

client.close()