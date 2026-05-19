"""
Producer Platform Task - Job Automation System
==========================================
Celery task to run producer for a specific platform.
Can be scheduled at specific times.
"""

from __future__ import annotations
import logging
import sys
import os
from typing import Any, Optional
from pathlib import Path

# Add project root to path - CRITICAL for worker
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Also try common paths (Windows local only — Docker uses PYTHONPATH=/app from compose)
import os as _os
if not _os.getenv('IN_DOCKER', '').lower() == 'true':
    COMMON_PATHS = [
        'D:/ai-bot-resumes/job_automation_system',
        'D:\\\\ai-bot-resumes\\\\job_automation_system',
    ]
    for p in COMMON_PATHS:
        if p not in sys.path:
            sys.path.insert(0, p)

# Ensure PYTHONPATH uses the dynamically resolved root (works in Docker AND locally)
os.environ['PYTHONPATH'] = str(PROJECT_ROOT)

from celery import Task
from celery_app.app import app
from utils.logger import get_logger

logger = get_logger("producer_platform")


PLATFORM_CONFIG = {
    "naukri": {
        "name": "Naukri",
        "jobs_per_student": 10,
        "queue": "naukri",
        "routing_key": "naukri",
    },
    "foundit": {
        "name": "FoundIt",
        "jobs_per_student": 10,
        "queue": "foundit",
        "routing_key": "foundit",
    },
    "linkedin": {
        "name": "LinkedIn",
        "jobs_per_student": 6,
        "queue": "linkedin",
        "routing_key": "linkedin",
    },
}


class ProducerPlatformTask(Task):
    """Base Task with common error handling if needed, though not strictly required."""
    abstract = True


def _run_platform_logic(task_instance: Any, platform: str, jobs_per_student: Optional[int] = None, student_limit: int = 0) -> dict[str, Any]:
    """Internal logic to run producer for a specific platform."""
    import sys
    import os
    
    # Ensure proper path for worker — use dynamic root, never hardcode Windows paths
    project_root = str(Path(__file__).parent.parent.resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ['PYTHONPATH'] = project_root
    
    platform = platform.lower()
    config = PLATFORM_CONFIG.get(platform)
    
    if not config:
        logger.log_err(f"Unknown platform: {platform}")
        return {"status": "failed", "error": f"Unknown platform: {platform}"}

    jobs_count = jobs_per_student or config["jobs_per_student"]
    
    logger.log_info(f"Starting producer logic for {config['name']}: {jobs_count} jobs/student")

    try:
        from producer.producer import JobProducer

        producer = JobProducer()
        producer.run(
            student_limit=student_limit,
            platforms=[platform],
            jobs_per_student=jobs_count,
            dry_run=False,
        )

        return {
            "status": "completed",
            "platform": platform,
            "platform_name": config["name"],
            "jobs_per_student": jobs_count,
            "tasks_submitted": producer.tasks_submitted,
            "tasks_skipped": producer.tasks_skipped,
        }

    except Exception as e:
        logger.log_err(f"Producer logic failed: {e}")
        if task_instance and hasattr(task_instance, 'retry'):
            raise task_instance.retry(exc=e, countdown=300)
        return {"status": "failed", "error": str(e)}


@app.task(
    bind=True,
    base=ProducerPlatformTask,
    name="tasks.producer_platform_task.run_platform",
    queue="producer",
    routing_key="producer",
    max_retries=2,
    default_retry_delay=300,
)
def run_platform(
    self,
    platform: str,
    jobs_per_student: Optional[int] = None,
    student_limit: int = 0,
) -> dict[str, Any]:
    """
    Run producer for a specific platform.
    """
    return _run_platform_logic(self, platform, jobs_per_student, student_limit)


# =============================================================================
# Celery Beat scheduled tasks - one per platform
# =============================================================================

@app.task(
    bind=True,
    base=ProducerPlatformTask,
    name="tasks.producer_platform_task.run_naukri",
    queue="producer",
    routing_key="producer",
    max_retries=2,
)
def run_naukri(self, jobs_per_student: int = 10) -> dict[str, Any]:
    logger.log_info(f"Running manual/scheduled Naukri producer ({jobs_per_student} jobs)")
    return _run_platform_logic(self, platform="naukri", jobs_per_student=jobs_per_student)


@app.task(
    bind=True,
    base=ProducerPlatformTask,
    name="tasks.producer_platform_task.run_foundit",
    queue="producer",
    routing_key="producer",
    max_retries=2,
)
def run_foundit(self, jobs_per_student: int = 10) -> dict[str, Any]:
    logger.log_info(f"Running manual/scheduled FoundIt producer ({jobs_per_student} jobs)")
    return _run_platform_logic(self, platform="foundit", jobs_per_student=jobs_per_student)


@app.task(
    bind=True,
    base=ProducerPlatformTask,
    name="tasks.producer_platform_task.run_linkedin",
    queue="producer",
    routing_key="producer",
    max_retries=2,
)
def run_linkedin(self, jobs_per_student: int = 6) -> dict[str, Any]:
    logger.log_info(f"Running manual/scheduled LinkedIn producer ({jobs_per_student} jobs)")
    return _run_platform_logic(self, platform="linkedin", jobs_per_student=jobs_per_student)
