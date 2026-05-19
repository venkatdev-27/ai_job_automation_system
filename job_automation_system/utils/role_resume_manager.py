"""
Role Resume Manager
==================
Generates and manages role-specific resumes for students.
- Creates role resumes from master resume
- Uploads to Cloudinary
- Stores URLs in MongoDB
"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Any, Optional


# Cloudinary config (from environment)
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "dco7jegub")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")


# Role configurations
ROLE_CONFIGS = {
    "master": {"name": "master_resume", "title": "Master Resume"},
    "frontend": {"name": "role_frontend", "title": "Frontend Developer"},
    "backend": {"name": "role_backend", "title": "Backend Developer"},
    "fullstack": {"name": "role_fullstack", "title": "Full Stack Developer"},
    "java": {"name": "role_java", "title": "Java Developer"},
    "python": {"name": "role_python", "title": "Python Developer"},
    "data_engineer": {"name": "role_data_engineer", "title": "Data Engineer"},
}


def get_cloudinary_url(public_id: str, format: str = "docx") -> str:
    """Get Cloudinary URL from public_id"""
    return f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/raw/upload/{public_id}.{format}"


def upload_to_cloudinary(
    local_file_path: str,
    student_id: str,
    role: str = "master"
) -> tuple[str, str]:
    """
    Upload resume to Cloudinary.
    
    Args:
        local_file_path: Path to local resume file
        student_id: MongoDB _id of student
        role: Role type (master, frontend, etc.)
    
    Returns:
        (cloudinary_url, public_id)
    """
    if not os.path.exists(local_file_path):
        print(f"[ERROR] File not found: {local_file_path}")
        return "", ""
    
    role_config = ROLE_CONFIGS.get(role, ROLE_CONFIGS["master"])
    folder = f"resumes/{student_id}"
    public_id = f"{folder}/{role_config['name']}"
    file_format = local_file_path.split('.')[-1]
    
    try:
        # Upload using Cloudinary API
        import cloudinary
        from cloudinary import uploader
        
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET
        )
        
        result = uploader.upload(
            local_file_path,
            folder=folder,
            public_id=role_config['name'],
            resource_type="raw",
            use_filename=True,
            unique_filename=False,
            overwrite=True
        )
        
        secure_url = result.get("secure_url", "")
        returned_public_id = result.get("public_id", "")
        
        print(f"[SUCCESS] Uploaded {role} resume for {student_id}")
        print(f"  URL: {secure_url}")
        
        return secure_url, returned_public_id
        
    except ImportError:
        print("[WARNING] Cloudinary SDK not available, trying HTTP upload")
        
        # Fallback: Use unsigned HTTP upload
        url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/raw/upload"
        
        with open(local_file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'file': f,
                'public_id': public_id,
                'folder': folder,
                'resource_type': 'raw',
            }
            
            response = requests.post(url, files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            return result.get("secure_url", ""), result.get("public_id", "")
        
        print(f"[ERROR] HTTP upload failed: {response.status_code}")
        return "", ""
        
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        return "", ""


def generate_role_resumes_for_student(
    student_id: str,
    master_resume_path: str,
    role_list: list[str] = None
) -> dict[str, dict]:
    """
    Generate role-specific resumes for a student.
    
    In a real implementation, this would use a PDF generator
    to customize the resume for each role. For now, we'll
    use the master resume as-is for each role.
    
    Args:
        student_id: MongoDB _id
        master_resume_path: Path to master resume (local file)
        role_list: List of roles to generate
    
    Returns:
        Dict with role -> {url, public_id, success}
    """
    if role_list is None:
        role_list = list(ROLE_CONFIGS.keys())
    
    results = {}
    
    for role in role_list:
        # In production: Generate customized resume for role
        # For now: Use master resume directly
        
        if role == "master":
            # Master resume - use as-is
            role_path = master_resume_path
        else:
            # Role resume - use master for now
            # In future: PDF generator to customize
            role_path = master_resume_path
        
        if os.path.exists(role_path):
            url, public_id = upload_to_cloudinary(
                role_path,
                student_id,
                role
            )
            
            results[role] = {
                "url": url,
                "public_id": public_id,
                "success": bool(url)
            }
        else:
            results[role] = {
                "url": "",
                "public_id": "",
                "success": False,
                "error": f"File not found: {role_path}"
            }
    
    return results


def get_role_resume_url(
    student_id: str,
    role: str = "master"
) -> tuple[str, bool]:
    """
    Get Cloudinary URL for a student's role resume.
    
    Returns (url, exists)
    """
    # First check local cache
    in_docker = os.getenv("IN_DOCKER", "").lower() == "true" or Path("/app").exists()
    temp_dir = Path(os.getenv("TEMP_RESUMES_DIR", "/app/temp_resumes" if in_docker else "D:/ai-bot-resumes/temp_resumes"))
    
    for file_path in temp_dir.glob(f"{student_id}_{role}*.docx"):
        if file_path.exists():
            url = get_cloudinary_url(
                f"resumes/{student_id}/role_{role}",
                "docx"
            )
            return url, True
    
    # Need to get from Cloudinary or regenerate
    # In production: Get from MongoDB
    return "", False


def list_student_resumes(student_id: str) -> list[dict]:
    """List all resumes stored for a student"""
    # In production: Query from MongoDB
    # For now: Check local temp folder
    in_docker = os.getenv("IN_DOCKER", "").lower() == "true" or Path("/app").exists()
    temp_dir = Path(os.getenv("TEMP_RESUMES_DIR", "/app/temp_resumes" if in_docker else "D:/ai-bot-resumes/temp_resumes"))
    
    resumes = []
    for file_path in temp_dir.glob(f"{student_id}_*.docx"):
        if file_path.exists():
            role = file_path.name.replace(f"{student_id}_", "").split("_")[0]
            resumes.append({
                "role": role,
                "path": str(file_path),
                "size_kb": file_path.stat().st_size / 1024
            })
    
    return resumes


# Demo
def demo():
    print("=== Role Resume Manager Demo ===\n")
    
    # List roles
    print("Available Roles:")
    for role, config in ROLE_CONFIGS.items():
        print(f"  - {role}: {config['title']}")
    
    # Check for any cached resumes
    print("\nCached Resumes:")
    # This would normally query MongoDB
    print("  (Check temp_resumes folder)")


if __name__ == "__main__":
    demo()
