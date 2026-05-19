import os
import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')
os.environ['REDIS_HOST'] = 'localhost'

import redis
r = redis.Redis(host='localhost', port=6379)
keys = r.keys('idemp*')
print(f'Found {len(keys)} idemp keys')
for k in keys:
    print(f'  {k}')