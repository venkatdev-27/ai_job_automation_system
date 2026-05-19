"""
Generate Initial Resumes Task - Job Automation System
==================================================
Celery task for generating initial role resumes using RAG engine.
"""

from __future__ import annotations
import asyncio
import logging
import sys
from typing import Any
from datetime import datetime
from pathlib import Path

BASE_PATH = Path(__file__).parent.parent
if str(BASE_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_PATH))

from celery_app.app import app
from utils.logger import get_logger

logger = logging.getLogger("generate_initial_resumes")


def _run_async(coro):
    """Run async code in Celery worker."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@app.task(
    name="tasks.generate_initial_resumes_task.generate_resumes",
    queue="warmup",
    routing_key="warmup",
    max_retries=2,
    bind=True,
)
def generate_resumes(self, student_id: str) -> dict[str, Any]:
    """
    Generate initial resumes for a student.
    """
    logger.info(f"Starting generate_initial_resumes for student: {student_id}")

    try:
        async def _generate():
            from utils.student_mongodb import get_student_by_id
            
            student = get_student_by_id(student_id)
            if not student:
                raise ValueError(f"Student not found: {student_id}")
            
            from rag_engine.rag_resume_generator import get_rag_resume_generator
            
            generator = get_rag_resume_generator(student_id=student_id)
            generator.hydrate_from_db(student)
            
            resumes = await generator.generate_initial_resumes()
            
            from utils.helpers import upload_to_cloudinary
            resume_urls = {}
            for role_key, role_resume in resumes.items():
                file_path = Path(role_resume.file_path)
                if file_path.exists():
                    logger.info(f"Uploading {role_key} resume to Cloudinary...")
                    # Create a specific folder per student to keep it clean
                    cloud_url = upload_to_cloudinary(file_path, folder=f"ai_bot_resumes/{student_id}")
                    if cloud_url:
                        resume_urls[role_key] = cloud_url
                        
            return {
                "student_id": student_id,
                "resumes_generated": len(resumes),
                "resumes_dir": str(generator.resumes_dir),
                "resume_urls": resume_urls
            }
        
        result = _run_async(_generate())
        logger.info(f"Completed generate_initial_resumes: {result['resumes_generated']} resumes")
        
        from database.student_repo import update_student
        
        update_data = {
            "warmup_complete": True,
            "warmup_resumes_generated": result['resumes_generated'],
            "last_warmup": datetime.now().isoformat()
        }
        
        if result.get("resume_urls"):
            update_data["resume_urls"] = result["resume_urls"]
            
        update_student(student_id, update_data)
        logger.info(f"Marked warmup_complete and updated resume_urls for {student_id}")
        
        return result

    except Exception as e:
        logger.error(f"Generate initial resumes failed: {e}")
        raise self.retry(exc=e, countdown=300)