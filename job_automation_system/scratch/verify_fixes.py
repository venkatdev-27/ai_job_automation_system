"""
Verify both fixes:
1. Student model can load docs that only have 'name' (no 'full_name')
2. httpx is importable
"""
import sys

# Fix 1: Test Student model with legacy doc (no full_name)
try:
    sys.path.insert(0, '/app')
    from database.models import Student
    from datetime import datetime

    legacy_doc = {
        '_id': 'fake-oid',
        'student_id': 'STU001',
        'name': 'John Doe',
        # full_name intentionally absent — simulating legacy DB doc
        'email': 'john@example.com',
        'phone': '+91 9999999999',
        'location': 'India',
        'skills': ['Python'],
        'preferred_locations': [],
        'candidate_titles': [],
        'active': True,
        'warmup_complete': False,
        'warmup_resumes_generated': 0,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow(),
    }
    s = Student(**legacy_doc)
    print(f"[OK] Student validation passed")
    print(f"     name={s.name!r}, full_name={s.full_name!r} (backfilled: {s.full_name == s.name})")
except Exception as e:
    print(f"[FAIL] Student validation: {e}")

# Fix 2: Test httpx import
try:
    import httpx
    print(f"[OK] httpx importable: version={httpx.__version__}")
except ImportError as e:
    print(f"[FAIL] httpx: {e}")
