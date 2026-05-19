"""
Monitoring System - Job Automation System
======================================
Basic monitoring logs for visibility into system health.
Tracks success rate, failures, applications count.
"""

from __future__ import annotations
import logging
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
from services.redis_client import redis_client
from config import settings

logger = logging.getLogger(__name__)


@dataclass
class PlatformStats:
    platform: str
    total_applications: int = 0
    successful: int = 0
    failed: int = 0
    challenges: int = 0
    rate_limited: int = 0
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    success_rate: float = 0.0


class MonitoringService:
    """
    Simple monitoring for production visibility.
    Stores stats in Redis for dashboard access.
    """

    def __init__(self):
        self._prefix = "monitoring"

    def _key(self, metric: str) -> str:
        return f"{self._prefix}:{metric}"

    def record_application(
        self,
        platform: str,
        student_id: str,
        status: str,
        job_title: str = "",
        error: Optional[str] = None,
    ):
        timestamp = datetime.utcnow().isoformat()

        try:
            pipe = redis_client.client.pipeline()

            platform_key = f"{self._prefix}:{platform}"

            pipe.hincrby(platform_key, "total", 1)
            if status == "applied":
                pipe.hincrby(platform_key, "success", 1)
                pipe.hset(platform_key, "last_success", timestamp)
            else:
                pipe.hincrby(platform_key, "failed", 1)
                pipe.hset(platform_key, "last_failure", timestamp)
                if error:
                    pipe.hincrby(platform_key, f"error_{error[:20]}", 1)

            if "challenge" in (error or "").lower():
                pipe.hincrby(platform_key, "challenges", 1)

            if "rate limit" in (error or "").lower():
                pipe.hincrby(platform_key, "rate_limited", 1)

            pipe.expire(platform_key, 86400)
            pipe.execute()

            logger.info(
                f"[{platform}] {status}: {student_id} | "
                f"Job: {job_title[:30] if job_title else 'N/A'}"
            )
        except Exception as e:
            logger.warning(f"Monitoring record error: {e}")

    def get_platform_stats(self, platform: str) -> PlatformStats:
        try:
            key = f"{self._prefix}:{platform}"
            data = redis_client.client.hgetall(key)

            total = int(data.get("total", 0))
            success = int(data.get("success", 0))
            failed = int(data.get("failed", 0))

            return PlatformStats(
                platform=platform,
                total_applications=total,
                successful=success,
                failed=failed,
                challenges=int(data.get("challenges", 0)),
                rate_limited=int(data.get("rate_limited", 0)),
                last_success=data.get("last_success"),
                last_failure=data.get("last_failure"),
                success_rate=(success / total * 100) if total > 0 else 0.0,
            )
        except Exception as e:
            logger.warning(f"Monitoring get error: {e}")
            return PlatformStats(platform=platform)

    def get_all_stats(self) -> dict[str, PlatformStats]:
        stats = {}
        for platform in ["naukri", "linkedin", "foundit"]:
            stats[platform] = self.get_platform_stats(platform)
        return stats

    def get_daily_summary(self) -> dict:
        stats = self.get_all_stats()
        total_apps = sum(s.total_applications for s in stats.values())
        total_success = sum(s.successful for s in stats.values())

        return {
            "date": datetime.utcnow().date().isoformat(),
            "total_applications": total_apps,
            "successful": total_success,
            "failed": sum(s.failed for s in stats.values()),
            "success_rate": (total_success / total_apps * 100) if total_apps > 0 else 0,
            "platforms": {
                platform: {
                    "applications": s.total_applications,
                    "success_rate": s.success_rate,
                }
                for platform, s in stats.items()
            },
        }

    def reset(self, platform: Optional[str] = None):
        try:
            if platform:
                redis_client.client.delete(f"{self._prefix}:{platform}")
            else:
                keys = redis_client.client.keys(f"{self._prefix}:*")
                if keys:
                    redis_client.client.delete(*keys)
        except Exception:
            pass


monitoring = MonitoringService()


def record_application(platform: str, student_id: str, status: str, **kwargs):
    monitoring.record_application(platform, student_id, status, **kwargs)


def get_stats(platform: str) -> PlatformStats:
    return monitoring.get_platform_stats(platform)


def get_all_stats() -> dict[str, PlatformStats]:
    return monitoring.get_all_stats()


def get_daily_summary() -> dict:
    return monitoring.get_daily_summary()