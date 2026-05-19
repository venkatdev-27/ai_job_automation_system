import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

print("DEBUG: Importing settings...")
from config import settings
print(f"DEBUG: settings defined: {settings is not None}")

print("DEBUG: Importing JobProducer...")
from producer.producer import JobProducer
print("DEBUG: JobProducer imported successfully!")

print("DEBUG: Creating JobProducer instance...")
producer = JobProducer()
print("DEBUG: JobProducer instance created!")
