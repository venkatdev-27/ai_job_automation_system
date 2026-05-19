"""
Celery Routes - Job Automation System
=====================================
Task routing to specific queues based on platform.
"""

from celery import signals


def setup_task_routes(app):
    """Configure task routing based on platform."""
    
    # Import task modules to trigger registration
    from tasks import naukri_task, linkedin_task, foundit_task
    
    return {
        "tasks.naukri_task.apply_to_job": {
            "queue": "naukri",
            "routing_key": "naukri",
        },
        "tasks.linkedin_task.apply_to_job": {
            "queue": "linkedin",
            "routing_key": "linkedin",
        },
        "tasks.foundit_task.apply_to_job": {
            "queue": "foundit",
            "routing_key": "foundit",
        },
    }


# Signal handler to configure routes when app is ready
@signals.worker_init.connect
def configure_routes(sender=None, **kwargs):
    """Configure routes on worker initialization."""
    pass  # Routes are already defined in config.py