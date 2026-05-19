"""
Database Package - Job Automation System
=========================================
"""

from database.client import mongodb_client, get_database, get_collection, close_database
from database.models import (
    Student,
    StudentCreate,
    StudentUpdate,
    JobApplication,
    JobApplicationCreate,
    JobApplicationUpdate,
    TaskExecution,
    TaskExecutionCreate,
    TaskExecutionUpdate,
    ApplicationStatus,
    TaskStatus,
)
from database.student_repo import (
    StudentRepository,
    student_repository,
    create_student,
    get_student,
    get_all_students,
    update_student,
    delete_student,
    count_students,
    get_active_students,
)
from database.application_repo import (
    ApplicationRepository,
    application_repository,
    create_application,
    get_application,
    check_application_duplicate,
    mark_application_applied,
    mark_application_failed,
    get_applications_by_status,
    get_recent_applications,
)
from database.credentials import (
    build_dynamic_runtime_settings,
    get_student_credentials,
    set_student_credentials,
    rotate_credentials,
    RuntimeSettings,
)

__all__ = [
    # Client
    "mongodb_client",
    "get_database",
    "get_collection",
    "close_database",
    # Models
    "Student",
    "StudentCreate",
    "StudentUpdate",
    "JobApplication",
    "JobApplicationCreate",
    "JobApplicationUpdate",
    "TaskExecution",
    "TaskExecutionCreate",
    "TaskExecutionUpdate",
    "ApplicationStatus",
    "TaskStatus",
    # Student Repository
    "StudentRepository",
    "student_repository",
    "create_student",
    "get_student",
    "get_all_students",
    "update_student",
    "delete_student",
    "count_students",
    "get_active_students",
    # Application Repository
    "ApplicationRepository",
    "application_repository",
    "create_application",
    "get_application",
    "check_application_duplicate",
    "mark_application_applied",
    "mark_application_failed",
    "get_applications_by_status",
    "get_recent_applications",
]