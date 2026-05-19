"""
Configuration Package - Job Automation System
==============================================
"""

from config.settings import settings, Settings
from config.platforms import PLATFORMS, get_platform_config, CELERY_QUEUES, QUEUE_PRIORITY

__all__ = [
    "settings",
    "Settings",
    "PLATFORMS",
    "get_platform_config",
    "CELERY_QUEUES",
    "QUEUE_PRIORITY",
]