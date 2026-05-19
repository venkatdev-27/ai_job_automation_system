#!/usr/bin/env python3
"""Run producer for each platform in the worker."""
import os
import sys
sys.path.insert(0, '/app')

from celery import Celery

app = Celery('job_automation', broker='redis://job-automation-redis:6379/0')

def run_platform(platform, jobs_per_student=10):
    try:
        from producer.producer import JobProducer
        p = JobProducer()
        p.run(
            platforms=[platform],
            jobs_per_student=jobs_per_student,
            dry_run=False
        )
        return p.tasks_submitted
    except Exception as e:
        print(f"Error for {platform}: {e}")
        return 0

if __name__ == '__main__':
    platform = sys.argv[1] if len(sys.argv) > 1 else 'naukri'
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    print(f"Running producer for {platform}: {jobs} jobs/student")
    count = run_platform(platform, jobs)
    print(f"DONE - {count} jobs queued for {platform}")