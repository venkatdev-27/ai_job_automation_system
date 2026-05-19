"""
Celery Configuration - Job Automation System
============================================
Broker, backend, task routing, and worker settings.
"""

from kombu import Queue, Exchange
from celery import Celery
from celery.schedules import crontab
from config.settings import settings
from config.platforms import CELERY_QUEUES


def create_celery_config() -> dict:
    """Create Celery configuration from settings."""
    # Build queue list
    queues = []
    for queue_name, config in CELERY_QUEUES.items():
        exchange = Exchange(config["exchange"], type="direct")
        queue = Queue(
            config["exchange"],
            exchange=exchange,
            routing_key=config["routing_key"],
        )
        queues.append(queue)
    
    return {
        # Broker & Backend
        "broker_url": settings.celery_broker_url,
        "result_backend": settings.celery_result_backend,
        "broker_pool_limit": None,  # Disable connection pooling to prevent 10054 dropped connection errors after idle
        "broker_transport_options": {
            "health_check_interval": 10,
            "socket_keepalive": True,
            "retry_on_timeout": True
        },
        "redis_backend_health_check_interval": 10,
        
        # Task Tracking
        "task_track_started": settings.celery_task_track_started,
        "task_time_limit": settings.celery_task_time_limit,
        "task_soft_time_limit": settings.celery_task_soft_time_limit,
        
        # Worker Settings
        "worker_prefetch_multiplier": settings.worker_prefetch_multiplier,
        "worker_max_tasks_per_child": settings.worker_max_tasks_per_child,
        "worker_disable_rate_limits": False,
        
        # Task Execution
        "task_acks_late": True,
        "task_reject_on_worker_lost": True,
        "task_default_retry_delay": 60,
        "task_default_max_retries": settings.max_retries,
        
        # Timezone
        "timezone": "Asia/Kolkata",
        "enable_utc": True,
        
        # Serialization
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        
        # Queues
        "task_queues": queues,
        "task_routes": _task_routes(),
        
        # Auto-discover tasks
        "task_ignore_result": False,
        
        # Result Expires
        "result_expires": 86400,  # 24 hours
        
        # Beat Schedule (for periodic tasks)
        "beat_schedule": _beat_schedule(),
    }


def _task_routes() -> dict:
    """Define task routing rules."""
    return {
        "tasks.naukri_task.*": {"queue": "naukri", "routing_key": "naukri"},
        "tasks.linkedin_task.*": {"queue": "linkedin", "routing_key": "linkedin"},
        "tasks.foundit_task.*": {"queue": "foundit", "routing_key": "foundit"},
        "tasks.warmup_task.*": {"queue": "warmup", "routing_key": "warmup"},
        "tasks.generate_initial_resumes_task.*": {"queue": "warmup", "routing_key": "warmup"},
        "tasks.producer_beat_task.*": {"queue": "producer", "routing_key": "producer"},
        "tasks.producer_platform_task.*": {"queue": "producer", "routing_key": "producer"},
        "tasks.student_wave_task.*": {"queue": "student_wave", "routing_key": "student_wave"},
        "tasks.dlq_handler.*": {"queue": "failed_jobs", "routing_key": "failed_jobs"},
    }


def _get_beat_schedule_from_env() -> dict:
    """Get beat schedule from environment variables with sensible defaults."""
    import os
    
    # Get schedule times from env or use defaults
    schedule_times = os.getenv("BEAT_SCHEDULE_TIMES", "06:00,11:00,17:00").split(",")
    
    schedule = {}
    
    # Map times to platforms with Wave Mode
    time_platform_map = [
        ("06:00", "naukri", "Morning - Naukri priority"),
        ("11:00", "foundit", "Afternoon - FoundIt priority"),
        ("17:00", "linkedin", "Evening - LinkedIn priority"),
    ]
    
    for idx, (time, platform, desc) in enumerate(time_platform_map):
        if idx < len(schedule_times):
            time_parts = schedule_times[idx].strip().split(":")
            if len(time_parts) == 2:
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                
                schedule[f"run-{platform}-{time}"] = {
                    "task": f"tasks.producer_beat_task.run_{platform}_beat",
                    "schedule": crontab(hour=hour, minute=minute),
                    "options": {"queue": "producer", "routing_key": "producer"},
                    "args": (),
                }
    
    # Add combined Wave Mode run at 20:00 (8 PM) - all platforms with time-based weights
    schedule["run-all-wave-evening"] = {
        "task": "tasks.producer_beat_task.run_all_wave_beat",
        "schedule": crontab(hour=20, minute=0),  # 8 PM
        "options": {"queue": "producer", "routing_key": "producer"},
        "args": (),
    }

    schedule["run-recovery-1030pm"] = {
        "task": "tasks.producer_beat_task.run_recovery_beat",
        "schedule": crontab(hour=22, minute=30),
        "options": {"queue": "producer", "routing_key": "producer"},
        "args": (),
    }
    
    return schedule


def _beat_schedule() -> dict:
    """
    11/10 Production Beat Schedule with Wave Mode (Asia/Kolkata timezone).
    
    Schedule:
    - 06:00 AM: Naukri (5 jobs - Mini-Wave)
    - 11:00 AM: FoundIt (5 jobs - Mini-Wave)
    - 05:00 PM: LinkedIn (5 jobs - Mini-Wave)
    - 08:00 PM: All Platforms with Wave Mode (time-based weights)
    
    Features:
    - Uses Wave Mode (5 jobs per batch)
    - Time-based platform weights
    - 5+ hour gaps between runs (anti-detection)
    - Full Wave Mode integration
    """
    return _get_beat_schedule_from_env()


# Global Celery config instance
celery_config = create_celery_config()
