import sys
import os
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')
os.environ['PYTHONPATH'] = 'D:/ai-bot-resumes/job_automation_system'

import asyncio
from pymongo import MongoClient
from config.settings import settings

print("=" * 60)
print("FULL WARMUP - ALL 4 STEPS - WITH PROPER DATA STORAGE")
print("=" * 60)

student_id = "student_2b4359c4"
client = MongoClient(settings.mongo_uri)
db = client[settings.mongo_db]
students = db['students']

# =====================
# STEP 1: Fetch Student
# =====================
print("\n[STEP 1/4] Fetching student from MongoDB...")
student = students.find_one({'student_id': student_id})
if not student:
    print("ERROR: Student not found")
    exit(1)

resume_url = student.get('resume') or student.get('resumeUrl') or student.get('resume_data', {}).get('url')
print(f"  OK: Student: {student.get('full_name')} ({student.get('name')})")
print(f"  OK: Email: {student.get('email')}")
print(f"  OK: Resume URL: {str(resume_url)[:60] if resume_url else 'N/A'}...")

# =====================
# STEP 2: Download Resume
# =====================
print("\n[STEP 2/4] Downloading Master Resume...")
from utils.resume_downloader import download_if_needed

local_path = download_if_needed(resume_url, student_id)
if not local_path:
    print("ERROR: Download failed")
    exit(1)
print(f"  OK: Downloaded: {local_path}")

# =====================
# STEP 3: Extract Template
# =====================
print("\n[STEP 3/4] Extracting Master Resume Template...")
from utils.master_template_extractor import extract_master_template

master_template = extract_master_template(student_id, str(local_path))
print(f"  OK: Template extracted:")
print(f"      - alignment: {master_template.get('alignment')}")
print(f"      - font_family: {master_template.get('font_family')}")
print(f"      - font_size: {master_template.get('font_size')}")
print(f"      - margins: {master_template.get('margins')}")

# =====================
# STEP 4: Deep Extract Profile
# =====================
print("\n[STEP 4/4] Deep Extracting AI Master Profile...")

async def extract_profile():
    from rag_engine.rag_resume_generator import get_rag_resume_generator
    generator = get_rag_resume_generator(student_id=student_id)
    await generator._init_rag(file_path=str(local_path), force_reindex=True, force_extract=True)
    return generator

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
generator = loop.run_until_complete(extract_profile())
profile = generator.profile

if not profile or not profile.skills:
    print("ERROR: Profile extraction failed")
    exit(1)

print(f"  OK: Profile extracted: {profile.full_name}")
print(f"  OK: Email: {profile.email}")
print(f"  OK: Phone: {profile.phone}")
print(f"  OK: Location: {profile.location}")
print(f"  OK: Primary Role: {profile.primary_role}")
print(f"  OK: Skills: {len(profile.skills)} skills")
print(f"  OK: Experience: {len(profile.experience)} entries")
print(f"  OK: Projects: {len(profile.projects)} entries")
print(f"  OK: Education: {len(profile.education)} entries")

# =====================
# SAVE ALL TO MONGODB
# =====================
print("\n[SAVING] Saving all data to MongoDB...")

# Build the update document with ALL fields
update_data = {
    "full_name": profile.full_name or student.get('name'),
    "email": profile.email or student.get('email'),
    "phone": profile.phone or student.get('phone'),
    "location": profile.location,
    "primary_role": profile.primary_role,
    "skills": profile.skills or [],
    "experience": profile.experience or [],
    "projects": profile.projects or [],
    "education": profile.education or [],
    "master_template": master_template,
    "last_extracted": "2025-01-01",
    "warmup_status": "profile_extracted"
}

# Save to MongoDB
result = students.update_one(
    {'student_id': student_id},
    {'$set': update_data}
)

print(f"  OK: MongoDB updated: {result.modified_count} documents")

# Also save discovered roles if available
if generator.custom_roles:
    roles_result = students.update_one(
        {'student_id': student_id},
        {'$set': {"custom_roles": generator.custom_roles}}
    )
    print(f"  OK: Custom roles saved: {len(generator.custom_roles)} roles")

# =====================
# VERIFY STORAGE
# =====================
print("\n[VERIFYING] Verifying data in MongoDB...")
updated_student = students.find_one({'student_id': student_id})
print(f"  full_name: {updated_student.get('full_name')}")
print(f"  email: {updated_student.get('email')}")
print(f"  skills count: {len(updated_student.get('skills', []))}")
print(f"  experience count: {len(updated_student.get('experience', []))}")
print(f"  projects count: {len(updated_student.get('projects', []))}")
print(f"  education count: {len(updated_student.get('education', []))}")
print(f"  master_template: {updated_student.get('master_template')}")
print(f"  custom_roles: {bool(updated_student.get('custom_roles'))}")

print("\n" + "=" * 60)
print("STEPS 1-4 COMPLETE!")
print("All data stored in MongoDB successfully!")
print("=" * 60)

client.close()