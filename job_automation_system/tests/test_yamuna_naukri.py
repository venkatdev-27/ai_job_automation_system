import logging
import os
import sys
from pathlib import Path

# Setup logging early
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Force localhost Redis for host-machine runs before importing app/settings.
LOCAL_BROKER_URL = os.environ.get("TEST_CELERY_BROKER_URL", "redis://localhost:6379/0")
LOCAL_RESULT_BACKEND = os.environ.get("TEST_CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = os.environ.get("REDIS_PORT", "6379") or "6379"
os.environ["CELERY_BROKER_URL"] = LOCAL_BROKER_URL
os.environ["CELERY_RESULT_BACKEND"] = LOCAL_RESULT_BACKEND

from config import settings  # noqa: E402
from database import get_student  # noqa: E402
from celery_app.app import app  # noqa: E402


DEFAULT_STUDENT_ID = os.environ.get("TEST_STUDENT_ID", "student_2b4359c4")
DEFAULT_MAX_JOBS = int(os.environ.get("TEST_MAX_JOBS", "3"))


def _check_redis(url: str, name: str) -> None:
    import redis
    client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
    client.ping()
    logger.info("%s connection successful: %s", name, url)


def trigger_yamuna_test():
    student_id = DEFAULT_STUDENT_ID
    platform = "naukri"

    broker_url = os.environ["CELERY_BROKER_URL"]
    result_url = os.environ["CELERY_RESULT_BACKEND"]

    logger.info("Using broker URL: %s", broker_url)
    logger.info("Using result backend URL: %s", result_url)

    try:
        _check_redis(broker_url, "Broker Redis")
        _check_redis(result_url, "Result backend Redis")
    except Exception as exc:
        logger.error("Could not connect to Redis using configured URLs: %s", exc)
        logger.info("Ensure your Redis container/service is running and reachable.")
        return

    # Ensure Celery uses these URLs even if it was imported earlier. Disable connection pooling to avoid Windows/WSL 10054 errors.
    app.conf.update(
        broker_url=broker_url, 
        result_backend=result_url,
        broker_pool_limit=None
    )

    logger.info("Settings broker URL: %s", settings.celery_broker_url)
    logger.info("Settings result backend URL: %s", settings.celery_result_backend)
    logger.info("App broker URL: %s", app.conf.broker_url)
    logger.info("App result backend URL: %s", app.conf.result_backend)

    student = get_student(student_id)
    if not student:
        logger.error("Student %s not found!", student_id)
        return

    logger.info("Found student: %s", student.name)

    # DYNAMIC: Use JobGenerator to create URLs from ALL student skills
    from producer.job_generator import get_job_urls
    
    # Get ALL jobs (use all skills)
    job_urls = get_job_urls(
        student=student,
        platform=platform,
        max_jobs=DEFAULT_MAX_JOBS,
    )
    
    if not job_urls:
        logger.error("No job URLs generated from student profile!")
        return
    
    logger.info("Generated %d job URLs from student profile", len(job_urls))
    
    # Get all job URLs and variants for batch processing
    job_url = job_urls[0].get("url", "") if job_urls else ""
    resume_variant = job_urls[0].get("resume_variant", "backend") if job_urls else "backend"
    
    logger.info("DYNAMIC: Primary job URL: %s", job_url)
    logger.info("DYNAMIC: Resume variant: %s", resume_variant)
    logger.info("DYNAMIC: Student skills: %s", student.skills[:10] if student.skills else "None")

    task_name = "tasks.naukri_task.apply_to_job"

    logger.info("Queuing task for %s on %s...", student.name, platform)
    try:
        result = app.send_task(
            task_name,
            args=[student_id, job_url, resume_variant],
            kwargs={"job_batch": job_urls},
            queue="naukri",
        )
    except Exception as exc:
        logger.exception("Task enqueue failed: %s", exc)
        return

    logger.info("Task submitted. ID: %s", result.id)
    logger.info("DYNAMIC: Using resume_variant: %s", resume_variant)
    print(f"\nTask queued successfully for {student_id}.")
    print(f"Task ID: {result.id}")
    print(f"Platform: {platform}")
    print(f"Resume variant: {resume_variant}")
    print(f"Job URL: {job_url}")
    print(f"Total jobs queued in batch: {len(job_urls)}")
    print("Check logs with: docker logs -f celery-naukri-1")


if __name__ == "__main__":
    trigger_yamuna_test()
