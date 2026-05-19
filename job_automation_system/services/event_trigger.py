"""
Event-Based Triggering System - Job Automation System
==================================================
Triggers next platform after previous completes.
Better than fixed cron - runs when work is available.
"""

from __future__ import annotations
import logging
from typing import Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    PLATFORM_COMPLETED = "platform_completed"
    STUDENT_COMPLETED = "student_completed"
    ALL_JOBS_PROCESSED = "all_jobs_processed"
    RATE_LIMIT_CLEARED = "rate_limit_cleared"


@dataclass
class Event:
    event_type: EventType
    platform: str
    student_id: Optional[str]
    timestamp: datetime
    data: dict


class EventBus:
    """
    Simple event bus for triggering downstream tasks.
    """

    def __init__(self):
        self._subscribers: dict[EventType, list[Callable]] = {}
        self._event_log: list[Event] = []

    def subscribe(self, event_type: EventType, callback: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.info(f"Subscribed to {event_type.value}")

    def publish(self, event: Event):
        logger.info(f"Event published: {event.event_type.value} | {event.platform}")
        self._event_log.append(event)

        if len(self._event_log) > 100:
            self._event_log = self._event_log[-50:]

        if event.event_type in self._subscribers:
            for callback in self._subscribers[event.event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")

    def get_recent_events(self, event_type: Optional[EventType] = None,
                          limit: int = 10) -> list[Event]:
        events = self._event_log
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]


class EventTriggeredScheduler:
    """
    Scheduler that triggers next platform when current completes.
    Instead of fixed cron, runs when work is available.
    """

    PLATFORM_ORDER = ["naukri", "foundit", "linkedin"]

    def __init__(self):
        self._event_bus = EventBus()
        self._setup_subscriptions()

    def _setup_subscriptions(self):
        self._event_bus.subscribe(
            EventType.PLATFORM_COMPLETED,
            self._on_platform_completed
        )

    def _on_platform_completed(self, event: Event):
        current_idx = self.PLATFORM_ORDER.index(event.platform)
        next_idx = (current_idx + 1) % len(self.PLATFORM_ORDER)
        next_platform = self.PLATFORM_ORDER[next_idx]

        logger.info(f"Triggering {next_platform} after {event.platform} completed")
        self._trigger_platform(next_platform)

    def _trigger_platform(self, platform: str):
        try:
            from celery import group
            from tasks.producer_platform_task import run_platform

            task = run_platform.s(platform=platform, jobs_per_student=10)
            logger.info(f"Queued {platform} platform task")
        except Exception as e:
            logger.warning(f"Failed to trigger {platform}: {e}")

    def publish_platform_completed(self, platform: str, student_id: Optional[str] = None):
        event = Event(
            event_type=EventType.PLATFORM_COMPLETED,
            platform=platform,
            student_id=student_id,
            timestamp=datetime.utcnow(),
            data={}
        )
        self._event_bus.publish(event)

    def publish_student_completed(self, student_id: str, platform: str):
        event = Event(
            event_type=EventType.STUDENT_COMPLETED,
            platform=platform,
            student_id=student_id,
            timestamp=datetime.utcnow(),
            data={}
        )
        self._event_bus.publish(event)


event_bus = EventBus()
scheduler = EventTriggeredScheduler()


def publish_platform_completed(platform: str, student_id: Optional[str] = None):
    scheduler.publish_platform_completed(platform, student_id)


def publish_student_completed(student_id: str, platform: str):
    scheduler.publish_student_completed(student_id, platform)