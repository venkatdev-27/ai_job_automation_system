import logging
import os
import sys
from pathlib import Path
from typing import Optional

# V2-style colors
class C:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'


class TaskLogger:
    """Wrapper for task-specific logging."""
    def __init__(self, logger: logging.Logger, task_id: str):
        self.logger = logger
        self.task_id = task_id

    def info(self, msg: str):
        self.logger.info(f"[{self.task_id}] {msg}")

    def warning(self, msg: str):
        self.logger.warning(f"[{self.task_id}] {msg}")

    def error(self, msg: str):
        self.logger.error(f"[{self.task_id}] {msg}")

    def ok(self, msg: str):
        self.logger.log(25, f"[{self.task_id}] {msg}")


def setup_logging(log_dir: Optional[Path] = None, level: int = logging.INFO):
    """Setup logging for the application."""
    if log_dir is None:
        log_dir = Path("/app/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)


def get_logger(log_file: Path | str) -> logging.Logger:
    logger = logging.getLogger("job_automation_system")
    if logger.handlers:
        return logger

    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Standard file formatter (no colors)
    file_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    # Custom console formatter with colors (mirrors v2 style)
    class V2ColorFormatter(logging.Formatter):
        def format(self, record):
            msg = record.getMessage()
            # ANSI encoding cleanup (mirrors v2 safe_msg)
            safe_msg = str(msg).encode("ascii", "ignore").decode("ascii")

            if record.levelno == logging.INFO:
                return f"{C.CYAN}[INFO] {safe_msg}{C.RESET}"
            elif record.levelno == logging.WARNING:
                return f"{C.YELLOW}[WARN] {safe_msg}{C.RESET}"
            elif record.levelno == logging.ERROR:
                return f"{C.RED}[ERR] {safe_msg}{C.RESET}"
            elif record.levelno >= 25: # Custom OK level or success
                return f"{C.GREEN}[OK] {safe_msg}{C.RESET}"
            return safe_msg

    # Only add stream handler if NOT in celery (to avoid recursion when celery redirects stdout)
    if not os.environ.get("CELERY_LOADER"):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(V2ColorFormatter())
        logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Helper methods injection (to mimic v2 standalone functions)
    def log_info(msg, *args): logger.info(msg, *args)
    def log_ok(msg, *args): logger.log(25, msg, *args)
    def log_warn(msg, *args): logger.warning(msg, *args)
    def log_err(msg, *args): logger.error(msg, *args)

    logger.log_info = log_info
    logger.log_ok = log_ok
    logger.log_warn = log_warn
    logger.log_err = log_err

    # v3.5 DASHBOARD SYNC: Report successful application to API
    async def log_application_success(job_id, title, company, platform, student_id=None):
        try:
            import aiohttp
            # Use environment variable as fallback for student_id
            final_student_id = student_id or os.getenv("STUDENT_ID")
            
            async with aiohttp.ClientSession() as session:
                normalized_platform = {
                    "linkedin": "LinkedIn",
                    "naukri": "Naukri",
                    "foundit": "Foundit",
                }.get(str(platform).strip().lower(), str(platform))
                payload = {
                    "job_id": str(job_id),
                    "studentId": final_student_id,
                    "student_id": final_student_id,
                    "title": str(title),
                    "role": str(title),
                    "jobTitle": str(title),
                    "company": str(company),
                    "platform": normalized_platform,
                    "status": "applied",
                    "timestamp": "__auto__",
                }
                api_base = os.getenv(
                    "API_URL",
                    "http://node-api:5000" if os.getenv("IN_DOCKER", "").lower() == "true" else "http://localhost:5000",
                ).rstrip("/")
                primary = f"{api_base}/api/notify-application"
                async with session.post(primary, json=payload, timeout=4.0) as response:
                    response.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to report application to dashboard: {e}")

    logger.log_application_success = log_application_success

    return logger
