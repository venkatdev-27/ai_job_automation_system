"""
Producer Package - Job Automation System
=========================================
"""

from producer.producer import JobProducer, main
from producer.job_generator import JobGenerator, get_job_urls
from producer.seed_data import seed_students, seed_additional

__all__ = [
    "JobProducer",
    "main",
    "JobGenerator",
    "get_job_urls",
    "seed_students",
    "seed_additional",
]