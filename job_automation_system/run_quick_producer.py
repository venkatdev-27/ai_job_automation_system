#!/usr/bin/env python
"""Quick producer to run 2 jobs per platform."""
import os
import sys

# Set correct Redis host
os.environ['REDIS_HOST'] = 'localhost'  # localhost:6379 via docker port mapping

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from producer.producer import JobProducer

def main():
    producer = JobProducer()
    result = producer.run(
        student_limit=0,
        platforms=None,  # All platforms
        jobs_per_student=2,
        dry_run=False,
    )
    print(f"Producer completed: {result}")
    return 0

if __name__ == "__main__":
    sys.exit(main())