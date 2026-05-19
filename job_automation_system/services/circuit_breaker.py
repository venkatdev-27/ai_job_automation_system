"""
Circuit Breaker Service - Job Automation System
================================================
Prevents repeated failures by temporarily pausing platform tasks.
Enhanced with state transition logging.
"""

from __future__ import annotations
import time
import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from services.redis_client import redis_client
from config import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    timeout: int = 300
    success_threshold: int = 2


class CircuitBreaker:
    """
    Circuit breaker with logging for observability.
    """
    
    def __init__(self, platform: str, config: Optional[CircuitBreakerConfig] = None):
        self.platform = platform.lower()
        self.config = config or CircuitBreakerConfig(
            failure_threshold=settings.circuit_breaker_threshold,
            timeout=settings.circuit_breaker_timeout,
        )
        self._key_prefix = f"circuit:{self.platform}"
        self._last_state = CircuitState.CLOSED
    
    @property
    def _state_key(self) -> str:
        return f"{self._key_prefix}:state"
    
    @property
    def _failure_key(self) -> str:
        return f"{self._key_prefix}:failures"
    
    @property
    def _last_failure_key(self) -> str:
        return f"{self._key_prefix}:last_failure"
    
    @property
    def _success_key(self) -> str:
        return f"{self._key_prefix}:successes"
    
    def get_state(self) -> CircuitState:
        try:
            state = redis_client.client.get(self._state_key)
            if state is None:
                return CircuitState.CLOSED
            return CircuitState(state)
        except Exception:
            return CircuitState.CLOSED
    
    def set_state(self, state: CircuitState):
        try:
            old_state = self.get_state()
            if old_state != state:
                logger.info(f"Circuit[{self.platform}]: {old_state.value} -> {state.value}")
                self._last_state = old_state
            
            if state == CircuitState.CLOSED:
                redis_client.client.delete(self._failure_key)
                redis_client.client.delete(self._success_key)
            
            redis_client.client.setex(self._state_key, self.config.timeout, state.value)
        except Exception as e:
            logger.warning(f"Circuit set_state failed: {e}")
    
    def record_failure(self):
        try:
            pipe = redis_client.client.pipeline()
            pipe.incr(self._failure_key)
            pipe.set(self._last_failure_key, time.time(), ex=self.config.timeout)
            pipe.get(self._failure_key)
            results = pipe.execute()
            
            failure_count = int(results[2]) if results[2] else 1
            
            if failure_count >= self.config.failure_threshold:
                self.set_state(CircuitState.OPEN)
                logger.warning(
                    f"Circuit[{self.platform}] OPEN after {failure_count} failures"
                )
        except Exception:
            pass
    
    def record_success(self):
        try:
            state = self.get_state()
            
            if state == CircuitState.HALF_OPEN:
                pipe = redis_client.client.pipeline()
                pipe.incr(self._success_key)
                pipe.get(self._success_key)
                results = pipe.execute()
                
                success_count = int(results[1]) if results[1] else 1
                
                if success_count >= self.config.success_threshold:
                    self.set_state(CircuitState.CLOSED)
                    logger.info(
                        f"Circuit[{self.platform}] CLOSED after {success_count} successes"
                    )
        except Exception:
            pass
    
    def can_execute(self) -> bool:
        state = self.get_state()
        
        if state == CircuitState.CLOSED:
            return True
        
        if state == CircuitState.OPEN:
            try:
                last_failure = redis_client.client.get(self._last_failure_key)
                if last_failure:
                    elapsed = time.time() - float(last_failure)
                    if elapsed >= self.config.timeout:
                        self.set_state(CircuitState.HALF_OPEN)
                        logger.info(f"Circuit[{self.platform}] HALF_OPEN (timeout)")
                        return True
            except Exception:
                pass
            return False
        
        return state == CircuitState.HALF_OPEN
    
    def get_wait_time(self) -> float:
        try:
            last_failure = redis_client.client.get(self._last_failure_key)
            if last_failure:
                elapsed = time.time() - float(last_failure)
                remaining = self.config.timeout - elapsed
                return max(0, remaining)
        except Exception:
            pass
        return 0
    
    def reset(self):
        try:
            keys = [
                self._state_key,
                self._failure_key,
                self._last_failure_key,
                self._success_key,
            ]
            redis_client.client.delete(*keys)
        except Exception:
            pass
    
    def get_stats(self) -> dict:
        try:
            state = self.get_state().value
            failures = redis_client.client.get(self._failure_key) or "0"
            return {
                "platform": self.platform,
                "state": state,
                "failures": int(failures),
                "last_failure": redis_client.client.get(self._last_failure_key),
            }
        except Exception:
            return {"platform": self.platform, "state": "unknown"}


_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(platform: str) -> CircuitBreaker:
    platform = platform.lower()
    
    if platform not in _circuit_breakers:
        _circuit_breakers[platform] = CircuitBreaker(platform)
    
    return _circuit_breakers[platform]


def check_circuit(platform: str) -> tuple[bool, Optional[str]]:
    breaker = get_circuit_breaker(platform)
    
    if breaker.can_execute():
        return True, None
    
    wait_time = breaker.get_wait_time()
    return False, f"Circuit open, wait {wait_time:.0f}s"


def record_platform_failure(platform: str):
    get_circuit_breaker(platform).record_failure()


def record_platform_success(platform: str):
    get_circuit_breaker(platform).record_success()


def get_all_circuit_stats() -> list[dict]:
    return [cb.get_stats() for cb in _circuit_breakers.values()]