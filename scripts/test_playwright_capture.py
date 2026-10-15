import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            http_credentials={"username": "judge", "password": "Aegis2026!"},
            viewport={"width": 1440, "height": 900}
        )
        page = await context.new_page()
        print("Navigating to Cloud Run...")
        await page.goto("https://ai-meeting-assistant-7y3l4a2iba-uc.a.run.app", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        # Take initial screenshot
        await page.screenshot(path="01_live_cloud_dashboard.png")
        print("01_live_cloud_dashboard.png saved!")
        
        # Check text input existence
        input_el = page.locator("#chat-input, #text-input, input[type='text'], textarea")
        count = await input_el.count()
        print(f"Found {count} text input elements")
        
        # Let's inspect page elements
        title = await page.title()
        print("Page title:", title)
        await browser.close()

asyncio.run(run())
