"""
Producer - Job Automation System
================================
Main producer script to push job application tasks to Celery.
"""

from __future__ import annotations
import asyncio
import sys
import logging
import argparse
import os
import random
import time
from typing import Any, Optional
from datetime import datetime, timedelta, timezone

# Add parent directory to path for imports
sys.path.insert(0, ".")

from config.settings import settings
from config.platforms import get_platform_config
from config.wave_config import wave_config, get_time_period, get_platform_weights
from database import get_active_students, count_students
from database.client import get_collection
from producer.job_generator import get_job_urls
from producer.wave_scheduler import WaveScheduler, PlatformDistributor
from utils.logger import get_logger

# Defer celery import to avoid circular import
# NOT caching the app - create fresh each time to pick up env var changes
def _get_celery_app():
    from celery_app.app import app as _app
    return _app


logger = logging.getLogger(__name__)


class JobProducer:
    """
    Producer that generates and queues job application tasks.
    
    Supports two modes:
    1. Legacy (WAVE_MODE=false): Platform-first batch processing
    2. Wave (WAVE_MODE=true): Mini-Wave with anti-detection layers
    
    Wave Mode Anti-Detection:
    - Mini-Wave: 5 jobs per batch + random pause
    - Random Platform: weighted by time of day
    - Time-Based: morning/afternoon/evening patterns
    - Student Spacing: 30-60s random between students
    - Day Distribution: spread applications throughout day
    """
    
    def __init__(self):
        self.tasks_submitted = 0
        self.tasks_skipped = 0
        self._warmup_checked_students: set[str] = set()
        self._wave_scheduler: Optional[WaveScheduler] = None
        self._platform_distributor: Optional[PlatformDistributor] = None
        self._student_state_cache: dict[str, dict[str, Any]] = {}
    
    @property
    def is_wave_mode(self) -> bool:
        """Check if wave mode is enabled."""
        return wave_config.enabled
    
    def run(
        self,
        student_limit: int = 0,
        student_id: Optional[str] = None,
        platforms: Optional[list[str]] = None,
        jobs_per_student: int = 10,
        dry_run: bool = False,
        wait_between_platforms_seconds: int = 600,
        schedule_name: str = "manual",
    ):
        """
        Run the producer.

        Args:
            student_limit: Max students to process (0 = all)
            student_id: Specific student ID to process (overrides student_limit)
            platforms: List of platforms to target (None = all)
            jobs_per_student: Requested jobs per student/platform. Platform caps still apply.
            dry_run: If True, don't submit tasks
            wait_between_platforms_seconds: Pause between platform rounds.
            schedule_name: Name of schedule (morning-6am, afternoon-11am, evening-5pm, night-8pm)
        """
        logger.info("=" * 60)
        logger.info("JOB PRODUCER STARTED")
        logger.info("=" * 60)
        
        from config.platforms import PLATFORMS
        
        # Default platforms
        if not platforms:
            platforms = list(PLATFORMS.keys())
        
        # Fetch students
        if student_id:
            logger.info(f"Processing specific student: {student_id}")
            students = get_active_students(limit=0, student_id=student_id)
            if not students:
                logger.error(f"Student {student_id} not found or inactive!")
                return
        else:
            students = get_active_students(limit=student_limit)
        
        total_students = count_students()
        self._student_state_cache = self._preload_student_state(students)
        
        logger.info(f"Total active students: {total_students}")
        logger.info(f"Processing: {len(students)} students")
        logger.info(f"Platforms: {', '.join(platforms)}")
        
        if not students:
            logger.warning("No active students found!")
            return
        
        if self.is_wave_mode:
            logger.info("=" * 60)
            logger.info("WAVE MODE ENABLED - Mini-Wave Anti-Detection")
            logger.info("=" * 60)
            time_period = get_time_period()
            weights = get_platform_weights(time_period)
            logger.info(f"Time Period: {time_period}")
            logger.info(f"Platform Weights: {weights}")
            
            self._wave_scheduler = WaveScheduler()
            self._platform_distributor = PlatformDistributor(self._wave_scheduler)
            
            self._run_wave_mode(
                students=students,
                platforms=platforms,
                jobs_per_student=jobs_per_student,
                dry_run=dry_run,
                schedule_name=schedule_name,
            )
        else:
            sorted_platforms = sorted(
                platforms,
                key=lambda p: getattr(get_platform_config(p), "weight", 0),
                reverse=True,
            )
            logger.info(f"Platform execution order (by weight): {sorted_platforms}")
            
            for student in students:
                self._ensure_student_warmup(student=student, dry_run=dry_run)

            platform_round_offset = 0
            for index, platform in enumerate(sorted_platforms):
                logger.info(f"\n--- ROUND: {platform.upper()} (weight={getattr(get_platform_config(platform), 'weight', 0)}) ---")
                
                platform_cap = getattr(
                    get_platform_config(platform),
                    "max_applies_per_run",
                    jobs_per_student,
                )
                if jobs_per_student and jobs_per_student > 0:
                    jobs_count = min(jobs_per_student, platform_cap)
                else:
                    jobs_count = platform_cap
                
                for idx, student in enumerate(students):
                    if self._is_in_cooldown(student.student_id, platform):
                        logger.info(f"  [{platform}] Student {student.student_id} in cooldown, skipping.")
                        self.tasks_skipped += 1
                        continue

                    self._submit_tasks_for_platform(
                        student=student,
                        student_index=idx,
                        platform=platform,
                        jobs_per_platform=jobs_count,
                        dry_run=dry_run,
                        countdown=platform_round_offset,
                    )
                
                is_last_platform = index == len(sorted_platforms) - 1
                if not dry_run and not is_last_platform and wait_between_platforms_seconds > 0:
                    logger.info(
                        f"  Scheduling next platform round with {wait_between_platforms_seconds}s offset "
                        f"after {platform} submissions..."
                    )
                    platform_round_offset += wait_between_platforms_seconds

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("PRODUCER SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Tasks submitted: {self.tasks_submitted}")
        logger.info(f"Tasks skipped: {self.tasks_skipped}")
        logger.info(f"Total students: {len(students)}")
        logger.info(f"Platforms: {', '.join(platforms)}")

    def _preload_student_state(self, students: list[Any]) -> dict[str, dict[str, Any]]:
        student_ids = [getattr(student, "student_id", "") for student in students if getattr(student, "student_id", "")]
        if not student_ids:
            return {}

        try:
            docs = get_collection("students").find(
                {"student_id": {"$in": student_ids}},
                {
                    "student_id": 1,
                    "custom_roles": 1,
                    "platform_cooldowns": 1,
                },
            )
            state: dict[str, dict[str, Any]] = {}
            for doc in docs:
                student_id = str(doc.get("student_id", "")).strip()
                if not student_id:
                    continue
                state[student_id] = {
                    "custom_roles": doc.get("custom_roles") or {},
                    "platform_cooldowns": doc.get("platform_cooldowns") or {},
                }
            return state
        except Exception as exc:
            logger.warning(f"Failed to preload student state cache: {exc}")
            return {}

    def _ensure_student_warmup(self, student: any, dry_run: bool) -> None:
        """
        Auto-trigger warmup once per student before submitting application tasks.

        Warmup is skipped when role discovery data already exists in MongoDB.
        """
        student_id = getattr(student, "student_id", "")
        if not student_id or student_id in self._warmup_checked_students:
            return

        self._warmup_checked_students.add(student_id)

        if dry_run:
            logger.info(f"  [DRY RUN] Would auto-trigger warmup for {student_id}")
            return
        
        try:
            student_state = self._student_state_cache.get(student_id, {})
            existing_roles = student_state.get("custom_roles", {})
            if isinstance(existing_roles, dict) and existing_roles:
                logger.info(f"  Warmup already present for {student_id}; skipping.")
                return
        except Exception as exc:
            logger.warning(f"  Warmup pre-check failed for {student_id}: {exc}")

        try:
            from tasks.warmup_task import warmup_student

            logger.info(f"  Auto-triggering warmup for {student_id}...")
            warmup_student.apply_async(
                args=[student_id],
                queue="warmup",
                ignore_result=True,
            )
            self._student_state_cache.setdefault(student_id, {})["custom_roles"] = {"_pending": True}
            logger.info(f"  Warmup task submitted for {student_id}.")
        except Exception as exc:
            logger.warning(f"  Warmup trigger error for {student_id}: {exc}. Proceeding anyway.")
    
    def _is_in_cooldown(self, student_id: str, platform: str) -> bool:
        """
        Step 11: Check if this student+platform was applied recently.
        Prevents repeated hits to the same platform within the cooldown window.
        """
        try:
            student_doc = self._student_state_cache.get(student_id)
            if not isinstance(student_doc, dict):
                return False
            
            cooldowns = student_doc.get("platform_cooldowns", {})
            last_applied = cooldowns.get(platform)
            if not last_applied:
                return False
            
            if isinstance(last_applied, str):
                last_applied = datetime.fromisoformat(last_applied)
            
            # Platform-specific cooldown windows
            cooldown_hours = {"linkedin": 4, "naukri": 1, "foundit": 2}
            window = timedelta(hours=cooldown_hours.get(platform, 2))
            
            if datetime.now(timezone.utc) - last_applied < window:
                return True
        except Exception:
            pass
        return False
    
    def _run_wave_mode(
        self,
        students: list,
        platforms: list[str],
        jobs_per_student: int,
        dry_run: bool,
        schedule_name: str = "manual",
    ) -> None:
        """
        Run producer in Wave Mode with time-aware platform distribution.

        Per-run distribution:
        - 6:00 AM (morning-6am):  FoundIt=7, Naukri=1, LinkedIn=1 = 9 total
        - 11:00 AM (afternoon-11am): FoundIt=4, Naukri=1, LinkedIn=1 = 6 total
        - 5:00 PM (evening-5pm):    FoundIt=2, Naukri=3, LinkedIn=3 = 8 total
        - 8:00 PM (night-8pm):      FoundIt=1, Naukri=1, LinkedIn=1 = 3 total
        Total per student per day: 26 (14 FoundIt + 6 Naukri + 6 LinkedIn)
        """
        logger.info("\n" + "=" * 60)
        logger.info("WAVE MODE EXECUTION")
        logger.info(f"Schedule: {schedule_name}")
        logger.info("=" * 60)

        # Record beat trigger time when starting (non-dry-run)
        if not dry_run and schedule_name != "manual":
            try:
                import requests
                node_api_url = os.getenv("NODE_API_URL", "http://localhost:3000")
                requests.post(
                    f"{node_api_url}/api/automation/record-beat-trigger",
                    json={"schedule_name": schedule_name},
                    timeout=5
                )
                logger.info(f"Beat trigger recorded: {schedule_name}")
            except Exception as e:
                logger.warning(f"Could not record beat trigger: {e}")

        if not self._wave_scheduler or not self._platform_distributor:
            logger.error("Wave scheduler not initialized!")
            return

        scheduler = self._wave_scheduler
        distributor = self._platform_distributor

        # Time-aware platform distribution based on schedule_name
        schedule_platform_jobs = {
            "morning-6am": {"foundit": 7, "naukri": 1, "linkedin": 1},
            "afternoon-11am": {"foundit": 4, "naukri": 1, "linkedin": 1},
            "evening-5pm": {"foundit": 2, "naukri": 3, "linkedin": 3},
            "night-8pm": {"foundit": 1, "naukri": 1, "linkedin": 1},
            "recovery-1030pm": {"foundit": 4, "naukri": 1, "linkedin": 1},
            "manual": {"foundit": 4, "naukri": 1, "linkedin": 1},
        }
        platform_jobs = schedule_platform_jobs.get(schedule_name, schedule_platform_jobs["manual"])
        logger.info(f"Platform jobs for {schedule_name}: {platform_jobs}")
        logger.info(f"Expected total: {sum(platform_jobs.values())} jobs per student")
        logger.info(f"Batch size: {jobs_per_student} jobs per task (Mini-Wave)")
        
        total_students = len(students)
        students_per_wave = wave_config.students_per_wave
        
        logger.info(f"Total students: {total_students}")
        logger.info(f"Students per wave: {students_per_wave}")
        
        for student in students:
            self._ensure_student_warmup(student=student, dry_run=dry_run)
        
        num_waves = (total_students + students_per_wave - 1) // students_per_wave
        logger.info(f"Expected waves: {num_waves}")
        
        wave_offset_seconds = 0
        for wave_num in range(num_waves):
            start_idx = wave_num * students_per_wave
            end_idx = min(start_idx + students_per_wave, total_students)
            wave_students = students[start_idx:end_idx]
            
            scheduler.start_wave()
            logger.info(f"\n--- WAVE {wave_num + 1}/{num_waves} (Students {start_idx + 1}-{end_idx}) ---")
            
            for student_idx, student in enumerate(wave_students):
                overall_student_idx = start_idx + student_idx

                # Check if student already hit daily cap (26 jobs max per day)
                from services.daily_caps import get_remaining_total_applications
                total_remaining = get_remaining_total_applications(student.student_id)
                if total_remaining <= 0:
                    logger.info(f"  [{student.student_id}] Daily cap (26) reached, skipping for today")
                    continue

                filtered_platform_jobs = {
                    platform: int(jobs_count or 0)
                    for platform, jobs_count in platform_jobs.items()
                    if platform in platforms and int(jobs_count or 0) > 0
                }

                if not filtered_platform_jobs:
                    logger.info(f"  [{student.student_id}] No enabled platforms for this wave")
                    continue

                target_count = min(sum(filtered_platform_jobs.values()), total_remaining)
                if not scheduler.can_submit_application(total_students, target_count):
                    logger.info(f"  Day distribution limit reached, pausing wave...")
                    break

                countdown = scheduler.get_countdown_with_spacing(
                    student_index=overall_student_idx,
                    wave_offset=0,
                )
                countdown += wave_offset_seconds

                self._submit_student_wave_task(
                    student=student,
                    student_index=overall_student_idx,
                    schedule_name=schedule_name,
                    platform_jobs=filtered_platform_jobs,
                    dry_run=dry_run,
                    countdown=countdown,
                )

                for platform, jobs_count in filtered_platform_jobs.items():
                    distributor.record_submission(platform)
                    scheduler.record_application(platform, jobs_count)

                # Spacing between students (30-60s random)
                actual_spacing = scheduler.get_student_spacing()
                logger.debug(f"  Student spacing: {actual_spacing}s")

            if wave_num < num_waves - 1:
                wave_pause = scheduler.get_wave_pause()
                logger.info(
                    f"\n  Wave {wave_num + 1} complete. Scheduling next wave with +{wave_pause}s offset..."
                )
                wave_offset_seconds += wave_pause
        
        summary = scheduler.get_wave_summary()
        logger.info("\n" + "=" * 60)
        logger.info("WAVE MODE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Waves executed: {summary['wave_number']}")
        logger.info(f"Applications submitted: {summary['applications_submitted']}")
        logger.info(f"Time period: {summary['time_period']}")
        logger.info(f"Platform distribution: {distributor.get_distribution_summary()}")

    def _submit_student_wave_task(
        self,
        student: any,
        student_index: int,
        schedule_name: str,
        platform_jobs: dict[str, int],
        dry_run: bool,
        countdown: Optional[int] = None,
    ) -> None:
        """Submit one student-first wave task."""
        target_count = sum(int(v or 0) for v in platform_jobs.values())
        if dry_run:
            logger.info(
                f"    [DRY RUN] Would submit student wave: student={student.student_id}, "
                f"schedule={schedule_name}, target={target_count}, platform_jobs={platform_jobs}"
            )
            self.tasks_skipped += 1
            return

        try:
            celery_app_instance = _get_celery_app()
            from celery import signature

            sig = signature(
                "tasks.student_wave_task.run_student_wave",
                app=celery_app_instance,
            )
            result = sig.apply_async(
                args=[student.student_id, schedule_name, platform_jobs, False],
                countdown=countdown or 0,
                queue="student_wave",
                routing_key="student_wave",
                ignore_result=False,
                retry=True,
                retry_policy={
                    "max_retries": 3,
                    "interval_start": 1,
                    "interval_step": 2,
                    "interval_max": 5,
                },
            )

            logger.info(
                f"    Submitted student wave: student={student.student_id}, "
                f"schedule={schedule_name}, target={target_count}, task_id={result.id}"
            )
            self.tasks_submitted += 1
        except Exception as exc:
            logger.error(f"    Failed to submit student wave for {student.student_id}: {exc}")
            self.tasks_skipped += 1
    
    def _submit_tasks_for_platform(
        self,
        student: any,
        student_index: int,
        platform: str,
        jobs_per_platform: int,
        dry_run: bool,
        countdown: Optional[int] = None,
    ):
        """Submit tasks for a specific platform."""
        
        platform_config = get_platform_config(platform)
        
        if not platform_config:
            logger.warning(f"Unknown platform: {platform}")
            return
        
        logger.info(f"  Platform: {platform} ({jobs_per_platform} jobs)")
        
        # Generate job URLs
        try:
            job_urls = get_job_urls(
                student=student,
                platform=platform,
                max_jobs=jobs_per_platform,
            )
        except Exception as e:
            logger.error(f"  Error generating job URLs: {e}")
            return
        
        if not job_urls:
            logger.warn(f"  No job URLs generated")
            self.tasks_skipped += 1
            return
        
        logger.info(f"  Generated {len(job_urls)} job URLs")

        resume_variant = self._select_batch_resume_variant(job_urls)
        primary_job_url = str(job_urls[0].get("url", "")).strip() or self._default_job_url(platform)
        
        task_countdown = countdown if 'countdown' in dir() else None
        self._submit_batch_task(
            student=student,
            student_index=student_index,
            platform=platform,
            primary_job_url=primary_job_url,
            job_batch=job_urls,
            resume_variant=resume_variant,
            dry_run=dry_run,
            countdown=task_countdown,
        )

    def _select_batch_resume_variant(self, job_batch: list[dict]) -> str:
        """Pick a stable resume variant for a batch (majority vote, fallback backend)."""
        counts: dict[str, int] = {}
        for job in job_batch:
            variant = str(job.get("resume_variant", "backend")).strip().lower()
            if not variant:
                variant = "backend"
            counts[variant] = counts.get(variant, 0) + 1
        if not counts:
            return "backend"
        return max(counts, key=counts.get)

    def _default_job_url(self, platform: str) -> str:
        """Fallback URL per platform when generator returned malformed data."""
        defaults = {
            "naukri": "https://www.naukri.com/jobs-in-India",
            "linkedin": "https://www.linkedin.com/jobs",
            "foundit": "https://www.foundit.in/search/software-engineer-jobs-in-india",
        }
        return defaults.get(platform, "")

    def _submit_batch_task(
        self,
        student: any,
        student_index: int,
        platform: str,
        primary_job_url: str,
        job_batch: list[dict],
        resume_variant: str,
        dry_run: bool,
        countdown: Optional[int] = None,
    ):
        """Submit one batched Celery task for student+platform."""
        
        if dry_run:
            logger.info(
                f"    [DRY RUN] Would submit batch: student={student.student_id}, "
                f"platform={platform}, jobs={len(job_batch)}, variant={resume_variant}"
            )
            self.tasks_skipped += 1
            return
        
        try:
            celery_app_instance = _get_celery_app()
            
            task_name_map = {
                "naukri": "tasks.naukri_task.apply_to_job",
                "linkedin": "tasks.linkedin_task.apply_to_job",
                "foundit": "tasks.foundit_task.apply_to_job",
            }
            
            task_name = task_name_map.get(platform)
            if not task_name:
                logger.error(f"Unknown platform: {platform}")
                return
            
            platform_config = get_platform_config(platform)
            final_countdown = countdown or 0
            final_countdown += getattr(platform_config, "stagger_delay", 0) if platform_config else 0
            
            if self.is_wave_mode and self._wave_scheduler:
                final_countdown += self._wave_scheduler.get_student_spacing() * student_index
                final_countdown += self._wave_scheduler.get_jitter()
            else:
                student_spacing_seconds = 15
                student_countdown = student_index * student_spacing_seconds
                final_countdown += student_countdown
                final_countdown += random.randint(0, 15)
            
            from celery import signature
            
            # Robust retry loop for ConnectionResetError / OperationalError
            max_submit_retries = 3
            for attempt in range(max_submit_retries):
                try:
                    sig = signature(task_name, app=celery_app_instance)
                    result = sig.apply_async(
                        args=[student.student_id, primary_job_url, resume_variant],
                        kwargs={"job_batch": job_batch},
                        countdown=final_countdown,
                        ignore_result=True,  # Don't store result in Redis
                        retry=True,
                        retry_policy={
                            'max_retries': 3,
                            'interval_start': 0,
                            'interval_step': 1.0,
                            'interval_max': 2.0,
                        }
                    )
                    break # Success!
                except Exception as e:
                    if attempt < max_submit_retries - 1:
                        logger.warning(f"Connection error during submit (attempt {attempt+1}): {e}. Retrying...")
                        import time
                        time.sleep(2)
                        # Force connection refresh on the app instance if possible
                        try:
                            if hasattr(celery_app_instance, 'pool'):
                                celery_app_instance.pool.force_close_all()
                        except Exception:
                            pass
                    else:
                        raise e # Re-raise on final attempt

            task_id = result.id if result else "unknown"

            logger.info(
                f"    Submitted batch: jobs={len(job_batch)}, platform={platform}, "
                f"primary_url={primary_job_url[:60]}..., task_id={task_id}"
            )
            self.tasks_submitted += 1
            
            # Record daily application for cap tracking
            from services.daily_caps import record_total_daily_application, record_daily_application
            applied_reservation_count = max(1, len(job_batch or []))
            record_total_daily_application(student.student_id, applied_reservation_count)
            record_daily_application(student.student_id, platform, applied_reservation_count)
            
        except Exception as e:
            import traceback
            logger.error(f"    Failed to submit batch: {e}\n{traceback.format_exc()}")
            self.tasks_skipped += 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Job Automation Producer")
    
    parser.add_argument(
        "--students",
        type=int,
        default=0,
        help="Number of students to process (0 = all)",
    )
    
    parser.add_argument(
        "--platforms",
        type=str,
        default="naukri,linkedin",
        help="Comma-separated list of platforms",
    )
    
    parser.add_argument(
        "--jobs",
        type=int,
        default=10,
        help="Default number of jobs per student",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't submit tasks, just show what would be done",
    )

    parser.add_argument(
        "--wait-between-platforms",
        type=int,
        default=600,
        help="Seconds to wait between platform rounds (default: 600)",
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Parse platforms
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    
    # Run producer
    producer = JobProducer()
    producer.run(
        student_limit=args.students,
        platforms=platforms,
        jobs_per_student=args.jobs,
        dry_run=args.dry_run,
        wait_between_platforms_seconds=args.wait_between_platforms,
    )


if __name__ == "__main__":
    main()
