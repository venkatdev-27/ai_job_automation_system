"""
Browser Semaphore Service - Job Automation System
==================================================
Global semaphore to limit concurrent Playwright browser instances.
Optimized with adaptive backoff for 40+ concurrent students.
"""

from __future__ import annotations
import time
import random
import logging
import uuid
from typing import Optional
from services.redis_client import redis_client
from config import settings

logger = logging.getLogger(__name__)

LUA_ACQUIRE = """
local leases_key = KEYS[1]
local gauge_key = KEYS[2]
local max = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local token = ARGV[4]

redis.call('zremrangebyscore', leases_key, 0, now)
local current = redis.call('zcard', leases_key)

if current < max then
    redis.call('zadd', leases_key, now + ttl, token)
    current = current + 1
    redis.call('set', gauge_key, current, 'ex', ttl + 60)
    redis.call('expire', leases_key, ttl + 60)
    return 1
end

redis.call('set', gauge_key, current, 'ex', ttl + 60)
return 0
"""

LUA_RELEASE = """
local leases_key = KEYS[1]
local gauge_key = KEYS[2]
local token = ARGV[1]
local now = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

redis.call('zremrangebyscore', leases_key, 0, now)
local removed = redis.call('zrem', leases_key, token)
local current = redis.call('zcard', leases_key)
redis.call('set', gauge_key, current, 'ex', ttl + 60)
return removed
"""

LUA_GET_WAIT = """
local current = tonumber(redis.call('get', KEYS[1]) or '0')
local max = tonumber(ARGV[1])
if current >= max then
    return max - current + 1
else
    return 0
end
"""


class BrowserSemaphore:
    """
    Global semaphore using Redis to limit concurrent browser instances.
    Optimized with adaptive exponential backoff + jitter.
    """
    
    def __init__(self, max_browsers: Optional[int] = None):
        self.max_browsers = max_browsers or settings.max_parallel_browsers
        self._key = "semaphore:browsers"
        self._leases_key = "semaphore:browsers:leases"
        self._lease_ttl = max(int(getattr(settings, "celery_task_time_limit", 3600)) + 300, 900)
        self._tokens: list[str] = []
        self._lua_acquire = None
        self._lua_release = None
        self._wait_estimate = 0
    
    def _get_lua_acquire(self):
        if self._lua_acquire is None:
            self._lua_acquire = redis_client.client.register_script(LUA_ACQUIRE)
        return self._lua_acquire
    
    def _get_lua_release(self):
        if self._lua_release is None:
            self._lua_release = redis_client.client.register_script(LUA_RELEASE)
        return self._lua_release
    
    def acquire(self, blocking: bool = True, timeout: int = 120) -> bool:
        start_time = time.time()
        backoff = 0.5
        
        while True:
            try:
                token = str(uuid.uuid4())
                result = self._get_lua_acquire()(
                    keys=[self._leases_key, self._key],
                    args=[self.max_browsers, time.time(), self._lease_ttl, token],
                )
                
                if result:
                    self._tokens.append(token)
                    return True
                
                if not blocking:
                    return False
                
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
                
                jitter = random.uniform(0, backoff * 0.3)
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
        token = self._tokens.pop() if self._tokens else ""
        try:
            if not token:
                self._refresh_gauge()
                return False
            return self._get_lua_release()(
                keys=[self._leases_key, self._key],
                args=[token, time.time(), self._lease_ttl],
            ) > 0
        except Exception:
            return False
    
    def get_current_count(self) -> int:
        try:
            redis_client.client.zremrangebyscore(self._leases_key, 0, time.time())
            count = int(redis_client.client.zcard(self._leases_key))
            redis_client.client.set(self._key, count, ex=self._lease_ttl + 60)
            return count
        except Exception:
            return 0

    def _refresh_gauge(self) -> None:
        try:
            self.get_current_count()
        except Exception:
            pass
    
    def get_available_slots(self) -> int:
        current = self.get_current_count()
        return max(0, self.max_browsers - current)
    
    def get_estimated_wait(self) -> float:
        try:
            current = self.get_current_count()
            if current >= self.max_browsers:
                return (current / self.max_browsers) * 30
            return 0
        except Exception:
            return 0
    
    def reset(self):
        try:
            redis_client.client.delete(self._key)
        except Exception:
            pass
    
    def __enter__(self):
        self.acquire(blocking=True, timeout=120)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


browser_semaphore = BrowserSemaphore()


def acquire_browser(timeout: int = 120, blocking: bool = True) -> bool:
    return browser_semaphore.acquire(blocking=blocking, timeout=timeout)


def release_browser() -> bool:
    return browser_semaphore.release()


def get_browser_count() -> int:
    return browser_semaphore.get_current_count()


def get_available_browsers() -> int:
    return browser_semaphore.get_available_slots()
