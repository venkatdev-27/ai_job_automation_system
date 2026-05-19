"""
Resume Downloader
================
Downloads resumes from Cloudinary URL to local file.
Stores in temp_resumes folder for reuse.
"""

import os
import requests
from pathlib import Path
from datetime import datetime

from config import settings

IN_DOCKER = os.getenv("IN_DOCKER", "").lower() == "true" or Path("/app").exists()

# Configure paths
TEMP_RESUMES_DIR = Path(settings.temp_resumes_dir)
TEMP_RESUMES_DIR.mkdir(parents=True, exist_ok=True)

_initialized = False

def _ensure_initialized():
    """Lazy initialize Cloudinary and environment vars"""
    global _initialized
    if _initialized:
        return
    
    from dotenv import load_dotenv
    # Load .env from project root
    PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", "/app" if IN_DOCKER else "D:/ai-bot-resumes"))
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    
    import cloudinary
    from cloudinary import config as cloud_config
    
    cloud_config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True
    )
    _initialized = True


def get_resume_filename(student_id: str, role: str = "master", url: str = None) -> str:
    """Generate local filename for resume without timestamp to allow caching"""
    ext = ".pdf"
    if url:
        # Extract extension from URL, handling query params
        path_part = url.split('?')[0]
        ext = os.path.splitext(path_part)[1]
        if not ext or len(ext) > 5: # Fallback if no valid ext found
            ext = ".pdf"
            
    return f"{student_id}_{role}{ext}"


def find_cached_resume(student_id: str, role: str = "master") -> str:
    """Find any existing cached resume for student_id and role."""
    prefix = f"{student_id}_{role}"
    if not TEMP_RESUMES_DIR.exists():
        return ""
    
    # Look for files starting with the prefix
    for f in TEMP_RESUMES_DIR.glob(f"{prefix}*"):
        if f.is_file():
            return str(f)
    return ""


def get_signed_download_url(cloudinary_url: str) -> str:
    """Generate signed URL for downloading from Cloudinary"""
    _ensure_initialized()
    try:
        # If URL already has signature, use it
        if 'sig=' in cloudinary_url or 's--' in cloudinary_url:
            return cloudinary_url
        
        # Parse URL to get public_id
        # Format: https://res.cloudinary.com/cloud_name/raw/upload/v(version)/folder/public_id.format
        parts = cloudinary_url.replace('https://res.cloudinary.com/', '').split('/')
        
        if len(parts) >= 4:
            resource_type = parts[0]  # 'raw' or 'image'
            if parts[1] == 'upload' and len(parts) >= 4:
                version = parts[2]  # v1776289922
                folder_pub = parts[3] if len(parts) > 3 else ''
                
                # Split folder and public_id
                if '/' in folder_pub:
                    folder, pub_with_ext = folder_pub.split('/', 1)
                    public_id = pub_with_ext.rsplit('.', 1)[0]
                else:
                    folder = 'resumes'
                    public_id = folder_pub.rsplit('.', 1)[0]
                
                # Generate signed URL
                from cloudinary.utils import cloudinary_url as gen_url
                signed, _ = gen_url(
                    f"{folder}/{public_id}",
                    sign_url=True,
                    resource_type='raw'
                )
                return signed
        
        return cloudinary_url
        
    except Exception as e:
        print(f"[WARN] Signed URL failed: {e}")
        return cloudinary_url


def download_resume_from_url(
    cloudinary_url: str,
    student_id: str,
    role: str = "master"
) -> tuple[str, bool]:
    """Download resume from Cloudinary URL to local file."""
    if not cloudinary_url:
        print(f"[ERROR] No Cloudinary URL provided for {student_id}")
        return "", False
    
    local_filename = get_resume_filename(student_id, role, cloudinary_url)
    cached = find_cached_resume(student_id, role)
    if cached:
        print(f"[CACHED] Resume already exists: {cached}")
        return cached, True
    
    # Use fixed filename (no timestamp)
    local_path = TEMP_RESUMES_DIR / local_filename
    
    try:
        # Generate signed URL
        download_url = get_signed_download_url(cloudinary_url)
        
        print(f"[DOWNLOADING] Resume for {student_id}")
        
        # Download with signed URL
        response = requests.get(
            download_url,
            timeout=120,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        
        if response.status_code != 200:
            # Try original URL
            print(f"[ERROR] Signed URL failed ({response.status_code}), trying original...")
            response = requests.get(
                cloudinary_url,
                timeout=120,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            
            if response.status_code != 200:
                print(f"[ERROR] Download failed: {response.status_code}")
                return "", False
        
        # Save file
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, 'wb') as f:
            f.write(response.content)
        
        size_kb = local_path.stat().st_size / 1024
        print(f"[SUCCESS] Downloaded: {local_path} ({size_kb:.1f} KB)")
        
        return str(local_path), True
        
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        return "", False


def download_if_needed(cloudinary_url: str, student_id: str, role: str = "master", force: bool = False) -> str:
    """Download resume if not cached."""
    if not force:
        cached_filename = get_resume_filename(student_id, role, cloudinary_url)
        cached_path = TEMP_RESUMES_DIR / cached_filename
        if cached_path.exists():
            return str(cached_path)
    
    path, success = download_resume_from_url(cloudinary_url, student_id, role)
    return path if success else ""


def get_cached_resume_path(student_id: str, role: str = "master", url: str = None) -> str:
    """Get cached resume path if exists."""
    local_filename = get_resume_filename(student_id, role, url)
    cached_path = TEMP_RESUMES_DIR / local_filename
    return str(cached_path) if cached_path.exists() else ""


if __name__ == "__main__":
    print("=== Resume Downloader ===")
    url = "https://res.cloudinary.com/dco7jegub/raw/upload/v1776289922/ai_bot_resumes/resume_venkat_1776289913907.pdf"
    path, success = download_resume_from_url(url, "student_65a834b8", "master")
    print(f"Result: {success} - {path}")
