"""
Test FoundIt with undetected-chromedriver
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FOUNDIT_EMAIL = "k.venky5678@gmail.com"
FOUNDIT_PASSWORD = "Venkyyamuna@143322"


class SimpleLogger:
    def log_info(self, msg):
        print(f"INFO: {msg}")
    def log_warn(self, msg):
        print(f"WARN: {msg}")
    def log_err(self, msg):
        print(f"ERROR: {msg}")
    def log_ok(self, msg):
        print(f"OK: {msg}")


def test_foundit_undetected():
    from scraper_adapter.foundit_selenium import FoundItSelenium
    
    logger = SimpleLogger()
    
    print("=" * 60)
    print("TESTING FOUNDIT WITH UNDETECTED-CHROMEDRIVER")
    print("=" * 60)
    
    scraper = FoundItSelenium(logger)
    
    try:
        result = scraper.login(FOUNDIT_EMAIL, FOUNDIT_PASSWORD, max_retries=2)
        
        if result:
            print("RESULT: PASSED")
        else:
            print("RESULT: FAILED")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    test_foundit_undetected()