import os
import sys
sys.path.insert(0, '/app')

from pymongo import MongoClient

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation"))
db = client['ai_bot_resumes']

print("Running Naukri producer (second batch)...")
from producer.producer import JobProducer
producer = JobProducer()
result = producer.run(
    student_limit=1,
    platforms=['naukri'],
    jobs_per_student=4,
    dry_run=False,
)
print(f"Naukri Result: {result}")

print("\nRunning FoundIt producer (second batch)...")
producer2 = JobProducer()
result2 = producer2.run(
    student_limit=1,
    platforms=['foundit'],
    jobs_per_student=4,
    dry_run=False,
)
print(f"FoundIt Result: {result2}")

print("\nRunning LinkedIn producer (second batch)...")
producer3 = JobProducer()
result3 = producer3.run(
    student_limit=1,
    platforms=['linkedin'],
    jobs_per_student=4,
    dry_run=False,
)
print(f"LinkedIn Result: {result3}")

# Final count
apps = list(db.job_applications.find({'student_id': 'student_4443c80f'}))
print(f"\nTotal job applications: {len(apps)}")