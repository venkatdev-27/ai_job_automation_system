"""
Celery Application - Job Automation System
==========================================
Main Celery application instance with queue-aware task loading.
"""

from __future__ import annotations

import os

from celery import Celery

from celery_app.config import celery_config


ALL_TASK_MODULES = [
    "tasks.naukri_task",
    "tasks.linkedin_task",
    "tasks.foundit_task",
    "tasks.warmup_task",
    "tasks.generate_initial_resumes_task",
    "tasks.producer_platform_task",
    "tasks.producer_beat_task",
    "tasks.student_wave_task",
]

QUEUE_TASK_MODULES = {
    "naukri": ["tasks.naukri_task"],
    "linkedin": ["tasks.linkedin_task"],
    "foundit": ["tasks.foundit_task"],
    "warmup": ["tasks.warmup_task", "tasks.generate_initial_resumes_task"],
    "producer": ["tasks.producer_platform_task", "tasks.producer_beat_task"],
    "student_wave": ["tasks.student_wave_task"],
}

ROLE_TASK_MODULES = {
    "beat": ["tasks.producer_beat_task"],
}


def _parse_csv_env(name: str) -> list[str]:
    raw_value = os.getenv(name, "")
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _get_task_modules() -> list[str]:
    modules: list[str] = []

    for role in _parse_csv_env("CELERY_TASK_SCOPE"):
        modules.extend(ROLE_TASK_MODULES.get(role, []))

    for queue_name in _parse_csv_env("CELERY_QUEUE"):
        modules.extend(QUEUE_TASK_MODULES.get(queue_name, []))

    if not modules:
        return ALL_TASK_MODULES

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(modules))


app = Celery("job_automation")
app.config_from_object(celery_config)
app.autodiscover_tasks(_get_task_modules())


if __name__ == "__main__":
    app.start()
