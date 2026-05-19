"""
Student Wave Task
=================
Student-first orchestration for production waves.

One task owns one student schedule window and runs platforms sequentially:
FoundIt -> Naukri -> LinkedIn. Different students can run in parallel via the
student_wave queue, but the same student cannot overlap waves.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from celery import Task

from celery_app.app import app
from database import get_database, get_student
from producer.job_generator import get_job_urls
from services import get_available_browsers
from services.daily_caps import (
    check_daily_cap,
    get_remaining_applications,
    get_remaining_total_applications,
    record_daily_application,
    record_total_daily_application,
)
from services.distributed_lock import DistributedLock, release_task_lock
from services.redis_client import redis_client
from services.wave_progress import finalize_wave_progress, update_wave_progress

logger = logging.getLogger(__name__)


SCHEDULE_PLATFORM_JOBS = {
    "morning-6am": {"foundit": 7, "naukri": 1, "linkedin": 1},
    "afternoon-11am": {"foundit": 4, "naukri": 1, "linkedin": 1},
    "evening-5pm": {"foundit": 2, "naukri": 3, "linkedin": 3},
    "night-8pm": {"foundit": 1, "naukri": 1, "linkedin": 1},
    "recovery-1030pm": {"foundit": 4, "naukri": 1, "linkedin": 1},
    "manual": {"foundit": 4, "naukri": 1, "linkedin": 1},
    "recovery": {"foundit": 4, "naukri": 1, "linkedin": 1},
}

PLATFORM_ORDER = ("foundit", "naukri", "linkedin")


class StudentWaveTask(Task):
    name = "tasks.student_wave_task.run_student_wave"
    max_retries = 2
    default_retry_delay = 300

    def _check_health(self) -> tuple[bool, str]:
        try:
            redis_client.client.ping()
        except Exception as exc:
            return False, f"redis_unhealthy:{exc}"

        try:
            get_database().client.admin.command("ping")
        except Exception as exc:
            return False, f"mongo_unhealthy:{exc}"

        try:
            if get_available_browsers() <= 0:
                return False, "no_browser_slots_available"
        except Exception as exc:
            return False, f"browser_semaphore_unhealthy:{exc}"

        # CDP is useful for Naukri/FoundIt but not always required because both
        # have non-CDP fallback paths. Keep this as telemetry unless strict mode
        # is explicitly enabled.
        if os.getenv("HEALTH_GATE_CDP_STRICT", "false").lower() == "true":
            cdp_url = os.getenv("CDP_URL", "").rstrip("/")
            if cdp_url:
                try:
                    import requests

                    response = requests.get(f"{cdp_url}/json/version", timeout=5)
                    if response.status_code >= 400:
                        return False, f"cdp_unhealthy:{response.status_code}"
                except Exception as exc:
                    return False, f"cdp_unhealthy:{exc}"

        return True, "ok"

    def _task_for_platform(self, platform: str):
        if platform == "foundit":
            from tasks.foundit_task import apply_to_foundit

            return apply_to_foundit
        if platform == "naukri":
            from tasks.naukri_task import apply_to_naukri

            return apply_to_naukri
        if platform == "linkedin":
            from tasks.linkedin_task import apply_to_linkedin

            return apply_to_linkedin
        raise ValueError(f"Unknown platform: {platform}")

    def _default_job_url(self, platform: str) -> str:
        defaults = {
            "foundit": "https://www.foundit.in/search/software-engineer-jobs-in-india",
            "naukri": "https://www.naukri.com/jobs-in-India",
            "linkedin": "https://www.linkedin.com/jobs",
        }
        return defaults.get(platform, "")

    def _run_platform_step(
        self,
        student: Any,
        platform: str,
        target_count: int,
    ) -> dict[str, Any]:
        if self._is_in_cooldown(student.student_id, platform):
            return {
                "status": "skipped",
                "platform": platform,
                "target": target_count,
                "applied_count": 0,
                "skipped_count": target_count,
                "error": "platform_cooldown_active",
            }

        total_remaining = get_remaining_total_applications(student.student_id)
        platform_remaining = get_remaining_applications(student.student_id, platform)
        effective_count = min(int(target_count or 0), total_remaining, platform_remaining)

        if effective_count <= 0:
            return {
                "status": "skipped",
                "platform": platform,
                "target": target_count,
                "applied_count": 0,
                "skipped_count": target_count,
                "error": "daily_cap_reached",
            }

        if not check_daily_cap(student.student_id, platform, effective_count):
            return {
                "status": "skipped",
                "platform": platform,
                "target": target_count,
                "applied_count": 0,
                "skipped_count": effective_count,
                "error": "platform_daily_cap_reached",
            }

        job_batch = get_job_urls(
            student=student,
            platform=platform,
            max_jobs=effective_count,
        )
        if not job_batch:
            return {
                "status": "failed",
                "platform": platform,
                "target": effective_count,
                "applied_count": 0,
                "skipped_count": 0,
                "error": "no_job_urls_generated",
            }

        job_batch = job_batch[:effective_count]
        primary_job_url = str(job_batch[0].get("url", "")).strip() or self._default_job_url(platform)
        resume_variant = self._select_resume_variant(job_batch)

        reservation_count = len(job_batch)

        task = self._task_for_platform(platform)
        started = time.time()
        eager_result = task.apply(
            args=[student.student_id, primary_job_url, resume_variant],
            kwargs={"job_batch": job_batch},
        )

        try:
            result = eager_result.get()
        except Exception as exc:
            return {
                "status": "failed",
                "platform": platform,
                "target": reservation_count,
                "applied_count": 0,
                "skipped_count": 0,
                "error": str(exc),
                "duration_seconds": round(time.time() - started, 2),
            }

        result = result if isinstance(result, dict) else {}
        result.setdefault("platform", platform)
        result.setdefault("target", reservation_count)
        result.setdefault("applied_count", int(result.get("applied", 0) or 0))
        result["duration_seconds"] = round(time.time() - started, 2)
        return result

    def _select_resume_variant(self, job_batch: list[dict[str, Any]]) -> str:
        counts: dict[str, int] = {}
        for job in job_batch:
            variant = str(job.get("resume_variant", "backend")).strip().lower() or "backend"
            counts[variant] = counts.get(variant, 0) + 1
        return max(counts, key=counts.get) if counts else "backend"

    def _is_in_cooldown(self, student_id: str, platform: str) -> bool:
        try:
            from utils.student_mongodb import get_student_by_id

            student_doc = get_student_by_id(student_id)
            if not isinstance(student_doc, dict):
                return False
            cooldowns = student_doc.get("platform_cooldowns", {})
            last_applied = cooldowns.get(platform)
            if not last_applied:
                return False
            if isinstance(last_applied, str):
                last_applied = datetime.fromisoformat(last_applied)
            if last_applied.tzinfo is None:
                last_applied = last_applied.replace(tzinfo=timezone.utc)
            windows = {"linkedin": 4, "naukri": 1, "foundit": 2}
            return datetime.now(timezone.utc) - last_applied < timedelta(
                hours=windows.get(platform, 2)
            )
        except Exception:
            return False

    def run(
        self,
        student_id: str,
        schedule_name: str = "manual",
        platform_jobs: dict[str, int] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        platform_jobs = platform_jobs or SCHEDULE_PLATFORM_JOBS.get(
            schedule_name,
            SCHEDULE_PLATFORM_JOBS["manual"],
        )

        wave_lock = DistributedLock(f"student_wave:{student_id}", ttl=7200)
        if not wave_lock.acquire(blocking=False):
            raise self.retry(
                exc=RuntimeError(f"student_wave_lock_busy:{student_id}"),
                countdown=300,
            )

        summary = {
            "student_id": student_id,
            "schedule_name": schedule_name,
            "target": sum(int(v or 0) for v in platform_jobs.values()),
            "applied": 0,
            "skipped": 0,
            "failed": 0,
            "platforms": {},
        }

        try:
            ok, reason = self._check_health()
            if not ok:
                raise self.retry(exc=RuntimeError(reason), countdown=300)

            student = get_student(student_id)
            if not student:
                raise ValueError(f"Student not found: {student_id}")

            for platform in PLATFORM_ORDER:
                target_count = int(platform_jobs.get(platform, 0) or 0)
                if target_count <= 0:
                    continue

                if dry_run:
                    result = {
                        "status": "dry_run",
                        "platform": platform,
                        "target": target_count,
                        "applied_count": 0,
                        "skipped_count": target_count,
                    }
                else:
                    result = self._run_platform_step(student, platform, target_count)

                applied = int(result.get("applied_count", result.get("applied", 0)) or 0)
                skipped = int(result.get("skipped_count", result.get("skipped", 0)) or 0)
                failed = max(0, int(result.get("target", target_count) or target_count) - applied - skipped)
                status = str(result.get("status", "unknown"))
                error = result.get("error")

                summary["applied"] += applied
                summary["skipped"] += skipped
                summary["failed"] += failed
                summary["platforms"][platform] = result

                if applied > 0 and not dry_run:
                    record_total_daily_application(student_id, applied)
                    record_daily_application(student_id, platform, applied)

                update_wave_progress(
                    student_id=student_id,
                    schedule_name=schedule_name,
                    platform=platform,
                    target=int(result.get("target", target_count) or target_count),
                    applied=applied,
                    skipped=skipped,
                    failed=failed,
                    status=status,
                    error=str(error) if error else None,
                )

            final_status = "completed"
            if summary["applied"] <= 0 and summary["failed"] > 0:
                final_status = "failed"
            elif summary["applied"] < summary["target"]:
                final_status = "partial_success"

            summary["status"] = final_status
            finalize_wave_progress(student_id, schedule_name, final_status, summary)
            return summary
        finally:
            release_task_lock(wave_lock)


@app.task(
    bind=True,
    base=StudentWaveTask,
    name="tasks.student_wave_task.run_student_wave",
    queue="student_wave",
    routing_key="student_wave",
    max_retries=2,
    default_retry_delay=300,
)
def run_student_wave(
    self,
    student_id: str,
    schedule_name: str = "manual",
    platform_jobs: dict[str, int] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    return StudentWaveTask.run(
        self,
        student_id=student_id,
        schedule_name=schedule_name,
        platform_jobs=platform_jobs,
        dry_run=dry_run,
    )
