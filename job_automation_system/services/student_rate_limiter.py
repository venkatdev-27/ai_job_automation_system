"""
Student Rate Limiter - Per-Student Daily Limits
=======================================
Limits applications per student per day.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Tuple
from services.redis_client import redis_client


DEFAULT_DAILY_LIMIT = 20


class StudentRateLimiter:
    """
    Rate limiter per student per day.
    
    Usage:
        limiter = StudentRateLimiter()
        
        can_apply, count = limiter.can_apply("stu_001")
        if can_apply:
            limiter.increment("stu_001")
    """
    
    PREFIX = "student_rate"
    
    def __init__(self, daily_limit: int = DEFAULT_DAILY_LIMIT):
        self.redis = redis_client.client
        self.daily_limit = daily_limit
    
    def _key(self, student_id: str) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"{self.PREFIX}:{student_id}:{today}"
    
    def can_apply(self, student_id: str) -> Tuple[bool, int]:
        """
        Check if student can apply today.
        
        Returns:
            (can_apply, current_count)
        """
        key = self._key(student_id)
        count = self.redis.get(key)
        current = int(count) if count else 0
        
        return (current < self.daily_limit, current)
    
    def increment(self, student_id: str) -> bool:
        """Increment application count for today."""
        key = self._key(student_id)
        
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)  # 24 hours
        results = pipe.execute()
        
        return results[0] > 0
    
    def get_count(self, student_id: str) -> int:
        """Get current application count for today."""
        key = self._key(student_id)
        count = self.redis.get(key)
        return int(count) if count else 0
    
    def get_remaining(self, student_id: str) -> int:
        """Get remaining applications for today."""
        can_apply, count = self.can_apply(student_id)
        return max(0, self.daily_limit - count)
    
    def reset(self, student_id: str) -> bool:
        """Reset count for student (for admin)."""
        key = self._key(student_id)
        return bool(self.redis.delete(key))
    
    def get_reset_time(self, student_id: str) -> int:
        """Get seconds until daily reset."""
        key = self._key(student_id)
        ttl = self.redis.ttl(key)
        return max(0, ttl)
    
    def is_at_limit(self, student_id: str) -> bool:
        """Check if student is at daily limit."""
        can_apply, _ = self.can_apply(student_id)
        return not can_apply


student_rate_limiter = StudentRateLimiter()