"""
Platform Semaphore Service
==========================
Small Redis-backed semaphores for global platform concurrency.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from config import settings
from services.redis_client import redis_client


PLATFORM_LIMITS = {
    "foundit": lambda: int(getattr(settings, "browser_concurrency_foundit", 3) or 3),
    "naukri": lambda: int(getattr(settings, "browser_concurrency_naukri", 2) or 2),
    "linkedin": lambda: int(getattr(settings, "browser_concurrency_linkedin", 1) or 1),
}

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
    redis.call('set', gauge_key, current + 1, 'ex', ttl + 60)
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


class PlatformSemaphore:
    def __init__(self, platform: str, limit: Optional[int] = None):
        self.platform = platform.lower()
        limit_factory = PLATFORM_LIMITS.get(self.platform, lambda: 1)
        self.limit = max(1, int(limit or limit_factory()))
        self.ttl = max(int(getattr(settings, "celery_task_time_limit", 3600)) + 300, 900)
        self.token = str(uuid.uuid4())
        self.leases_key = f"semaphore:platform:{self.platform}:leases"
        self.gauge_key = f"semaphore:platform:{self.platform}"
        self._acquired = False
        self._lua_acquire = None
        self._lua_release = None

    def _get_lua_acquire(self):
        if self._lua_acquire is None:
            self._lua_acquire = redis_client.client.register_script(LUA_ACQUIRE)
        return self._lua_acquire

    def _get_lua_release(self):
        if self._lua_release is None:
            self._lua_release = redis_client.client.register_script(LUA_RELEASE)
        return self._lua_release

    def acquire(self, blocking: bool = True, timeout: int = 900) -> bool:
        start = time.time()
        backoff = 1.0
        while True:
            try:
                ok = self._get_lua_acquire()(
                    keys=[self.leases_key, self.gauge_key],
                    args=[self.limit, time.time(), self.ttl, self.token],
                )
                if ok:
                    self._acquired = True
                    return True
                if not blocking or time.time() - start >= timeout:
                    return False
                time.sleep(backoff)
                backoff = min(backoff * 1.3, 10.0)
            except Exception:
                if not blocking or time.time() - start >= timeout:
                    return False
                time.sleep(2)

    def release(self) -> bool:
        if not self._acquired:
            return True
        try:
            removed = self._get_lua_release()(
                keys=[self.leases_key, self.gauge_key],
                args=[self.token, time.time(), self.ttl],
            )
            self._acquired = False
            return bool(removed)
        except Exception:
            self._acquired = False
            return False


def acquire_platform_slot(platform: str, timeout: int = 900) -> Optional[PlatformSemaphore]:
    semaphore = PlatformSemaphore(platform)
    if semaphore.acquire(blocking=True, timeout=timeout):
        return semaphore
    return None


def release_platform_slot(semaphore: Optional[PlatformSemaphore]) -> None:
    if semaphore:
        semaphore.release()
