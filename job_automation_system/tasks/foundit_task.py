"""
FoundIt Task - Job Automation System
===================================
Celery task for applying to FoundIt jobs.
Uses integrated scraper_adapter (no external dependencies).
"""

from __future__ import annotations
import asyncio
import logging
import sys
from typing import Any, Optional
from pathlib import Path

# Local imports - using integrated modules
BASE_PATH = Path(__file__).parent.parent
if str(BASE_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_PATH))

from tasks.base_task import BasePlatformTask
from celery_app.app import app
from utils.logger import get_logger
from celery.exceptions import Retry as CeleryRetry

logger = logging.getLogger(__name__)

# Import from local scraper_adapter
try:
    from scraper_adapter.foundit_selenium import FoundItSelenium
    from utils.resume_selector import ResumeSelector, extract_skills_from_jd
    from utils.skill_scorer import SkillScorer, calculate_match_percentage
    SCRAPER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import FoundIt scraper: {e}")
    SCRAPER_AVAILABLE = False


def _run_async(coro):
    """Run async code safely across platforms (Playwright on Windows needs Proactor)."""
    if sys.platform == "win32" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        policy = asyncio.get_event_loop_policy()
        if not isinstance(policy, asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.run(coro)


class FoundItApplyTask(BasePlatformTask):
    """Task for applying to FoundIt jobs."""

    name = "tasks.foundit_task.apply_to_job"

    def _retry_on_login_failure(self, result: dict[str, Any], task_logger: Any, student_id: str) -> None:
        """Trigger task retry when scraper reports a login failure."""
        err = str((result or {}).get("error", "")).strip().lower()
        if "login_failed" in err:
            task_logger.log_warn(f"Retrying due to login failure signal: {err}")
            self._retry_with_jitter(f"foundit_login_retry:{student_id}:{err}")

    def _execute_platform_task(
        self,
        student: Any,
        platform: str,
        job_url: str,
        job_id: str,
        resume_variant: str,
        application_id: str,
        platform_config: Optional[Any] = None,
        job_batch: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Execute FoundIt job application."""

        log_file = f"logs/foundit_{student.student_id}.log"
        task_logger = get_logger(log_file)
        batch_size = max(1, len(job_batch or []))

        task_logger.log_info(f"Starting FoundIt application for {student.name}")
        task_logger.log_info(f"Resume variant: {resume_variant}")
        task_logger.log_info(f"Batch size: {batch_size}")

        if not SCRAPER_AVAILABLE:
            task_logger.log_err("Scraper not available")
            return {
                "status": "failed",
                "error": "Scraper module not available",
                "student_id": student.student_id,
                "platform": platform,
            }

        try:
            runtime_settings = self._build_runtime_settings(
                student,
                resume_variant,
                batch_size=batch_size,
            )

            result = self._apply_to_foundit_selenium(
                student=student,
                settings=runtime_settings,
                logger=task_logger,
            )
            self._retry_on_login_failure(result, task_logger, student.student_id)
            return result

        except Exception as e:
            if isinstance(e, CeleryRetry):
                raise
            task_logger.log_err(f"Application failed: {str(e)}")
            import traceback
            task_logger.log_err(traceback.format_exc())
            return {
                "status": "failed",
                "error": str(e),
                "student_id": student.student_id,
                "platform": platform,
                "job_url": job_url,
            }

    def _build_runtime_settings(self, student: Any, resume_variant: str, batch_size: int = 1) -> Any:
        """Build runtime settings for scraper."""
        target_applies = max(1, int(batch_size))

        try:
            from database.credentials import build_dynamic_runtime_settings
            profile = self._convert_to_profile(student)

            from config import settings as original_settings
            runtime = build_dynamic_runtime_settings(
                original_settings,
                profile,
                student_id=getattr(student, "student_id", None),
            )
            runtime.max_applies_per_run = target_applies
            runtime.max_pages_per_run = min(max(1, target_applies), 6)
            runtime.min_delay_seconds = 3.0
            runtime.max_delay_seconds = 7.0
            return runtime
        except Exception:
            pass

        class RuntimeSettings:
            max_applies_per_run = target_applies
            max_pages_per_run = min(max(1, target_applies), 6)
            min_skill_match_count = 4
            request_timeout_seconds = 30
            min_delay_seconds = 3.0
            max_delay_seconds = 7.0
            extra_delay_after_applies = 6
            extra_delay_min = 5.0
            extra_delay_max = 9.0
            foundit_username = None
            foundit_password = None
            foundit_email = None
            use_human_delay = True
            random_user_agent = True
            session_reuse = True

        runtime = RuntimeSettings()
        runtime.resume_variant = resume_variant
        return runtime

    def _convert_to_profile(self, student: Any) -> Any:
        """Convert student model to profile format."""

        class Profile:
            def __init__(self, s):
                self.student_id = getattr(s, "student_id", "")
                self.name = s.name
                self.email = s.email
                self.phone = s.phone
                self.location = s.location
                self.skills = s.skills
                self.candidate_titles = (
                    s.candidate_titles if hasattr(s, "candidate_titles") else []
                )
                self.education = ""
                self.years_experience = "0-1"
                self.preferred_locations = (
                    s.preferred_locations
                    if hasattr(s, "preferred_locations")
                    else []
                )
                self.domain_keywords = []
                self.raw_resume_context = ""
                self.resume_variant = "backend"

        return Profile(student)

    def _apply_to_foundit_selenium(
        self,
        student: Any,
        settings: Any,
        logger: Any,
    ) -> dict[str, Any]:
        """FoundIt application using Selenium."""
        profile = self._convert_to_profile(student)

        try:
            scraper = FoundItSelenium(
                logger=logger,
                settings=settings,
                student_id=getattr(student, "student_id", None)
            )

            result = scraper.search_and_apply(profile, settings)

            applied_count = result.get("applied", 0)
            scraper_error = result.get("error")
            status = result.get("status")

            payload = {
                "status": "applied" if applied_count > 0 else "failed",
                "applied_count": applied_count,
                "skipped_count": result.get("skipped", 0),
                "student_id": student.student_id,
                "platform": "foundit",
                "job_title": result.get("job_title"),
                "company": result.get("company"),
            }
            if scraper_error:
                payload["status"] = "failed"
                payload["error"] = str(scraper_error)
            elif status and str(status).lower() not in ("ok", "applied", "success"):
                payload["raw_status"] = str(status)
            return payload

        except Exception as e:
            logger.log_err(f"Scraper error: {e}")
            import traceback
            logger.log_err(traceback.format_exc())
            return {
                "status": "failed",
                "error": str(e),
                "student_id": student.student_id,
                "platform": "foundit",
            }


@app.task(
    bind=True,
    base=FoundItApplyTask,
    name="tasks.foundit_task.apply_to_job",
    queue="foundit",
    routing_key="foundit",
    max_retries=3,
    default_retry_delay=60,
)
def apply_to_foundit(
    self,
    student_id: str,
    job_url: str = "",
    resume_variant: str = "backend",
    job_batch: Optional[list[dict[str, Any]]] = None,
    batch_size: Optional[int] = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Apply to FoundIt jobs for a student.
    """
    # If batch_size is provided, create a dummy batch to satisfy the base task logic
    if batch_size and not job_batch:
        job_batch = [{"url": job_url}] * int(batch_size)

    return BasePlatformTask.run(
        self,
        student_id=student_id,
        platform="foundit",
        job_url=job_url
        or "https://www.foundit.in/search/software-engineer-jobs-in-india",
        resume_variant=resume_variant,
        job_batch=job_batch,
    )
