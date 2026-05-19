import os
import sys
os.environ['REDIS_HOST'] = 'localhost'
os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
os.environ['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/1'
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')

# Test imports
print("Testing imports...")
try:
    from celery_app.app import app
    print("Celery app imported OK!")
    
    from services.idempotency_v2 import clear_all_duplicates
    print("Idempotency V2 imported OK!")
    
    from database.client import get_database
    print("Database client imported OK!")
    
    print("\nAll imports successful!")
    
except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()