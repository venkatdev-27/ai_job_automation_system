import os
import json
import redis
from dotenv import load_dotenv

load_dotenv()

redis_client = redis.Redis(
    host="localhost",
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

student_id = "student_2b4359c4" # Phani Krishna

task_payload = {
    "args": [student_id, "foundit"],
    "kwargs": {
        "job_url": "https://www.foundit.in/srp/results?query=React+Developer&locations=India",
        "resume_variant": "frontend",
        "batch_size": 1
    }
}

# Push to foundit queue
redis_client.lpush("foundit", json.dumps(task_payload))
print(f"Pushed Foundit task for {student_id} (1 job test)")
