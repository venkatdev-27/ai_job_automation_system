"""
Job Application Repository - Job Automation System
===================================================
CRUD operations for job_applications collection.
"""

from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from database.client import get_collection
from database.models import (
    JobApplication,
    JobApplicationCreate,
    JobApplicationUpdate,
    ApplicationStatus,
)


class ApplicationRepository:
    """Repository for job application operations."""
    
    COLLECTION_NAME = "job_applications"
    
    @property
    def collection(self):
        return get_collection(self.COLLECTION_NAME)
    
    def create(self, application: JobApplicationCreate) -> JobApplication:
        """Create a new job application."""
        doc = application.model_dump()
        doc["created_at"] = datetime.utcnow()
        
        result = self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        
        return JobApplication(**doc)
    
    def get_by_id(self, app_id: str) -> Optional[JobApplication]:
        """Get application by ID."""
        from bson import ObjectId
        try:
            doc = self.collection.find_one({"_id": ObjectId(app_id)})
        except Exception:
            return None
        return JobApplication(**doc) if doc else None
    
    def get_by_student_and_platform(
        self,
        student_id: str,
        platform: str,
        limit: int = 0,
    ) -> List[JobApplication]:
        """Get applications by student and platform."""
        filter_query = {
            "student_id": student_id,
            "platform": platform,
        }
        
        docs = self.collection.find(filter_query).sort("applied_at", -1).limit(limit) if limit > 0 else self.collection.find(filter_query).sort("applied_at", -1)
        
        return [JobApplication(**doc) for doc in docs]
    
    def get_by_status(
        self,
        status: ApplicationStatus,
        platform: Optional[str] = None,
        limit: int = 0,
    ) -> List[JobApplication]:
        """Get applications by status."""
        filter_query = {"status": status}
        if platform:
            filter_query["platform"] = platform
        
        docs = self.collection.find(filter_query).limit(limit) if limit > 0 else self.collection.find(filter_query)
        
        return [JobApplication(**doc) for doc in docs]
    
    def check_duplicate(
        self,
        student_id: str,
        platform: str,
        job_id: str,
    ) -> bool:
        """Check if application already exists."""
        filter_query = {
            "student_id": student_id,
            "platform": platform,
            "job_id": job_id,
        }
        return self.collection.count_documents(filter_query) > 0
    
    def update(
        self,
        app_id: str,
        update: JobApplicationUpdate,
    ) -> Optional[JobApplication]:
        """Update a job application."""
        update_data = {k: v for k, v in update.model_dump().items() if v is not None}
        
        if not update_data:
            return self.get_by_id(app_id)
        
        update_data["updated_at"] = datetime.utcnow()
        
        from bson import ObjectId
        try:
            result = self.collection.find_one_and_update(
                {"_id": ObjectId(app_id)},
                {"$set": update_data},
                return_document=True,
            )
        except Exception:
            return None
        
        return JobApplication(**result) if result else None
    
    def mark_applied(
        self,
        app_id: str,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
    ) -> Optional[JobApplication]:
        """Mark application as applied."""
        update = JobApplicationUpdate(
            status="applied",
            applied_at=datetime.utcnow(),
            job_title=job_title,
            company=company,
        )
        return self.update(app_id, update)
    
    def mark_failed(
        self,
        app_id: str,
        error_message: str,
    ) -> Optional[JobApplication]:
        """Mark application as failed."""
        update = JobApplicationUpdate(
            status="failed",
            error_message=error_message,
        )
        return self.update(app_id, update)
    
    def mark_skipped(
        self,
        app_id: str,
        reason: str = "",
    ) -> Optional[JobApplication]:
        """Mark application as skipped."""
        update = JobApplicationUpdate(
            status="skipped",
            error_message=reason,
        )
        return self.update(app_id, update)
    
    def increment_retry(self, app_id: str) -> int:
        """Increment retry count and return new count."""
        from bson import ObjectId
        try:
            result = self.collection.find_one_and_update(
                {"_id": ObjectId(app_id)},
                {
                    "$inc": {"retry_count": 1},
                    "$set": {"updated_at": datetime.utcnow()},
                },
                return_document=True,
            )
            return result["retry_count"] if result else 0
        except Exception:
            return 0
    
    def delete(self, app_id: str) -> bool:
        """Delete an application."""
        from bson import ObjectId
        try:
            result = self.collection.delete_one({"_id": ObjectId(app_id)})
            return result.deleted_count > 0
        except Exception:
            return False
    
    def count_by_status(self, platform: Optional[str] = None) -> dict:
        """Count applications by status."""
        pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        
        if platform:
            pipeline.insert(0, {"$match": {"platform": platform}})
        
        results = list(self.collection.aggregate(pipeline))
        
        status_counts = {r["_id"]: r["count"] for r in results}
        
        return {
            "pending": status_counts.get("pending", 0),
            "applied": status_counts.get("applied", 0),
            "failed": status_counts.get("failed", 0),
            "skipped": status_counts.get("skipped", 0),
            "duplicate": status_counts.get("duplicate", 0),
        }
    
    def get_recent_applications(
        self,
        student_id: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 100,
    ) -> List[JobApplication]:
        """Get recent applications."""
        filter_query = {}
        if student_id:
            filter_query["student_id"] = student_id
        if platform:
            filter_query["platform"] = platform
        
        docs = (
            self.collection.find(filter_query)
            .sort("applied_at", -1)
            .limit(limit)
        )
        
        return [JobApplication(**doc) for doc in docs]


# Global repository instance
application_repository = ApplicationRepository()


# Convenience functions
def create_application(application: JobApplicationCreate) -> JobApplication:
    """Create a new job application."""
    return application_repository.create(application)


def get_application(app_id: str) -> Optional[JobApplication]:
    """Get application by ID."""
    return application_repository.get_by_id(app_id)


def check_application_duplicate(
    student_id: str,
    platform: str,
    job_id: str,
) -> bool:
    """Check if application is duplicate."""
    return application_repository.check_duplicate(student_id, platform, job_id)


def mark_application_applied(
    app_id: str,
    job_title: Optional[str] = None,
    company: Optional[str] = None,
) -> Optional[JobApplication]:
    """Mark application as applied."""
    return application_repository.mark_applied(app_id, job_title, company)


def mark_application_failed(
    app_id: str,
    error_message: str,
) -> Optional[JobApplication]:
    """Mark application as failed."""
    return application_repository.mark_failed(app_id, error_message)


def get_applications_by_status(
    status: ApplicationStatus,
    platform: Optional[str] = None,
    limit: int = 0,
) -> List[JobApplication]:
    """Get applications by status."""
    return application_repository.get_by_status(status, platform, limit)


def get_recent_applications(
    student_id: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 100,
) -> List[JobApplication]:
    """Get recent applications."""
    return application_repository.get_recent_applications(student_id, platform, limit)