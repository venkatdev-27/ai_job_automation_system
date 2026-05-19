"""
Platform Configuration - Job Automation System
================================================
Queue definitions, rate limits, and platform-specific settings.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class PlatformConfig:
    name: str
    queue: str
    priority: int
    weight: int  # Higher weight = earlier platform round.
    rate_limit: str  # e.g., "10/m"
    concurrency: int
    min_delay: float
    max_delay: float
    cooldown_after_applies: int
    extra_delay_min: float
    extra_delay_max: float
    max_retries: int
    max_applies_per_run: int = 10
    session_time_limit: int = 2100
    micro_break_interval: int = 3
    micro_break_min: float = 20.0
    micro_break_max: float = 60.0
    stagger_delay: int = 0
    
    # Time-based weights for wave mode (50% FoundIt, 25% Naukri, 25% LinkedIn all times)
    weight_morning: float = 0.50
    weight_afternoon: float = 0.50
    weight_evening: float = 0.50
    weight_night: float = 0.50


PLATFORMS: dict[str, PlatformConfig] = {
    "naukri": PlatformConfig(
        name="naukri",
        queue="naukri",
        priority=1,
        weight=3,
        rate_limit="10/m",
        concurrency=3,
        min_delay=1.5,
        max_delay=3.0,
        cooldown_after_applies=5,
        extra_delay_min=4.0,
        extra_delay_max=6.0,
        max_retries=3,
        max_applies_per_run=2,
        session_time_limit=2100,
        micro_break_interval=3,
        micro_break_min=15.0,
        micro_break_max=40.0,
        stagger_delay=0,
    ),
    "foundit": PlatformConfig(
        name="foundit",
        queue="foundit",
        priority=3,
        weight=2,
        rate_limit="8/m",
        concurrency=2,
        min_delay=3.0,
        max_delay=8.0,
        cooldown_after_applies=8,
        extra_delay_min=20.0,
        extra_delay_max=40.0,
        max_retries=3,
        max_applies_per_run=7,
        session_time_limit=1800,
        micro_break_interval=3,
        micro_break_min=20.0,
        micro_break_max=50.0,
        stagger_delay=30,
    ),
    "linkedin": PlatformConfig(
        name="linkedin",
        queue="linkedin",
        priority=2,
        weight=1,
        rate_limit="6/m",
        concurrency=1,
        min_delay=8.0,
        max_delay=18.0,
        cooldown_after_applies=10,
        extra_delay_min=45.0,
        extra_delay_max=90.0,
        max_retries=3,
        max_applies_per_run=1,
        session_time_limit=1500,
        micro_break_interval=2,
        micro_break_min=45.0,
        micro_break_max=90.0,
        stagger_delay=60,
    ),
}


def get_platform_config(platform: str) -> Optional[PlatformConfig]:
    """Get platform configuration by name."""
    return PLATFORMS.get(platform.lower())


def get_platform_weight_for_time(platform: str, time_period: str) -> float:
    """
    Get platform weight for a specific time period.
    
    Args:
        platform: Platform name (naukri, linkedin, foundit)
        time_period: Time period (morning, afternoon, evening, night)
    
    Returns:
        Weight float value
    """
    config = get_platform_config(platform)
    if not config:
        return 0.25
    
    time_weight_map = {
        "morning": config.weight_morning,
        "afternoon": config.weight_afternoon,
        "evening": config.weight_evening,
        "night": config.weight_night,
    }
    
    return time_weight_map.get(time_period, 0.25)


CELERY_QUEUES = {
    "naukri": {
        "exchange": "naukri",
        "routing_key": "naukri",
    },
    "linkedin": {
        "exchange": "linkedin",
        "routing_key": "linkedin",
    },
    "foundit": {
        "exchange": "foundit",
        "routing_key": "foundit",
    },
    "warmup": {
        "exchange": "warmup",
        "routing_key": "warmup",
    },
    "producer": {
        "exchange": "producer",
        "routing_key": "producer",
    },
    "student_wave": {
        "exchange": "student_wave",
        "routing_key": "student_wave",
    },
    "failed_jobs": {
        "exchange": "failed_jobs",
        "routing_key": "failed_jobs",
    },
}


QUEUE_PRIORITY = {
    "naukri": 1,
    "linkedin": 2,
    "foundit": 3,
    "warmup": 4,
    "producer": 5,
    "student_wave": 6,
    "failed_jobs": 10,
}
