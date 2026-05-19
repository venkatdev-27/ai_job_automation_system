"""
Wave Configuration - Job Automation System
==========================================
Mini-Wave anti-detection strategy and time-based platform distribution.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class WaveConfig:
    enabled: bool = True
    jobs_per_wave: int = 5
    students_per_wave: int = 5
    pause_min_seconds: int = 30
    pause_max_seconds: int = 90
    student_spacing_min: int = 30
    student_spacing_max: int = 60
    jitter_max: int = 30
    time_based_weights: bool = True
    human_activity_enabled: bool = True
    day_distribution_enabled: bool = True


TIME_PERIOD_WEIGHTS = {
    # 6AM run: FoundIt=7, Naukri=1, LinkedIn=1 (Total = 9) => 77.8% FoundIt, 11.1% Naukri/LinkedIn
    "morning": {
        "foundit": 0.778,
        "naukri": 0.111,
        "linkedin": 0.111,
    },
    # 11AM run: FoundIt=4, Naukri=1, LinkedIn=1 (Total = 6) => 66.7% FoundIt, 16.7% Naukri/LinkedIn
    "afternoon": {
        "foundit": 0.667,
        "naukri": 0.167,
        "linkedin": 0.167,
    },
    # 5PM run: FoundIt=2, Naukri=3, LinkedIn=3 (Total = 8) => 25% FoundIt, 37.5% Naukri/LinkedIn
    "evening": {
        "foundit": 0.25,
        "naukri": 0.375,
        "linkedin": 0.375,
    },
    # 8PM run: FoundIt=1, Naukri=1, LinkedIn=1 (Total = 3) => 33.3% FoundIt, 33.3% Naukri/LinkedIn
    "night": {
        "foundit": 0.333,
        "naukri": 0.333,
        "linkedin": 0.333,
    },
}

DAY_DISTRIBUTION = {
    "morning": {"start_hour": 6, "end_hour": 12, "target_percentage": 30},
    "afternoon": {"start_hour": 12, "end_hour": 18, "target_percentage": 25},
    "evening": {"start_hour": 18, "end_hour": 22, "target_percentage": 35},
    "night": {"start_hour": 22, "end_hour": 6, "target_percentage": 10},
}


def get_time_period() -> str:
    """Get current time period based on hour."""
    from datetime import datetime
    hour = datetime.now().hour
    
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"


def get_platform_weights(time_period: Optional[str] = None) -> dict[str, float]:
    """Get platform weights for the current time period."""
    if time_period is None:
        time_period = get_time_period()
    return TIME_PERIOD_WEIGHTS.get(time_period, TIME_PERIOD_WEIGHTS["morning"])


def get_day_distribution_target(time_period: Optional[str] = None) -> int:
    """Get target percentage of daily applications for this time period."""
    if time_period is None:
        time_period = get_time_period()
    return DAY_DISTRIBUTION.get(time_period, {}).get("target_percentage", 30)


def load_wave_config() -> WaveConfig:
    """Load wave configuration from environment variables."""
    return WaveConfig(
        enabled=os.getenv("WAVE_MODE", "true").lower() == "true",
        jobs_per_wave=int(os.getenv("JOBS_PER_WAVE", "5")),
        students_per_wave=int(os.getenv("STUDENTS_PER_WAVE", "5")),
        pause_min_seconds=int(os.getenv("WAVE_PAUSE_MIN", "30")),
        pause_max_seconds=int(os.getenv("WAVE_PAUSE_MAX", "90")),
        student_spacing_min=int(os.getenv("STUDENT_SPACING_MIN", "30")),
        student_spacing_max=int(os.getenv("STUDENT_SPACING_MAX", "60")),
        jitter_max=int(os.getenv("WAVE_JITTER_MAX", "30")),
        time_based_weights=os.getenv("TIME_BASED_WEIGHTS", "true").lower() == "true",
        human_activity_enabled=os.getenv("HUMAN_ACTIVITY_ENABLED", "true").lower() == "true",
        day_distribution_enabled=os.getenv("DAY_DISTRIBUTION_ENABLED", "true").lower() == "true",
    )


wave_config = load_wave_config()