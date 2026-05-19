import os
import re
import requests
from .config import C

def log_info(msg): print(f"{C.CYAN}[INFO] {msg}{C.RESET}")
def log_ok(msg):   print(f"{C.GREEN}[OK] {msg}{C.RESET}")
def log_err(msg):  print(f"{C.RED}[ERR] {msg}{C.RESET}")
def log_warn(msg): print(f"{C.YELLOW}[WARN] {msg}{C.RESET}")

BACKEND_URL = os.getenv("DASHBOARD_BACKEND_URL", "http://localhost:5000/api/applications").strip()
STUDENTS_URL = os.getenv("DASHBOARD_STUDENTS_URL", "http://localhost:5000/api/students").strip()
LEGACY_DEFAULT_STUDENT_ID = "65f1a2b3c4d5e6f7a8b9c0d1"

def _is_valid_object_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-fA-F0-9]{24}", str(value or "").strip()))

def _extract_students(payload) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
    return []

def _resolve_student_id(explicit_student_id: str = "", candidate_email: str = "") -> str:
    explicit = str(explicit_student_id or "").strip()
    if _is_valid_object_id(explicit):
        return explicit

    env_student_id = os.getenv("DASHBOARD_STUDENT_ID", "").strip()
    if _is_valid_object_id(env_student_id):
        return env_student_id

    email = str(candidate_email or "").strip().lower()
    if email:
        try:
            response = requests.get(STUDENTS_URL, timeout=10)
            if response.status_code == 200:
                students = _extract_students(response.json())
                for student in students:
                    student_email = str((student or {}).get("email", "")).strip().lower()
                    student_id = str((student or {}).get("_id", "")).strip()
                    if student_email == email and _is_valid_object_id(student_id):
                        log_info(f"Resolved studentId from email match: {student_email}")
                        return student_id
        except Exception as e:
            log_warn(f"Could not resolve studentId by email: {e}")

    if _is_valid_object_id(LEGACY_DEFAULT_STUDENT_ID):
        log_warn("Falling back to legacy static studentId. Configure DASHBOARD_STUDENT_ID for accurate mapping.")
        return LEGACY_DEFAULT_STUDENT_ID
    return ""

def sync_result_to_backend(
    pipeline_results,
    student_id: str = "",
    candidate_email: str = "",
    candidate_name: str = "",
):
    """
    Sends the pipeline results to the Node.js backend to update the Dashboard.
    Resolves studentId from explicit value, env, or student email.
    """
    log_info("Syncing results to the Dashboard backend...")
    
    try:
        resolved_student_id = _resolve_student_id(student_id, candidate_email)
        if not _is_valid_object_id(resolved_student_id):
            log_err("Dashboard Sync Failed: could not resolve a valid studentId.")
            return False

        job = pipeline_results.get("job", {}) if isinstance(pipeline_results.get("job"), dict) else {}
        job_title = (
            pipeline_results.get("job_title")
            or pipeline_results.get("jobTitle")
            or job.get("job_title")
            or job.get("jobTitle")
            or "Unknown"
        )
        company = (
            pipeline_results.get("job_company")
            or pipeline_results.get("company")
            or job.get("job_company")
            or job.get("company")
            or "Unknown"
        )
        job_description = (
            pipeline_results.get("job_description")
            or pipeline_results.get("jobDescription")
            or job.get("job_description")
            or job.get("jobDescription")
            or ""
        )
        resolved_candidate_name = (
            str(candidate_name or "").strip()
            or str(pipeline_results.get("candidate_name") or "").strip()
            or str(pipeline_results.get("fullName") or "").strip()
            or "Unknown"
        )
        resolved_candidate_email = (
            str(candidate_email or "").strip()
            or str(pipeline_results.get("candidate_email") or "").strip()
        )
        resume_url = (
            pipeline_results.get("tailored_resume_url")
            or pipeline_results.get("resume_url")
            or pipeline_results.get("resumeUrl")
            or os.getenv("CLOUDINARY_RESUME_URL", "")
        )
        if not resume_url:
            log_warn("Dashboard Sync: No resumeUrl found. Using placeholder to satisfy schema.")
            resume_url = "https://placeholder.com/failed_apply_resume.pdf"

        # Map pipeline results to the Application model schema
        payload = {
            "studentId": resolved_student_id,
            "jobTitle": job_title,
            "company": company,
            "candidateName": resolved_candidate_name,
            "candidateEmail": resolved_candidate_email,
            "platform": "LinkedIn",
            "status": "Applied" if pipeline_results.get("applied") else "Rejected",
            "resumeUrl": resume_url,
            "jobDescription": job_description,
            "atsScore": pipeline_results.get("ats_score", 0)
        }
        
        response = requests.post(BACKEND_URL, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            log_ok("Dashboard Sync Successful!")
            return True
        else:
            log_err(f"Dashboard Sync Failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        log_err(f"Dashboard Sync Exception: {e}")
        return False
