@echo off
REM Clear all Redis data before host migration
echo ========================================
echo   Clearing All Redis Data
echo ========================================

cd /d d:\ai-bot-resumes\job_automation_system

python -c "
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=False)

# Clear idempotency keys
idemp_keys = r.keys('idemp*')
print('[*] Found', len(idemp_keys), 'idempotency keys')
for k in idemp_keys:
    r.delete(k)
print('[*] Cleared idempotency keys')

# Clear locks
lock_keys = r.keys('*lock*')
print('[*] Found', len(lock_keys), 'lock keys')
for k in lock_keys:
    r.delete(k)
print('[*] Cleared lock keys')

# Clear queues (celery)
r.delete('celery')
r.delete('celery naukri')
r.delete('celery linkedin')
r.delete('celery foundit')
print('[*] Cleared queues')

print('Done!')
"

echo.
pause