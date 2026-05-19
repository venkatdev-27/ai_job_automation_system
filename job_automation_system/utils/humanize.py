"""
Humanize Utility - Job Automation System
=========================================
Anti-bot human-like typing and interaction patterns.
"""

from __future__ import annotations
import random
import asyncio
from typing import Optional


class Humanizer:
    """
    Utility for human-like interactions to avoid bot detection.
    """
    
    # Typing speeds (ms per character)
    MIN_TYPING_DELAY = 0.05  # 50ms
    MAX_TYPING_DELAY = 0.15  # 150ms
    
    # Word-level delays
    MIN_WORD_DELAY = 0.1
    MAX_WORD_DELAY = 0.5
    
    # Mouse movement
    MIN_MOVE_DELAY = 0.05
    MAX_MOVE_DELAY = 0.2
    
    @staticmethod
    async def human_type(page_element, text: str, typing_delay: Optional[float] = None) -> None:
        """
        Type text with human-like delays.
        
        Args:
            page_element: Playwright element
            text: Text to type
            typing_delay: Optional custom delay per character
        """
        delay = typing_delay or random.uniform(
            Humanizer.MIN_TYPING_DELAY,
            Humanizer.MAX_TYPING_DELAY,
        )
        
        for char in text:
            await page_element.type(char, delay=delay)
            
            # Random pause between characters
            if random.random() < 0.1:  # 10% chance of pause
                await asyncio.sleep(random.uniform(0.1, 0.3))
    
    @staticmethod
    async def human_click(page_element) -> None:
        """
        Click with slight delay to simulate human behavior.
        """
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await page_element.click()
    
    @staticmethod
    async def human_move_and_click(page, x: int, y: int) -> None:
        """
        Move mouse to position and click with human-like path.
        """
        # Move in non-linear path (multiple waypoints)
        current_x, current_y = 0, 0
        
        # Add waypoints
        waypoints = [
            (x + random.randint(-50, 50), y + random.randint(-50, 50)),
            (x + random.randint(-20, 20), y + random.randint(-20, 20)),
            (x, y),
        ]
        
        for wx, wy in waypoints:
            await page.mouse.move(wx, wy)
            await asyncio.sleep(random.uniform(0.05, 0.15))
        
        # Click with slight delay
        await asyncio.sleep(random.uniform(0.1, 0.2))
        await page.mouse.click(x, y)
    
    @staticmethod
    async def random_scroll(page, direction: str = "down") -> None:
        """
        Scroll page randomly.
        
        Args:
            page: Playwright page
            direction: "up" or "down"
        """
        scroll_amount = random.randint(200, 500)
        if direction == "up":
            scroll_amount = -scroll_amount
        
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(random.uniform(0.3, 0.7))
    
    @staticmethod
    async def random_pause(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """Random pause between actions."""
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))
    
    @staticmethod
    def get_random_delay(min_seconds: float, max_seconds: float) -> float:
        """Get random delay in range."""
        return random.uniform(min_seconds, max_seconds)


async def random_delay(min_ms: int = 220, max_ms: int = 700) -> None:
    """Convenience helper for random async delays."""
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)


async def apply_with_human_delay(page, element, text: str) -> None:
    """Helper to type with human-like delays."""
    await Humanizer.human_type(element, text)


async def click_with_delay(page, element) -> None:
    """Helper to click with delay."""
    await Humanizer.human_click(element)


# Top-level aliases for compatibility with legacy engine.humanize calls
human_type = Humanizer.human_type
human_click = Humanizer.human_click


def get_delay_for_platform(platform: str) -> tuple[float, float]:
    """
    Get platform-specific delays.
    
    Returns:
        (min_delay, max_delay) in seconds
    """
    from config.settings import settings
    
    platform = platform.lower()
    
    if platform == "linkedin":
        return (settings.linkedin_min_delay, settings.linkedin_max_delay)
    
    return (settings.min_delay_seconds, settings.max_delay_seconds)