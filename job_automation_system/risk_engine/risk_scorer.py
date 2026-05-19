import os
import time
import random
from typing import Dict, Any, Optional
import redis
from datetime import datetime, timedelta


class RiskScorer:
    """Risk scoring engine to dynamically adjust automation behavior."""
    
    def __init__(self):
        self._redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        try:
            redis_host = os.environ.get("REDIS_HOST", "redis")
            redis_port = int(os.environ.get("REDIS_PORT", "6379"))
            self._redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=1,
                decode_responses=True
            )
        except Exception:
            pass
    
    def _get_risk_key(self, student_id: str) -> str:
        return f"risk_score:{student_id}"
    
    def _get_cooldown_key(self, student_id: str) -> str:
        return f"cooldown:{student_id}"
    
    def _get_login_key(self, student_id: str) -> str:
        return f"last_login:{student_id}"
    
    def get_risk_score(self, student_id: str) -> int:
        """Get current risk score (0-100) for a student."""
        try:
            if self._redis_client:
                score = self._redis_client.hget(self._get_risk_key(student_id), "score")
                return int(score) if score else 0
            return 0
        except Exception:
            return 0
    
    def increment_captcha(self, student_id: str):
        """Increase risk score when CAPTCHA is detected."""
        try:
            if self._redis_client:
                key = self._get_risk_key(student_id)
                current = self.get_risk_score(student_id)
                new_score = min(100, current + 25)
                self._redis_client.hset(key, mapping={
                    "score": str(new_score),
                    "last_captcha": str(int(time.time())),
                    "captcha_count": str(
                        int(self._redis_client.hget(key, "captcha_count") or 0) + 1
                    )
                })
                self._redis_client.expire(key, 86400 * 7)
        except Exception:
            pass
    
    def increment_login_failure(self, student_id: str):
        """Increase risk score when login fails."""
        try:
            if self._redis_client:
                key = self._get_risk_key(student_id)
                current = self.get_risk_score(student_id)
                new_score = min(100, current + 15)
                self._redis_client.hset(key, mapping={
                    "score": str(new_score),
                    "last_failure": str(int(time.time())),
                    "failure_count": str(
                        int(self._redis_client.hget(key, "failure_count") or 0) + 1
                    )
                })
                self._redis_client.expire(key, 86400 * 7)
        except Exception:
            pass
    
    def decrement_risk(self, student_id: str, amount: int = 10):
        """Decrease risk score after successful actions."""
        try:
            if self._redis_client:
                key = self._get_risk_key(student_id)
                current = self.get_risk_score(student_id)
                new_score = max(0, current - amount)
                self._redis_client.hset(key, "score", str(new_score))
                self._redis_client.expire(key, 86400 * 7)
        except Exception:
            pass
    
    def set_cooldown(self, student_id: str, hours: int = 24):
        """Set cooldown period for a student after too many CAPTCHAs."""
        try:
            if self._redis_client:
                key = self._get_cooldown_key(student_id)
                cooldown_until = int(time.time()) + (hours * 3600)
                self._redis_client.set(key, cooldown_until, ex=86400 * 2)
        except Exception:
            pass
    
    def is_in_cooldown(self, student_id: str) -> bool:
        """Check if student is in cooldown period."""
        try:
            if self._redis_client:
                key = self._get_cooldown_key(student_id)
                cooldown_until = self._redis_client.get(key)
                if cooldown_until and int(cooldown_until) > int(time.time()):
                    return True
            return False
        except Exception:
            return False
    
    def get_cooldown_remaining(self, student_id: str) -> int:
        """Get remaining cooldown seconds."""
        try:
            if self._redis_client:
                key = self._get_cooldown_key(student_id)
                cooldown_until = self._redis_client.get(key)
                if cooldown_until:
                    remaining = int(cooldown_until) - int(time.time())
                    return max(0, remaining)
            return 0
        except Exception:
            return 0
    
    def set_last_login(self, student_id: str):
        """Record last login time for rate limiting."""
        try:
            if self._redis_client:
                key = self._get_login_key(student_id)
                self._redis_client.set(key, int(time.time()), ex=86400 * 7)
        except Exception:
            pass
    
    def get_last_login(self, student_id: str) -> Optional[int]:
        """Get timestamp of last login attempt."""
        try:
            if self._redis_client:
                key = self._get_login_key(student_id)
                timestamp = self._redis_client.get(key)
                return int(timestamp) if timestamp else None
            return None
        except Exception:
            return None
    
    def can_login(self, student_id: str, min_interval_hours: int = 4) -> bool:
        """Check if enough time has passed since last login."""
        last_login = self.get_last_login(student_id)
        if not last_login:
            return True
        
        elapsed = time.time() - last_login
        return elapsed > (min_interval_hours * 3600)
    
    def get_throttle_delay(self, student_id: str) -> float:
        """Get adaptive throttle delay based on risk score."""
        score = self.get_risk_score(student_id)
        
        if score >= 80:
            return random.uniform(5, 10)
        elif score >= 60:
            return random.uniform(3, 6)
        elif score >= 40:
            return random.uniform(2, 4)
        elif score >= 20:
            return random.uniform(1, 2)
        else:
            return random.uniform(0.5, 1)
    
    def get_risk_factors(self, student_id: str) -> Dict[str, Any]:
        """Get detailed risk factors for a student."""
        try:
            if self._redis_client:
                key = self._get_risk_key(student_id)
                data = self._redis_client.hgetall(key)
                return {
                    "score": int(data.get("score", 0)),
                    "captcha_count": int(data.get("captcha_count", 0)),
                    "failure_count": int(data.get("failure_count", 0)),
                }
            return {"score": 0, "captcha_count": 0, "failure_count": 0}
        except Exception:
            return {"score": 0, "captcha_count": 0, "failure_count": 0}
    
    def reset_risk(self, student_id: str):
        """Reset risk score for a student."""
        try:
            if self._redis_client:
                self._redis_client.delete(self._get_risk_key(student_id))
                self._redis_client.delete(self._get_cooldown_key(student_id))
        except Exception:
            pass


risk_scorer = RiskScorer()