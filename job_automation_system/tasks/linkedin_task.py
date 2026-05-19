"""
LinkedIn Task - Job Automation System
====================================
Celery task for applying to LinkedIn jobs.
STRICT ANTI-BOT: 1 worker, 1 concurrency, 5-15s delays, cooldown after 10 applies.
Uses integrated scraper_adapter (no external dependencies).
"""

from __future__ import annotations
import asyncio
import logging
import os
import sys
from typing import Any, Optional
from pathlib import Path

# Local imports - using integrated modules
BASE_PATH = Path(__file__).parent.parent
if str(BASE_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_PATH))

from tasks.base_task import BasePlatformTask
from celery_app.app import app
from config import get_platform_config
from utils.logger import get_logger
from utils.async_runner import async_runner
from database import get_student
from celery.exceptions import Retry as CeleryRetry

logger = logging.getLogger(__name__)

# Import from local scraper_adapter
try:
    from scraper_adapter.linkedin import LinkedIn10_10
    from utils.resume_selector import ResumeSelector, extract_skills_from_jd
    from utils.skill_scorer import SkillScorer, calculate_match_percentage
    from ai_engine.llm_answers import LLMAnswers
    from role_manager.dynamic_role_generator import get_role_by_top_skills
    SCRAPER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import LinkedIn scraper: {e}")
    SCRAPER_AVAILABLE = False


def _run_async(coro):
    """Run async code on a persistent loop bound to the worker process."""
    return async_runner.run(coro)


class LinkedInApplyTask(BasePlatformTask):
    """Task for applying to LinkedIn jobs with strict anti-bot."""
    
    name = "tasks.linkedin_task.apply_to_job"

    def _retry_on_login_failure(self, result: dict[str, Any], task_logger: Any, student_id: str) -> None:
        """Trigger task retry when scraper reports a login failure."""
        err = str((result or {}).get("error", "")).strip().lower()
        if "login_failed" in err:
            task_logger.log_warn(f"Retrying due to login failure signal: {err}")
            self._retry_with_jitter(f"linkedin_login_retry:{student_id}:{err}")
    
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
        """Execute LinkedIn job application with strict anti-bot."""
        
        log_file = f"logs/linkedin_{student.student_id}.log"
        task_logger = get_logger(log_file)
        batch_size = max(1, len(job_batch or []))
        
        task_logger.log_info(f"Starting LinkedIn application for {student.name}")
        task_logger.log_info(f"Resume variant: {resume_variant}")
        task_logger.log_info(f"Batch size: {batch_size}")
        task_logger.log_warn("LINKEDIN STRICT MODE: 5-10s delays, high caution")
        
        if not SCRAPER_AVAILABLE:
            task_logger.log_err("LinkedIn scraper not available")
            return {
                "status": "failed",
                "error": "Scraper module not available",
                "student_id": student.student_id,
                "platform": platform,
            }
        
        try:
            # Create runtime settings for scraper with LinkedIn strict config
            from config import settings as app_settings
            
            # Build dynamic runtime settings with LinkedIn constraints
            runtime_settings = self._build_runtime_settings(
                student,
                app_settings,
                resume_variant,
                batch_size=batch_size,
            )
            
            # Execute async scraper with strict anti-bot
            result = _run_async(
                self._apply_to_linkedin(
                    student=student,
                    settings=runtime_settings,
                    logger=task_logger,
                )
            )
            self._retry_on_login_failure(result, task_logger, student.student_id)
            return result
            
        except Exception as e:
            if isinstance(e, CeleryRetry):
                raise
            task_logger.log_err(f"LinkedIn application failed: {str(e)}")
            import traceback
            task_logger.log_err(traceback.format_exc())
            return {
                "status": "failed",
                "error": str(e),
                "student_id": student.student_id,
                "platform": platform,
                "job_url": job_url,
            }
    
    def _build_runtime_settings(
        self,
        student: Any,
        settings: Any,
        resume_variant: str,
        batch_size: int = 1,
    ) -> Any:
        """Build runtime settings with LinkedIn strict constraints"""
        target_applies = max(1, int(batch_size))
        
        # Use existing config logic if available
        try:
            from database.credentials import build_dynamic_runtime_settings
            profile = self._convert_to_profile(student)
            runtime = build_dynamic_runtime_settings(
                settings,
                profile,
                student_id=getattr(student, "student_id", None),
            )
            
            # Apply LinkedIn strict settings
            runtime.max_applies_per_run = target_applies
            runtime.max_pages_per_run = min(max(1, target_applies), 4)
            
            # LinkedIn gets the fixed 6-job target, but slower pacing.
            runtime.min_delay_seconds = 8.0
            runtime.max_delay_seconds = 18.0
            runtime.extra_delay_after_applies = 3
            runtime.extra_delay_min = 45.0
            runtime.extra_delay_max = 90.0
            
            # Strict filters - use global threshold
            from config import settings
            runtime.linkedin_min_skill_match = 4
            runtime.linkedin_ats_threshold = settings.ats_threshold
            runtime.linkedin_easy_apply_only = True
            
            return runtime
        except:
            pass
        
        # Fallback - use global threshold
        from config import settings
        class RuntimeSettings:
            max_applies_per_run = target_applies
            max_pages_per_run = min(max(1, target_applies), 4)
            min_delay_seconds = 8.0
            max_delay_seconds = 18.0
            extra_delay_after_applies = 3
            extra_delay_min = 45.0
            extra_delay_max = 90.0
            linkedin_min_skill_match = 4
            linkedin_ats_threshold = settings.ats_threshold
            linkedin_easy_apply_only = True
            request_timeout_seconds = 30
            include_keywords = student.skills if hasattr(student, 'skills') else []
            preferred_locations = student.preferred_locations if hasattr(student, 'preferred_locations') else ["India"]
            use_human_delay = True
            humanize_typing = True
            random_mouse_moves = True
        
        return RuntimeSettings()
    
    def _convert_to_profile(self, student: Any) -> Any:
        """Convert student model to profile format expected by scraper"""
        class Profile:
            def __init__(self, s):
                raw_skills = getattr(s, "skills", []) or []
                if isinstance(raw_skills, str):
                    raw_skills = [x.strip() for x in raw_skills.split(",") if x.strip()]
                skills = [str(x).strip() for x in raw_skills if str(x).strip()]

                # Mongo fallback: top-level skills may be empty while resumeData.skills exists.
                if not skills:
                    try:
                        from utils.student_mongodb import get_student_profile
                        mongo_profile = get_student_profile(getattr(s, "student_id", ""))
                        if mongo_profile and getattr(mongo_profile, "skills", None):
                            skills = [str(x).strip() for x in mongo_profile.skills if str(x).strip()]
                    except Exception:
                        pass

                candidate_titles = getattr(s, "candidate_titles", []) or []
                if isinstance(candidate_titles, str):
                    candidate_titles = [x.strip() for x in candidate_titles.split(",") if x.strip()]
                candidate_titles = [str(x).strip() for x in candidate_titles if str(x).strip()]
                if not candidate_titles:
                    try:
                        from utils.student_mongodb import get_student_profile
                        mongo_profile = get_student_profile(getattr(s, "student_id", ""))
                        if mongo_profile and getattr(mongo_profile, "candidate_titles", None):
                            candidate_titles = [str(x).strip() for x in mongo_profile.candidate_titles if str(x).strip()]
                    except Exception:
                        pass
                if not candidate_titles and skills:
                    try:
                        generated = get_role_by_top_skills(skills, top_n=5)
                        candidate_titles = [r.get("title", "").strip() for r in generated if r.get("title")]
                    except Exception:
                        candidate_titles = []

                self.student_id = getattr(s, "student_id", "")
                self.name = s.name
                self.email = s.email
                self.phone = s.phone
                self.location = s.location
                self.skills = skills
                self.candidate_titles = candidate_titles
                self.education = ""
                self.years_experience = "0-1"
                self.preferred_locations = s.preferred_locations if hasattr(s, 'preferred_locations') else []
                self.domain_keywords = []
                self.raw_resume_context = ""
                self.linkedin = ""
                self.github = ""
                self.portfolio = ""
        
        return Profile(student)
    
    async def _apply_to_linkedin(
        self,
        student: Any,
        settings: Any,
        logger: Any,
    ) -> dict[str, Any]:
        """Async LinkedIn application with strict anti-bot."""
        
        profile = self._convert_to_profile(student)

        try:
            # Initialize scraper
            scraper = LinkedIn10_10()
            
            # Use existing search_and_apply method
            result = await scraper.search_and_apply(profile, settings, logger)
            
            applied_count = result.get("applied", 0)
            scraper_error = result.get("error")
            status = result.get("status")
            
            payload = {
                "status": "applied" if applied_count > 0 else "failed",
                "applied_count": applied_count,
                "skipped_count": result.get("skipped", 0),
                "student_id": student.student_id,
                "platform": "linkedin",
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
            return {
                "status": "failed",
                "error": str(e),
                "student_id": student.student_id,
                "platform": "linkedin",
            }


@app.task(
    bind=True,
    base=LinkedInApplyTask,
    name="tasks.linkedin_task.apply_to_job",
    queue="linkedin",
    routing_key="linkedin",
    max_retries=3,
    default_retry_delay=120,  # Longer delay for LinkedIn
)
def apply_to_linkedin(
    self,
    student_id: str,
    job_url: str = "",
    resume_variant: str = "backend",
    job_batch: Optional[list[dict[str, Any]]] = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Apply to LinkedIn jobs (STRICT ANTI-BOT).
    Uses existing ai_job_auto_apply scraper.
    
    Args:
        student_id: Student identifier
        job_url: Job URL (optional - scraper handles search)
        resume_variant: Resume variant to use
        
    Returns:
        Application result
    """
    return BasePlatformTask.run(
        self,
        student_id=student_id,
        platform="linkedin",
        job_url=job_url or "https://www.linkedin.com/jobs",
        resume_variant=resume_variant,
        job_batch=job_batch,
    )
