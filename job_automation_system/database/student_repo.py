"""
Student Repository - Job Automation System
============================================
CRUD operations for students collection.
"""

from __future__ import annotations
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
from database.client import get_collection
from database.models import Student, StudentCreate, StudentUpdate


class StudentRepository:
    """Repository for student operations."""
    
    COLLECTION_NAME = "students"
    
    @property
    def collection(self):
        return get_collection(self.COLLECTION_NAME)
    
    def create(self, student: StudentCreate) -> Student:
        """Create a new student."""
        doc = student.model_dump()
        doc["active"] = True
        doc["created_at"] = datetime.now(timezone.utc)
        doc["updated_at"] = datetime.now(timezone.utc)
        
        result = self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        
        return Student(**doc)
    
    def get_by_id(self, student_id: str) -> Optional[Student]:
        """Get student by ID."""
        doc = self.collection.find_one({"student_id": student_id})
        return Student(**doc) if doc else None
    
    def get_by_email(self, email: str) -> Optional[Student]:
        """Get student by email."""
        doc = self.collection.find_one({"email": email})
        return Student(**doc) if doc else None
    
    def get_all(self, active_only: bool = True, limit: int = 0) -> List[Student]:
        """Get all students."""
        filter_query = {"active": True} if active_only else {}
        
        docs = self.collection.find(filter_query).limit(limit) if limit > 0 else self.collection.find(filter_query)
        
        return [Student(**doc) for doc in docs]
    
    def update(self, student_id: str, update: StudentUpdate | dict) -> Optional[Student]:
        """Update a student."""
        if isinstance(update, dict):
            update_data = {k: v for k, v in update.items() if v is not None}
        else:
            update_data = {k: v for k, v in update.model_dump().items() if v is not None}
        
        if not update_data:
            return self.get_by_id(student_id)
        
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        result = self.collection.find_one_and_update(
            {"student_id": student_id},
            {"$set": update_data},
            return_document=True,
        )
        
        return Student(**result) if result else None
    
    def delete(self, student_id: str) -> bool:
        """Delete a student (soft delete - set active to False)."""
        result = self.collection.update_one(
            {"student_id": student_id},
            {"$set": {"active": False, "updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0
    
    def hard_delete(self, student_id: str) -> bool:
        """Permanently delete a student."""
        result = self.collection.delete_one({"student_id": student_id})
        return result.deleted_count > 0
    
    def count(self, active_only: bool = True) -> int:
        """Count students."""
        filter_query = {"active": True} if active_only else {}
        return self.collection.count_documents(filter_query)
    
    def get_active_students(self, limit: int = 0, student_id: Optional[str] = None) -> List[Student]:
        """Get all active students, optionally filtered by student_id."""
        if student_id:
            student = self.get_by_id(student_id)
            if student and student.active:
                return [student]
            return []
        return self.get_all(active_only=True, limit=limit)
    
    def get_by_skills(self, skills: List[str], limit: int = 0) -> List[Student]:
        """Get students with specific skills."""
        filter_query = {
            "active": True,
            "skills": {"$in": skills},
        }
        
        docs = self.collection.find(filter_query).limit(limit) if limit > 0 else self.collection.find(filter_query)
        
        return [Student(**doc) for doc in docs]


# Global repository instance
student_repository = StudentRepository()


# Convenience functions
def create_student(student: StudentCreate) -> Student:
    """Create a new student."""
    return student_repository.create(student)


def get_student(student_id: str) -> Optional[Student]:
    """Get student by ID."""
    return student_repository.get_by_id(student_id)


def get_all_students(active_only: bool = True, limit: int = 0) -> List[Student]:
    """Get all students."""
    return student_repository.get_all(active_only, limit)


def update_student(student_id: str, update: StudentUpdate) -> Optional[Student]:
    """Update a student."""
    return student_repository.update(student_id, update)


def delete_student(student_id: str) -> bool:
    """Delete a student."""
    return student_repository.delete(student_id)


def count_students(active_only: bool = True) -> int:
    """Count students."""
    return student_repository.count(active_only)


def get_active_students(limit: int = 0, student_id: Optional[str] = None) -> List[Student]:
    """Get active students, optionally filtered by student_id."""
    return student_repository.get_active_students(limit, student_id)