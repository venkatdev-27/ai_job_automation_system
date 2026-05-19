"""
Seed Data - Job Automation System
==================================
Script to seed sample students into MongoDB for testing.
"""

from __future__ import annotations
import sys
import logging

sys.path.insert(0, ".")

from database import create_student, get_student, count_students
from database.models import StudentCreate, ResumeUrls, StudentCredentials, PlatformCredentials


logger = logging.getLogger(__name__)


SAMPLE_STUDENTS = [
    {
        "student_id": "STU001",
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+91-9876543210",
        "location": "Bangalore",
        "skills": ["python", "django", "react", "javascript", "sql", "postgresql"],
        "preferred_locations": ["Bangalore", "Hyderabad", "Pune"],
        "candidate_titles": ["Python Developer", "Backend Developer", "Full Stack Developer"],
        "resume_urls": {
            "frontend": "https://res.cloudinary.com/dco7jegub/raw/upload/v1/STU001_frontend.pdf",
            "backend": "https://res.cloudinary.com/dco7jegub/raw/upload/v1/STU001_backend.pdf",
            "fullstack": "https://res.cloudinary.com/dco7jegub/raw/upload/v1/STU001_fullstack.pdf",
        },
        "credentials": {
            "naukri": {"email": "john.doe@naukri.com", "password": "encrypted_password"},
            "linkedin": {"email": "john.doe.linkedin@gmail.com", "password": "encrypted_password"},
        },
    },
    {
        "student_id": "STU002",
        "name": "Jane Smith",
        "email": "jane.smith@example.com",
        "phone": "+91-9876543211",
        "location": "Hyderabad",
        "skills": ["java", "spring", "react", "mysql", "aws", "docker"],
        "preferred_locations": ["Hyderabad", "Bangalore", "Chennai"],
        "candidate_titles": ["Java Developer", "Backend Engineer", "Software Developer"],
        "resume_urls": {
            "frontend": "https://res.cloudinary.com/dco7jegub/raw/upload/v1/STU002_frontend.pdf",
            "backend": "https://res.cloudinary.com/dco7jegub/raw/upload/v1/STU002_backend.pdf",
            "fullstack": "https://res.cloudinary.com/dco7jegub/raw/upload/v1/STU002_fullstack.pdf",
        },
        "credentials": {
            "naukri": {"email": "jane.smith@naukri.com", "password": "encrypted_password"},
            "linkedin": {"email": "jane.smith.linkedin@gmail.com", "password": "encrypted_password"},
        },
    },
    {
        "student_id": "STU003",
        "name": "Alice Johnson",
        "email": "alice.j@example.com",
        "phone": "+91-9876543212",
        "location": "Pune",
        "skills": ["javascript", "react", "nodejs", "mongodb", "typescript", "docker"],
        "preferred_locations": ["Pune", "Bangalore", "Mumbai"],
        "candidate_titles": ["Frontend Developer", "React Developer", "UI Developer"],
        "resume_urls": {
            "frontend": "https://res.cloudinary.com/dco7jegub/raw/upload/v1/STU003_frontend.pdf",
            "backend": "https://res.cloudinary.com/dco7jegub/raw/upload/v1/STU003_backend.pdf",
            "fullstack": "https://res.cloudinary.com/dco7jegub/raw/upload/v1/STU003_fullstack.pdf",
        },
        "credentials": {
            "naukri": {"email": "alice.j@naukri.com", "password": "encrypted_password"},
        },
    },
]


def seed_students(students: list[dict] = None, clear_existing: bool = False):
    """
    Seed students into MongoDB.
    
    Args:
        students: List of student dicts (uses SAMPLE_STUDENTS if None)
        clear_existing: If True, clear existing students first
    """
    if students is None:
        students = SAMPLE_STUDENTS
    
    logger.info(f"Seeding {len(students)} students...")
    
    for student_data in students:
        student_id = student_data["student_id"]
        
        # Check if student exists
        existing = get_student(student_id)
        
        if existing:
            if clear_existing:
                logger.info(f"  Updating existing student: {student_id}")
            else:
                logger.info(f"  Skipping existing student: {student_id}")
                continue
        
        # Create student
        try:
            # Build ResumeUrls
            resume_urls = None
            if "resume_urls" in student_data:
                resume_urls = ResumeUrls(**student_data["resume_urls"])
            
            # Build credentials
            credentials = None
            if "credentials" in student_data:
                creds_dict = {}
                for platform, cred in student_data["credentials"].items():
                    creds_dict[platform] = PlatformCredentials(**cred)
                credentials = StudentCredentials(**creds_dict)
            
            # Create student
            student = StudentCreate(
                student_id=student_data["student_id"],
                name=student_data["name"],
                email=student_data["email"],
                phone=student_data["phone"],
                location=student_data.get("location", "India"),
                skills=student_data.get("skills", []),
                preferred_locations=student_data.get("preferred_locations", []),
                candidate_titles=student_data.get("candidate_titles", []),
                resume_urls=resume_urls,
                credentials=credentials,
            )
            
            create_student(student)
            logger.info(f"  Created: {student_id} - {student_data['name']}")
            
        except Exception as e:
            logger.error(f"  Failed to create {student_id}: {e}")
    
    logger.info(f"Seeding complete! Total students: {count_students()}")


def seed_additional(count: int = 30):
    """Seed additional students for testing."""
    
    students = []
    
    for i in range(1, count + 1):
        student_id = f"STU{100 + i:03d}"
        
        students.append({
            "student_id": student_id,
            "name": f"Student {i}",
            "email": f"student{i}@example.com",
            "phone": f"+91-98765{i:05d}",
            "location": "India",
            "skills": ["python", "java", "javascript"],
            "preferred_locations": ["Bangalore", "Hyderabad", "Pune"],
            "candidate_titles": ["Software Developer", "Developer"],
            "resume_urls": {
                "frontend": f"https://res.cloudinary.com/dco7jegub/raw/upload/v1/{student_id}_frontend.pdf",
                "backend": f"https://res.cloudinary.com/dco7jegub/raw/upload/v1/{student_id}_backend.pdf",
                "fullstack": f"https://res.cloudinary.com/dco7jegub/raw/upload/v1/{student_id}_fullstack.pdf",
            },
        })
    
    seed_students(students)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed students to MongoDB")
    parser.add_argument("--count", type=int, default=0, help="Additional students to create")
    parser.add_argument("--clear", action="store_true", help="Clear existing students first")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    
    if args.count > 0:
        seed_additional(args.count)
    else:
        seed_students(clear_existing=args.clear)


if __name__ == "__main__":
    main()