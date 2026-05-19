"""
Distributed Lock Service - Job Automation System
===============================================
Redis-based distributed locking to prevent concurrent execution of same task.
Optimized for 40+ concurrent students with faster recovery.
"""

from __future__ import annotations
import time
import uuid
import random
from typing import Optional
import logging
from services.redis_client import redis_client
from config import settings

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300
HEARTBEAT_INTERVAL = 60


def _runtime_lock_ttl() -> int:
    """Use a lock TTL that outlives the longest Celery task."""
    configured = int(getattr(settings, "lock_ttl", DEFAULT_TTL) or DEFAULT_TTL)
    task_limit = int(getattr(settings, "celery_task_time_limit", 3600) or 3600)
    return max(configured, task_limit + 300)


class DistributedLock:
    """
    Redis-based distributed lock using SETNX with heartbeat.
    
    Usage:
        lock = DistributedLock("task:student_001:naukri", ttl=300)
        if lock.acquire():
            try:
                while doing_work():
                    lock.heartbeat()
            finally:
                lock.release()
    """
    
    def __init__(self, key: str, ttl: Optional[int] = None):
        self.key = f"lock:{key}"
        self.ttl = ttl or DEFAULT_TTL
        self.lock_value = str(uuid.uuid4())
        self._acquired = False
        self._last_heartbeat = 0
    
    def acquire(self, blocking: bool = False, timeout: int = 30) -> bool:
        start_time = time.time()
        backoff = 0.5
        
        while True:
            try:
                result = redis_client.client.set(
                    self.key,
                    self.lock_value,
                    nx=True,
                    ex=self.ttl,
                )
                
                if result:
                    self._acquired = True
                    self._last_heartbeat = time.time()
                    return True
                
                if not blocking:
                    return False
                
                if time.time() - start_time >= timeout:
                    return False
                
                jitter = random.uniform(0, backoff * 0.5)
                time.sleep(backoff + jitter)
                backoff = min(backoff * 1.5, 5.0)
                
            except Exception:
                if not blocking:
                    return False
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
                time.sleep(1)
        
        return False
    
    def release(self) -> bool:
        if not self._acquired:
            return True
        
        try:
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = redis_client.client.eval(lua_script, 1, self.key, self.lock_value)
            self._acquired = False
            return result > 0
        except Exception:
            self._acquired = False
            return False
    
    def extend(self, additional_time: int = None) -> bool:
        if not self._acquired:
            return False
        
        additional_time = additional_time or HEARTBEAT_INTERVAL
        
        try:
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            new_ttl = self.ttl + additional_time
            result = redis_client.client.eval(
                lua_script, 1, self.key, self.lock_value, new_ttl
            )
            if result:
                self._last_heartbeat = time.time()
            return result > 0
        except Exception:
            return False
    
    def heartbeat(self) -> bool:
        return self.extend()
    
    def should_heartbeat(self) -> bool:
        return time.time() - self._last_heartbeat >= HEARTBEAT_INTERVAL
    
    def __enter__(self):
        self.acquire(blocking=True, timeout=30)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


def acquire_task_lock(
    student_id: str,
    platform: str,
    job_id: str,
    ttl: Optional[int] = None,
    *,
    blocking: bool = True,
    timeout: int = 30,
) -> Optional[DistributedLock]:
    """
    Acquire a distributed lock for a task.
    Uses a TTL longer than the Celery task time limit for crash-safe recovery.
    """
    lock_key = f"task:{student_id}:{platform}:{job_id}"
    lock = DistributedLock(lock_key, ttl or _runtime_lock_ttl())
    
    if lock.acquire(blocking=blocking, timeout=timeout):
        return lock
    
    return None


def release_task_lock(lock: Optional[DistributedLock]):
    """Release a task lock."""
    if lock:
        lock.release()


def acquire_student_platform_lock(
    student_id: str,
    platform: str,
    ttl: Optional[int] = None,
    *,
    blocking: bool = False,
    timeout: int = 5,
) -> Optional[DistributedLock]:
    """
    Acquire a strict lock for student+platform scope.
    Uses a TTL longer than the Celery task time limit for crash-safe recovery.
    """
    lock_key = f"student_platform:{student_id}:{platform}"
    lock = DistributedLock(lock_key, ttl or _runtime_lock_ttl())
    if lock.acquire(blocking=blocking, timeout=timeout):
        return lock
    return None


def acquire_student_session_lock(
    student_id: str,
    ttl: Optional[int] = None,
    *,
    blocking: bool = False,
    timeout: int = 10,
) -> Optional[DistributedLock]:
    """
    Acquire a cross-platform lock on the student's browser session/profile.

    This prevents multiple platforms (naukri, linkedin, foundit) from
    opening the same student's Playwright browser profile directory at the
    same time, which would cause 'Profile in use' crashes.

    Key: student_session:{student_id}  (no platform qualifier)
    TTL: 15 min default – long enough for a full apply run with heartbeat.
    """
    lock_key = f"student_session:{student_id}"
    lock = DistributedLock(lock_key, ttl or _runtime_lock_ttl())
    if lock.acquire(blocking=blocking, timeout=timeout):
        return lock
    return None
