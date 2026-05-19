import asyncio
from scraper_adapter.playwright_manager import playwright_manager
from config.settings import settings

async def run():
    try:
        page = await playwright_manager.get_page(settings)
        content = await page.content()
        with open('/app/logs/naukri_page_debug.html', 'w', encoding='utf-8') as f:
            f.write(content)
        await page.screenshot(path='/app/logs/naukri_page_debug.png')
        print('Page saved to /app/logs/naukri_page_debug.html and .png')
        await playwright_manager.return_page(page)
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    asyncio.run(run())
