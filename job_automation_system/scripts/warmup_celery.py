import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')

import os
os.environ['PYTHONPATH'] = 'D:/ai-bot-resumes/job_automation_system'

from celery_app.app import app
from utils.student_mongodb import get_student_by_id, update_student_profile
from utils.resume_downloader import download_if_needed
from utils.master_template_extractor import extract_master_template

print("=" * 60)
print("FULL WARMUP - 5 STEPS VIA CELERY")
print("=" * 60)

student_id = "student_2b4359c4"

# Step 1: Fetch student
print("\n[STEP 1/5] Fetching student from MongoDB...")
student = get_student_by_id(student_id)
if not student:
    print(f"ERROR: Student {student_id} not found")
    exit(1)
    
resume_url = student.get('resume') or student.get('resumeUrl')
print(f"  OK: Student found: {student.get('full_name', 'N/A')}")
print(f"  OK: Resume URL: {resume_url[:60] if resume_url else 'N/A'}...")

# Step 2: Download resume
print("\n[STEP 2/5] Downloading Master Resume...")
local_path = download_if_needed(resume_url, student_id)
if not local_path:
    print("ERROR: Download failed")
    exit(1)
print(f"  OK: Downloaded: {local_path}")

# Step 3: Extract template
print("\n[STEP 3/5] Extracting Master Resume Template...")
master_template = extract_master_template(student_id, str(local_path))
print(f"  OK: Template: {master_template.get('alignment')} alignment, {master_template.get('font_family')} font")

# Step 4: Deep extract profile (in-line, not via Celery)
print("\n[STEP 4/5] Deep Extracting AI Master Profile...")
import asyncio
from rag_engine.rag_resume_generator import get_rag_resume_generator

async def extract_profile():
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
print(f"  OK: Skills: {len(profile.skills)} found")

# Sync to MongoDB
profile_dict = {
    'full_name': profile.full_name,
    'email': profile.email,
    'phone': profile.phone,
    'location': profile.location,
    'primary_role': profile.primary_role,
    'skills': profile.skills,
    'education': profile.education,
    'experience': profile.experience,
    'projects': profile.projects,
    'master_template': master_template,
}
update_student_profile(student_id, profile_dict)
print("  OK: Profile synced to MongoDB")

# Step 5: Push to Celery for resume generation
print("\n[STEP 5/5] Pushing generate_initial_resumes to Celery...")
result = app.send_task(
    "tasks.generate_initial_resumes_task.generate_resumes",
    args=[student_id],
    queue="warmup",
    routing_key="warmup"
)

print(f"  OK: Celery task pushed!")
print(f"  Task ID: {result.id}")
print(f"  Queue: warmup")

print("\n" + "=" * 60)
print("WARMUP STEPS 1-4 COMPLETE!")
print("Step 5 (resume generation) running in Celery worker")
print("=" * 60)