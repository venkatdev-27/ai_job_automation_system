import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')

import asyncio
from utils.student_mongodb import get_student_by_id
from rag_engine.rag_resume_generator import get_rag_resume_generator

print("=" * 60)
print("STEP 5: GENERATE INITIAL RESUMES (DIRECT)")
print("=" * 60)

student_id = "student_2b4359c4"

# Get student from MongoDB
student = get_student_by_id(student_id)
if not student:
    print("ERROR: Student not found")
    exit(1)

print(f"Student: {student.get('full_name', student_id)}")

# Create generator and hydrate from DB
generator = get_rag_resume_generator(student_id=student_id)
generator.hydrate_from_db(student)

print(f"Profile loaded: {generator.profile.full_name if generator.profile else 'N/A'}")
print(f"Skills: {len(generator.profile.skills) if generator.profile else 0}")

# Generate initial resumes
async def generate():
    print("\nGenerating 6 role resumes...")
    resumes = await generator.generate_initial_resumes()
    return resumes

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
resumes = loop.run_until_complete(generate())

print(f"\n✓ Generated {len(resumes)} resumes")
for key, resume in resumes.items():
    print(f"  - {key}: {resume.role_title}")

# Save resume URLs to MongoDB
from database.student_repo import update_student
from utils.helpers import upload_to_cloudinary
from pathlib import Path

resume_urls = {}
for role_key, role_resume in resumes.items():
    file_path = Path(role_resume.file_path)
    if file_path.exists():
        print(f"Uploading {role_key} to Cloudinary...")
        cloud_url = upload_to_cloudinary(file_path, folder=f"ai_bot_resumes/{student_id}")
        if cloud_url:
            resume_urls[role_key] = cloud_url
            print(f"  OK: {cloud_url[:50]}...")

# Update student with resume URLs
if resume_urls:
    update_student(student_id, {
        "resume_urls": resume_urls,
        "warmup_complete": True,
        "custom_roles": generator.custom_roles
    })
    print(f"\n✓ Updated MongoDB with resume_urls and warmup_complete=True")

print("\n" + "=" * 60)
print("WARMUP COMPLETE!")
print("=" * 60)