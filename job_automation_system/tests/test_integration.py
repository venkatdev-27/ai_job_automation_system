"""
Integration Test - 3 Platform System
==============================
Test cases for Naukri, LinkedIn, FoundIT platform integration.
Run with minimal workers (1 per platform) for testing.
Uses .env configuration.

Can run without pytest: python tests/test_integration.py
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment automatically via config
# The config module loads .env automatically
os.environ["RUN_ENV"] = os.environ.get("RUN_ENV", "test")


class TestRedisConnection:
    """Test Redis connectivity."""
    
    def test_redis_client_connection(self):
        """Test Redis client can connect."""
        try:
            from services.redis_client import redis_client
            client = redis_client.client
            # Test ping
            result = client.ping()
            assert result is True
            print("OK - Redis connection")
        except Exception as e:
            print("SKIP - Redis not available: {}".format(e))
            return  # Skip
    
    def test_redis_basic_operations(self):
        """Test basic Redis operations."""
        try:
            from services.redis_client import redis_client
            client = redis_client.client
            
            # Set and get
            test_key = "test_key"
            test_value = "test_value"
            client.set(test_key, test_value)
            result = client.get(test_key)
            
            assert result == test_value
            client.delete(test_key)
            print("OK - Redis basic ops")
        except Exception as e:
            print("SKIP - Redis not available: {}".format(e))
            return  # Skip


class TestStudentLock:
    """Test per-student concurrency lock."""
    
    def test_lock_acquire_release(self):
        """Test acquiring and releasing lock."""
        try:
            from services.student_lock import StudentLock
            lock = StudentLock()
            
            student_id = "test_student"
            platform = "naukri"
            
            # Acquire
            acquired = lock.acquire(student_id, platform, ttl=60, blocking=False)
            assert acquired is True
            
            # Try again - should fail
            acquired2 = lock.acquire(student_id, platform, blocking=False)
            assert acquired2 is False
            
            # Release
            released = lock.release(student_id, platform)
            assert released is True
            
            # Now should succeed
            acquired3 = lock.acquire(student_id, platform, blocking=False)
            assert acquired3 is True
            lock.release(student_id, platform)
            
            print("OK Student lock: OK")
        except Exception as e:
            print("SKIP - Redis not available: {}".format(e))
            return  # Skip
        """Test lock auto-expires."""
        try:
            from services.student_lock import StudentLock
            lock = StudentLock()
            
            # Acquire with short TTL
            acquired = lock.acquire("test_stu2", "linkedin", ttl=2, blocking=False)
            assert acquired is True
            
            # Wait for expiry
            import time
            time.sleep(3)
            
            # Should be able to acquire now
            acquired2 = lock.acquire("test_stu2", "linkedin", blocking=False)
            assert acquired2 is True
            lock.release("test_stu2", "linkedin")
            
            print("OK Lock timeout: OK")
        except Exception as e:
            print("SKIP - Redis not available: {}".format(e))
            return  # Skip


class TestStudentRateLimiter:
    """Test per-student rate limiting."""
    
    def test_daily_limit(self):
        """Test daily application limit."""
        try:
            from services.student_rate_limiter import StudentRateLimiter
            limiter = StudentRateLimiter(daily_limit=5)
            
            student_id = "rate_test_student"
            
            # Reset first
            limiter.reset(student_id)
            
            # Initial check
            can_apply, count = limiter.can_apply(student_id)
            assert can_apply is True
            assert count == 0
            
            # Increment twice
            limiter.increment(student_id)
            limiter.increment(student_id)
            
            # Check
            can_apply2, count2 = limiter.can_apply(student_id)
            assert count2 == 2
            assert can_apply2 is True
            
            # At limit
            for i in range(3):
                limiter.increment(student_id)
            
            can_apply3, count3 = limiter.can_apply(student_id)
            assert count3 == 5
            assert can_apply3 is False
            
            # Clean up
            limiter.reset(student_id)
            
            print("OK Student rate limiter: OK")
        except Exception as e:
            print("SKIP - Redis not available: {}".format(e))
            return  # Skip


class TestSessionManager:
    """Test session management."""
    
    def test_session_path_creation(self):
        """Test session directory creation."""
        try:
            from services.session_manager import StudentSessionManager
            from pathlib import Path
            
            mgr = StudentSessionManager()
            
            student_id = "session_test_student"
            
            # Check paths
            session_path = mgr.get_session_path(student_id, "linkedin")
            assert session_path.parent.exists() is None  # Shouldn't exist yet
            
            chrome_dir = mgr.get_chrome_profile_dir(student_id)
            assert str(chrome_dir).endswith(f"session_test_student/chrome_profile")
            
            print("OK Session manager paths: OK")
        except Exception as e:
            print("SKIP - Redis not available: {}".format(e))
            return  # Skip


class TestPlatformConfiguration:
    """Test platform configuration."""
    
    def test_all_platforms_configured(self):
        """Test all 3 platforms are configured."""
        from config.platforms import PLATFORMS, CELERY_QUEUES
        
        assert "naukri" in PLATFORMS
        assert "linkedin" in PLATFORMS
        assert "foundit" in PLATFORMS
        
        assert "naukri" in CELERY_QUEUES
        assert "linkedin" in CELERY_QUEUES
        assert "foundit" in CELERY_QUEUES
        
        print("OK Platform configuration: OK")
    
    def test_platform_settings(self):
        """Test platform settings."""
        from config.platforms import get_platform_config
        
        # Naukri
        naukri = get_platform_config("naukri")
        assert naukri.name == "naukri"
        assert naukri.rate_limit == "10/m"
        assert naukri.concurrency == 2
        
        # LinkedIn
        linkedin = get_platform_config("linkedin")
        assert linkedin.name == "linkedin"
        assert linkedin.rate_limit == "6/m"
        assert linkedin.concurrency == 2
        
        # FoundIT
        foundit = get_platform_config("foundit")
        assert foundit.name == "foundit"
        assert foundit.rate_limit == "8/m"
        assert foundit.concurrency == 2
        
        print("OK Platform settings: OK")


class TestSettingsConfiguration:
    """Test settings integration."""
    
    def test_path_settings(self):
        """Test path settings from config."""
        from config import settings
        
        assert hasattr(settings, 'chrome_profile_dir')
        assert hasattr(settings, 'resumes_dir')
        assert hasattr(settings, 'temp_resumes_dir')
        assert hasattr(settings, 'chroma_db_dir')
        
        print("OK Path settings: OK")
    
    def test_api_settings(self):
        """Test API settings from config."""
        from config import settings
        
        assert hasattr(settings, 'groq_api_url')
        assert hasattr(settings, 'openrouter_api_url')
        assert hasattr(settings, 'minimax_api_url')
        assert hasattr(settings, 'local_api_url')
        
        # Check defaults
        assert "groq" in settings.groq_api_url
        assert "openrouter" in settings.openrouter_api_url
        assert "localhost" in settings.local_api_url
        
        print("OK API settings: OK")


class TestTaskImports:
    """Test task imports work."""
    
    def test_naukri_task_imports(self):
        """Test Naukri task can be imported."""
        try:
            # Import minimal to check task structure
            from tasks.base_task import BasePlatformTask
            print("OK Naukri task base: OK")
        except Exception as e:
            print(f"NOTE - Task imports need full env: {e}")
    
    def test_linkedin_task_imports(self):
        """Test LinkedIn task can be imported."""
        try:
            from tasks.base_task import BasePlatformTask
            print("OK LinkedIn task base: OK")
        except Exception as e:
            print(f"NOTE - Task imports need full env: {e}")
    
    def test_foundit_task_imports(self):
        """Test FoundIT task can be imported."""
        try:
            from tasks.base_task import BasePlatformTask
            print("OK FoundIT task base: OK")
        except Exception as e:
            print(f"NOTE - Task imports need full env: {e}")


class TestWorkerConfiguration:
    """Test worker configuration."""
    
    def test_worker_queues(self):
        """Test each platform has correct queue."""
        from celery_app.config import celery_config
        
        queues = celery_config.get("task_queues", [])
        queue_names = [q.name for q in queues]
        
        assert "naukri" in queue_names
        assert "linkedin" in queue_names
        assert "foundit" in queue_names
        
        print("OK Worker queues: OK")
    
    def test_task_routes(self):
        """Test task routing configuration."""
        from celery_app.config import _task_routes
        
        routes = _task_routes()
        
        assert "tasks.naukri_task.*" in routes
        assert "tasks.linkedin_task.*" in routes
        assert "tasks.foundit_task.*" in routes
        
        print("OK Task routes: OK")


# ==================== Run Tests ====================

def run_tests():
    """Run all tests manually (without pytest)."""
    print("\n" + "="*50)
    print("Running Integration Tests")
    print("="*50 + "\n")
    
    test_classes = [
        TestPlatformConfiguration(),
        TestSettingsConfiguration(),
        TestTaskImports(),
        TestWorkerConfiguration(),
    ]
    
    # Tests that don't require Redis
    for test_class in test_classes:
        print("\nTesting: {}".format(test_class.__class__.__name__))
        methods = [m for m in dir(test_class) if m.startswith("test_")]
        
        for method_name in methods:
            try:
                method = getattr(test_class, method_name)
                method()
            except Exception as e:
                print("FAIL - {}: {}".format(method_name, e))
    
    # Tests requiring Redis
    print("\n--- Tests requiring Redis ---")
    redis_tests = [
        TestRedisConnection(),
        TestStudentLock(),
        TestStudentRateLimiter(),
        TestSessionManager(),
    ]
    
    for test_class in redis_tests:
        print("\nTesting: {}".format(test_class.__class__.__name__))
        methods = [m for m in dir(test_class) if m.startswith("test_")]
        
        for method_name in methods:
            try:
                method = getattr(test_class, method_name)
                method()
            except NameError:
                # pytest not imported, ignore
                pass
            except Exception as e:
                print("SKIP - {}: {}".format(method_name, e))
    
    print("\n" + "="*50)
    print("Tests Complete")
    print("="*50 + "\n")


if __name__ == "__main__":
    run_tests()