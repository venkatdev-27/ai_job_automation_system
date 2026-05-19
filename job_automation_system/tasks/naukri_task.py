"""
Naukri Task - Job Automation System
===================================
Celery task for applying to Naukri jobs.
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
from utils.async_runner import async_runner
from celery.exceptions import Retry as CeleryRetry

logger = logging.getLogger(__name__)

# Import from local scraper_adapter
try:
    from scraper_adapter.naukri import NaukriScraper
    from scraper_adapter.playwright_manager import playwright_manager
    from utils.resume_selector import ResumeSelector, extract_skills_from_jd
    from utils.skill_scorer import SkillScorer, calculate_match_percentage
    from role_manager.dynamic_role_generator import generate_dynamic_resumes_from_skills, get_role_by_top_skills
    SCRAPER_AVAILABLE = True
    logger.info("Scraper modules imported successfully")
except Exception as e:
    import traceback
    error_msg = f"CRITICAL: Could not import scraper: {e}"
    print(error_msg)
    traceback.print_exc()
    logger.error(error_msg)
    SCRAPER_AVAILABLE = False



def _run_async(coro):
    """Run async code on a persistent loop bound to the worker process."""
    return async_runner.run(coro)


class NaukriApplyTask(BasePlatformTask):
    """Task for applying to Naukri jobs using existing scraper."""
    
    name = "tasks.naukri_task.apply_to_job"

    def _retry_on_login_failure(self, result: dict[str, Any], task_logger: Any, student_id: str) -> None:
        """Trigger task retry when scraper reports a login failure."""
        err = str((result or {}).get("error", "")).strip().lower()
        if "login_failed" in err:
            task_logger.log_warn(f"Retrying due to login failure signal: {err}")
            self._retry_with_jitter(f"naukri_login_retry:{student_id}:{err}")
    
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
        """Execute Naukri job application using existing scraper."""
        
        log_file = f"logs/naukri_{student.student_id}.log"
        task_logger = get_logger(log_file)
        
        task_logger.log_info(f"Starting Naukri application for {student.name}")
        task_logger.log_info(f"Resume variant: {resume_variant}")
        
        if not SCRAPER_AVAILABLE:
            task_logger.log_err("Scraper not available")
            return {
                "status": "failed",
                "error": "Scraper module not available",
                "student_id": student.student_id,
                "platform": platform,
            }
        
        try:
            batch_size = max(1, len(job_batch or []))
            # Build runtime settings
            runtime_settings = self._build_runtime_settings(student, resume_variant, batch_size=batch_size)
            
            # Execute async scraper
            result = _run_async(
                self._apply_to_naukri(
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
        
        # Use existing config logic
        try:
            from database.credentials import build_dynamic_runtime_settings
            profile = self._convert_to_profile(student)
            
            # Import original settings
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
            runtime.min_apply_delay = 3.0
            runtime.max_apply_delay = 7.0
            runtime.extra_delay_after_n_applies = 5
            return runtime
        except Exception:
            pass
        
        # Fallback - create basic settings
        class RuntimeSettings:
            max_applies_per_run = target_applies
            max_pages_per_run = min(max(1, target_applies), 6)
            min_skill_match_count = 4
            naukri_ats_threshold = 60
            request_timeout_seconds = 30
            min_delay_seconds = 3.0
            max_delay_seconds = 7.0
            min_apply_delay = 3.0
            max_apply_delay = 7.0
            extra_delay_after_n_applies = 5
            extra_delay_after_applies = 5
            extra_delay_min = 4.0
            extra_delay_max = 6.0
        
        return RuntimeSettings()
    
    def _convert_to_profile(self, student: Any) -> Any:
        """Convert student model to profile format expected by scraper."""
        class Profile:
            def __init__(self, s):
                self.student_id = getattr(s, "student_id", "")
                self.name = s.name
                self.email = s.email
                self.phone = s.phone
                self.location = s.location
                self.skills = getattr(s, "skills", []) or []
                candidate_titles = getattr(s, "candidate_titles", []) or []
                if not candidate_titles and self.skills:
                    try:
                        generated = get_role_by_top_skills(self.skills, top_n=5)
                        candidate_titles = [r.get("title", "").strip() for r in generated if r.get("title")]
                    except Exception:
                        candidate_titles = []
                self.candidate_titles = candidate_titles
                self.education = ""
                self.years_experience = "0-1"
                self.preferred_locations = s.preferred_locations if hasattr(s, 'preferred_locations') else []
                self.domain_keywords = []
                self.raw_resume_context = ""
        
        return Profile(student)
    
    async def _apply_to_naukri(
        self,
        student: Any,
        settings: Any,
        logger: Any,
    ) -> dict[str, Any]:
        """Async Naukri application using existing search_and_apply flow."""
        
        profile = self._convert_to_profile(student)
        
        try:
            # Get page from browser pool
            page = await playwright_manager.get_page(
                settings,
                student_id=getattr(student, "student_id", None),
            )
        except Exception as e:
            logger.log_err(f"Failed to get browser page: {e}")
            return {
                "status": "failed",
                "error": f"Browser error: {e}",
                "student_id": student.student_id,
                "platform": "naukri",
            }
        
        try:
            # Initialize scraper
            scraper = NaukriScraper(
                max_results=1,
                timeout_seconds=getattr(settings, 'request_timeout_seconds', 30),
                logger=logger,
            )
            
            # Use existing search_and_apply method
            result = await scraper.search_and_apply(profile, settings)
            
            applied_count = result.get("applied", 0)
            scraper_error = result.get("error")
            status = result.get("status")
            
            payload = {
                "status": "applied" if applied_count > 0 else "failed",
                "applied_count": applied_count,
                "skipped_count": result.get("skipped", 0),
                "student_id": student.student_id,
                "platform": "naukri",
                # Forward job identity so base_task can persist it to MongoDB
                "job_title": result.get("job_title") or None,
                "company": result.get("company") or None,
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
                "platform": "naukri",
            }
            
        finally:
            try:
                await playwright_manager.return_page(page)
            except:
                pass


@app.task(
    bind=True,
    base=NaukriApplyTask,
    name="tasks.naukri_task.apply_to_job",
    queue="naukri",
    routing_key="naukri",
    max_retries=3,
    default_retry_delay=60,
)
def apply_to_naukri(
    self,
    student_id: str,
    job_url: str = "",
    resume_variant: str = "backend",
    job_batch: Optional[list[dict[str, Any]]] = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Apply to Naukri jobs for a student.
    Uses existing ai_job_auto_apply scraper.
    """
    return BasePlatformTask.run(
        self,
        student_id=student_id,
        platform="naukri",
        job_url=job_url or "https://www.naukri.com/jobs-in-India",
        resume_variant=resume_variant,
        job_batch=job_batch,
    )
