import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')
from pymongo import MongoClient
from config.settings import settings

client = MongoClient(settings.mongo_uri)
db = client[settings.mongo_db]
students = db['students']

# Find students with same email
print("=== Finding duplicate emails ===")
email_map = {}
for s in students.find():
    email = s.get('email', '')
    if email:
        if email not in email_map:
            email_map[email] = []
        email_map[email].append(s.get('student_id'))

print("\nDuplicate emails:")
for email, sids in email_map.items():
    if len(sids) > 1:
        print(f"  {email}: {sids}")

# Find phani krishna student
print("\n=== Phani Krishna current record ===")
phani = students.find_one({'student_id': 'student_2b4359c4'})
if phani:
    print(f"  student_id: {phani.get('student_id')}")
    print(f"  full_name: {phani.get('full_name')}")
    print(f"  email: {phani.get('email')}")
    print(f"  skills: {phani.get('skills', [])[:5]}")
    print(f"  experience: {len(phani.get('experience', []))}")
    print(f"  projects: {len(phani.get('projects', []))}")
    print(f"  master_template: {phani.get('master_template')}")
    print(f"  resumeData keys: {list(phani.get('resumeData', {}).keys()) if phani.get('resumeData') else 'N/A'}")

client.close()