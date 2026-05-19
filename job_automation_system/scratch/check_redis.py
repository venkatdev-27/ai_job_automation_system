import redis
import os

r = redis.Redis(host='localhost', port=6379, db=0)
print(f"Browsers Semaphore: {r.get('semaphore:browsers')}")
print(f"Active Locks: {r.keys('lock:*')}")
print(f"Active Sessions: {r.keys('session:*')}")
print(f"Circuit Breakers: {r.keys('circuit:*')}")
print(f"Rate Limits: {r.keys('rate_limit:*')}")
