"""
Rate Limiter Service - Job Automation System
============================================
Token bucket rate limiting using Redis with atomic Lua operations.
Optimized for 40+ concurrent students.
"""

from __future__ import annotations
import time
import random
import logging
from typing import Optional
from services.redis_client import redis_client
from config import settings

logger = logging.getLogger(__name__)

LUA_ACQUIRE_ATOMIC = """
local tokens_key = KEYS[1]
local last_refill_key = KEYS[2]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local tokens = tonumber(redis.call('get', tokens_key) or capacity)
local last_refill = tonumber(redis.call('get', last_refill_key) or now)

local elapsed = now - last_refill
local new_tokens = math.min(capacity, tokens + (elapsed * refill_rate))

if new_tokens >= 1 then
    redis.call('set', tokens_key, math.floor(new_tokens - 1), 'ex', 3600)
    redis.call('set', last_refill_key, now, 'ex', 3600)
    return 1
end
return 0
"""


class RateLimiter:
    """
    Token bucket rate limiter using Redis with atomic Lua script.
    No more race conditions between workers.
    """
    
    def __init__(
        self,
        platform: str,
        capacity: int = 10,
        refill_rate: float = 0.166,
    ):
        self.platform = platform.lower()
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._key_prefix = f"rate_limit:{self.platform}"
        self._lua_acquire = None
    
    @property
    def _tokens_key(self) -> str:
        return f"{self._key_prefix}:tokens"
    
    @property
    def _last_refill_key(self) -> str:
        return f"{self._key_prefix}:last_refill"
    
    def _get_lua_acquire(self):
        if self._lua_acquire is None:
            self._lua_acquire = redis_client.client.register_script(LUA_ACQUIRE_ATOMIC)
        return self._lua_acquire
    
    def acquire(self, blocking: bool = False, timeout: int = 30) -> bool:
        start_time = time.time()
        backoff = 0.5
        
        while True:
            try:
                result = self._get_lua_acquire()(
                    keys=[self._tokens_key, self._last_refill_key],
                    args=[self.capacity, self.refill_rate, time.time()]
                )
                
                if result:
                    return True
                
                if not blocking:
                    return False
                
                if time.time() - start_time >= timeout:
                    return False
                
                jitter = random.uniform(0, backoff * 0.3)
                time.sleep(backoff + jitter)
                backoff = min(backoff * 1.5, 5.0)
            
            except Exception as e:
                logger.warning(f"Rate limiter acquire failed: {e}")
                if not blocking:
                    return False
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
                time.sleep(1)
        
        return False
    
    def _get_bucket_state(self) -> tuple[int, float]:
        try:
            pipe = redis_client.client.pipeline()
            pipe.get(self._tokens_key)
            pipe.get(self._last_refill_key)
            results = pipe.execute()
            
            tokens = int(results[0]) if results[0] else self.capacity
            last_refill = float(results[1]) if results[1] else time.time()
            
            return tokens, last_refill
        except Exception:
            return self.capacity, time.time()
    
    def reset(self):
        try:
            redis_client.client.delete(self._tokens_key)
            redis_client.client.delete(self._last_refill_key)
        except Exception:
            pass
    
    def get_wait_time(self) -> float:
        tokens, last_refill = self._get_bucket_state()
        if tokens >= 1:
            return 0.0
        return (1 - tokens) / self.refill_rate


_naukri_limiter: Optional[RateLimiter] = None
_linkedin_limiter: Optional[RateLimiter] = None
_foundit_limiter: Optional[RateLimiter] = None


def get_rate_limiter(platform: str) -> RateLimiter:
    global _naukri_limiter, _linkedin_limiter, _foundit_limiter
    
    platform = platform.lower()
    
    if platform == "naukri":
        if _naukri_limiter is None:
            _naukri_limiter = RateLimiter(
                "naukri",
                capacity=settings.naukri_rate_limit,
                refill_rate=settings.naukri_rate_limit / 60.0,
            )
        return _naukri_limiter
    
    elif platform == "linkedin":
        if _linkedin_limiter is None:
            _linkedin_limiter = RateLimiter(
                "linkedin",
                capacity=settings.linkedin_rate_limit,
                refill_rate=settings.linkedin_rate_limit / 60.0,
            )
        return _linkedin_limiter
    
    elif platform == "foundit":
        if _foundit_limiter is None:
            _foundit_limiter = RateLimiter(
                "foundit",
                capacity=settings.foundit_rate_limit,
                refill_rate=settings.foundit_rate_limit / 60.0,
            )
        return _foundit_limiter
    
    return RateLimiter(platform, capacity=10, refill_rate=0.166)


class WaveRateLimiter:
    """
    Wave-level rate limiter for Mini-Wave anti-detection.
    Tracks submissions per time period and enforces day distribution.
    """
    
    def __init__(self):
        self._key_prefix = "wave_rate_limit"
        self._redis = redis_client.client
    
    def _get_time_period_key(self, time_period: str) -> str:
        """Get Redis key for time period submissions."""
        return f"{self._key_prefix}:{time_period}:submissions"
    
    def _get_wave_key(self, wave_id: str) -> str:
        """Get Redis key for wave tracking."""
        return f"{self._key_prefix}:wave:{wave_id}"
    
    def record_submission(self, time_period: str, platform: str) -> None:
        """Record a submission for the current time period."""
        try:
            key = self._get_time_period_key(time_period)
            self._redis.incr(key)
            self._redis.expire(key, 86400)
            
            platform_key = f"{self._key_prefix}:{time_period}:{platform}"
            self._redis.incr(platform_key)
            self._redis.expire(platform_key, 86400)
        except Exception as e:
            logger.warning(f"Failed to record wave submission: {e}")
    
    def get_period_submissions(self, time_period: str) -> int:
        """Get total submissions for a time period."""
        try:
            key = self._get_time_period_key(time_period)
            value = self._redis.get(key)
            return int(value) if value else 0
        except Exception:
            return 0
    
    def get_platform_period_submissions(self, time_period: str, platform: str) -> int:
        """Get submissions for a platform in a time period."""
        try:
            key = f"{self._key_prefix}:{time_period}:{platform}"
            value = self._redis.get(key)
            return int(value) if value else 0
        except Exception:
            return 0
    
    def is_period_at_limit(
        self,
        time_period: str,
        target_percentage: int,
        total_daily_target: int,
    ) -> bool:
        """Check if time period has reached its target."""
        current = self.get_period_submissions(time_period)
        max_for_period = int((target_percentage / 100) * total_daily_target)
        return current >= max_for_period
    
    def get_cooldown_remaining(self, wave_id: str) -> float:
        """Get remaining cooldown for a wave."""
        try:
            key = self._get_wave_key(wave_id)
            ttl = self._redis.ttl(key)
            return max(0, ttl) if ttl > 0 else 0
        except Exception:
            return 0
    
    def set_wave_cooldown(self, wave_id: str, cooldown_seconds: int) -> None:
        """Set cooldown for a wave after completion."""
        try:
            key = self._get_wave_key(wave_id)
            self._redis.setex(key, cooldown_seconds, "cooldown")
        except Exception as e:
            logger.warning(f"Failed to set wave cooldown: {e}")
    
    def get_stats(self, time_periods: list[str]) -> dict:
        """Get statistics for all time periods."""
        stats = {}
        for period in time_periods:
            stats[period] = {
                "total": self.get_period_submissions(period),
                "naukri": self.get_platform_period_submissions(period, "naukri"),
                "linkedin": self.get_platform_period_submissions(period, "linkedin"),
                "foundit": self.get_platform_period_submissions(period, "foundit"),
            }
        return stats
    
    def reset_all(self) -> None:
        """Reset all wave rate limit data."""
        try:
            pattern = f"{self._key_prefix}:*"
            keys = self._redis.keys(pattern)
            if keys:
                self._redis.delete(*keys)
            logger.info("Wave rate limiter reset complete")
        except Exception as e:
            logger.warning(f"Failed to reset wave rate limiter: {e}")