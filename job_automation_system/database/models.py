"""
Data Models - Job Automation System
===================================
MongoDB document schemas using Pydantic for validation.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal, Any, Annotated
from pydantic import BaseModel, Field, EmailStr, BeforeValidator, model_validator


def validate_object_id(v: Any) -> str:
    """Convert MongoDB ObjectId to string for Pydantic."""
    if hasattr(v, "__str__") and not isinstance(v, str):
        return str(v)
    return v


PyObjectId = Annotated[str, BeforeValidator(validate_object_id)]


# ==================== Student Models ====================

class PlatformCredentials(BaseModel):
    """Credentials for a specific platform."""
    email: Optional[str] = None
    username: Optional[str] = None
    password: str  # Will be encrypted in storage


class StudentCredentials(BaseModel):
    """All platform credentials for a student."""
    naukri: Optional[PlatformCredentials] = None
    linkedin: Optional[PlatformCredentials] = None
    foundit: Optional[PlatformCredentials] = None
    indeed: Optional[PlatformCredentials] = None
    internshala: Optional[PlatformCredentials] = None


class ResumeUrls(BaseModel):
    """Resume URLs per variant."""
    frontend: Optional[str] = None
    backend: Optional[str] = None
    fullstack: Optional[str] = None
    python: Optional[str] = None
    java: Optional[str] = None
    react: Optional[str] = None

    class Config:
        extra = "allow"


class StudentBase(BaseModel):
    """Base student model."""
    student_id: str = Field(...)
    full_name: Optional[str] = Field(default=None, alias="full_name")
    name: str
    email: EmailStr
    phone: str = Field(..., pattern=r"^\+?[\d\s\-]+$")
    location: str = "India"
    skills: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    candidate_titles: list[str] = Field(default_factory=list)
    resume_urls: Optional[ResumeUrls] = None
    credentials: Optional[StudentCredentials] = None
    active: bool = True
    warmup_complete: bool = False
    custom_roles: Any = Field(default_factory=dict)
    resume_variants: dict[str, dict] = Field(default_factory=dict)
    warmup_resumes_generated: int = 0
    last_warmup: Optional[str] = None

    @model_validator(mode="after")
    def populate_full_name(self) -> "StudentBase":
        """Backfill full_name from name for legacy documents that predate the field."""
        if not self.full_name:
            self.full_name = self.name
        return self


class StudentCreate(StudentBase):
    """Model for creating a new student."""
    pass


class Student(StudentBase):
    """Full student model with timestamps."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True
        populate_by_name = True


class StudentUpdate(BaseModel):
    """Model for updating a student."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    skills: Optional[list[str]] = None
    preferred_locations: Optional[list[str]] = None
    candidate_titles: Optional[list[str]] = None
    resume_urls: Optional[ResumeUrls] = None
    credentials: Optional[StudentCredentials] = None
    active: Optional[bool] = None
    warmup_complete: Optional[bool] = None
    custom_roles: Optional[dict[str, Any]] = None
    resume_variants: Optional[dict[str, dict]] = None
    warmup_resumes_generated: Optional[int] = None
    last_warmup: Optional[str] = None


# ==================== Job Application Models ====================

ApplicationStatus = Literal["pending", "applied", "failed", "skipped", "duplicate"]


class JobApplicationBase(BaseModel):
    """Base job application model."""
    student_id: str
    platform: str
    job_id: str = Field(..., description="Unique platform job ID")
    job_url: str
    job_title: Optional[str] = None
    company: Optional[str] = None
    status: ApplicationStatus = "pending"
    resume_variant: Optional[str] = None


class JobApplicationCreate(JobApplicationBase):
    """Model for creating a job application."""
    pass


class JobApplication(JobApplicationBase):
    """Full job application model with timestamps."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    applied_at: Optional[datetime] = None
    retry_count: int = 0
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True
        populate_by_name = True


class JobApplicationUpdate(BaseModel):
    """Model for updating a job application."""
    status: Optional[ApplicationStatus] = None
    applied_at: Optional[datetime] = None
    retry_count: Optional[int] = None
    error_message: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None


# ==================== Task Execution Models ====================

TaskStatus = Literal["started", "completed", "failed", "retrying"]


class TaskExecutionBase(BaseModel):
    """Base task execution model."""
    task_id: str = Field(..., description="Celery task ID")
    student_id: str
    platform: str
    job_url: str
    status: TaskStatus = "started"


class TaskExecutionCreate(TaskExecutionBase):
    """Model for creating a task execution."""
    pass


class TaskExecution(TaskExecutionBase):
    """Full task execution model with timestamps."""
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class TaskExecutionUpdate(BaseModel):
    """Model for updating a task execution."""
    status: Optional[TaskStatus] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None


# ==================== Metrics/Aggregation Models ====================

class PlatformStats(BaseModel):
    """Statistics for a platform."""
    platform: str
    total_applied: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_duplicate: int = 0


class StudentStats(BaseModel):
    """Statistics for a student."""
    student_id: str
    platform: str
    total_applied: int = 0
    total_failed: int = 0