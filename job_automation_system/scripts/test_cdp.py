"""
Test CDP connection from within Docker container.
"""
import os
import sys
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = "/app"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

async def test_cdp():
    logger.info("="*50)
    logger.info("CDP CONNECTION TEST")
    logger.info("="*50)
    
    cdp_url = os.environ.get("CDP_URL", "http://host.docker.internal:9222")
    use_cdp = os.environ.get("USE_CDP", "true").lower() == "true"
    
    logger.info(f"CDP_URL: {cdp_url}")
    logger.info(f"USE_CDP: {use_cdp}")
    
    if not use_cdp:
        logger.warn("USE_CDP=false - skipping CDP test")
        return
    
    try:
        from playwright.sync_api import sync_playwright
        
        logger.info(f"Attempting to connect to Chrome via CDP: {cdp_url}")
        
        p = sync_playwright().start()
        browser = p.chromium.connect_over_cdp(cdp_url)
        logger.info("Connected to Chrome!")
        
        # Get page
        contexts = browser.contexts
        if contexts and contexts[0].pages:
            page = contexts[0].pages[0]
            logger.info(f"Current page URL: {page.url}")
        else:
            page = browser.new_page()
            logger.info("Created new page")
        
        # Try to load Naukri
        logger.info("Loading Naukri...")
        page.goto("https://www.naukri.com/nlogin/login", timeout=30000)
        
        content = page.content()
        content_len = len(content)
        
        logger.info(f"Page loaded. Content length: {content_len} bytes")
        
        if content_len == 1945 or "Application error" in content:
            logger.error("1945 ERROR - Naukri blocked the browser!")
        else:
            logger.info("SUCCESS - Page loaded without 1945 error!")
        
        browser.close()
        p.stop()
        
    except Exception as e:
        logger.error(f"CDP connection failed: {e}")
        logger.info("Make sure Chrome is running with:")
        logger.info("  chrome.exe --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0")
        return False
    
    return True

if __name__ == "__main__":
    result = asyncio.run(test_cdp())
    if result:
        logger.info("TEST PASSED")
    else:
        logger.error("TEST FAILED")