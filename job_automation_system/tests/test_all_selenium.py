"""
Test all Selenium scrapers
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

NAUKRI_EMAIL = "k.venky5678@gmail.com"
NAUKRI_PASSWORD = "Venkyyamuna@143322"

LINKEDIN_EMAIL = "k.venky5678@gmail.com"
LINKEDIN_PASSWORD = "Venkyyamuna@1433"


class SimpleLogger:
    def log_info(self, msg):
        print(f"INFO: {msg}")
    def log_warn(self, msg):
        print(f"WARN: {msg}")
    def log_err(self, msg):
        print(f"ERROR: {msg}")
    def log_ok(self, msg):
        print(f"OK: {msg}")


def test_naukri_sel():
    from scraper_adapter.naukri_selenium import NaukriSelenium
    logger = SimpleLogger()
    
    print("=" * 60)
    print("TESTING NAUKRI SELENIUM")
    print("=" * 60)
    
    scraper = NaukriSelenium(logger)
    
    try:
        result = scraper.login(NAUKRI_EMAIL, NAUKRI_PASSWORD)
        
        if result:
            print("NAUKRI SELENIUM: PASSED")
        else:
            print("NAUKRI SELENIUM: FAILED")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        scraper.close()


def test_linkedin_sel():
    from scraper_adapter.linkedin_selenium import LinkedInSelenium
    logger = SimpleLogger()
    
    print("=" * 60)
    print("TESTING LINKEDIN SELENIUM")
    print("=" * 60)
    
    scraper = LinkedInSelenium(logger)
    
    try:
        result = scraper.login(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
        
        if result:
            print("LINKEDIN SELENIUM: PASSED")
        else:
            print("LINKEDIN SELENIUM: FAILED")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        scraper.close()


def test_foundit_sel():
    from scraper_adapter.foundit_selenium import FoundItSelenium
    logger = SimpleLogger()
    
    print("=" * 60)
    print("TESTING FOUNDIT SELENIUM")
    print("=" * 60)
    
    scraper = FoundItSelenium(logger)
    
    try:
        result = scraper.login(NAUKRI_EMAIL, NAUKRI_PASSWORD)
        
        if result:
            print("FOUNDIT SELENIUM: PASSED")
        else:
            print("FOUNDIT SELENIUM: FAILED")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        scraper.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", default="all", choices=["all", "naukri", "linkedin", "foundit"])
    args = parser.parse_args()
    
    if args.platform in ["all", "naukri"]:
        test_naukri_sel()
    
    if args.platform in ["all", "linkedin"]:
        test_linkedin_sel()
    
    if args.platform in ["all", "foundit"]:
        test_foundit_sel()