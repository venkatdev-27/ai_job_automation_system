"""
Failure Classification System - Job Automation System
===================================================
Classifies errors into categories for smart retry decisions.
"""

from __future__ import annotations
import logging
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class FailureType(Enum):
    NETWORK_ERROR = "network"
    SESSION_EXPIRED = "session_expired"
    ALREADY_APPLIED = "already_applied"
    CHALLENGE_BLOCKED = "challenge"
    RATE_LIMIT = "rate_limit"
    FORM_ERROR = "form_error"
    CAPTCHA = "captcha"
    PLATFORM_DOWN = "platform_down"
    UNKNOWN = "unknown"


class FailureClassifier:
    """
    Classifies errors into actionable categories.
    Determines retry strategy based on failure type.
    """

    RETRY_STRATEGY = {
        FailureType.NETWORK_ERROR: {"retry": True, "max_attempts": 3, "backoff": "exponential"},
        FailureType.SESSION_EXPIRED: {"retry": True, "max_attempts": 2, "backoff": "linear"},
        FailureType.ALREADY_APPLIED: {"retry": False, "max_attempts": 0, "backoff": None},
        FailureType.CHALLENGE_BLOCKED: {"retry": False, "max_attempts": 0, "backoff": None},
        FailureType.RATE_LIMIT: {"retry": True, "max_attempts": 3, "backoff": "long"},
        FailureType.FORM_ERROR: {"retry": True, "max_attempts": 2, "backoff": "linear"},
        FailureType.CAPTCHA: {"retry": False, "max_attempts": 0, "backoff": None},
        FailureType.PLATFORM_DOWN: {"retry": True, "max_attempts": 5, "backoff": "exponential"},
        FailureType.UNKNOWN: {"retry": True, "max_attempts": 2, "backoff": "linear"},
    }

    ERROR_PATTERNS = {
        FailureType.NETWORK_ERROR: [
            "connection", "timeout", "network", "dns", "econnreset",
            "socket", "ENOTFOUND", "ECONNREFUSED", "503",
        ],
        FailureType.SESSION_EXPIRED: [
            "session", "unauthorized", "401", "login again", "please sign in",
            "session expired", "auth", "token",
        ],
        FailureType.ALREADY_APPLIED: [
            "already applied", "already applied to this job", "duplicate",
            "you have already applied", "application received",
        ],
        FailureType.CHALLENGE_BLOCKED: [
            "checkpoint", "challenge", "security alert", "suspicious",
        ],
        FailureType.RATE_LIMIT: [
            "429", "too many requests", "rate limit", "please wait",
            "slow down", "maximum attempts",
        ],
        FailureType.FORM_ERROR: [
            "required field", "invalid", "validation", "fill in",
            "mandatory", "cannot be empty",
        ],
        FailureType.CAPTCHA: [
            "captcha", "recaptcha", "verify you're human", "robot",
        ],
        FailureType.PLATFORM_DOWN: [
            "502", "503", "504", "site down", "maintenance",
            "temporarily unavailable",
        ],
    }

    @classmethod
    def classify(cls, error_message: str) -> FailureType:
        error_lower = (error_message or "").lower()

        for failure_type, patterns in cls.ERROR_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in error_lower:
                    logger.info(f"Classified error as: {failure_type.value}")
                    return failure_type

        logger.warning(f"Unknown error type: {error_message[:100]}")
        return FailureType.UNKNOWN

    @classmethod
    def should_retry(cls, failure_type: FailureType) -> bool:
        return cls.RETRY_STRATEGY[failure_type]["retry"]

    @classmethod
    def get_max_attempts(cls, failure_type: FailureType) -> int:
        return cls.RETRY_STRATEGY[failure_type]["max_attempts"]

    @classmethod
    def get_backoff_type(cls, failure_type: FailureType) -> str:
        return cls.RETRY_STRATEGY[failure_type]["backoff"]


def classify_failure(error_message: str) -> FailureType:
    return FailureClassifier.classify(error_message)


def should_retry(failure_type: FailureType) -> bool:
    return FailureClassifier.should_retry(failure_type)


def get_retry_strategy(failure_type: FailureType) -> dict:
    return FailureClassifier.RETRY_STRATEGY[failure_type]