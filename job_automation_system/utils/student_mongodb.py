"""
Student MongoDB Lookup
====================
Gets student data from MongoDB including resume URL.
Used by Python scrapers to get Cloudinary URLs.
"""

import os
import sys
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field, replace

# Add project to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.job_utils import normalize_skills, top_keywords


@dataclass
class StudentProfile:
    student_id: str
    name: str
    email: str
    phone: str
    location: str
    skills: List[str] = field(default_factory=list)
    resume_url: str = ""
    candidate_titles: List[str] = field(default_factory=list)
    experience: List[Dict[str, Any]] = field(default_factory=list)
    projects: List[Dict[str, Any]] = field(default_factory=list)
    education: str = ""
    master_template: Dict[str, Any] = field(default_factory=dict)
    years_experience: str = "0-1"
    preferred_locations: List[str] = field(default_factory=list)
    domain_keywords: List[str] = field(default_factory=list)
    raw_resume_context: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "student_id": self.student_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "skills": self.skills,
            "resume_url": self.resume_url,
            "candidate_titles": self.candidate_titles,
            "experience": self.experience,
            "projects": self.projects,
            "education": self.education,
            "master_template": self.master_template,
            "years_experience": self.years_experience,
            "preferred_locations": self.preferred_locations,
            "domain_keywords": self.domain_keywords,
            "raw_resume_context": self.raw_resume_context,
            "extra": self.extra,
        }



def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        token = item.strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(token)
    return result


def _tokenize_phrase(value: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+.#-]{2,}", value.lower())
    return [token for token in tokens if token not in {"engineer", "developer", "software"}]




def build_dynamic_runtime_settings(settings: Any, profile: StudentProfile) -> Any:
    """Build runtime settings using profile data"""
    # Build include keywords from parsed resume skills + title tokens.
    title_tokens: list[str] = []
    for title in profile.candidate_titles:
        title_tokens.extend(_tokenize_phrase(title))

    resume_keywords = normalize_skills(top_keywords(profile.raw_resume_context, limit=18))
    include_keywords = _dedupe(
        normalize_skills(
            [
                *profile.skills,
                *title_tokens,
                *resume_keywords,
                *getattr(settings, 'include_keywords', []),
            ]
        )
    )
    if not include_keywords:
        include_keywords = ["python", "java", "backend", "software", "api"]

    candidate_titles = _dedupe(profile.candidate_titles or getattr(settings, 'candidate_previous_resume_job_titles', []))
    if not candidate_titles:
        candidate_titles = ["software developer", "backend developer"]

    # ALWAYS include major Indian tech hubs for fresher pipeline
    mandatory_tech_hubs = ["Bangalore", "Hyderabad", "Chennai", "Pune", "Delhi", "Mumbai", "Kolkata"]
    preferred_locations = _dedupe(
        [
            *profile.preferred_locations,
            profile.location,
            "remote",
            *mandatory_tech_hubs,
            *getattr(settings, 'preferred_locations', []),
        ]
    )
    preferred_locations = [loc for loc in preferred_locations if loc and loc.lower() != "india"]
    if not preferred_locations:
        preferred_locations = ["remote"]

    years_text = str(profile.years_experience).lower()
    fresher_like = any(token in years_text for token in {"0", "fresher", "entry"})
    preferred_job_types = _dedupe(
        [
            *getattr(settings, 'preferred_job_types', []),
            "full-time",
            "internship" if fresher_like else "",
        ]
    )
    preferred_job_types = [job_type for job_type in preferred_job_types if job_type]

    domain_keywords = _dedupe(
        normalize_skills(
            [
                *profile.domain_keywords,
                *include_keywords[:10],
                *title_tokens,
                *getattr(settings, 'candidate_domain_keywords', []),
            ]
        )
    )
    if not domain_keywords:
        domain_keywords = include_keywords[:8]

    # Dynamic exclusion list tuned by domain
    non_software_terms = ["sales", "bpo", "voice process", "telecaller", "field sales", "collection", "banking sales"]
    exclude_keywords = _dedupe([*getattr(settings, 'exclude_keywords', []), *non_software_terms])
    if any(token in domain_keywords for token in {"data", "ai", "ml", "scientist"}):
        exclude_keywords = _dedupe([keyword for keyword in exclude_keywords if keyword != "analyst"])

    return replace(
        settings,
        include_keywords=include_keywords,
        exclude_keywords=exclude_keywords,
        preferred_locations=preferred_locations,
        preferred_job_types=preferred_job_types,
        candidate_previous_resume_job_titles=candidate_titles,
        candidate_domain_keywords=domain_keywords,
    )




_mongo_client = None

def get_mongo_connection():
    """Get MongoDB connection (cached)"""
    global _mongo_client
    if _mongo_client:
        return _mongo_client

    from pymongo import MongoClient
    from dotenv import load_dotenv
    
    # Load .env from project root
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    
    mongo_uri = os.getenv("MONGO_URI", "")
    if not mongo_uri:
        print("[WARNING] MONGO_URI not set")
        return None
    
    try:
        _mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # Test connection
        _mongo_client.admin.command('ping')
        return _mongo_client
    except Exception as e:
        print(f"[ERROR] MongoDB connection failed: {e}")
        _mongo_client = None
        return None


def get_student_by_id(student_id: str) -> Optional[dict]:
    """
    Get student data by ID from MongoDB.
    
    Args:
        student_id: MongoDB _id string
    
    Returns:
        dict with student data or None
    """
    client = get_mongo_connection()
    if not client:
        return None
    
    try:
        db = client["ai_bot_resumes"]
        collection = db["students"]
        
        student = collection.find_one({"student_id": student_id})
        
        if student:
            # Remove MongoDB _id for serialization
            student.pop("_id", None)
            return student
        
        return None
        
    except Exception as e:
        print(f"[ERROR] Failed to get student: {e}")
        return None


def get_student_resume_url(student_id: str, role: str = "master") -> str:
    """
    Get Cloudinary resume URL for a student.
    
    Args:
        student_id: MongoDB _id or student_id
        role: Role type (master, frontend, backend, etc.)
    
    Returns:
        Cloudinary URL or empty string
    """
    student = get_student_by_id(student_id)
    
    if not student:
        print(f"[WARNING] Student not found: {student_id}")
        return ""
    
    # Try role_resumes first
    role_resumes = student.get("role_resumes", {})
    if role in role_resumes:
        return role_resumes[role]
    
    # Fallback to main resume
    resume_url = student.get("resume", "")
    if resume_url:
        return resume_url
    
    return ""


def get_student_profile(student_id: str) -> Optional[StudentProfile]:
    """Get a complete StudentProfile object from MongoDB"""
    data = get_student_by_id(student_id)
    if not data:
        return None

    # Skills fallback across schema variants.
    skills = data.get("skills", []) or []
    if not skills:
        resume_data = data.get("resumeData", {}) or {}
        if isinstance(resume_data, dict):
            fallback_chunks: list[str] = []
            for key in ("skills", "technical_skills", "tools", "frameworks", "languages"):
                values = resume_data.get(key, [])
                if isinstance(values, list):
                    fallback_chunks.extend([str(v).strip() for v in values if str(v).strip()])
            if fallback_chunks:
                # stable de-dup
                skills = list(dict.fromkeys(fallback_chunks))
    
    # Extract candidate titles from custom_roles if missing
    candidate_titles = data.get('candidate_titles', [])
    if not candidate_titles:
        custom_roles = data.get('custom_roles', {})
        for role_key, role_cfg in custom_roles.items():
            if isinstance(role_cfg, dict) and role_cfg.get('title'):
                candidate_titles.append(role_cfg['title'])
            elif isinstance(role_cfg, str):
                candidate_titles.append(role_cfg)
    
    # Build raw_resume_context if missing but resumeData exists
    raw_resume_context = data.get('raw_resume_context', '')
    if not raw_resume_context:
        resume_data = data.get('resumeData', {})
        if resume_data:
            context_parts = []
            if resume_data.get('education'):
                edu_text = ", ".join([f"{e.get('degree', '')} from {e.get('institution', '')} ({e.get('year', '')})" for e in resume_data['education'] if e])
                context_parts.append(f"Education: {edu_text}")
            if resume_data.get('experience'):
                exp_text = "; ".join([f"{e.get('role', '')} at {e.get('company', '')} ({e.get('duration', '')}): {e.get('summary', '')}" for e in resume_data['experience'] if e])
                context_parts.append(f"Experience: {exp_text}")
            if resume_data.get('skills'):
                context_parts.append(f"Skills: {', '.join(resume_data['skills'])}")
            raw_resume_context = "\n".join(context_parts)

    return StudentProfile(
        student_id=data.get('student_id', student_id),
        name=data.get('full_name') or data.get('name', 'Candidate'),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        location=data.get('location', 'India'),
        skills=skills,
        resume_url=data.get('resume', ''),
        candidate_titles=candidate_titles,
        experience=data.get('experience', []),
        projects=data.get('projects', []),
        education=data.get('education', ''),
        master_template=data.get('master_template', {}),
        years_experience=data.get('years_experience', '0-1'),
        preferred_locations=data.get('preferred_locations', []),
        domain_keywords=data.get('domain_keywords', []),
        raw_resume_context=raw_resume_context,
        extra=data.get('links', {})
    )


def get_student_skills(student_id: str) -> list:
    """Get skills for a student"""
    student = get_student_by_id(student_id)
    
    if student:
        return student.get("skills", [])
    
    return []


def list_all_students() -> list:
    """List all students in database"""
    client = get_mongo_connection()
    if not client:
        return []
    
    try:
        db = client["ai_bot_resumes"]
        collection = db["students"]
        
        students = list(collection.find({}, {
            "_id": 0,
            "student_id": 1,
            "name": 1,
            "email": 1,
            "skills": 1,
            "resume": 1,
            "created_at": 1
        }))
        
        return students
        
    except Exception as e:
        print(f"[ERROR] Failed to list students: {e}")
        return []


def update_student_profile(student_id: str, profile_data: dict) -> bool:
    """
    Update student profile with extracted data.
    
    Args:
        student_id: Student ID to update
        profile_data: Dict containing skills, experience, projects, etc.
    """
    client = get_mongo_connection()
    if not client:
        return False
    
    try:
        db = client["ai_bot_resumes"]
        collection = db["students"]
        
        # Prepare update document
        update_fields = {
            "full_name": profile_data.get("full_name"),
            "email": profile_data.get("email"),
            "phone": profile_data.get("phone"),
            "location": profile_data.get("location"),
            "links": {
                "linkedin": profile_data.get("linkedin"),
                "github": profile_data.get("github"),
                "portfolio": profile_data.get("portfolio")
            },
            "primary_role": profile_data.get("primary_role"),
            "skills": profile_data.get("skills", []),
            "categorized_skills": profile_data.get("categorized_skills", {}),
            "education": profile_data.get("education", []),
            "experience": profile_data.get("experience", []),
            "projects": profile_data.get("projects", []),
            "master_template": profile_data.get("master_template", {}),
            "full_text": profile_data.get("full_text", ""),
            "last_extracted": datetime.now().isoformat()
        }
        
        # Remove None values
        update_fields = {k: v for k, v in update_fields.items() if v is not None}
        
        result = collection.update_one(
            {"student_id": student_id},
            {"$set": update_fields},
            upsert=False
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        print(f"[ERROR] Failed to update student profile: {e}")
        return False


# Demo
def demo():
    print("=== Student MongoDB Lookup Demo ===\n")
    
    # List all students
    students = list_all_students()
    print(f"Total students: {len(students)}")
    
    for s in students[:10]:
        print(f"  - {s.get('name')} (ID: {s.get('student_id')}): {s.get('email')}")
        print(f"    Skills: {len(s.get('skills', []))}")
        print(f"    Resume: {'Yes' if s.get('resume') else 'No'}")


if __name__ == "__main__":
    demo()
