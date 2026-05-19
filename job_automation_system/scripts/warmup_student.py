import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Also add parent for imports
PARENT = PROJECT_ROOT.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

from dataclasses import asdict

# Defer celery import to avoid issues when celery not running
_celery_app = None

def _get_celery_app():
    global _celery_app
    if _celery_app is None:
        from celery_app.app import app as _app
        _celery_app = _app
    return _celery_app

def log(msg, flush=True):
    """Print with flush for real-time visibility"""
    print(msg, flush=flush)

async def warmup_student(student_id: str, wait: bool = True):
    """
    Master Profile Warmup Pipeline:
    1. Fetch student metadata
    2. Download master resume
    3. Extract master resume template
    4. Deep extract + sync profile to MongoDB
    5. Generate initial role resumes
    """
    log(f"\n{'='*60}")
    log(f"STARTING MASTER WARMUP FOR STUDENT: {student_id}")
    log(f"PROJECT ROOT: {PROJECT_ROOT}")
    log(f"{'='*60}")
    
    try:
        # Step 1: Fetch metadata from MongoDB
        log(f"\n[1/5] Fetching student from MongoDB...")
        from utils.student_mongodb import get_student_by_id, update_student_profile, get_student_resume_url
        
        student = get_student_by_id(student_id)
        if not student:
            log(f"ERROR: Student {student_id} not found in MongoDB.")
            return False

        resume_url = get_student_resume_url(student_id)
        if not resume_url:
            log(f"ERROR: No resume URL found for {student_id}.")
            return False
        
        log(f"  OK: Student found: {student.get('full_name', 'N/A')}")
        log(f"  OK: Resume URL: {resume_url[:50]}...")

        # Step 2: Download Resume (Once)
        from utils.resume_downloader import download_if_needed, get_cached_resume_path
        
        cached_path = get_cached_resume_path(student_id, "master", resume_url)
        is_cached = os.path.exists(cached_path)
        
        if is_cached:
            log(f"\n[2/5] Using Cached Master Resume...")
            local_path = cached_path
        else:
            log(f"\n[2/5] Downloading Master Resume from Cloudinary...")
            local_path = download_if_needed(resume_url, student_id)
            
        if not local_path or not os.path.exists(local_path):
            log("ERROR: Download failed.")
            return False
            
        if is_cached:
            log(f"  OK: Found in cache: {local_path}")
        else:
            log(f"  OK: Downloaded: {local_path}")

        # Step 3: Extract Master Template
        log(f"\n[3/5] Extracting Master Resume Template...")
        from utils.master_template_extractor import extract_master_template
        master_template = extract_master_template(student_id, str(local_path))
        log(f"  OK: Template extracted: {master_template.get('alignment', 'center')} alignment, {master_template.get('font_family', 'Calibri')} font")

        # Step 4: Deep Extraction (Stage 1 - The Master)
        log(f"\n[4/5] Deep Extracting AI Master Profile Details...")
        from rag_engine.rag_resume_generator import get_rag_resume_generator
        
        generator = get_rag_resume_generator(student_id=student_id)
        
        # Force re-index but use FAISS=False to avoid memory issues
        # This uses simple text extraction + MongoDB profile fallback
        await generator._init_rag(file_path=str(local_path), force_reindex=True, force_extract=True)
        profile = generator.profile
        
        if not profile or not profile.skills:
            log("ERROR: Extraction failed or returned empty profile.")
            return False
        
        log(f"  OK: Master Extracted: {profile.full_name}")
        log(f"  OK: Master Role: {profile.primary_role}")
        log(f"  OK: Skills: {len(profile.skills)} found")

        # Step 4 (continued): Sync Master Data to MongoDB
        log(f"\n[4/5] Syncing Master Profile to MongoDB...")
        
        # Update student record with the FULL profile
        profile_dict = asdict(profile)
        profile_dict['master_template'] = master_template  # Add template config
        success = update_student_profile(student_id, profile_dict)
        if success:
            log("  OK: Master Profile synced to MongoDB collection.")
        else:
            log("  Warning: MongoDB profile sync reported no changes.")

        # Re-fetch the student document to ensure we have the absolute truth from DB
        updated_student = get_student_by_id(student_id)
        if updated_student:
            generator.hydrate_from_db(updated_student)
        else:
            log("  Warning: Could not re-fetch student after sync; skipping hydrate_from_db.")

        # Step 5: Generate Core 6 Resumes via Celery Task
        log(f"\n[5/5] Submitting generate_initial_resumes task to Celery...")
        
        celery_app = _get_celery_app()
        result = celery_app.send_task(
            "tasks.generate_initial_resumes_task.generate_resumes",
            args=[student_id],
        )
        
        log(f"  OK: Task submitted, ID: {result.id}")
        log(f"  INFO: Use 'celery -A tasks inspect active' to monitor")
        
        if not wait:
            log("  INFO: wait=False, proceeding without waiting for resume completion.")
            return True

        # For now, wait for result (can be changed to async in future)
        try:
            task_result = result.get(timeout=3600)  # 1 hour timeout
            log(f"  OK: Celery task completed: {task_result['resumes_generated']} resumes")
            log(f"  Folder: {task_result['resumes_dir']}")
        except Exception as e:
            log(f"  ERROR: Celery task failed: {e}")
            return False
        
        log(f"\n{'='*60}")
        log(f"MASTER WARMUP COMPLETE FOR {student_id}!")
        log(f"  - Total Roles Generated: {task_result['resumes_generated']}")
        log(f"{'='*60}")
        
        return True
        
    except Exception as e:
        log(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        log("Usage: python warmup_student.py <student_id>")
        sys.exit(1)
    
    student_id = sys.argv[1]
    log(f"Running warmup for: {student_id}")
    result = asyncio.run(warmup_student(student_id))
    log(f"Warmup {'SUCCESS' if result else 'FAILED'}")
    sys.exit(0 if result else 1)
