import redis
import os

r = redis.Redis(host='localhost', port=6379, db=0)
keys = r.keys("*student_2b4359c4*")
if keys:
    print(f"Deleting {len(keys)} keys...")
    r.delete(*keys)
else:
    print("No keys found.")
