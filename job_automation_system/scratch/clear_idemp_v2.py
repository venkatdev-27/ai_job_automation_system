import os
import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')
os.environ['REDIS_HOST'] = 'localhost'

from services.idempotency_v2 import clear_all_duplicates
cleared = clear_all_duplicates()
print(f'Cleared: {cleared} idempotency keys')