import os
import json
import redis
from dotenv import load_dotenv

load_dotenv()

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

student_id = "student_2b4359c4" # Phani Krishna

task_payload = {
    "args": [student_id, "naukri"],
    "kwargs": {
        "job_url": "https://www.naukri.com/java-developer-jobs-in-india?k=java%20developer&l=india",
        "resume_variant": "backend",
        "batch_size": 3
    }
}

# Push to naukri queue
redis_client.lpush("naukri", json.dumps(task_payload))
print(f"Pushed Naukri task for {student_id}")
