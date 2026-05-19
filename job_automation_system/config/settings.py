"""
Central Configuration - Job Automation System
==============================================
All settings loaded from environment variables with type safety.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv():
    """Load .env file (don't override existing system env vars)"""
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        if load_dotenv:
            load_dotenv(env_path, override=False)
        else:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


_load_dotenv()

IN_DOCKER = os.getenv("IN_DOCKER", "").lower() == "true" or Path("/app").exists()


def _docker_path(container_path: str, local_path: str) -> str:
    return container_path if IN_DOCKER else local_path


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


def _float(name: str, default: float = 0.0) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


def _str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    # Environment
    run_env: str = field(default_factory=lambda: _str("RUN_ENV", "production"))
    debug: bool = field(default_factory=lambda: _bool("DEBUG", False))

    # MongoDB
    mongo_uri: str = field(default_factory=lambda: _str("MONGO_URI", ""))
    mongo_db: str = field(default_factory=lambda: _str("MONGO_DB", "job_automation"))

    # Redis
    redis_host: str = field(default_factory=lambda: _str("REDIS_HOST", "localhost"))
    redis_port: int = field(default_factory=lambda: _int("REDIS_PORT", 6379))
    redis_db: int = field(default_factory=lambda: _int("REDIS_DB", 0))
    redis_password: str = field(default_factory=lambda: _str("REDIS_PASSWORD", ""))

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ==================== Path Configuration ====================
    chrome_profile_dir: str = field(default_factory=lambda: _str("CHROME_PROFILE_DIR", _docker_path("/app/chrome_profile", "d:/ai-bot-resumes/chrome_profile")))
    resumes_dir: str = field(default_factory=lambda: _str("RESUMES_DIR", _docker_path("/app/ai_engine/resumes", "d:/ai-bot-resumes/ai_engine/resumes")))
    temp_resumes_dir: str = field(default_factory=lambda: _str("TEMP_RESUMES_DIR", _docker_path("/app/temp_resumes", "d:/ai-bot-resumes/temp_resumes")))
    chroma_db_dir: str = field(default_factory=lambda: _str("CHROMA_PERSIST_DIR", _docker_path("/app/chroma_db", "d:/ai-bot-resumes/chroma_db")))
    sessions_dir: str = field(default_factory=lambda: _str("SESSIONS_DIR", _docker_path("/app/sessions", "d:/ai-bot-resumes/job_automation_system/sessions")))

    # ==================== API Configuration ====================
    groq_api_url: str = field(default_factory=lambda: _str("GROQ_API_URL", "https://api.groq.com/openai/v1"))
    openrouter_api_url: str = field(default_factory=lambda: _str("OPENROUTER_API_URL", "https://openrouter.ai/api/v1"))
    minimax_api_url: str = field(default_factory=lambda: _str("MINIMAX_API_URL", "https://api.minimax.chat/v1"))
    local_api_url: str = field(default_factory=lambda: _str("LOCAL_API_URL", "http://ai-engine:8000" if IN_DOCKER else "http://localhost:8000"))
    backend_env_path: str = field(default_factory=lambda: _str("BACKEND_ENV_PATH", _docker_path("/app/backend/.env", "d:/ai-bot-resumes/backend/.env")))

    # API Keys
    groq_api_key: str = field(default_factory=lambda: _str("GROQ_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: _str("GEMINI_API_KEY", ""))
    openrouter_api_key: str = field(default_factory=lambda: _str("OPENROUTER_API_KEY", ""))
    minimax_api_key: str = field(default_factory=lambda: _str("MINIMAX_API_KEY", ""))

    # Celery
    celery_broker_url: str = field(default_factory=lambda: _str("CELERY_BROKER_URL", ""))
    celery_result_backend: str = field(default_factory=lambda: _str("CELERY_RESULT_BACKEND", ""))
    celery_task_track_started: bool = field(default_factory=lambda: _bool("CELERY_TASK_TRACK_STARTED", True))
    celery_task_time_limit: int = field(default_factory=lambda: _int("CELERY_TASK_TIME_LIMIT", 1800))
    celery_task_soft_time_limit: int = field(default_factory=lambda: _int("CELERY_TASK_SOFT_TIME_LIMIT", 1500))

    # Worker Config
    worker_prefetch_multiplier: int = field(default_factory=lambda: _int("WORKER_PREFETCH_MULTIPLIER", 1))
    worker_max_tasks_per_child: int = field(default_factory=lambda: _int("WORKER_MAX_TASKS_PER_CHILD", 20))

    # Rate Limits (per minute)
    naukri_rate_limit: int = field(default_factory=lambda: _int("NAUKRI_RATE_LIMIT", 10))
    linkedin_rate_limit: int = field(default_factory=lambda: _int("LINKEDIN_RATE_LIMIT", 6))
    foundit_rate_limit: int = field(default_factory=lambda: _int("FOUNDIT_RATE_LIMIT", 10))

    # Browser Concurrency
    max_parallel_browsers: int = field(default_factory=lambda: _int("MAX_PARALLEL_BROWSERS", 6))
    browser_concurrency_naukri: int = field(default_factory=lambda: _int("BROWSER_CONCURRENCY_NAUKRI", 2))
    browser_concurrency_linkedin: int = field(default_factory=lambda: _int("BROWSER_CONCURRENCY_LINKEDIN", 1))
    browser_concurrency_foundit: int = field(default_factory=lambda: _int("BROWSER_CONCURRENCY_FOUNDIT", 1))

    # AI Engine Toggle
    ai_engine_enabled: bool = field(default_factory=lambda: _bool("AI_ENGINE_ENABLED", True))

    # Anti-Bot
    min_delay_seconds: float = field(default_factory=lambda: _float("MIN_DELAY_SECONDS", 1.5))
    max_delay_seconds: float = field(default_factory=lambda: _float("MAX_DELAY_SECONDS", 3.0))
    linkedin_min_delay: float = field(default_factory=lambda: _float("LINKEDIN_MIN_DELAY", 5))
    linkedin_max_delay: float = field(default_factory=lambda: _float("LINKEDIN_MAX_DELAY", 15))
    extra_delay_after_applies: int = field(default_factory=lambda: _int("EXTRA_DELAY_AFTER_APPLIES", 5))
    extra_delay_min: float = field(default_factory=lambda: _float("EXTRA_DELAY_MIN", 4.0))
    extra_delay_max: float = field(default_factory=lambda: _float("EXTRA_DELAY_MAX", 6.0))

    # Applies per run (how many jobs each browser session processes before closing)
    max_applies_per_run: int = field(default_factory=lambda: _int("MAX_APPLIES_PER_RUN", 10))

    # Retry
    max_retries: int = field(default_factory=lambda: _int("MAX_RETRIES", 3))
    retry_backoff_base: int = field(default_factory=lambda: _int("RETRY_BACKOFF_BASE", 1))
    retry_backoff_max: int = field(default_factory=lambda: _int("RETRY_BACKOFF_MAX", 600))

    # Idempotency & Lock
    idempotency_ttl: int = field(default_factory=lambda: _int("IDEMPOTENCY_TTL", 86400))
    lock_ttl: int = field(default_factory=lambda: _int("LOCK_TTL", 1800))

    # Circuit Breaker
    circuit_breaker_threshold: int = field(default_factory=lambda: _int("CIRCUIT_BREAKER_THRESHOLD", 5))

    # Resume Selection & Matching (Global)
    ats_threshold: float = field(default_factory=lambda: _float("ATS_THRESHOLD", 65.0))
    circuit_breaker_timeout: int = field(default_factory=lambda: _int("CIRCUIT_BREAKER_TIMEOUT", 300))

    # Cloudinary
    cloudinary_cloud_name: str = field(default_factory=lambda: _str("CLOUDINARY_CLOUD_NAME", ""))
    cloudinary_api_key: str = field(default_factory=lambda: _str("CLOUDINARY_API_KEY", ""))
    cloudinary_api_secret: str = field(default_factory=lambda: _str("CLOUDINARY_API_SECRET", ""))

    # Credentials Fallback (.env)
    linkedin_email: str = field(default_factory=lambda: _str("LINKEDIN_EMAIL", ""))
    linkedin_password: str = field(default_factory=lambda: _str("LINKEDIN_PASSWORD", ""))
    naukri_email: str = field(default_factory=lambda: _str("NAUKRI_EMAIL", ""))
    naukri_password: str = field(default_factory=lambda: _str("NAUKRI_PASSWORD", ""))
    foundit_email: str = field(default_factory=lambda: _str("FOUNDIT_EMAIL", ""))
    foundit_password: str = field(default_factory=lambda: _str("FOUNDIT_PASSWORD", ""))

    # Playwright
    playwright_headless: bool = field(default_factory=lambda: _bool("PLAYWRIGHT_HEADLESS", IN_DOCKER))
    playwright_timeout: int = field(default_factory=lambda: _int("PLAYWRIGHT_TIMEOUT", 30000))

    # Encryption
    encryption_key: str = field(default_factory=lambda: _str("ENCRYPTION_KEY", ""))

    # Cookie Settings
    linkedin_cookie_max_age_hours: int = field(default_factory=lambda: _int("LINKEDIN_COOKIE_MAX_AGE_HOURS", 24))

    # Logging
    log_level: str = field(default_factory=lambda: _str("LOG_LEVEL", "INFO"))
    log_format: str = field(default_factory=lambda: _str("LOG_FORMAT", "json"))

    def __post_init__(self):
        if not self.celery_broker_url:
            self.celery_broker_url = self.redis_url
        if not self.celery_result_backend:
            self.celery_result_backend = self.redis_url


settings = Settings()
