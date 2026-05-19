"""
Idempotency Service V2 - Job Automation System
===========================================
Production-grade idempotency with:
- Two-tier system: session keys + application keys
- Daily limits per student per platform
- Configurable allow/block behavior

Key Formats:
- Session: idemp:session:{platform}:{student}:{session_id} (TTL: 1-4 hours)
- Apply: idemp:apply:{platform}:{student}:{job_hash} (TTL: 24 hours)  
- Daily: idemp:daily:{platform}:{student}:{date} (TTL: 24 hours, counter)
"""

from __future__ import annotations
from datetime import datetime, timedelta
import hashlib
import uuid
from typing import Optional
from services.redis_client import redis_client
from config import settings
import logging

logger = logging.getLogger(__name__)

# Configuration
SESSION_TTL_HOURS = 4  # Retry window
DAILY_LIMIT = 20  # Max applications per student/platform/day
DAILY_LIMIT_JOBS = 50  # Max different jobs per day

# Lua script for atomic check-and-increment daily counter
LUA_DAILY_INCREMENT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local current = redis.call('incr', key)
if current == 1 then
    redis.call('expire', key, 86400)
end
if current > limit then
    return 0
end
return current
"""

# Lua script for atomic session check
LUA_SESSION_CHECK = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local status = redis.call('get', key)
if status == 'completed' then
    return 'completed'
end
if status == 'started' then
    return 'started'
end
redis.call('set', key, 'started', 'ex', ttl)
return nil
"""

# Lua script for atomic apply check
LUA_APPLY_CHECK = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local status = redis.call('get', key)
if status == 'completed' then
    return 'completed'
end
if status == 'started' then
    return 'started'
end
redis.call('set', key, 'completed', 'ex', ttl)
return nil
"""


# Lua script for atomic full check: apply + daily + session
LUA_ATOMIC_CAN_APPLY = """
local apply_key = KEYS[1]
local daily_key = KEYS[2]
local session_key = KEYS[3]

local apply_ttl = tonumber(ARGV[1])
local daily_limit = tonumber(ARGV[2])
local session_ttl = tonumber(ARGV[3])

-- 1. Check apply key (true duplicate)
local apply_status = redis.call('get', apply_key)
if apply_status == 'completed' then
    return {'already_applied', tonumber(redis.call('get', daily_key) or 0)}
end

-- 2. Check daily limit (atomic reserve)
local daily_count = tonumber(redis.call('get', daily_key) or 0)
if daily_count >= daily_limit then
    return {'daily_limit', daily_count}
end

-- 3. Check session
local session_status = redis.call('get', session_key)
if session_status == 'completed' then
    return {'already_applied', daily_count}
end

-- 4. SUCCESS: Mark and Increment
if not apply_status then
    redis.call('set', apply_key, 'started', 'ex', apply_ttl)
end

local new_daily = redis.call('incr', daily_key)
if new_daily == 1 then
    redis.call('expire', daily_key, 86400)
end

if not session_status then
    redis.call('set', session_key, 'started', 'ex', session_ttl)
end

return {'ok', new_daily}
"""


class IdempotencyManagerV2:
    """
    Production-grade idempotency manager.
    
    Two-tier system:
    1. Session keys - allow retries within same session
    2. Apply keys - true duplicate protection
    
    Daily limits enforced.
    """
    
    def __init__(
        self,
        session_ttl_hours: int = None,
        daily_limit: int = None,
    ):
        self.session_ttl = (session_ttl_hours or SESSION_TTL_HOURS) * 3600
        self.daily_limit = daily_limit or DAILY_LIMIT
        self._lua_session = None
        self._lua_apply = None
        self._lua_daily = None
        self._lua_atomic = None
    
    def _get_lua_session(self):
        if self._lua_session is None:
            self._lua_session = redis_client.client.register_script(LUA_SESSION_CHECK)
        return self._lua_session
    
    def _get_lua_apply(self):
        if self._lua_apply is None:
            self._lua_apply = redis_client.client.register_script(LUA_APPLY_CHECK)
        return self._lua_apply
    
    def _get_lua_daily(self):
        if self._lua_daily is None:
            self._lua_daily = redis_client.client.register_script(LUA_DAILY_INCREMENT)
        return self._lua_daily
    
    def _get_lua_atomic(self):
        if self._lua_atomic is None:
            self._lua_atomic = redis_client.client.register_script(LUA_ATOMIC_CAN_APPLY)
        return self._lua_atomic
    
    # ============== Key Generation ==============
    
    @staticmethod
    def generate_session_key(
        platform: str,
        student_id: str,
        session_id: str = None,
    ) -> str:
        """Generate session idempotency key."""
        sid = session_id or str(uuid.uuid4())[:8]
        return f"idemp:session:{platform.lower()}:{student_id}:{sid}"
    
    @staticmethod
    def generate_apply_key(
        platform: str,
        student_id: str,
        job_id: str,
    ) -> str:
        """Generate application idempotency key."""
        job_hash = hashlib.sha256(job_id.encode()).hexdigest()[:16]
        return f"idemp:apply:{platform.lower()}:{student_id}:{job_hash}"
    
    @staticmethod
    def generate_daily_key(
        platform: str,
        student_id: str,
        date: str = None,
    ) -> str:
        """Generate daily limit counter key."""
        d = date or datetime.now().strftime("%Y-%m-%d")
        return f"idemp:daily:{platform.lower()}:{student_id}:{d}"
    
    @staticmethod
    def generate_run_key(
        platform: str,
        student_id: str,
        run_id: str = None,
    ) -> str:
        """Generate run idempotency key (for the entire run)."""
        rid = run_id or str(uuid.uuid4())[:8]
        return f"idemp:run:{platform.lower()}:{student_id}:{rid}"
    
    # ============== Core Operations ==============
    
    def check_and_start_session(self, session_key: str) -> str:
        """
        Atomically check session and mark as started.
        Allows retries within session window.
        
        Returns:
            None = new session, "started" = in progress, "completed" = done
        """
        try:
            result = self._get_lua_session()(
                keys=[session_key],
                args=[self.session_ttl]
            )
            return result
        except Exception as e:
            logger.warning(f"Session check failed: {e}")
            return None
    
    def check_and_mark_applied(self, apply_key: str) -> str:
        """
        Atomically check apply and mark as completed.
        True duplicate protection.
        
        Returns:
            None = new, "started" = retry allowed, "completed" = already applied
        """
        try:
            result = self._get_lua_apply()(
                keys=[apply_key],
                args=[86400]  # 24 hour TTL for apply
            )
            return result
        except Exception as e:
            logger.warning(f"Apply check failed: {e}")
            return None
    
    def check_daily_limit(self, daily_key: str) -> tuple[bool, int]:
        """
        Check and increment daily counter.
        
        Returns:
            (allowed, current_count)
        """
        try:
            count = self._get_lua_daily()(
                keys=[daily_key],
                args=[self.daily_limit]
            )
            allowed = count != 0
            return allowed, int(count) if count else 0
        except Exception as e:
            logger.warning(f"Daily limit check failed: {e}")
            return True, 0
    
    def clear_session(self, session_key: str) -> bool:
        """Clear session key to allow retry."""
        try:
            redis_client.client.delete(session_key)
            return True
        except Exception:
            return False
    
    def clear_apply(self, apply_key: str) -> bool:
        """Clear apply key (for testing/reset)."""
        try:
            redis_client.client.delete(apply_key)
            return True
        except Exception:
            return False

    def mark_apply_completed(self, apply_key: str) -> bool:
        """Mark an application idempotency key as completed."""
        try:
            redis_client.client.set(apply_key, "completed", ex=86400)
            return True
        except Exception:
            return False
    
    def clear_daily(self, daily_key: str) -> bool:
        """Clear daily counter (for testing)."""
        try:
            redis_client.client.delete(daily_key)
            return True
        except Exception:
            return False
    
    def get_daily_count(self, daily_key: str) -> int:
        """Get current daily application count."""
        try:
            count = redis_client.client.get(daily_key)
            return int(count) if count else 0
        except Exception:
            return 0
    
    def can_apply(
        self,
        platform: str,
        student_id: str,
        job_id: str,
        session_id: str = None,
    ) -> tuple[bool, str, int]:
        """
        Full check: session + apply + daily limit.
        
        Returns:
            (can_apply, reason, daily_count)
            
        Reasons:
            "ok" = apply allowed
            "session_active" = same session in progress
            "already_applied" = job already applied
            "daily_limit" = daily limit reached
        """
        session_key = self.generate_session_key(platform, student_id, session_id)
        apply_key = self.generate_apply_key(platform, student_id, job_id)
        daily_key = self.generate_daily_key(platform, student_id)
        
        try:
            result = self._get_lua_atomic()(
                keys=[apply_key, daily_key, session_key],
                args=[86400, self.daily_limit, self.session_ttl]
            )
            
            status = result[0].decode() if isinstance(result[0], bytes) else result[0]
            count = int(result[1])
            
            if status == "ok":
                return True, "ok", count
            return False, status, count
            
        except Exception as e:
            logger.warning(f"Atomic can_apply failed, falling back: {e}")
            # Fallback to non-atomic check if Lua fails
            return self._can_apply_fallback(platform, student_id, job_id, session_id)

    def _can_apply_fallback(
        self,
        platform: str,
        student_id: str,
        job_id: str,
        session_id: str = None,
    ) -> tuple[bool, str, int]:
        session_key = self.generate_session_key(platform, student_id, session_id)
        apply_key = self.generate_apply_key(platform, student_id, job_id)
        daily_key = self.generate_daily_key(platform, student_id)
    
    def mark_session_completed(self, session_key: str) -> bool:
        """Mark session as completed."""
        try:
            redis_client.client.set(session_key, "completed", ex=self.session_ttl)
            return True
        except Exception:
            return False


# Global instance
idempotency_v2 = IdempotencyManagerV2()


# ============== Convenience Functions ==============

def generate_run_id() -> str:
    """Generate unique run ID for a producer run."""
    return str(uuid.uuid4())[:8]


def can_apply_for_job(
    platform: str,
    student_id: str,
    job_id: str,
    session_id: str = None,
) -> tuple[bool, str, int]:
    """Check if job application is allowed."""
    return idempotency_v2.can_apply(platform, student_id, job_id, session_id)


def mark_session_completed(
    platform: str,
    student_id: str,
    session_id: str,
) -> bool:
    """Mark run session as completed."""
    key = idempotency_v2.generate_session_key(platform, student_id, session_id)
    return idempotency_v2.mark_session_completed(key)


def clear_session_for_run(
    platform: str,
    student_id: str,
    session_id: str,
) -> bool:
    """Clear a specific run/session idempotency key."""
    if not session_id:
        return False
    key = idempotency_v2.generate_session_key(platform, student_id, session_id)
    return idempotency_v2.clear_session(key)


def clear_apply_for_job(
    platform: str,
    student_id: str,
    job_id: str,
) -> bool:
    """Clear a specific apply idempotency key."""
    if not job_id:
        return False
    key = idempotency_v2.generate_apply_key(platform, student_id, job_id)
    return idempotency_v2.clear_apply(key)


def mark_apply_completed_for_job(
    platform: str,
    student_id: str,
    job_id: str,
) -> bool:
    """Mark a specific apply idempotency key as completed."""
    if not job_id:
        return False
    key = idempotency_v2.generate_apply_key(platform, student_id, job_id)
    return idempotency_v2.mark_apply_completed(key)


def get_daily_count(platform: str, student_id: str) -> int:
    """Get today's application count for student."""
    key = idempotency_v2.generate_daily_key(platform, student_id)
    return idempotency_v2.get_daily_count(key)


def clear_all_for_student(platform: str, student_id: str) -> int:
    """Clear all idempotency keys for a student (for testing)."""
    cleared = 0
    patterns = [
        f"idemp:session:{platform.lower()}:{student_id}:*",
        f"idemp:apply:{platform.lower()}:{student_id}:*",
        f"idemp:run:{platform.lower()}:{student_id}:*",
        f"idemp:daily:{platform.lower()}:{student_id}:*",
    ]
    for pattern in patterns:
        keys = redis_client.client.keys(pattern)
        for key in keys:
            redis_client.client.delete(key)
            cleared += 1
    return cleared


def clear_all_duplicates() -> int:
    """Clear ALL idempotency keys (admin function)."""
    cleared = 0
    for pattern in ["idemp:session:*", "idemp:apply:*", "idemp:run:*", "idemp:daily:*"]:
        keys = redis_client.client.keys(pattern)
        for key in keys:
            redis_client.client.delete(key)
            cleared += 1
    logger.info(f"Cleared {cleared} idempotency keys")
    return cleared
