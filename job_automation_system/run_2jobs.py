#!/usr/bin/env python
"""Quick run 10 jobs per platform (to get 2 fresh after duplicates)."""
import os
import sys

# Fix Redis connection - use docker host
os.environ['REDIS_HOST'] = 'localhost'
os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
os.environ['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/1'

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from producer.producer import JobProducer

if __name__ == "__main__":
    try:
        prod = JobProducer()
        # Request 10 jobs per platform - duplicates will be skipped, we need 2 fresh
        prod.run(
            student_limit=0,
            platforms=None,
            jobs_per_student=10,
            dry_run=False,
        )
        print("DONE - Jobs queued")
    except Exception as e:
        print(f"Error: {e}")