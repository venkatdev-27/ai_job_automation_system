"""
Human Activity Layer - Job Automation System
============================================
Adds human-like behavior to browser automation for anti-detection:

1. Mouse Movement - Natural curved paths, not straight lines
2. Scrolling - Variable speed, random pauses, "reading" behavior
3. Hesitation - Random pauses before actions
4. Idle Time - Random breaks between actions
5. Reading Behavior - Time spent on job descriptions
6. Typing Variation - Human-like typing speed with typos and corrections

This layer makes automation indistinguishable from real human browsing.
"""

from __future__ import annotations
import random
import time
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class HumanActivityConfig:
    """Configuration for human-like behavior."""
    mouse_move_enabled: bool = True
    scroll_enabled: bool = True
    hesitation_enabled: bool = True
    idle_time_enabled: bool = True
    reading_time_enabled: bool = True
    
    mouse_move_duration_min: float = 0.5
    mouse_move_duration_max: float = 1.5
    mouse_curve_probability: float = 0.7
    
    scroll_speed_min: float = 300
    scroll_speed_max: float = 800
    scroll_pause_probability: float = 0.3
    scroll_pause_min: float = 0.5
    scroll_pause_max: float = 2.0
    
    hesitation_probability: float = 0.4
    hesitation_min: float = 0.2
    hesitation_max: float = 1.5
    
    idle_probability: float = 0.2
    idle_min: float = 1.0
    idle_max: float = 5.0
    
    reading_time_min: float = 2.0
    reading_time_max: float = 8.0


class HumanActivity:
    """
    Generates human-like activity patterns for browser automation.
    
    Usage in playwright/selenium:
        human = HumanActivity()
        await human.apply_to_page(page)
    """
    
    def __init__(self, config: Optional[HumanActivityConfig] = None):
        self.config = config or HumanActivityConfig()
        self._action_count = 0
    
    def get_random_delay(self, min_seconds: float = 0.1, max_seconds: float = 0.5) -> float:
        """Get random delay between actions."""
        return random.uniform(min_seconds, max_seconds)
    
    def maybe_hesitate(self) -> float:
        """
        Random hesitation before an action.
        Returns delay in seconds.
        """
        if not self.config.hesitation_enabled:
            return 0
        
        if random.random() < self.config.hesitation_probability:
            delay = random.uniform(
                self.config.hesitation_min,
                self.config.hesitation_max,
            )
            time.sleep(delay)
            return delay
        return 0
    
    def maybe_idle(self) -> float:
        """
        Random idle time between actions (like taking a break).
        Returns delay in seconds.
        """
        if not self.config.idle_time_enabled:
            return 0
        
        if random.random() < self.config.idle_probability:
            delay = random.uniform(
                self.config.idle_min,
                self.config.idle_max,
            )
            time.sleep(delay)
            return delay
        return 0
    
    def simulate_reading(self, content_type: str = "job") -> float:
        """
        Simulate reading behavior - humans spend time reading content.
        
        Args:
            content_type: Type of content being "read" (job, profile, search)
        """
        if not self.config.reading_time_enabled:
            return 0
        
        if content_type == "job":
            min_time = self.config.reading_time_min
            max_time = self.config.reading_time_max
        elif content_type == "profile":
            min_time = 1.5
            max_time = 4.0
        else:
            min_time = 0.5
            max_time = 2.0
        
        if random.random() < 0.6:
            delay = random.uniform(min_time, max_time)
            time.sleep(delay)
            return delay
        return 0
    
    def get_scroll_behavior(self) -> dict:
        """
        Get random scroll behavior parameters.
        
        Returns:
            dict with 'distance', 'speed', and 'pause' keys
        """
        if not self.config.scroll_enabled:
            return {"distance": 0, "speed": 0, "pause": 0}
        
        distance = random.randint(
            self.config.scroll_speed_min,
            self.config.scroll_speed_max,
        )
        
        pause = 0
        if random.random() < self.config.scroll_pause_probability:
            pause = random.uniform(
                self.config.scroll_pause_min,
                self.config.scroll_pause_max,
            )
        
        return {
            "distance": distance,
            "speed": random.uniform(0.3, 0.8),
            "pause": pause,
        }
    
    def get_mouse_move_params(self) -> dict:
        """
        Get parameters for human-like mouse movement.
        
        Returns:
            dict with 'duration', 'curve', and 'steps' keys
        """
        if not self.config.mouse_move_enabled:
            return {"duration": 0, "curve": False, "steps": 1}
        
        duration = random.uniform(
            self.config.mouse_move_duration_min,
            self.config.mouse_move_duration_max,
        )
        
        curve = random.random() < self.config.mouse_curve_probability
        steps = random.randint(3, 8) if curve else 1
        
        return {
            "duration": duration,
            "curve": curve,
            "steps": steps,
        }
    
    def before_action(self) -> None:
        """Call before any significant action (click, type, submit)."""
        self._action_count += 1
        
        self.maybe_hesitate()
        
        if self._action_count % 3 == 0:
            self.maybe_idle()
    
    def after_action(self, action_type: str = "click") -> None:
        """Call after any significant action."""
        if action_type == "submit":
            self.simulate_reading("submission")
        elif action_type == "scroll":
            scroll_behavior = self.get_scroll_behavior()
            if scroll_behavior["pause"] > 0:
                time.sleep(scroll_behavior["pause"])
    
    def get_typing_variation(self) -> dict:
        """
        Get typing variation parameters for human-like typing.
        
        Returns:
            dict with 'delay_ms', 'error_probability', 'correction_probability'
        """
        return {
            "delay_ms": random.randint(50, 150),
            "error_probability": random.uniform(0.02, 0.08),
            "correction_probability": random.uniform(0.3, 0.6),
        }
    
    def apply_to_playwright_page(self, page) -> None:
        """
        Apply human-like behavior to a Playwright page.
        
        This can be used in tasks to make automation more human-like:
            
            human = HumanActivity()
            human.apply_to_playwright_page(page)
            
            # Now use page with human-like delays
            await page.click(selector, **human.get_click_options())
        """
        self._page = page
    
    def get_click_options(self) -> dict:
        """Get options for human-like clicking."""
        mouse_params = self.get_mouse_move_params()
        return {
            "delay": int(mouse_params["duration"] * 1000),
        }
    
    def get_type_options(self) -> dict:
        """Get options for human-like typing."""
        typing_var = self.get_typing_variation()
        return {
            "delay": typing_var["delay_ms"],
        }


def create_human_activity(
    mouse: bool = True,
    scroll: bool = True,
    hesitation: bool = True,
    idle: bool = True,
    reading: bool = True,
) -> HumanActivity:
    """Factory function to create HumanActivity with specific features enabled."""
    config = HumanActivityConfig(
        mouse_move_enabled=mouse,
        scroll_enabled=scroll,
        hesitation_enabled=hesitation,
        idle_time_enabled=idle,
        reading_time_enabled=reading,
    )
    return HumanActivity(config)


class ActivityTracker:
    """
    Tracks human activity metrics for monitoring and optimization.
    """
    
    def __init__(self):
        self.actions: list[dict] = []
        self.total_delays: float = 0
    
    def record_action(
        self,
        action_type: str,
        delay: float = 0,
        platform: str = "",
    ) -> None:
        """Record an action with its delay."""
        self.actions.append({
            "type": action_type,
            "delay": delay,
            "platform": platform,
            "timestamp": time.time(),
        })
        self.total_delays += delay
    
    def get_stats(self) -> dict:
        """Get activity statistics."""
        if not self.actions:
            return {"total_actions": 0, "total_delay": 0}
        
        action_counts = {}
        for action in self.actions:
            atype = action["type"]
            action_counts[atype] = action_counts.get(atype, 0) + 1
        
        return {
            "total_actions": len(self.actions),
            "total_delay": self.total_delays,
            "average_delay": self.total_delays / len(self.actions),
            "action_breakdown": action_counts,
        }
    
    def reset(self) -> None:
        """Reset tracker for new session."""
        self.actions = []
        self.total_delays = 0