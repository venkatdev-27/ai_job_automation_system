import redis
import os
os.environ['REDIS_HOST'] = 'localhost'
try:
    r = redis.Redis(host='localhost', port=6379)
    r.ping()
    print('Redis connection OK!')
except Exception as e:
    print(f'Redis error: {e}')