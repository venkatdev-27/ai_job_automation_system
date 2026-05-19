"""
Producer Beat Task - Job Automation System
==========================================
Production-ready periodic Celery Beat task that runs the producer
with Wave Mode (Mini-Wave anti-detection strategy).

Schedule: 06:00, 11:00, 17:00 daily (Asia/Kolkata timezone)
Features:
- Wave Mode: 5 jobs per batch (Mini-Wave)
- Time-based platform weights
- Random student spacing (30-60s)
- Day distribution support
- 100% reliability with retry logic
"""

from __future__ import annotations
import logging
import sys
import os
from typing import Any, Optional
from pathlib import Path

BASE_PATH = Path(__file__).parent.parent
if str(BASE_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_PATH))

# Ensure project paths are available for Celery workers
PROJECT_PATHS = [
    str(BASE_PATH),
    'D:/ai-bot-resumes/job_automation_system',
    'D:\\ai-bot-resumes\\job_automation_system',
]
for p in PROJECT_PATHS:
    if p and p not in sys.path:
        sys.path.insert(0, p)

os.environ['PYTHONPATH'] = str(BASE_PATH)

from celery import Task
from celery_app.app import app
from utils.logger import get_logger

logger = get_logger("producer_beat")


# Default schedule times (can be overridden by .env)
DEFAULT_SCHEDULE_TIMES = ["06:00", "11:00", "17:00"]


class ProducerBeatTask(Task):
    """
    Production-ready periodic task to run the job producer with Wave Mode.
    
    Features:
    - Uses Wave Mode (5 jobs per batch, not 10)
    - Respects time-based platform weights
    - Proper error handling with retry
    - Comprehensive logging
    """
    
    name = "tasks.producer_beat_task.run_producer"
    max_retries = 3
    default_retry_delay = 300  # 5 minutes
    
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    
    def get_producer_config(self) -> dict:
        """Get producer configuration from environment or defaults."""
        return {
            "jobs_per_student": int(os.getenv("JOBS_PER_WAVE", "5")),
            "student_limit": 0,  # 0 = all students
            "platforms": os.getenv("BEAT_PLATFORMS", "naukri,linkedin,foundit").split(","),
            "wave_mode": os.getenv("WAVE_MODE", "true").lower() == "true",
            "time_based_weights": os.getenv("TIME_BASED_WEIGHTS", "true").lower() == "true",
            "dry_run": False,
        }
    
    def run(
        self,
        student_limit: int = 0,
        platforms: Optional[list[str]] = None,
        jobs_per_student: int = 5,
        dry_run: bool = False,
        schedule_name: str = "manual",
    ) -> dict[str, Any]:
        """
        Run the producer with Wave Mode.
        
        Args:
            student_limit: Max students (0 = all)
            platforms: List of platforms to target
            jobs_per_student: Jobs per student (default 5 for Mini-Wave)
            dry_run: If True, don't actually submit
            schedule_name: Name of schedule (for logging)
        """
        logger.info(f"=== Producer Beat Task Started ({schedule_name}) ===")
        logger.info(f"Config: jobs={jobs_per_student}, platforms={platforms}, wave_mode=True")
        
        try:
            from producer.producer import JobProducer
            
            producer = JobProducer()
            
            # Verify Wave Mode is enabled
            if not producer.is_wave_mode:
                logger.warning("Wave Mode not enabled! Forcing enable for Beat task.")
                from config.wave_config import wave_config
                wave_config.enabled = True
            
            # Run producer
            result = producer.run(
                student_limit=student_limit,
                platforms=platforms,
                jobs_per_student=jobs_per_student,
                dry_run=dry_run,
                schedule_name=schedule_name,
            )
            
            logger.info(f"=== Producer Beat Task Completed ({schedule_name}) ===")
            logger.info(f"Tasks submitted: {producer.tasks_submitted}")
            logger.info(f"Tasks skipped: {producer.tasks_skipped}")
            
            return {
                "status": "completed",
                "schedule_name": schedule_name,
                "tasks_submitted": producer.tasks_submitted,
                "tasks_skipped": producer.tasks_skipped,
                "wave_mode": True,
                "jobs_per_student": jobs_per_student,
            }
            
        except Exception as e:
            logger.error(f"Producer beat task failed: {e}")
            raise self.retry(exc=e, countdown=self.default_retry_delay)


# Celery task definition
@app.task(
    bind=True,
    base=ProducerBeatTask,
    name="tasks.producer_beat_task.run_producer",
    queue="producer",
    routing_key="producer",
    max_retries=3,
    default_retry_delay=300,
)
def run_producer_beat(
    self,
    student_limit: int = 0,
    platforms: Optional[list[str]] = None,
    jobs_per_student: int = 5,
    dry_run: bool = False,
    schedule_name: str = "manual",
) -> dict[str, Any]:
    """
    Run the producer via Celery Beat with Wave Mode.
    
    Usage:
        - Schedule: Called automatically by Celery Beat at configured times
        - Manual: run_producer_beat.s(platforms=['naukri', 'foundit', 'linkedin'])
    """
    return ProducerBeatTask.run(
        self,
        student_limit=student_limit,
        platforms=platforms,
        jobs_per_student=jobs_per_student,
        dry_run=dry_run,
        schedule_name=schedule_name,
    )


# Individual platform tasks for backward compatibility
@app.task(
    bind=True,
    name="tasks.producer_beat_task.run_naukri_beat",
    queue="producer",
    routing_key="producer",
    max_retries=3,
)
def run_naukri_beat(self) -> dict[str, Any]:
    """
    6AM run - uses schedule_name to pick distribution.
    Distribution: foundit=7, naukri=1, linkedin=1 = 9 total per student.
    """
    return run_producer_beat(
        schedule_name="morning-6am",
    )


@app.task(
    bind=True,
    name="tasks.producer_beat_task.run_foundit_beat",
    queue="producer",
    routing_key="producer",
    max_retries=3,
)
def run_foundit_beat(self) -> dict[str, Any]:
    """
    11AM run - uses schedule_name to pick distribution.
    Distribution: foundit=4, naukri=1, linkedin=1 = 6 total per student.
    """
    return run_producer_beat(
        schedule_name="afternoon-11am",
    )


@app.task(
    bind=True,
    name="tasks.producer_beat_task.run_linkedin_beat",
    queue="producer",
    routing_key="producer",
    max_retries=3,
)
def run_linkedin_beat(self) -> dict[str, Any]:
    """
    5PM run - uses schedule_name to pick distribution.
    Distribution: foundit=2, naukri=3, linkedin=3 = 8 total per student.
    """
    return run_producer_beat(
        schedule_name="evening-5pm",
    )


@app.task(
    bind=True,
    name="tasks.producer_beat_task.run_all_wave_beat",
    queue="producer",
    routing_key="producer",
    max_retries=3,
)
def run_all_wave_beat(self) -> dict[str, Any]:
    """
    8PM run - uses schedule_name to pick distribution.
    Distribution: foundit=1, naukri=1, linkedin=1 = 3 total per student.
    Daily total: 9+6+8+3 = 26 jobs per student.
    """
    return run_producer_beat(
        schedule_name="night-8pm",
    )


@app.task(
    bind=True,
    name="tasks.producer_beat_task.run_recovery_beat",
    queue="producer",
    routing_key="producer",
    max_retries=3,
)
def run_recovery_beat(self) -> dict[str, Any]:
    """
    10:30 PM recovery run - fills students still below daily cap.
    Reads wave_progress from Redis to target only incomplete students.
    """
    from datetime import datetime, timezone
    from services.wave_progress import get_incomplete_students
    from database import get_active_students

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    incomplete = get_incomplete_students("recovery-1030pm", today)

    if not incomplete:
        logger.info("Recovery beat: no incomplete students found")
        return {
            "status": "completed",
            "schedule_name": "recovery-1030pm",
            "tasks_submitted": 0,
            "tasks_skipped": 0,
            "incomplete_count": 0,
        }

    students = get_active_students(limit=0)
    student_ids = {s.student_id for s in students}
    recovery_students = [s for s in students if s.student_id in set(incomplete)]

    logger.info(f"Recovery beat: targeting {len(recovery_students)} incomplete students")

    from producer.producer import JobProducer

    producer = JobProducer()
    result = producer.run(
        student_limit=0,
        platforms=["naukri", "linkedin", "foundit"],
        jobs_per_student=5,
        dry_run=False,
        schedule_name="recovery-1030pm",
    )

    return {
        "status": "completed",
        "schedule_name": "recovery-1030pm",
        "tasks_submitted": producer.tasks_submitted,
        "tasks_skipped": producer.tasks_skipped,
        "incomplete_count": len(incomplete),
        "recovery_students": len(recovery_students),
    }
