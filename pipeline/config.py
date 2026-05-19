import os
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_DATA_DIR = BASE_DIR / "temp_pipeline"

def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

load_env_file(BASE_DIR / ".env")

PIPELINE_DATA_DIR = Path(
    os.getenv("PIPELINE_DATA_DIR", str(BASE_DIR / "temp_pipeline"))
).resolve()
PIPELINE_DATA_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR = PIPELINE_DATA_DIR

# --- Session Management ---
COOKIES_FILE = TEMP_DIR / "linkedin_state.json"

# --- Credentials ---
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "").strip()
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_API_BASE = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = "minimax/minimax-m2.5:free"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

# Cloudinary Setup
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "tailored_resumes").strip()

CLOUDINARY_RESUME_URL = os.getenv("CLOUDINARY_RESUME_URL", "").strip()

# --- Global Config ---
JOB_LIMIT = int(os.getenv("JOB_LIMIT", 2))
RUN_ENV = os.getenv("RUN_ENV", "local").strip().lower()
HEADLESS = os.getenv("HEADLESS", "false").strip().lower() in {"1", "true", "yes", "y", "on"}
if RUN_ENV == "local" and os.getenv("HEADLESS") is None:
    HEADLESS = False

LINKEDIN_LOCATION = os.getenv("LINKEDIN_LOCATION", "India").strip() or "India"
LINKEDIN_EXPERIENCE_FILTER = os.getenv("LINKEDIN_EXPERIENCE_FILTER", "1,2").strip() or "1,2"
LINKEDIN_TIME_FILTER = os.getenv("LINKEDIN_TIME_FILTER", "r604800").strip() or "r604800"
ATS_THRESHOLD = int(os.getenv("ATS_THRESHOLD", "70"))
PLAYWRIGHT_DEFAULT_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_DEFAULT_TIMEOUT_MS", 15000))
ARCHIVE_EXTRACTED_JD = os.getenv("ARCHIVE_EXTRACTED_JD", "false").strip().lower() in {"1", "true", "yes", "y", "on"}

RESULTS_LOG = Path(
    os.getenv("RESULTS_LOG_PATH", str(BASE_DIR / "venkat_pipeline_results.json"))
).resolve()
APPLIED_JOBS_LOG = Path(
    os.getenv("APPLIED_JOBS_LOG_PATH", str(PIPELINE_DATA_DIR / "applied_job_memory.json"))
).resolve()

# --- Stealth & Browser Context ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
VIEWPORT = {"width": 1366, "height": 768}
LOCALE = "en-US"
TIMEZONE_ID = "Asia/Kolkata"
# --- Production Safety Caps ---
MAX_APPLIES_PER_DAY = 32

# --- Colors for Logging ---
class C:
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
