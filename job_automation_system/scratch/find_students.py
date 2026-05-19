import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')

from pymongo import MongoClient
from config.settings import settings

client = MongoClient(settings.mongo_uri)
db = client[settings.mongo_db]
students = db['students']

print("=" * 60)
print("Searching for Phani Krishna and other students...")
print("=" * 60)

# Find all students
all_students = []
for s in students.find():
    name = s.get('name', s.get('full_name', 'N/A'))
    student_id = s.get('student_id')
    all_students.append((name, student_id))
    if 'phani' in name.lower() or 'krishna' in name.lower():
        print(f"\n*** FOUND: {name} ***")
        print(f"  student_id: {student_id}")
        print(f"  warmup_complete: {s.get('warmup_complete')}")
        print(f"  custom_roles: {bool(s.get('custom_roles'))}")
        print(f"  resume_urls: {bool(s.get('resume_urls'))}")
        print(f"  skills: {s.get('skills', [])[:5]}...")

print("\n" + "=" * 60)
print("ALL STUDENTS:")
for name, sid in all_students:
    print(f"  - {name}: {sid}")

print(f"\nTotal students: {len(all_students)}")
client.close()