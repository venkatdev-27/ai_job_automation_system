"""
Services Package - Job Automation System
=======================================
"""

from services.redis_client import redis_client, RedisClient
from services.rate_limiter import RateLimiter, get_rate_limiter
from services.idempotency import (
    IdempotencyManager,
    idempotency_manager,
    check_idempotency,
    mark_idempotency_started,
    mark_idempotency_completed,
)
from services.distributed_lock import (
    DistributedLock,
    acquire_task_lock,
    acquire_student_platform_lock,
    acquire_student_session_lock,
    release_task_lock,
)
from services.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    get_circuit_breaker,
    check_circuit,
    record_platform_failure,
    record_platform_success,
)
from services.browser_semaphore import (
    BrowserSemaphore,
    browser_semaphore,
    acquire_browser,
    release_browser,
    get_browser_count,
    get_available_browsers,
)
from services.student_rate_limiter import StudentRateLimiter, student_rate_limiter

# Backward-compatible alias used by older smoke scripts.
student_lock = acquire_student_platform_lock


from services.failure_classifier import (
    FailureClassifier,
    FailureType,
    classify_failure,
    should_retry,
    get_retry_strategy,
)
from services.adaptive_rate_limiter import (
    AdaptiveRateLimiter,
    get_adaptive_limiter,
    record_success,
    record_failure,
    get_delay,
)

from services.monitoring import (
    MonitoringService,
    PlatformStats,
    record_application,
    get_stats,
    get_all_stats,
    get_daily_summary,
)

from services.daily_caps import (
    DailyCapManager,
    check_daily_cap,
    record_daily_application,
    get_remaining_applications,
)

from services.platform_semaphore import (
    PlatformSemaphore,
    acquire_platform_slot,
    release_platform_slot,
)

from services.event_trigger import (
    EventBus,
    Event,
    EventType,
    scheduler,
    publish_platform_completed,
    publish_student_completed,
)

__all__ = [
    "redis_client",
    "RedisClient",
    "RateLimiter",
    "get_rate_limiter",
    "IdempotencyManager",
    "idempotency_manager",
    "check_idempotency",
    "mark_idempotency_started",
    "mark_idempotency_completed",
    "DistributedLock",
    "acquire_task_lock",
    "acquire_student_platform_lock",
    "acquire_student_session_lock",
    "release_task_lock",
    "CircuitBreaker",
    "CircuitState",
    "get_circuit_breaker",
    "check_circuit",
    "record_platform_failure",
    "record_platform_success",
    "BrowserSemaphore",
    "browser_semaphore",
    "acquire_browser",
    "release_browser",
    "get_browser_count",
    "get_available_browsers",
    "PlatformSemaphore",
    "acquire_platform_slot",
    "release_platform_slot",

    "StudentRateLimiter",
    "student_rate_limiter",
    "student_lock",

    "FailureClassifier",
    "FailureType",
    "classify_failure",
    "should_retry",
    "get_retry_strategy",
    "AdaptiveRateLimiter",
    "get_adaptive_limiter",
    "record_success",
    "record_failure",
    "get_delay",

    "MonitoringService",
    "PlatformStats",
    "record_application",
    "get_stats",
    "get_all_stats",
    "get_daily_summary",

    "EventBus",
    "Event",
    "EventType",
    "scheduler",
    "publish_platform_completed",
    "publish_student_completed",
]
