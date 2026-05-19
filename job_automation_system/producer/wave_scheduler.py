"""
Wave Scheduler - Job Automation System
=======================================
Manages wave-based job distribution with anti-detection layers:
1. Mini-Wave batching (5 jobs per wave)
2. Random platform selection (time-based weights)
3. Random student spacing (30-60s)
4. Day distribution (morning/afternoon/evening)
"""

from __future__ import annotations
import random
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from config.wave_config import (
    wave_config,
    get_time_period,
    get_platform_weights,
    get_day_distribution_target,
)

logger = logging.getLogger(__name__)


@dataclass
class WaveMetrics:
    """Track wave execution metrics."""
    wave_number: int = 0
    students_processed: int = 0
    applications_submitted: int = 0
    current_time_period: str = "morning"


class WaveScheduler:
    """
    Manages wave-based job distribution with anti-detection layers.
    
    Anti-Detection Layers:
    1. Mini-Wave: 5 jobs per batch + random pause
    2. Random Platform: weighted by time of day
    3. Time-Based: morning/afternoon/evening patterns
    4. Student Spacing: 30-60s random between students
    5. Day Distribution: spread applications throughout day
    """
    
    def __init__(self):
        self.config = wave_config
        self.metrics = WaveMetrics()
        self._wave_start_time: Optional[datetime] = None
        self._total_applications_today: int = 0
        self._time_period_applications: dict[str, int] = {
            "morning": 0,
            "afternoon": 0,
            "evening": 0,
            "night": 0,
        }
    
    @property
    def time_period(self) -> str:
        """Get current time period."""
        return get_time_period()
    
    @property
    def platform_weights(self) -> dict[str, float]:
        """Get platform weights for current time period."""
        if self.config.time_based_weights:
            return get_platform_weights()
        return {"naukri": 0.40, "foundit": 0.40, "linkedin": 0.20}
    
    def get_wave_pause(self) -> int:
        """Get random pause between waves (30-90 seconds)."""
        return random.randint(
            self.config.pause_min_seconds,
            self.config.pause_max_seconds,
        )
    
    def get_student_spacing(self) -> int:
        """Get random spacing between student submissions (30-60 seconds)."""
        return random.randint(
            self.config.student_spacing_min,
            self.config.student_spacing_max,
        )
    
    def get_jitter(self) -> int:
        """Get random jitter to add to countdown."""
        return random.randint(0, self.config.jitter_max)
    
    def select_platform(self) -> str:
        """
        Select platform using weighted random based on time of day.
        
        Morning (6-12): Naukri 45%, FoundIt 30%, LinkedIn 25%
        Afternoon (12-18): Naukri 50%, FoundIt 30%, LinkedIn 20%
        Evening (18-22): FoundIt 45%, Naukri 35%, LinkedIn 20%
        Night (22-6): FoundIt 50%, Naukri 30%, LinkedIn 20%
        """
        weights = self.platform_weights
        platforms = list(weights.keys())
        probabilities = list(weights.values())
        
        selected = random.choices(platforms, weights=probabilities, k=1)[0]
        logger.debug(f"Platform selected: {selected} (weights: {weights})")
        return selected
    
    def get_batch_size(self) -> int:
        """Get number of jobs per batch (Mini-Wave = 5)."""
        return self.config.jobs_per_wave
    
    def can_submit_application(self, total_students: int, count: int = 1) -> bool:
        """
        Check if we should submit based on day distribution.
        Spreads applications throughout the day to avoid bursts.
        """
        if not self.config.day_distribution_enabled:
            return True
        
        current_period = self.time_period
        target_percentage = get_day_distribution_target(current_period)
        
        count = max(1, int(count or 1))
        period_applications = self._time_period_applications.get(current_period, 0)
        
        max_for_period = int((target_percentage / 100) * (total_students * 26))
        
        if period_applications + count > max_for_period:
            logger.info(
                f"Day distribution limit reached for {current_period}: "
                f"{period_applications}+{count}/{max_for_period}"
            )
            return False
        
        return True
    
    def start_wave(self) -> None:
        """Mark the start of a new wave."""
        self._wave_start_time = datetime.now()
        self.metrics.wave_number += 1
        logger.info(f"Starting Wave {self.metrics.wave_number}")
    
    def record_application(self, platform: str, count: int = 1) -> None:
        """Record an application submission."""
        count = max(1, int(count or 1))
        self.metrics.applications_submitted += count
        self._total_applications_today += count
        
        current_period = self.time_period
        if current_period not in self._time_period_applications:
            self._time_period_applications[current_period] = 0
        self._time_period_applications[current_period] += count
    
    def get_wave_summary(self) -> dict:
        """Get current wave summary."""
        return {
            "wave_number": self.metrics.wave_number,
            "applications_submitted": self.metrics.applications_submitted,
            "time_period": self.time_period,
            "platform_weights": self.platform_weights,
            "total_today": self._total_applications_today,
            "period_breakdown": self._time_period_applications,
        }
    
    def should_wait_for_next_wave(self, students_in_wave: int) -> bool:
        """Determine if we should wait before starting next wave."""
        return students_in_wave >= self.config.students_per_wave
    
    def get_countdown_with_spacing(
        self,
        student_index: int,
        wave_offset: int = 0,
    ) -> int:
        """
        Calculate countdown with random spacing between students.
        
        Args:
            student_index: Index of student in overall list
            wave_offset: Additional offset for wave timing
        """
        base_spacing = self.get_student_spacing()
        jitter = self.get_jitter()
        
        countdown = (student_index * base_spacing) + (wave_offset * self.get_wave_pause()) + jitter
        return max(0, countdown)


class PlatformDistributor:
    """
    Distributes platform assignments across students with anti-detection.
    Ensures no platform gets all applications at once.
    """
    
    def __init__(self, scheduler: WaveScheduler):
        self.scheduler = scheduler
        self._platform_counts: dict[str, int] = {
            "naukri": 0,
            "linkedin": 0,
            "foundit": 0,
        }
    
    def get_platform_for_student(self, student_id: str) -> str:
        """
        Get platform assignment for a student.
        Uses weighted random with balance checking.
        """
        weights = self.scheduler.platform_weights
        
        min_count = min(self._platform_counts.values())
        eligible_platforms = [
            p for p, count in self._platform_counts.items()
            if count == min_count
        ]
        
        if eligible_platforms and random.random() < 0.3:
            return random.choice(eligible_platforms)
        
        return self.scheduler.select_platform()
    
    def record_submission(self, platform: str) -> None:
        """Record a platform submission."""
        if platform in self._platform_counts:
            self._platform_counts[platform] += 1
    
    def get_distribution_summary(self) -> dict:
        """Get current platform distribution."""
        return self._platform_counts.copy()
