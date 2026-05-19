import sys, json
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')

from pymongo import MongoClient
from config.settings import settings

client = MongoClient(settings.mongo_uri)
db = client[settings.mongo_db]
students = db['students']

# Find Phani Krishna
for s in students.find():
    name = s.get('name', s.get('full_name', 'N/A'))
    if 'phani' in name.lower() or 'krishna' in name.lower():
        print(f"FOUND: {name}")
        print(f"  student_id: {s.get('student_id')}")
        print(f"  email: {s.get('email')}")
        print(f"  phone: {s.get('phone')}")
        print(f"  ALL KEYS: {list(s.keys())}")
        # Print warmup-related fields
        print(f"  custom_roles: {bool(s.get('custom_roles'))}")
        print(f"  warmup_complete: {s.get('warmup_complete')}")
        print(f"  resume_variants: {bool(s.get('resume_variants'))}")
        print(f"  candidate_titles: {s.get('candidate_titles', [])}")
        print(f"  skills: {s.get('skills', [])[:5]}...")
        print(f"  resume_url: {s.get('resume_url', s.get('resumeUrl', 'N/A'))[:60]}")

client.close()
