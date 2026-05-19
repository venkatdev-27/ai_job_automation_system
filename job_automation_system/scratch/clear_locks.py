import os
import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')
os.environ['REDIS_HOST'] = 'localhost'

import redis
r = redis.Redis(host='localhost', port=6379)
keys = r.keys('*lock*')
print(f'Found {len(keys)} lock keys')
for k in keys:
    print(f'  {k}')

# Clear locks
for pattern in ['*lock*', '*semaphore*']:
    ks = r.keys(pattern)
    for k in ks:
        r.delete(k)
print('Cleared locks')