"""
Idempotency Service - Job Automation System
===========================================
Prevents duplicate job applications using Redis with atomic operations.
Idempotency key = student_id + platform + job_id + date
Optimized for 40+ concurrent students.
"""

from __future__ import annotations
from datetime import datetime
import hashlib
from typing import Optional
from services.redis_client import redis_client
from config import settings
import logging

logger = logging.getLogger(__name__)

LUA_CHECK_AND_START = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local status = redis.call('get', key)
if status then
    return status
end
redis.call('set', key, 'started', 'ex', ttl)
return nil
"""

LUA_MARK_COMPLETED = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local status = redis.call('get', key)
if status == 'completed' then
    return 'completed'
end
redis.call('set', key, 'completed', 'ex', ttl)
return 'completed'
"""

LUA_ATOMIC_CHECK = """
local key = KEYS[1]
local wanted = ARGV[1]
local status = redis.call('get', key)
if status == wanted then
    return 1
end
return 0
"""


class IdempotencyManager:
    """
    Manages idempotency keys to prevent duplicate job applications.
    
    Key format: idemp:{platform}:{student_id}:{job_hash}:{date}
    TTL: 24 hours (configurable)
    Uses atomic Lua scripts for thread-safe operations.
    """
    
    def __init__(self, ttl: Optional[int] = None):
        self.ttl = ttl or settings.idempotency_ttl
        self._lua_check_and_start = None
        self._lua_mark_completed = None
    
    def _get_lua_check_and_start(self):
        if self._lua_check_and_start is None:
            self._lua_check_and_start = redis_client.client.register_script(LUA_CHECK_AND_START)
        return self._lua_check_and_start
    
    def _get_lua_mark_completed(self):
        if self._lua_mark_completed is None:
            self._lua_mark_completed = redis_client.client.register_script(LUA_MARK_COMPLETED)
        return self._lua_mark_completed
    
    @staticmethod
    def generate_key(
        student_id: str,
        platform: str,
        job_id: str,
        date: Optional[str] = None,
    ) -> str:
        """
        Generate idempotency key.
        
        Args:
            student_id: Unique student identifier
            platform: Platform name (naukri, linkedin, etc.)
            job_id: Unique job identifier from platform
            date: Date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Redis key string
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        job_hash = hashlib.sha256(job_id.encode()).hexdigest()[:16]
        
        return f"idemp:{platform.lower()}:{student_id}:{job_hash}:{date}"
    
    def check_and_mark_started(self, key: str) -> str:
        """
        Atomically check if duplicate and mark as started.
        Single Redis round-trip!
        
        Args:
            key: Idempotency key
            
        Returns:
            "started" = new task started, "completed" = already done, "started" = already in progress
        """
        try:
            result = self._get_lua_check_and_start()(
                keys=[key],
                args=[self.ttl]
            )
            return result
        except Exception as e:
            logger.warning(f"Idempotency check failed: {e}")
            return "started"
    
    def is_duplicate(self, key: str) -> bool:
        """
        Check if this task has already been executed.
        
        Args:
            key: Idempotency key
            
        Returns:
            True if duplicate, False otherwise
        """
        try:
            status = redis_client.client.get(key)
            return status in ("started", "completed")
        except Exception:
            return False
    
    def mark_completed(self, key: str) -> bool:
        """
        Mark task as completed atomically.
        
        Args:
            key: Idempotency key
            
        Returns:
            True if successfully marked
        """
        try:
            self._get_lua_mark_completed()(
                keys=[key],
                args=[self.ttl]
            )
            return True
        except Exception as e:
            logger.warning(f"Idempotency mark completed failed: {e}")
            return False
    
    def mark_started(self, key: str) -> bool:
        """
        Mark task as started (to handle partial completion).
        Uses SETNX to avoid race conditions.
        
        Args:
            key: Idempotency key
            
        Returns:
            True if successfully marked
        """
        try:
            return redis_client.client.set(key, "started", nx=True, ex=self.ttl)
        except Exception:
            return False
    
    def get_status(self, key: str) -> Optional[str]:
        """
        Get current status of idempotency key.
        
        Returns:
            "started", "completed", or None
        """
        try:
            return redis_client.client.get(key)
        except Exception:
            return None
    
    def clear(self, key: str) -> bool:
        """Clear an idempotency key (for testing)."""
        try:
            redis_client.client.delete(key)
            return True
        except Exception:
            return False


idempotency_manager = IdempotencyManager()


def check_idempotency(
    student_id: str,
    platform: str,
    job_id: str,
) -> tuple[bool, Optional[str]]:
    """
    Check if job application is a duplicate.
    Optimized: single round-trip for check-and-mark.
    
    Returns:
        (is_duplicate, status) where status is "started", "completed", or None
    """
    key = idempotency_manager.generate_key(student_id, platform, job_id)
    status = idempotency_manager.check_and_mark_started(key)
    
    if status in ("started", "completed"):
        return True, status
    
    return False, None


def mark_idempotency_started(
    student_id: str,
    platform: str,
    job_id: str,
) -> bool:
    """Mark idempotency key as started."""
    key = idempotency_manager.generate_key(student_id, platform, job_id)
    return idempotency_manager.mark_started(key)


def mark_idempotency_completed(
    student_id: str,
    platform: str,
    job_id: str,
) -> bool:
    """Mark idempotency key as completed."""
    key = idempotency_manager.generate_key(student_id, platform, job_id)
    return idempotency_manager.mark_completed(key)