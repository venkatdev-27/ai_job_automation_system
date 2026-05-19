#!/usr/bin/env python
"""
Direct trigger for producer - bypasses Celery worker.
Uses Celery API to send tasks directly to broker.
"""

import sys
import json
import argparse
from pathlib import Path

BASE_PATH = Path(__file__).parent
sys.path.insert(0, str(BASE_PATH))

from celery import Celery
from celery_app.config import celery_config


def main():
    parser = argparse.ArgumentParser(description="Trigger producer with Celery direct")
    parser.add_argument("--jobs-per-student", type=int, default=2)
    parser.add_argument("--platforms", nargs="+", default=None)
    args = parser.parse_args()

    app = Celery("job_automation")
    app.config_from_object(celery_config)

    platforms = args.platforms or ["naukri", "linkedin", "foundit"]

    for platform in platforms:
        task_name = "tasks.producer_platform_task.run_platform"
        result = app.send_task(
            task_name,
            args=[],
            kwargs={
                "platform": platform,
                "jobs_per_student": args.jobs_per_student
            },
            queue="producer",
            routing_key="producer"
        )

        print(f"Queued {task_name}: {result.id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())