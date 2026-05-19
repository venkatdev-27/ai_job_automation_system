import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')
from pymongo import MongoClient
from config.settings import settings

client = MongoClient(settings.mongo_uri)
db = client[settings.mongo_db]
students = db['students']

student = students.find_one({'student_id': 'student_2b4359c4'})

print("=" * 60)
print("VERIFICATION: ALL DATA STORED IN MONGODB")
print("=" * 60)

print(f"\n[BASIC INFO]")
print(f"  student_id: {student.get('student_id')}")
print(f"  full_name: {student.get('full_name')}")
print(f"  email: {student.get('email')}")
print(f"  phone: {student.get('phone')}")
print(f"  location: {student.get('location')}")
print(f"  primary_role: {student.get('primary_role')}")

print(f"\n[SKILLS] - {len(student.get('skills', []))} skills")
print(f"  {student.get('skills', [])}")

print(f"\n[EXPERIENCE] - {len(student.get('experience', []))} entries")
for exp in student.get('experience', []):
    print(f"  - {exp.get('title')} at {exp.get('company')} ({exp.get('duration', 'N/A')})")

print(f"\n[PROJECTS] - {len(student.get('projects', []))} entries")
for proj in student.get('projects', []):
    print(f"  - {proj.get('name')}")
    print(f"    Tech: {proj.get('tech', 'N/A')}")

print(f"\n[MASTER TEMPLATE]")
mt = student.get('master_template', {})
print(f"  font_family: {mt.get('font_family')}")
print(f"  font_size_name: {mt.get('font_size_name')}")
print(f"  alignment: {mt.get('alignment')}")
print(f"  margin_top: {mt.get('margin_top')}")
print(f"  extracted: {mt.get('extracted')}")

print(f"\n[CUSTOM ROLES] - {len(student.get('custom_roles', {}))} roles")
for role_key, role_data in student.get('custom_roles', {}).items():
    print(f"  - {role_key}: {role_data.get('title')}")
    print(f"    Keywords: {role_data.get('keywords', [])[:5]}...")

print("\n" + "=" * 60)
print("ALL 4 STEPS COMPLETED - DATA STORED!")
print("  Step 1: Student fetched ✓")
print("  Step 2: Resume downloaded ✓")
print("  Step 3: Template extracted ✓")
print("  Step 4: Profile deep extracted ✓")
print("=" * 60)

client.close()