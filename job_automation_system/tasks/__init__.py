"""
Tasks Package - Job Automation System
=====================================
Celery tasks for Naukri, LinkedIn, and FoundIt platforms.
"""

from tasks.naukri_task import apply_to_naukri, NaukriApplyTask
from tasks.linkedin_task import apply_to_linkedin, LinkedInApplyTask
from tasks.foundit_task import apply_to_foundit, FoundItApplyTask
from tasks.generate_initial_resumes_task import generate_resumes
from tasks.producer_platform_task import (
    run_platform,
    run_naukri,
    run_foundit,
    run_linkedin,
    ProducerPlatformTask,
)
from tasks.student_wave_task import run_student_wave, StudentWaveTask

__all__ = [
    "apply_to_naukri",
    "NaukriApplyTask",
    "apply_to_linkedin",
    "LinkedInApplyTask",
    "apply_to_foundit",
    "FoundItApplyTask",
    "generate_resumes",
    "run_platform",
    "run_naukri",
    "run_foundit",
    "run_linkedin",
    "ProducerPlatformTask",
    "run_student_wave",
    "StudentWaveTask",
]
