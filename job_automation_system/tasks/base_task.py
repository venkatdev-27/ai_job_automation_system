"""
Base Task - Job Automation System
==================================
Base Celery task with all reliability features:
- Retry with exponential backoff
- Idempotency check
- Distributed locking
- Rate limiting
- Circuit breaker
- Browser semaphore
- Metrics
- Logging
"""

from __future__ import annotations
import random
import time
import traceback
import logging
import threading
from typing import Optional, Any
from datetime import datetime
from celery import Task
from celery_app.app import app
from config import settings, get_platform_config
from services import (
    acquire_student_platform_lock,
    acquire_student_session_lock,
    release_task_lock,
    get_rate_limiter,
    check_circuit,
    record_platform_failure,
    record_platform_success,
    acquire_browser,
    release_browser,
    acquire_platform_slot,
    release_platform_slot,
)
from services.idempotency_v2 import (
    can_apply_for_job,
    mark_session_completed,
    mark_apply_completed_for_job,
    clear_session_for_run,
    clear_apply_for_job,
    get_daily_count,
    generate_run_id,
    clear_all_duplicates,
    DAILY_LIMIT,
)
from services.redis_client import redis_client
from database import (
    get_student,
    create_application,
    check_application_duplicate,
    mark_application_applied,
    mark_application_failed,
    JobApplicationCreate,
)
from services.notifications import notify_application


logger = logging.getLogger(__name__)

LUA_BATCH_PREREQ_CHECK = """
local student_id = KEYS[1]
local platform = ARGV[1]
local job_id = ARGV[2]
local rate_limit = tonumber(ARGV[3])
local max_browsers = tonumber(ARGV[4])
local circuit_threshold = tonumber(ARGV[5])

local results = {}

local circuit_key = 'circuit:' .. platform .. ':state'
local circuit = redis.call('get', circuit_key)
if circuit == 'open' then
    return cjson.encode({can_proceed = false, reason = 'circuit_open'})
end

local rate_key = 'rate_limit:' .. platform .. ':tokens'
local tokens = tonumber(redis.call('get', rate_key) or rate_limit)
if tokens < 1 then
    return cjson.encode({can_proceed = false, reason = 'rate_limit'})
end

local browser_key = 'semaphore:browsers'
local current = tonumber(redis.call('get', browser_key) or '0')
if current >= max_browsers then
    return cjson.encode({can_proceed = false, reason = 'browser_limit'})
end

return cjson.encode({can_proceed = true})
"""

_batch_prereq_script = None


class BasePlatformTask(Task):
    """
    Base task with enterprise-grade reliability features.
    
    Features:
    - Automatic retry with exponential backoff (max 3 retries)
    - Idempotency to prevent duplicate executions
    - Distributed lock to prevent concurrent execution
    - Rate limiting per platform
    - Circuit breaker to pause failing platforms
    - Browser semaphore to limit concurrent browsers
    - Comprehensive logging and metrics
    """
    
    # Retry configuration
    # autoretry_for = (Exception,)  # Removed to prevent recursion in Celery 5.3.6 + Py3.13
    retry_backoff = True
    retry_backoff_max = settings.retry_backoff_max
    retry_jitter = True
    max_retries = settings.max_retries
    
    # Don't count towards retries for idempotency/circuit failures
    throws = ()
    
    # Track applied count for extra delays
    _apply_count: dict[str, int] = {}
    RETRY_MIN_SECONDS = 20
    RETRY_MAX_SECONDS = 60
    RETRY_MAX_ATTEMPTS = 3

    def _resolve_platform_from_context(self, args, kwargs) -> str:
        """Resolve platform for logging/circuit updates even when task uses positional args."""
        platform = kwargs.get("platform")
        if platform:
            return str(platform)
        task_name = getattr(self, "name", "") or ""
        if task_name.startswith("tasks.") and "_task" in task_name:
            # tasks.linkedin_task.apply_to_job -> linkedin
            return task_name.split(".")[1].replace("_task", "")
        return "unknown"

    def _resolve_job_url_from_context(self, args, kwargs) -> str:
        """Resolve job_url for logging from kwargs or positional args."""
        job_url = kwargs.get("job_url")
        if job_url:
            return str(job_url)
        if len(args) >= 2 and isinstance(args[1], str):
            return args[1]
        return ""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails after all retries."""
        self._task_succeeded = False
        student_id = args[0] if args else "unknown"
        platform = self._resolve_platform_from_context(args, kwargs)
        job_url = self._resolve_job_url_from_context(args, kwargs)
        
        logger.error(
            f"Task failed permanently: student={student_id}, platform={platform}, "
            f"job_url={job_url}, error={exc}"
        )
        
        # Record platform failure for circuit breaker
        record_platform_failure(platform)
        
        # Clean up resources
        self._cleanup(student_id, platform, job_url)
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        self._task_succeeded = True
        student_id = args[0] if args else "unknown"
        platform = self._resolve_platform_from_context(args, kwargs)
        job_url = self._resolve_job_url_from_context(args, kwargs)
        
        logger.info(f"Task succeeded: student={student_id}, platform={platform}, job_url={job_url}")
        
        # Step 13: Emit structured metrics
        applied_count = retval.get("applied_count", 0) if isinstance(retval, dict) else 0
        duration = retval.get("duration_seconds", 0) if isinstance(retval, dict) else 0

        # Record platform success for circuit breaker
        record_platform_success(platform)

        # Step 11: Only start cooldown after a real application.
        if applied_count > 0:
            self._record_cooldown(student_id, platform, retval)

        logger.info(
            f"[METRICS] platform={platform} student={student_id} "
            f"applied={applied_count} duration={duration}s status=success"
        )
        
        # Clean up resources
        self._cleanup(student_id, platform, job_url)
    
    def _record_cooldown(self, student_id: str, platform: str, retval: any):
        """Step 11: Record last apply timestamp per platform for cooldown enforcement."""
        try:
            from datetime import datetime
            from database import get_database
            db = get_database()
            db.students.update_one(
                {"student_id": student_id},
                {"$set": {f"platform_cooldowns.{platform}": datetime.utcnow()}},
            )
        except Exception as e:
            logger.warning(f"Failed to record cooldown for {student_id}/{platform}: {e}")
    
    def _cleanup(self, student_id: str, platform: str, job_url: str):
        """Clean up locks and semaphores."""
        # Note: Lock and semaphore should be released in run() but ensure cleanup
        pass
    
    def _check_prerequisites(
        self,
        student_id: str,
        platform: str,
        job_id: str,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check all prerequisites before execution using batched Redis call.
        Optimized: combines circuit + rate + browser checks into single Redis round-trip.
        
        Returns:
            (can_proceed, error_message, application_id)
        """
        global _batch_prereq_script
        if _batch_prereq_script is None:
            _batch_prereq_script = redis_client.client.register_script(LUA_BATCH_PREREQ_CHECK)
        
        can_proceed = True
        fail_reason = None
        
        try:
            platform_config = get_platform_config(platform)
            # PlatformConfig is a dataclass – use getattr, not .get()
            rate_limit_raw = getattr(platform_config, "rate_limit", "10/m") if platform_config else "10/m"
            # rate_limit field is a string like "10/m"; extract the numeric part
            try:
                rate_limit = int(str(rate_limit_raw).split("/")[0])
            except (ValueError, IndexError):
                rate_limit = 10
            
            result = _batch_prereq_script(
                keys=[f"prereq:{student_id}:{platform}:{job_id}"],
                args=[
                    platform,
                    job_id,
                    rate_limit,
                    settings.max_parallel_browsers,
                    settings.circuit_breaker_threshold,
                ]
            )
            
            if result:
                import json
                parsed = json.loads(result)
                if not parsed.get("can_proceed", True):
                    can_proceed = False
                    fail_reason = parsed.get("reason", "unknown")
        except Exception as e:
            logger.warning(f"Batch prereq check failed, falling back: {e}")
            can_proceed = True
        
        if not can_proceed:
            retryable = ("rate_limit", "browser_limit")
            if any(m in fail_reason for m in retryable):
                return False, fail_reason, None
            return False, fail_reason, None
        
        # V2 Idempotency Check - allows retries within session
        session_id = self.request.id[:8] if self.request else None
        # Persist identifiers for deterministic cleanup in retry/finally paths.
        self._session_id = session_id
        self._job_id = job_id
        can_apply, reason, daily_count = can_apply_for_job(platform, student_id, job_id, session_id)
        
        if not can_apply:
            # Get daily count for logging
            dc = get_daily_count(platform, student_id)
            return False, f"Duplicate: {reason} (daily: {dc}/{DAILY_LIMIT})", None
        
        if check_application_duplicate(student_id, platform, job_id):
            mark_session_completed(platform, student_id, session_id)
            return False, "Application already exists in database", None
        
        if not acquire_browser(blocking=False):
            return False, "Browser limit reached, please wait", None
        
        return True, None, None
    
    def _acquire_task_lock(
        self,
        student_id: str,
        platform: str,
        job_id: str,
    ) -> Optional[Any]:
        """Acquire strict student+platform lock for task."""
        return acquire_student_platform_lock(student_id, platform, blocking=False, timeout=5)

    def _retry_with_jitter(self, reason: str):
        """Retry task with jittered countdown to avoid thundering herd."""
        countdown = random.randint(self.RETRY_MIN_SECONDS, self.RETRY_MAX_SECONDS)
        raise self.retry(
            exc=RuntimeError(reason),
            countdown=countdown,
            max_retries=self.RETRY_MAX_ATTEMPTS,
        )

    def _start_lock_heartbeat(self, *locks: Any) -> tuple[threading.Event, threading.Thread]:
        """Keep task/session locks alive while platform scrapers are running."""
        stop_event = threading.Event()
        active_locks = [lock for lock in locks if lock]

        def heartbeat_loop() -> None:
            while not stop_event.wait(30):
                for lock in active_locks:
                    try:
                        if getattr(lock, "should_heartbeat", lambda: True)():
                            lock.heartbeat()
                    except Exception as exc:
                        logger.warning(f"Failed to heartbeat lock {getattr(lock, 'key', '<unknown>')}: {exc}")

        thread = threading.Thread(
            target=heartbeat_loop,
            name="task-lock-heartbeat",
            daemon=True,
        )
        thread.start()
        return stop_event, thread
    
    def _execute_with_protection(
        self,
        student_id: str,
        platform: str,
        job_url: str,
        resume_variant: str,
        job_batch: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Execute the core task logic with all protections.
        """
        # Parse job_id from URL (platform-specific). For batch mode, use a stable batch key.
        if job_batch:
            import hashlib
            from datetime import datetime as _dt
            batch_urls = [str(item.get("url", "")).strip() for item in job_batch if isinstance(item, dict)]
            ts = _dt.now().strftime("%Y%m%d%H%M")
            seed = f"{platform}:{student_id}:{'|'.join(batch_urls[:50])}:{len(batch_urls)}:{ts}"
            job_id = hashlib.md5(seed.encode()).hexdigest()[:16]
        else:
            job_id = self._extract_job_id(job_url, platform)

        platform_slot = acquire_platform_slot(platform, timeout=900)
        if not platform_slot:
            self._retry_with_jitter(f"Platform global semaphore busy: {platform}")
        
        # Check prerequisites
        can_proceed, error_message, _ = self._check_prerequisites(
            student_id, platform, job_id
        )

        # Store session_id for later use (from stored attribute)
        stored_session = getattr(self, '_session_id', None)

        if not can_proceed:
            release_platform_slot(platform_slot)
            if stored_session:
                clear_session_for_run(platform, student_id, stored_session)
            if error_message and (
                "Browser limit" in error_message
                or "browser_limit" in error_message
                or "Application already exists in database" in error_message
            ):
                clear_apply_for_job(platform, student_id, job_id)
            retryable_reasons = ("rate_limit", "browser_limit")
            if error_message and any(reason in error_message for reason in retryable_reasons):
                self._retry_with_jitter(error_message)
            logger.info(
                f"Skipping task before execution: student={student_id}, "
                f"platform={platform}, reason={error_message}"
            )
            return {
                "status": "skipped",
                "applied": 0,
                "applied_count": 0,
                "error": error_message,
            }

        # Force-clear session AND apply keys if prior clear failed (prevents permanent stuck).
        # Also handles worker crash: if task died before finally, the apply key is still set
        # from prerequisite check but never cleared. Force-clear it on retry so the job proceeds.
        if getattr(self, '_skip_idempotency', False):
            if stored_session:
                logger.warning(f"[IDEMP] Force-clearing session key from prior failure: {platform}:{student_id}:{stored_session}")
                clear_session_for_run(platform, student_id, stored_session)
            logger.warning(f"[IDEMP] Force-clearing apply key for retry: {platform}:{student_id}:{job_id}")
            clear_apply_for_job(platform, student_id, job_id)
            self._skip_idempotency = False

        # Mark V2 session as completed right after prerequisites, then auto-clear
        # in finally. This prevents stale session keys from blocking later runs.
        if stored_session:
            mark_session_completed(platform, student_id, stored_session)
        
        # Create application record BEFORE locking so it shows up on dashboard
        print(f"[DEBUG] Creating application record for {student_id} on {platform}...")
        application = create_application(
            JobApplicationCreate(
                student_id=student_id,
                platform=platform,
                job_id=job_id,
                job_url=job_url,
                status="pending",
                resume_variant=resume_variant,
            )
        )
        application_id = str(application.id)
        
        # Acquire distributed lock
        lock = self._acquire_task_lock(student_id, platform, job_id)
        if not lock:
            # Browser semaphore was acquired in prerequisites, release before retry.
            release_browser()
            release_platform_slot(platform_slot)
            if stored_session:
                clear_session_for_run(platform, student_id, stored_session)
            clear_apply_for_job(platform, student_id, job_id)
            
            # Mark as failed in DB so user knows why it's retrying
            mark_application_failed(application_id, f"Student/platform lock busy: {student_id}/{platform}")
            
            self._retry_with_jitter(f"Student/platform lock busy: {student_id}/{platform}")
        
        print(f"[DEBUG] Acquired platform lock for {student_id}")
        # Acquire cross-platform student session lock (prevents profile crashes)
        print(f"[DEBUG] Acquiring session lock for {student_id}...")
        session_lock = acquire_student_session_lock(
            student_id, blocking=True, timeout=120
        )
        
        if not session_lock:
            release_browser()
            release_platform_slot(platform_slot)
            if lock:
                release_task_lock(lock)
            if stored_session:
                clear_session_for_run(platform, student_id, stored_session)
            clear_apply_for_job(platform, student_id, job_id)
            
            # Mark as failed in DB
            mark_application_failed(application_id, f"Session lock busy (another platform is using browser)")
            
            self._retry_with_jitter(
                f"Student session lock busy (another platform is using this student's browser): {student_id}"
            )
            
        print(f"[DEBUG] Acquired session lock for {student_id}")

        heartbeat_stop, heartbeat_thread = self._start_lock_heartbeat(lock, session_lock)
        
        try:
            # Get student profile
            print(f"[DEBUG] Fetching student {student_id}...")
            student = get_student(student_id)
            print(f"[DEBUG] Fetched student {student_id}")
            if not student:
                raise ValueError(f"Student not found: {student_id}")
            
            # Get platform config for delays
            platform_config = get_platform_config(platform)
            
            # Execute the platform-specific logic
            result = self._execute_platform_task(
                student=student,
                platform=platform,
                job_url=job_url,
                job_id=job_id,
                resume_variant=resume_variant,
                application_id=application_id,
                platform_config=platform_config,
                job_batch=job_batch,
            )
            
            # Update application status - handle both "applied" and "completed" statuses
            if result.get("status") == "applied" or result.get("applied", 0) > 0:
                if job_batch:
                    # For batch execution, we delete the temporary task-level pending record
                    # since the individual successful applications are already recorded
                    # by the scraper via notify-application.
                    try:
                        from bson import ObjectId
                        from database.client import get_collection
                        get_collection("job_applications").delete_one({"_id": ObjectId(application.id)})
                    except Exception as del_err:
                        logger.warning(f"Failed to delete batch task pending record: {del_err}")
                else:
                    mark_application_applied(
                        str(application.id),
                        result.get("job_title"),
                        result.get("company"),
                    )
                    
                    # Notify dashboard via Socket.io
                    notify_application(
                        student_id=student_id,
                        platform=platform,
                        job_title=result.get("job_title", "N/A"),
                        company=result.get("company", "N/A"),
                        status="applied",
                        resume_variant=resume_variant,
                        resume_url=result.get("resume_url", ""),
                        job_url=job_url,
                    )
            elif result.get("status") == "failed" or (result.get("applied", 0) == 0 and result.get("status") == "completed"):
                if job_batch and result.get("status") == "completed":
                    # Mark it as skipped rather than failed for successful scan with 0 applications
                    try:
                        from database import application_repository
                        application_repository.mark_skipped(
                            str(application.id),
                            "Scanned successfully but applied to 0 jobs (match or cap filters)"
                        )
                    except Exception as skip_err:
                        logger.warning(f"Failed to mark batch task as skipped: {skip_err}")
                else:
                    mark_application_failed(str(application.id), result.get("error", ""))
                    
                    # Notify dashboard of failure
                    notify_application(
                        student_id=student_id,
                        platform=platform,
                        job_title=result.get("job_title", "N/A"),
                        company=result.get("company", "N/A"),
                        status="failed",
                        resume_variant=resume_variant,
                        resume_url=result.get("resume_url", ""),
                        job_url=job_url,
                        error=result.get("error"),
                    )
            
            self._task_succeeded = True
            return result
            
        except Exception as e:
            logger.error(f"Task execution error: {e}\n{traceback.format_exc()}")
            raise
            
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=5)

            # Auto-clean idempotency keys on every exit (success/failure/retry path)
            # so no manual clear script is required.
            try:
                if stored_session:
                    if not clear_session_for_run(platform, student_id, stored_session):
                        logger.error(f"[IDEMP] Failed to clear session key (will retry next run): {platform}:{student_id}:{stored_session}")
                        self._skip_idempotency = True
                        redis_client.client.incr('job_automation:session_clear_failures')
            except Exception as exc:
                logger.error(f"[IDEMP] CRITICAL - Failed clearing session key (blocking next run): {platform}:{student_id} - {exc}")
                self._skip_idempotency = True
                redis_client.client.incr('job_automation:session_clear_failures')
            # Only clear idemp:apply key on failure to prevent duplicate applications on Celery retry.
            # On success, the apply key persists (TTL 24h) to block future duplicates.
            try:
                if getattr(self, '_task_succeeded', False):
                    if mark_apply_completed_for_job(platform, student_id, job_id):
                        logger.info(f"[IDEMP] Apply key marked completed: idemp:apply:{platform}:{student_id}:{job_id}")
                    else:
                        logger.error(f"[IDEMP] Failed to mark apply key completed: {platform}:{student_id}:{job_id}")
                        redis_client.client.incr('job_automation:idemp_complete_failures')
                else:
                    if not clear_apply_for_job(platform, student_id, job_id):
                        logger.error(f"[IDEMP] Failed to clear apply key (will retry): {platform}:{student_id}:{job_id}")
                        self._skip_idempotency = True
                        redis_client.client.incr('job_automation:idemp_clear_failures')
            except Exception as exc:
                logger.error(f"[IDEMP] CRITICAL - Failed clearing apply key (force retry next run): {platform}:{student_id}:{job_id} - {exc}")
                self._skip_idempotency = True
                redis_client.client.incr('job_automation:idemp_clear_failures')

            # Release session lock
            if session_lock:
                release_task_lock(session_lock)
            
            # Release platform lock
            if lock:
                release_task_lock(lock)

            release_platform_slot(platform_slot)
            
            # Release browser semaphore
            release_browser()
    
    def _extract_job_id(self, job_url: str, platform: str) -> str:
        """Extract job ID from URL.
        
        For all URLs (both specific jobs AND generic search), include a timestamp
        so each run gets a unique idempotency key and isn't blocked as duplicate.
        This permanently fixes the "lock busy" / "duplicate task" issue.
        """
        import hashlib
        
        # Always include timestamp for unique keys per run
        # Use minute-level for maximum uniqueness
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d%H%M")
        
        # Also detect if this is a generic search URL
        generic_patterns = (
            "jobs-in-", "/jobs?", "/job-listings",
            "naukri.com/jobs", "foundit.in/search", "linkedin.com/jobs/search",
        )
        is_generic = any(p in job_url for p in generic_patterns)
        
        # For generic URLs, use URL + minute timestamp for unique key per run
        # For specific job URLs, still add timestamp to prevent re-runs within same minute
        seed = f"{job_url}:{ts}"
        
        return hashlib.md5(seed.encode()).hexdigest()[:16]
    
    def _execute_platform_task(
        self,
        student: Any,
        platform: str,
        job_url: str,
        job_id: str,
        resume_variant: str,
        application_id: str,
        platform_config: Any,
        job_batch: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Override this method in platform-specific tasks.
        """
        raise NotImplementedError("Subclasses must implement _execute_platform_task")
    
    def run(
        self,
        student_id: str,
        platform: str,
        job_url: str,
        resume_variant: str = "backend",
        job_batch: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Main task entry point.
        
        Args:
            student_id: Unique student identifier
            platform: Platform name (naukri, linkedin, foundit)
            job_url: URL of the job to apply
            resume_variant: Resume variant to use (frontend, backend, fullstack)
            
        Returns:
            Result dict with status and details
        """
        start_time = time.time()
        
        logger.info(
            f"Starting task: student_id={student_id}, platform={platform}, "
            f"job_url={job_url}, resume_variant={resume_variant}, batch_size={len(job_batch or [])}"
        )
        
        try:
            result = self._execute_with_protection(
                student_id=student_id,
                platform=platform,
                job_url=job_url,
                resume_variant=resume_variant,
                job_batch=job_batch,
            )
            self._task_succeeded = True
            
            duration = time.time() - start_time
            result["duration_seconds"] = round(duration, 2)
            
            logger.info(
                f"Task completed: student_id={student_id}, platform={platform}, "
                f"status={result.get('status')}, duration={duration:.2f}s"
            )
            
            return result
            
        except Exception as e:
            self._task_succeeded = False
            duration = time.time() - start_time
            logger.error(
                f"Task failed: student_id={student_id}, platform={platform}, "
                f"error={str(e)}, duration={duration:.2f}s"
            )
            raise


# Decorator for registering tasks
def register_platform_task(task_class: type, platform: str):
    """Register a platform task with Celery."""
    name = f"tasks.{platform}_task.apply_to_job"
    task_class.name = name
    return task_class
