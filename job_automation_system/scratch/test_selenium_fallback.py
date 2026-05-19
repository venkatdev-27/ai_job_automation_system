"""
Test script to verify Selenium scraper works standalone.
"""
import os
import sys
import logging
from pathlib import Path

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Simple logger
class SimpleLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(handler)
    
    def log_info(self, msg): self.logger.info(msg)
    def log_warn(self, msg): self.logger.warning(msg)
    def log_err(self, msg): self.logger.error(msg)
    def log_ok(self, msg): self.logger.info(f"OK: {msg}")

logger = SimpleLogger(__name__)

# Test with fake credentials - we just want to see if the browser can load
TEST_EMAIL = os.environ.get("TEST_NAUKRI_EMAIL", "test@example.com")
TEST_PASSWORD = os.environ.get("TEST_NAUKRI_PASSWORD", "testpassword")

logger.log_info("="*50)
logger.log_info("SELENIUM FALLBACK TEST")
logger.log_info("="*50)

# Import scraper
from scraper_adapter.naukri_selenium import create_selenium_scraper

async def run_test():
    logger.log_info("Creating Selenium scraper...")
    scraper = create_selenium_scraper(logger, None)
    
    # Step 1: Get driver
    logger.log_info("Step 1: Initializing Chrome driver (headless)...")
    try:
        driver = await scraper.get_driver(headless=True)
        logger.log_ok("Driver initialized successfully!")
        logger.log_info(f"Driver type: {type(driver)}")
    except Exception as e:
        logger.log_err(f"Driver init failed: {e}")
        return False
    
    # Step 2: Try to load Naukri
    logger.log_info("Step 2: Loading Naukri login page...")
    try:
        driver.get("https://www.naukri.com/nlogin/login")
        logger.log_ok("Page loaded!")
        
        # Get content length
        content_len = len(driver.page_source)
        logger.log_info(f"Page content length: {content_len} bytes")
        
        # Check for 1945
        if content_len == 1945 or "Application error" in driver.page_source:
            logger.log_warn("1945 ERROR DETECTED - Naukri blocking headless Chrome!")
        else:
            logger.log_ok("Page loaded without 1945 error!")
    except Exception as e:
        logger.log_err(f"Page load failed: {e}")
    
    # Step 3: Cleanup
    logger.log_info("Step 3: Closing driver...")
    await scraper.close()
    logger.log_ok("Driver closed!")
    
    return True

if __name__ == "__main__":
    import asyncio
    result = asyncio.run(run_test())
    if result:
        logger.log_ok("TEST COMPLETED")
    else:
        logger.log_err("TEST FAILED")