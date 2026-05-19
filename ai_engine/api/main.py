import sys
import os
import asyncio
from pathlib import Path

# Detect if running in Docker (mounted at /app)
IN_DOCKER = Path("/app/ai_engine").exists()
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", "/app" if IN_DOCKER else "D:/ai-bot-resumes"))

# Add project root to path for Docker and local
if IN_DOCKER:
    # Docker: parent (D:\ai-bot-resumes) mounted at /app
    # Both ai_engine and pipeline are at /app/ai_engine and /app/pipeline
    sys.path.insert(0, "/app")
    sys.path.insert(0, "/app/ai_engine")
    
    # Add job_automation_system for Celery
    job_auto_path = Path("/app/job_automation_system")
    if job_auto_path.exists():
        sys.path.insert(0, str(job_auto_path))
else:
    # Local: add PARENT of ai_engine so ai_engine can be imported as a package
    ai_engine_dir = Path(__file__).resolve().parent.parent  # D:\ai-bot-resumes\ai_engine
    parent_dir = ai_engine_dir.parent  # D:\ai-bot-resumes
    sys.path.insert(0, str(parent_dir))
    
    # Add job_automation_system for Celery
    job_auto_path = parent_dir / "job_automation_system"
    if job_auto_path.exists():
        sys.path.insert(0, str(job_auto_path))

import uuid
import time
import prometheus_client as prom
from fastapi import FastAPI, HTTPException, Request, Query, Response
from pydantic import BaseModel

# Add request model for warmup
class WarmupRequest(BaseModel):
    student_id: str

# Defer celery import to avoid issues when celery not running
_celery_app = None

def _get_celery_app():
    global _celery_app
    if _celery_app is None:
        try:
            from celery_app.app import app as _app
            _celery_app = _app
        except ImportError:
            _celery_app = False
    return _celery_app

from ai_engine.api.models import ResumeRequest, ResumeResponse
from ai_engine.core.orchestrator import ResumeOrchestrator
from ai_engine.utils.logging_setup import logger

app = FastAPI(
    title="AI Resume Engine API",
    description="Production-grade AI resume generation and polishing pipeline.",
    version="1.0.0"
)

# Prometheus metrics
REQUEST_COUNT = prom.Counter(
    'ai_engine_requests_total', 'Total requests', ['method', 'endpoint', 'status']
)
REQUEST_LATENCY = prom.Histogram(
    'ai_engine_request_duration_seconds', 'Request latency', ['method', 'endpoint']
)
ERROR_COUNT = prom.Counter(
    'ai_engine_errors_total', 'Total errors', ['type']
)
ACTIVE_REQUESTS = prom.Gauge('ai_engine_active_requests', 'Currently active requests')

# Standardize orchestrator
orchestrator = ResumeOrchestrator()

@app.on_event("shutdown")
async def shutdown_resources():
    try:
        from ai_engine.core.llm_client import close_llm_clients
        await close_llm_clients()
    except Exception as e:
        logger.warning(f"LLM client shutdown cleanup failed: {e}")

    try:
        from ai_engine.core.pdf_generator import pdf_service
        await pdf_service.aclose()
    except Exception as e:
        logger.warning(f"PDF service shutdown cleanup failed: {e}")

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    ACTIVE_REQUESTS.inc()
    
    logger.info(f"Incoming request", extra={"request_id": request_id, "path": request.url.path})
    
    try:
        response = await call_next(request)
        REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()
        process_time = time.time() - start_time
        REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(process_time)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        logger.info(f"Request completed", extra={"request_id": request_id, "duration": process_time})
        return response
    except Exception as e:
        REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status=500).inc()
        ERROR_COUNT.labels(type=type(e).__name__).inc()
        raise
    finally:
        ACTIVE_REQUESTS.dec()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-resume-engine"}

@app.get("/metrics")
async def metrics():
    return Response(media_type=prom.CONTENT_TYPE_LATEST, content=prom.generate_latest())

@app.get("/api/metrics")
async def api_metrics():
    return Response(media_type=prom.CONTENT_TYPE_LATEST, content=prom.generate_latest())

@app.post("/generate", response_model=ResumeResponse)
async def generate_resume(request: ResumeRequest):
    try:
        # Pass data to the orchestrator, including master template if provided
        result = await orchestrator.generate_resume_pipeline(
            retrieved_chunks=request.retrievedChunks,
            job_description=request.jobDescription,
            student_id=request.student_id,
            master_template=request.master_template,
            summary=request.summary
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Generation failed")
            
        return result

    except Exception as e:
        logger.error(f"Generation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/warmup-student")
async def warmup_student(request: WarmupRequest):
    """
    Trigger Master Profile warmup for a student via Celery.
    Non-blocking - returns immediately with task ID.
    """
    student_id = request.student_id
    try:
        celery_app = _get_celery_app()
        
        if celery_app is False:
            logger.error("Celery not available, cannot trigger warmup")
            return {
                "success": False,
                "message": "Celery not available for warmup",
                "student_id": student_id,
                "status": "failed"
            }
        
        logger.info(f"Submitting warmup task to Celery for student: {student_id}")
        
        result = celery_app.send_task(
            "tasks.generate_initial_resumes_task.generate_resumes",
            args=[student_id],
        )
        
        logger.info(f"Warmup task submitted, ID: {result.id}")
        
        return {
            "success": True,
            "message": f"Warmup task queued for {student_id}",
            "student_id": student_id,
            "status": "queued",
            "task_id": result.id,
            "mode": "celery"
        }
    except Exception as e:
        logger.error(f"Warmup trigger error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/warmup-status/{student_id}")
async def warmup_status(student_id: str):
    """
    Check if warmup has been run for a student by inspecting the resumes directory.
    """
    try:
        from pathlib import Path
        import os
        
        resume_roots = [
            Path(os.getenv("RESUMES_DIR", "")) if os.getenv("RESUMES_DIR") else None,
            PROJECT_ROOT / "ai_engine" / "resumes",
        ]
        student_resume_dir = next(
            (root / student_id for root in resume_roots if root and (root / student_id).exists()),
            (resume_roots[0] or PROJECT_ROOT / "ai_engine" / "resumes") / student_id,
        )
        
        status = {
            "student_id": student_id,
            "folder_exists": student_resume_dir.exists(),
            "role_count": 0,
            "pdfs": []
        }
        
        if student_resume_dir.exists():
            pdf_files = list(student_resume_dir.glob("*.pdf"))
            status["role_count"] = len(pdf_files)
            status["pdfs"] = [f.name for f in pdf_files]
            status["resumes_generated"] = len(pdf_files) >= 6
        else:
            status["resumes_generated"] = False
            
        return status
        
    except Exception as e:
        logger.error(f"Status check error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
