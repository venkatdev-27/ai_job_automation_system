"""
Celery Test Runner - Job Automation System
==========================================
Runs the producer through Celery with safe defaults.

This script does not open a visible browser. Workers handle browser automation
in the background using the configured Celery queues.

Usage:
    python test_all_platforms.py --dry-run
    python test_all_platforms.py --platforms naukri --jobs 1
    python test_all_platforms.py --platforms naukri,foundit,linkedin --jobs 1
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone


# Let the environment handle Redis connection:
# - Inside Docker: docker-compose.yml sets REDIS_HOST, CELERY_BROKER_URL, etc.
# - Outside Docker: default to localhost for local Celery/Redis testing.
if os.environ.get("REDIS_HOST") is None:
    print("WARNING: REDIS_HOST not set, defaulting to 'localhost'")
    os.environ["REDIS_HOST"] = "localhost"
    os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
    os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_PLATFORMS = ["naukri", "foundit", "linkedin"]
DEFAULT_STUDENT_ID = "student_2b4359c4"


def parse_platforms(raw: str) -> list[str]:
    """Parse and validate a comma-separated platform list."""
    platforms = [item.strip().lower() for item in raw.split(",") if item.strip()]
    unknown = [item for item in platforms if item not in DEFAULT_PLATFORMS]
    if unknown:
        valid = ", ".join(DEFAULT_PLATFORMS)
        raise argparse.ArgumentTypeError(
            f"Unknown platform(s): {', '.join(unknown)}. Valid platforms: {valid}"
        )
    return platforms


def clear_redis_idempotency() -> bool:
    """Clear transient Redis blockers so a test run can start cleanly."""
    try:
        from services.redis_client import redis_client

        client = redis_client.client

        idemp_keys = list(client.scan_iter("idemp:*"))
        if idemp_keys:
            client.delete(*idemp_keys)
            logger.info("Cleared %s Redis idempotency keys", len(idemp_keys))
        else:
            logger.info("No idempotency keys to clear")

        client.delete("semaphore:browsers")
        logger.info("Reset browser semaphore")

        circuit_keys = list(client.scan_iter("circuit:*"))
        if circuit_keys:
            client.delete(*circuit_keys)
            logger.info("Cleared %s circuit breaker keys", len(circuit_keys))

        lock_keys = list(client.scan_iter("lock:*"))
        if lock_keys:
            client.delete(*lock_keys)
            logger.info("Cleared %s stale lock keys", len(lock_keys))

        return True
    except Exception as exc:
        logger.error("Redis cleanup failed: %s", exc)
        return False


def clear_mongodb_cooldowns(student_id: str) -> bool:
    """Clear platform cooldown timestamps so the test student is not skipped."""
    try:
        from database import get_database

        db = get_database()
        result = db.students.update_one(
            {"student_id": student_id},
            {"$unset": {"platform_cooldowns": ""}},
        )

        if result.modified_count > 0:
            logger.info("Cleared cooldowns for %s", student_id)
        else:
            logger.info("No cooldowns to clear for %s", student_id)

        return True
    except Exception as exc:
        logger.error("MongoDB cooldown cleanup failed: %s", exc)
        return False


def clear_stale_applications(student_id: str, hours: int) -> bool:
    """Remove recent non-applied records that can block a clean test."""
    try:
        from datetime import timedelta

        from database import get_database

        db = get_database()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = db.job_applications.delete_many(
            {
                "student_id": student_id,
                "status": {"$in": ["pending", "failed", "skipped"]},
                "created_at": {"$gte": cutoff},
            }
        )

        logger.info(
            "Removed %s stale pending/failed/skipped applications from last %sh",
            result.deleted_count,
            hours,
        )
        return True
    except Exception as exc:
        logger.error("Application cleanup failed: %s", exc)
        return False


def check_infrastructure() -> bool:
    """Verify Redis, MongoDB, and active students before submitting work."""
    errors: list[str] = []

    try:
        from config.settings import settings
        from services.redis_client import redis_client

        logger.info("Redis host: %s", settings.redis_host)
        logger.info("Celery broker: %s", settings.celery_broker_url)
        if redis_client.health_check():
            logger.info("Redis is healthy")
        else:
            errors.append("Redis ping failed")
    except Exception as exc:
        errors.append(f"Redis connection error: {exc}")

    try:
        from database import get_database

        db = get_database()
        db.command("ping")
        logger.info("MongoDB is healthy")
    except Exception as exc:
        errors.append(f"MongoDB connection error: {exc}")

    try:
        from database import count_students, get_active_students

        total = count_students()
        students = get_active_students(limit=5)
        logger.info("Active students: %s", total)
        for student in students:
            skills_count = len(student.skills or [])
            logger.info("  -> %s: %s (%s skills)", student.student_id, student.name, skills_count)
    except Exception as exc:
        errors.append(f"Student query error: {exc}")

    for error in errors:
        logger.error(error)
    return not errors


def run_producer(
    *,
    jobs_per_platform: int,
    dry_run: bool,
    student_id: str,
    platforms: list[str],
    wait_between_platforms: int,
) -> tuple[int, int]:
    """Submit platform batches through Celery."""
    from producer.producer import JobProducer

    logger.info("=" * 60)
    logger.info("RUNNING CELERY PRODUCER")
    logger.info("Mode: %s", "DRY RUN" if dry_run else "LIVE")
    logger.info("Student: %s", student_id)
    logger.info("Platforms: %s", ", ".join(platforms))
    logger.info("Jobs requested per platform: %s", jobs_per_platform)
    logger.info("Wait between platforms: %ss", wait_between_platforms)
    logger.info("=" * 60)

    producer = JobProducer()
    producer.run(
        student_id=student_id,
        platforms=platforms,
        jobs_per_student=jobs_per_platform,
        dry_run=dry_run,
        wait_between_platforms_seconds=wait_between_platforms,
    )

    logger.info("=" * 60)
    logger.info("RESULTS")
    logger.info("Tasks submitted: %s", producer.tasks_submitted)
    logger.info("Tasks skipped:   %s", producer.tasks_skipped)
    logger.info("=" * 60)

    return producer.tasks_submitted, producer.tasks_skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Celery-only all-platform test runner")
    parser.add_argument("--jobs", type=int, default=1, help="Jobs per platform (default: 1)")
    parser.add_argument(
        "--platforms",
        type=parse_platforms,
        default=DEFAULT_PLATFORMS,
        help="Comma-separated platforms (default: naukri,foundit,linkedin)",
    )
    parser.add_argument("--student-id", default=DEFAULT_STUDENT_ID, help="Student ID to test")
    parser.add_argument("--dry-run", action="store_true", help="Preview without submitting tasks")
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip Redis/Mongo cleanup")
    parser.add_argument(
        "--cleanup-hours",
        type=int,
        default=6,
        help="Recent non-applied application window to clear (default: 6)",
    )
    parser.add_argument(
        "--wait-between-platforms",
        type=int,
        default=600,
        help="Seconds to wait between platform rounds (default: 600)",
    )
    args = parser.parse_args()

    platforms = args.platforms
    wait_between_platforms = 0 if args.dry_run else args.wait_between_platforms

    logger.info("Celery Test Runner - Starting")
    logger.info("Platforms: %s", ", ".join(platforms))
    logger.info("Jobs per platform: %s", args.jobs)
    logger.info("Student: %s", args.student_id)
    logger.info("Dry run: %s", args.dry_run)

    logger.info("-" * 40)
    logger.info("STEP 1: Infrastructure Check")
    logger.info("-" * 40)
    if not check_infrastructure():
        logger.error("Infrastructure check failed. Aborting.")
        sys.exit(1)

    if args.dry_run:
        logger.info("STEP 2: Skipping cleanup for dry run")
    elif not args.skip_cleanup:
        logger.info("-" * 40)
        logger.info("STEP 2: Clearing Test Blockers")
        logger.info("-" * 40)

        if not clear_redis_idempotency():
            sys.exit(1)
        if not clear_mongodb_cooldowns(args.student_id):
            sys.exit(1)
        if not clear_stale_applications(args.student_id, args.cleanup_hours):
            sys.exit(1)

    logger.info("-" * 40)
    logger.info("STEP 3: Submitting Celery Work")
    logger.info("-" * 40)
    submitted, skipped = run_producer(
        jobs_per_platform=args.jobs,
        dry_run=args.dry_run,
        student_id=args.student_id,
        platforms=platforms,
        wait_between_platforms=wait_between_platforms,
    )

    logger.info("TEST COMPLETE")
    if submitted > 0:
        logger.info("%s task(s) submitted to Celery workers", submitted)
        logger.info("Flower: http://localhost:5555")
        logger.info("Logs:")
        logger.info("  docker logs celery-naukri-1 --tail 80")
        logger.info("  docker logs celery-foundit-1 --tail 80")
        logger.info("  docker logs celery-linkedin-1 --tail 80")
    elif args.dry_run:
        logger.info("Dry run complete. No Celery tasks were submitted.")
    else:
        logger.info("No tasks submitted. Skipped: %s", skipped)


if __name__ == "__main__":
    main()
