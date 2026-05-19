"""
Adaptive Rate Limiter - Job Automation System
=============================================
Dynamic delays based on success/failure patterns.
Keeps LinkedIn safe while maximizing throughput.
"""

from __future__ import annotations
import time
import random
import logging
from typing import Optional
from dataclasses import dataclass
from services.redis_client import redis_client

logger = logging.getLogger(__name__)


@dataclass
class RateLimiterConfig:
    platform: str
    min_delay: float = 3.0
    max_delay: float = 20.0
    success_threshold: int = 10
    failure_threshold: int = 3
    decrease_factor: float = 0.9
    increase_factor: float = 1.5
    max_retries_before_backoff: int = 5


PLATFORM_CONFIGS = {
    "linkedin": RateLimiterConfig(
        platform="linkedin",
        min_delay=5.0,
        max_delay=25.0,
        success_threshold=15,
        failure_threshold=3,
    ),
    "naukri": RateLimiterConfig(
        platform="naukri",
        min_delay=1.5,
        max_delay=5.0,
        success_threshold=20,
        failure_threshold=3,
    ),
    "foundit": RateLimiterConfig(
        platform="foundit",
        min_delay=2.0,
        max_delay=10.0,
        success_threshold=15,
        failure_threshold=3,
    ),
}


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts delays based on success/failure.
    Starts conservative, speeds up on success, slows down on failure.
    """

    def __init__(self, platform: str, config: Optional[RateLimiterConfig] = None):
        self.platform = platform.lower()
        self.config = config or PLATFORM_CONFIGS.get(platform, RateLimiterConfig(platform))

        self._key_prefix = f"adaptive_rate:{self.platform}"
        self._current_delay = self.config.min_delay
        self._success_count = 0
        self._failure_count = 0
        self._consecutive_failures = 0

    def _get_stats_key(self) -> str:
        return f"{self._key_prefix}:stats"

    def _load_stats(self) -> dict:
        try:
            key = self._get_stats_key()
            data = redis_client.client.hgetall(key)
            if data:
                return {
                    "delay": float(data.get("delay", self.config.min_delay)),
                    "successes": int(data.get("successes", 0)),
                    "failures": int(data.get("failures", 0)),
                    "consecutive_failures": int(data.get("consecutive_failures", 0)),
                }
        except Exception:
            pass
        return {
            "delay": self.config.min_delay,
            "successes": 0,
            "failures": 0,
            "consecutive_failures": 0,
        }

    def _save_stats(self, stats: dict):
        try:
            key = self._get_stats_key()
            redis_client.client.hset(key, mapping=stats)
            redis_client.client.expire(key, 3600)
        except Exception:
            pass

    def record_success(self):
        stats = self._load_stats()
        stats["successes"] = stats.get("successes", 0) + 1
        stats["consecutive_failures"] = 0

        current_delay = stats.get("delay", self.config.min_delay)

        if stats["successes"] >= self.config.success_threshold:
            new_delay = max(self.config.min_delay, current_delay * self.config.decrease_factor)
            stats["delay"] = round(new_delay, 2)
            stats["successes"] = 0
            logger.info(f"[{self.platform}] Success: decreased delay to {new_delay:.2f}s")

        self._save_stats(stats)

    def record_failure(self, is_rate_limit_error: bool = False):
        stats = self._load_stats()
        stats["failures"] = stats.get("failures", 0) + 1
        stats["consecutive_failures"] = stats.get("consecutive_failures", 0) + 1

        current_delay = stats.get("delay", self.config.min_delay)

        if is_rate_limit_error or stats["consecutive_failures"] >= self.config.failure_threshold:
            new_delay = min(self.config.max_delay, current_delay * self.config.increase_factor)
            stats["delay"] = round(new_delay, 2)
            stats["consecutive_failures"] = 0
            logger.warning(f"[{self.platform}] Failure: increased delay to {new_delay:.2f}s")

        self._save_stats(stats)

    def get_delay(self) -> float:
        stats = self._load_stats()
        delay = stats.get("delay", self.config.min_delay)
        jitter = random.uniform(0, delay * 0.2)
        return delay + jitter

    def reset(self):
        try:
            redis_client.client.delete(self._get_stats_key())
        except Exception:
            pass


_adaptive_limiters: dict[str, AdaptiveRateLimiter] = {}


def get_adaptive_limiter(platform: str) -> AdaptiveRateLimiter:
    platform = platform.lower()
    if platform not in _adaptive_limiters:
        _adaptive_limiters[platform] = AdaptiveRateLimiter(platform)
    return _adaptive_limiters[platform]


def record_success(platform: str):
    get_adaptive_limiter(platform).record_success()


def record_failure(platform: str, is_rate_limit_error: bool = False):
    get_adaptive_limiter(platform).record_failure(is_rate_limit_error)


def get_delay(platform: str) -> float:
    return get_adaptive_limiter(platform).get_delay()