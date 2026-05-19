import redis
r = redis.Redis(host='localhost', port=6379)
keys = r.keys('idemp*')
print(f'Found {len(keys)} idempotency keys')
for k in keys:
    r.delete(k)
print('Cleared all idempotency keys')