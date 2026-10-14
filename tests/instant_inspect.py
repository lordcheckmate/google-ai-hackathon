"""
Instant inspection of Google Meet response right now.
"""
import asyncio
import os
from playwright.async_api import async_playwright

async def inspect():
    PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "google_profile"))
    os.system("powershell -Command \"Get-Process -Name chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*ms-playwright*' } | Stop-Process -Force\" >nul 2>&1")
    await asyncio.sleep(1)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            permissions=["microphone"],
            args=[
                "--disable-video-capture",
                "--use-fake-ui-for-media-stream",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ],
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()
        await page.goto("https://meet.google.com/zer-qtph-qfc", wait_until="domcontentloaded", timeout=45000)
        
        # Wait for lobby
        name_input = page.locator('input[placeholder*="name" i], input[type="text"]').first
        try:
            await name_input.wait_for(state="visible", timeout=25000)
            await name_input.fill("AEGIS Copilot")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Name input notice: {e}")

        # Dismiss got it
        try:
            got_it = page.locator('button:has-text("Got it")')
            if await got_it.count() > 0:
                await got_it.first.click(force=True)
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # Click Ask to join
        btn = page.locator('button:has-text("Ask to join"):not([disabled]), button:has-text("Join now"):not([disabled])').first
        await btn.wait_for(state="visible", timeout=10000)
        await btn.click()
        await asyncio.sleep(2)

        # Check modal
        modal = page.locator('button:has-text("Continue without camera"), [role="button"]:has-text("Continue without camera")')
        if await modal.count() > 0 and await modal.first.is_visible():
            print("Clicking Continue without camera...")
            await modal.first.click(force=True)
            await asyncio.sleep(2)

        await page.screenshot(path="instant_meet_result.png")
        print("Screenshot saved to instant_meet_result.png")
        print("Page text excerpt:")
        txt = await page.inner_text("body")
        print(txt[:400])
        await asyncio.sleep(10)
        await context.close()

if __name__ == "__main__":
    asyncio.run(inspect())
