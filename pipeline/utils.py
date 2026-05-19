import os
import time
import asyncio
import cloudinary
import cloudinary.utils
import cloudinary.uploader
from pathlib import Path
from .config import (
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, 
    CLOUDINARY_API_SECRET, CLOUDINARY_FOLDER, C
)

def log_info(msg): 
    # Sanitize for Windows Console compatibility
    safe_msg = str(msg).encode("ascii", "ignore").decode("ascii")
    print(f"{C.CYAN}[INFO] {safe_msg}{C.RESET}", flush=True)

def log_ok(msg):   
    safe_msg = str(msg).encode("ascii", "ignore").decode("ascii")
    print(f"{C.GREEN}[OK] {safe_msg}{C.RESET}", flush=True)

def log_warn(msg): 
    safe_msg = str(msg).encode("ascii", "ignore").decode("ascii")
    print(f"{C.YELLOW}[WARN] {safe_msg}{C.RESET}", flush=True)

def log_err(msg):  
    safe_msg = str(msg).encode("ascii", "ignore").decode("ascii")
    print(f"{C.RED}[ERR] {safe_msg}{C.RESET}", flush=True)

def _build_signed_download_url(public_id: str, file_path: Path, resource_type: str, delivery_type: str) -> str:
    """Build a signed Cloudinary download URL for restricted PDF delivery."""
    file_format = file_path.suffix.lstrip(".").lower() or "pdf"
    try:
        # Keep links valid for 30 days; regenerate on new applications.
        expires_at = int(time.time()) + (30 * 24 * 60 * 60)
        return cloudinary.utils.private_download_url(
            public_id,
            format=file_format,
            resource_type=resource_type or "raw",
            type=delivery_type or "upload",
            expires_at=expires_at,
            attachment=False,
        )
    except Exception as e:
        log_warn(f"Could not generate signed Cloudinary download URL: {e}")
        return ""

def upload_to_cloudinary(file_path: Path, folder: str = None) -> str:
    """Uploads a file to Cloudinary and returns the secure URL."""
    if not file_path.exists():
        log_err(f"File not found for upload: {file_path}")
        return ""

    folder = folder or CLOUDINARY_FOLDER
    log_info(f"Uploading {file_path.name} to Cloudinary folder: {folder}...")

    try:
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True
        )

        response = cloudinary.uploader.upload(
            str(file_path),
            folder=folder,
            resource_type="raw",
            type="upload",
            timeout=30
        )
        url = response.get("secure_url", "")
        public_id = response.get("public_id", "")
        resource_type = response.get("resource_type", "raw")
        delivery_type = response.get("type", "upload")

        # Some Cloudinary accounts block direct PDF delivery from res.cloudinary.com URLs.
        # Use signed download URLs for PDFs to avoid 401/ACL issues in dashboard links.
        if file_path.suffix.lower() == ".pdf" and public_id:
            signed_url = _build_signed_download_url(
                public_id=public_id,
                file_path=file_path,
                resource_type=resource_type,
                delivery_type=delivery_type,
            )
            if signed_url:
                url = signed_url

        if url:
            log_ok(f"Cloudinary Upload Success: {url}")
        return url
    except Exception as e:
        log_err(f"Cloudinary Upload Failed: {e}")
        return ""

async def retry(func, retries=3):
    """Generic async retry wrapper."""
    for i in range(retries):
        try:
            return await func()
        except Exception:
            if i < retries - 1:
                await asyncio.sleep(2)
    return None

