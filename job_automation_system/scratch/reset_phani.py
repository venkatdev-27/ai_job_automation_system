"""
Reset Phani Krishna's student record to fresh state.
KEEP: name, email, phone, gender, location, resume (URL), cloudinary_public_id, 
      resume_filename, credentials, skills, education, preferred_locations,
      createdAt, updatedAt, __v, student_id, _id, status
DELETE: custom_roles, candidate_titles, categorized_skills, experience, full_name,
        last_extracted, links, master_template, primary_role, projects, full_text,
        resumeData, role_config_id, roles_generated, platform_cooldowns,
        warmup_complete, resume_variants
"""
import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')

from pymongo import MongoClient
from config.settings import settings

client = MongoClient(settings.mongo_uri)
db = client[settings.mongo_db]
students = db['students']

STUDENT_ID = "student_2b4359c4"

# Fields to DELETE (set to unset)
fields_to_remove = {
    "custom_roles": "",
    "candidate_titles": "",
    "categorized_skills": "",
    "experience": "",
    "full_name": "",
    "last_extracted": "",
    "links": "",
    "master_template": "",
    "primary_role": "",
    "projects": "",
    "full_text": "",
    "resumeData": "",
    "role_config_id": "",
    "roles_generated": "",
    "platform_cooldowns": "",
    "warmup_complete": "",
    "resume_variants": "",
}

result = students.update_one(
    {"student_id": STUDENT_ID},
    {"$unset": fields_to_remove}
)

print(f"Modified: {result.modified_count}")
print(f"Matched: {result.matched_count}")

# Verify
doc = students.find_one({"student_id": STUDENT_ID})
print(f"\nRemaining keys: {list(doc.keys())}")
print(f"Name: {doc.get('name')}")
print(f"Email: {doc.get('email')}")
print(f"Phone: {doc.get('phone')}")
print(f"Skills: {doc.get('skills', [])[:5]}")
print(f"Resume: {doc.get('resume', 'N/A')[:60]}")
print(f"Credentials: {'YES' if doc.get('credentials') else 'NO'}")
print(f"custom_roles: {doc.get('custom_roles', 'DELETED')}")
print(f"candidate_titles: {doc.get('candidate_titles', 'DELETED')}")

client.close()
