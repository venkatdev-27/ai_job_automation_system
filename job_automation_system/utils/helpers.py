import asyncio
import functools
import logging
import json
import os
import requests
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import cloudinary
import cloudinary.uploader

logger = logging.getLogger("Helpers")

def async_safe_call(retries: int = 3, delay: float = 1.0, fallback: Any = None):
    """
    Decorator for async functions to handle failures and retries.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    wait_time = delay * (2 ** attempt)
                    logger.warning(f"Error in {func.__name__}: {e}. Retrying in {wait_time}s... (Attempt {attempt+1}/{retries})")
                    if attempt < retries - 1:
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Max retries reached for {func.__name__}. Falling back to default.")
            return fallback
        return wrapper
    return decorator


def upload_to_cloudinary(file_path: Path, folder: str = "tailored_resumes") -> str:
    """
    Uploads a file to Cloudinary and returns the secure URL.
    Uses environment variables for configuration.
    """
    if not file_path or not os.path.exists(str(file_path)):
        logger.error(f"File not found: {file_path}")
        return ""

    try:
        # Explicitly configure Cloudinary from environment
        cloudinary.config(
            cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
            api_key=os.environ.get("CLOUDINARY_API_KEY"),
            api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
            secure=True
        )

        response = cloudinary.uploader.upload(
            str(file_path),
            folder=folder,
            resource_type="raw"
        )
        url = response.get("secure_url", "")
        if url:
            logger.info(f"Successfully uploaded {file_path.name} to Cloudinary: {url}")
        return url
    except Exception as e:
        logger.error(f"Cloudinary upload failed: {e}")
        return ""


def download_file(url: str, target_path: Path | str) -> Path:
    """
    Downloads a file from a URL to a local path.
    Useful for production environments using Cloudinary.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=30) as response:
        response.raise_for_status()
        with target_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
    return target_path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_json_file(path: Path, default: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        write_json(path, default)


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    """Atomic write to prevent corruption."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        import os
        os.replace(temp_path, path)
    except Exception as e:
        logger.error(f"Atomic write failed for {path}: {e}")
        if temp_path.exists(): temp_path.unlink()


def latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    candidates = [path for path in directory.glob(pattern) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def latest_file_from_patterns(directory: Path, patterns: list[str]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        match = latest_file(directory, pattern)
        if match:
            candidates.append(match)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return default
