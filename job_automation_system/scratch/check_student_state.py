import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.student_mongodb import get_student_by_id
import json

student_id = "student_2b4359c4"
student = get_student_by_id(student_id)
if student:
    # Print keys and some details
    print(f"Student: {student.get('full_name')}")
    print(f"Email: {student.get('email')}")
    print(f"Phone: {student.get('phone')}")
    print(f"Location: {student.get('location')}")
    print(f"Skills: {len(student.get('skills', []))}")
    print(f"Custom Roles: {list(student.get('custom_roles', {}).keys())}")
    print(f"Experience Count: {len(student.get('experience', []))}")
    print(f"Projects Count: {len(student.get('projects', []))}")
    print(f"Education: {student.get('education')}")
else:
    print("Student not found")
