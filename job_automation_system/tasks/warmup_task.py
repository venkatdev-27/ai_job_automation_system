"""
Warmup Task - Job Automation System
================================
Celery task for warming up new students with roles and resumes.
Generates dynamic roles based on student skills and pre-generates resumes.
"""

from __future__ import annotations
import sys
from typing import Any, Optional
from pathlib import Path

BASE_PATH = Path(__file__).parent.parent
if str(BASE_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_PATH))

from celery import Task
from celery_app.app import app
from tasks.base_task import BasePlatformTask
from database import get_student, update_student

logger = None


def get_logger():
    global logger
    if logger is None:
        from utils.logger import get_logger
        logger = get_logger("warmup")
    return logger


def _execute_warmup(student_id: str) -> dict[str, Any]:
    """Core warmup logic - standalone to avoid Celery recursion."""
    log = get_logger()
    log.log_info(f"Starting warmup for student: {student_id}")

    try:
        student = get_student(student_id)
        if not student:
            return {
                "status": "failed",
                "error": f"Student not found: {student_id}",
                "student_id": student_id,
            }

        skills = student.skills if hasattr(student, 'skills') else []
        if not skills:
            return {
                "status": "failed",
                "error": "No skills found for student",
                "student_id": student_id,
            }


        # Generate resumes ASYNC
        import asyncio
        from rag_engine.rag_resume_generator import RAGResumeGenerator
        
        async def _gen_resumes_internal():
            generator = RAGResumeGenerator(logger=log, student_id=str(student_id))
            generator.rag_engine = None
            await generator._init_rag()
            if not generator.custom_roles:
                await generator.discover_top_roles()
            result = await generator.generate_initial_resumes()
            resumes = {}
            for key, resume in result.items():
                resumes[key] = {
                    "url": "",
                    "path": resume.file_path,
                    "success": bool(resume.file_path)
                }
            return resumes, generator.custom_roles

        resumes, roles = asyncio.run(_gen_resumes_internal())

        update_student(student_id, {
            "custom_roles": roles,
            "resume_variants": resumes,
            "warmup_complete": True,
        })

        log.log_info(f"Warmup completed: {len(roles)} roles, {len(resumes)} resumes")

        return {
            "status": "completed",
            "student_id": student_id,
            "roles_generated": len(roles),
            "resumes_generated": len(resumes),
        }

    except Exception as e:
        log.log_err(f"Warmup failed: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
            "student_id": student_id,
        }


class WarmupTask(Task):
    """Task for warming up students with roles and resumes."""

    name = "tasks.warmup_task.warmup_student"
    max_retries = 2

    def run(self, student_id: str) -> dict[str, Any]:
        return _execute_warmup(student_id)


@app.task(
    bind=True,
    base=WarmupTask,
    name="tasks.warmup_task.warmup_student",
    queue="warmup",
    routing_key="warmup",
    max_retries=2,
    default_retry_delay=300,
)
def warmup_student(self, student_id: str) -> dict[str, Any]:
    """
    Warmup a student with dynamic roles and resumes.
    """
    return _execute_warmup(student_id)