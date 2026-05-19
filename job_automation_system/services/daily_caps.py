"""
Daily Application Caps - Job Automation System
==============================================
Limits applications per student per day.
Prevents over-applying and account bans.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional
from services.redis_client import redis_client
from config import settings

logger = logging.getLogger(__name__)


class DailyCapManager:
    """
    Manages daily application limits per student per platform.
    """

    DEFAULT_CAPS = {
        "linkedin": 6,
        "naukri": 6,
        "foundit": 14,
    }

    TOTAL_DAILY_CAP = 26
    _total_prefix = "daily_total"

    def __init__(self):
        self._prefix = "daily_cap"
        self.TOTAL_DAILY_CAP = 26
        self._total_prefix = "daily_total"

    def _make_key(self, student_id: str, platform: str, date: str) -> str:
        return f"{self._prefix}:{student_id}:{platform}:{date}"

    def _make_total_key(self, student_id: str, date: str) -> str:
        return f"{self._total_prefix}:{student_id}:{date}"

    def get_cap(self, platform: str) -> int:
        return self.DEFAULT_CAPS.get(platform.lower(), 30)

    def get_total_applications_today(self, student_id: str) -> int:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = self._make_total_key(student_id, today)
        try:
            count = redis_client.client.get(key)
            return int(count) if count else 0
        except Exception:
            return 0

    def can_apply_total(self, student_id: str, count: int = 1) -> bool:
        count = max(1, int(count or 1))
        return self.get_total_applications_today(student_id) + count <= self.TOTAL_DAILY_CAP

    def record_total_application(self, student_id: str, count: int = 1) -> bool:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = self._make_total_key(student_id, today)
        count = max(1, int(count or 1))
        
        try:
            pipe = redis_client.client.pipeline()
            pipe.incrby(key, count)
            pipe.expire(key, 86400 * 2)
            pipe.execute()
            
            new_count = int(redis_client.client.get(key) or 0)
            
            if new_count > self.TOTAL_DAILY_CAP:
                logger.warning(
                    f"[{student_id}] TOTAL daily cap exceeded: {new_count}/{self.TOTAL_DAILY_CAP}"
                )
                return False
            if new_count == self.TOTAL_DAILY_CAP:
                logger.warning(
                    f"[{student_id}] TOTAL daily cap reached: {new_count}/{self.TOTAL_DAILY_CAP}"
                )
            
            return True
        except Exception as e:
            logger.warning(f"Daily total cap record error: {e}")
            return True

    def get_applications_today(self, student_id: str, platform: str) -> int:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = self._make_key(student_id, platform.lower(), today)
        try:
            count = redis_client.client.get(key)
            return int(count) if count else 0
        except Exception:
            return 0

    def record_application(self, student_id: str, platform: str, count: int = 1) -> bool:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = self._make_key(student_id, platform.lower(), today)
        cap = self.get_cap(platform)
        count = max(1, int(count or 1))

        try:
            pipe = redis_client.client.pipeline()
            pipe.incrby(key, count)
            pipe.expire(key, 86400 * 2)
            pipe.execute()

            new_count = int(redis_client.client.get(key) or 0)

            if new_count > cap:
                logger.warning(
                    f"[{student_id}] {platform} daily cap exceeded: {new_count}/{cap}"
                )
                return False
            if new_count == cap:
                logger.warning(
                    f"[{student_id}] {platform} daily cap reached: {new_count}/{cap}"
                )
                return True

            logger.info(
                f"[{student_id}] {platform} apps today: {new_count}/{cap}"
            )
            return True
        except Exception as e:
            logger.warning(f"Daily cap record error: {e}")
            return True

    def get_remaining(self, student_id: str, platform: str) -> int:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = self._make_key(student_id, platform.lower(), today)
        cap = self.get_cap(platform)

        try:
            count = int(redis_client.client.get(key) or 0)
            return max(0, cap - count)
        except Exception:
            return cap

    def can_apply(self, student_id: str, platform: str, count: int = 1) -> bool:
        count = max(1, int(count or 1))
        return self.get_applications_today(student_id, platform) + count <= self.get_cap(platform)

    def reset(self, student_id: Optional[str] = None, platform: Optional[str] = None):
        try:
            if student_id and platform:
                today = datetime.utcnow().strftime("%Y-%m-%d")
                redis_client.client.delete(self._make_key(student_id, platform, today))
            else:
                pattern = f"{self._prefix}:*"
                keys = redis_client.client.keys(pattern)
                if keys:
                    redis_client.client.delete(*keys)
        except Exception:
            pass


daily_cap_manager = DailyCapManager()


def check_daily_cap(student_id: str, platform: str, count: int = 1) -> bool:
    return daily_cap_manager.can_apply(student_id, platform, count)


def record_daily_application(student_id: str, platform: str, count: int = 1) -> bool:
    return daily_cap_manager.record_application(student_id, platform, count)


def get_remaining_applications(student_id: str, platform: str) -> int:
    return daily_cap_manager.get_remaining(student_id, platform)


def check_total_daily_cap(student_id: str, count: int = 1) -> bool:
    return daily_cap_manager.can_apply_total(student_id, count)


def record_total_daily_application(student_id: str, count: int = 1) -> bool:
    return daily_cap_manager.record_total_application(student_id, count)


def get_remaining_total_applications(student_id: str) -> int:
    remaining = daily_cap_manager.TOTAL_DAILY_CAP - daily_cap_manager.get_total_applications_today(student_id)
    return max(0, remaining)
