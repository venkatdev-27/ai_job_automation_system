#!/usr/bin/env python
"""
Run Producer - Job Automation System
==============================
Simple script to trigger the producer for a given number of jobs per platform.
"""

import sys
import argparse
from pathlib import Path

BASE_PATH = Path(__file__).parent
if str(BASE_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_PATH))

from producer.producer import JobProducer


def main():
    parser = argparse.ArgumentParser(description="Run job producer")
    parser.add_argument(
        "--jobs-per-student", 
        type=int, 
        default=2,
        help="Number of jobs per student"
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        default=None,
        help="Platforms to run (default: all)"
    )
    args = parser.parse_args()

    producer = JobProducer()
    result = producer.run(
        student_limit=0,
        platforms=args.platforms,
        jobs_per_student=args.jobs_per_student,
        dry_run=False,
    )
    
    print(f"Producer completed: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())