"""
Metrics Utility - Job Automation System
=========================================
Prometheus metrics for monitoring.
"""

from __future__ import annotations
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from typing import Optional


class Metrics:
    """Prometheus metrics for job automation."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or None
        
        # Task metrics
        self.tasks_total = Counter(
            "job_automation_tasks_total",
            "Total number of tasks",
            ["platform", "status"],
            registry=registry,
        )
        
        self.task_duration = Histogram(
            "job_automation_task_duration_seconds",
            "Task duration in seconds",
            ["platform"],
            registry=registry,
        )
        
        # Application metrics
        self.applications_total = Counter(
            "job_automation_applications_total",
            "Total job applications",
            ["platform", "status"],
            registry=registry,
        )
        
        # Browser metrics
        self.active_browsers = Gauge(
            "job_automation_active_browsers",
            "Number of active browser instances",
            registry=registry,
        )
        
        # Queue metrics
        self.queue_tasks = Gauge(
            "job_automation_queue_tasks",
            "Number of tasks in queue",
            ["platform"],
            registry=registry,
        )
        
        # Circuit breaker metrics
        self.circuit_state = Gauge(
            "job_automation_circuit_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            ["platform"],
            registry=registry,
        )
        
        # Rate limiter metrics
        self.rate_limit_wait = Gauge(
            "job_automation_rate_limit_wait_seconds",
            "Time waiting for rate limit",
            ["platform"],
            registry=registry,
        )
    
    def record_task(self, platform: str, status: str):
        """Record a task execution."""
        self.tasks_total.labels(platform=platform, status=status).inc()
    
    def record_task_duration(self, platform: str, duration: float):
        """Record task duration."""
        self.task_duration.labels(platform=platform).observe(duration)
    
    def record_application(self, platform: str, status: str):
        """Record a job application."""
        self.applications_total.labels(platform=platform, status=status).inc()
    
    def set_active_browsers(self, count: int):
        """Set active browser count."""
        self.active_browsers.set(count)
    
    def set_queue_tasks(self, platform: str, count: int):
        """Set queue task count."""
        self.queue_tasks.labels(platform=platform).set(count)
    
    def set_circuit_state(self, platform: str, state: int):
        """Set circuit breaker state."""
        self.circuit_state.labels(platform=platform).set(state)
    
    def set_rate_limit_wait(self, platform: str, wait_time: float):
        """Set rate limit wait time."""
        self.rate_limit_wait.labels(platform=platform).set(wait_time)
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics in text format."""
        return generate_latest(self.registry)


# Global metrics instance
metrics = Metrics()


# Convenience functions
def record_task(platform: str, status: str):
    """Record task execution."""
    metrics.record_task(platform, status)


def record_task_duration(platform: str, duration: float):
    """Record task duration."""
    metrics.record_task_duration(platform, duration)


def record_application(platform: str, status: str):
    """Record application."""
    metrics.record_application(platform, status)


def set_active_browsers(count: int):
    """Set active browser count."""
    metrics.set_active_browsers(count)


def set_circuit_state(platform: str, state: int):
    """Set circuit breaker state."""
    metrics.set_circuit_state(platform, state)