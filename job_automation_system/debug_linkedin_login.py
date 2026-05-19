import asyncio
from playwright.async_api import async_playwright
import os

async def run():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        )
        page = await context.new_page()
        print("Navigating to LinkedIn login...")
        try:
            await page.goto("https://www.linkedin.com/login", timeout=60000)
            await asyncio.sleep(5)
            await page.screenshot(path="/app/logs/linkedin_login_debug_manual.png")
            print("Screenshot saved to /app/logs/linkedin_login_debug_manual.png")
            
            content = await page.content()
            with open("/app/logs/linkedin_login_debug.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("HTML saved to /app/logs/linkedin_login_debug.html")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
