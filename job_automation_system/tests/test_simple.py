"""
Simple Test - 3 Platform System
================================
Minimal test to verify configuration works.
"""

import sys
from pathlib import Path

# Add project to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

print("="*50)
print("Simple Configuration Test")
print("="*50)

# Test 1: Settings
print("\n1. Testing Settings...")
try:
    from config import settings
    print("   OK - Settings loaded")
    print("   REDIS_HOST:", settings.redis_host)
    print("   MONGO_DB:", settings.mongo_db)
except Exception as e:
    print("   FAIL - Settings: {}".format(e))

# Test 2: Platform config
print("\n2. Testing Platform Config...")
try:
    from config.platforms import PLATFORMS
    print("   OK - Platforms: {}".format(list(PLATFORMS.keys())))
except Exception as e:
    print("   FAIL - Platforms: {}".format(e))

# Test 3: Celery config
print("\n3. Testing Celery Config...")
try:
    from celery_app.config import celery_config
    print("   OK - Celery config loaded")
except Exception as e:
    print("   FAIL - Celery: {}".format(e))

# Test 4: Services import
print("\n4. Testing Services...")
try:
    from services import redis_client, student_lock, student_rate_limiter
    print("   OK - Services imported")
except Exception as e:
    print("   FAIL - Services: {}".format(e))

print("\n" + "="*50)
print("Tests Complete - Run 'python tests/test_integration.py' for full tests")
print("="*50)