"""Dispatch a test naukri producer task and confirm no validation errors."""
from tasks.producer_platform_task import run_naukri
result = run_naukri.apply_async()
print(f"Task dispatched: {result.id}")
