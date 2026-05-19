import asyncio
import random
from playwright.async_api import Page, Locator


async def human_delay(min_sec: float = 1, max_sec: float = 3) -> float:
    """Random delay mimicking human pause to prevent bot detection."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)
    return delay


async def simulate_mouse_movement(page: Page, start_x: int = None, start_y: int = None):
    """Simulate human-like mouse movement with random pauses."""
    try:
        viewport = page.viewport_size
        if not viewport:
            return
        
        max_x = viewport["width"] - 100
        max_y = viewport["height"] - 100
        
        x = start_x if start_x else random.randint(100, max_x)
        y = start_y if start_y else random.randint(100, max_y)
        
        steps = random.randint(5, 15)
        for i in range(steps):
            step_x = x + random.randint(-50, 50)
            step_y = y + random.randint(-50, 50)
            step_x = max(0, min(max_x, step_x))
            step_y = max(0, min(max_y, step_y))
            await page.mouse.move(step_x, step_y)
            await asyncio.sleep(random.uniform(0.05, 0.2))
        
        return x, y
    except Exception:
        pass


async def simulate_typing(page: Locator, text: str, base_delay: float = 0.1):
    """Type text with variable delays to mimic human typing."""
    await page.click()
    await asyncio.sleep(random.uniform(0.1, 0.3))
    
    for char in text:
        await page.type(char, delay=random.uniform(base_delay * 0.5, base_delay * 1.5))
        if random.random() < 0.1:
            await asyncio.sleep(random.uniform(0.1, 0.4))


async def simulate_human_scroll(page: Page):
    """Simulate human-like scrolling behavior."""
    try:
        for _ in range(random.randint(2, 5)):
            scroll_amount = random.randint(200, 500)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
            if random.random() < 0.3:
                await page.evaluate("window.scrollBy(0, -100)")
                await asyncio.sleep(random.uniform(0.2, 0.5))
    except Exception:
        pass


async def simulate_click(page: Page, locator: Locator):
    """Click with human-like delay and movement."""
    try:
        await simulate_mouse_movement(page)
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await locator.click()
        await asyncio.sleep(random.uniform(0.2, 0.5))
    except Exception:
        await locator.click()


async def randomize_viewport(page: Page):
    """Randomize viewport slightly to avoid fingerprinting."""
    try:
        viewports = [
            {"width": 1280, "height": 720},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1920, "height": 1080},
        ]
        viewport = random.choice(viewports)
        await page.set_viewport_size(viewport)
    except Exception:
        pass


async def wait_forDomReady(page: Page, timeout: int = 30000):
    """Wait for page DOM to be ready."""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=timeout)
    except Exception:
        pass


async def wait_for_network_idle(page: Page, timeout: int = 10000):
    """Wait for network to be idle (fewer than 2 requests)."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        await asyncio.sleep(2)