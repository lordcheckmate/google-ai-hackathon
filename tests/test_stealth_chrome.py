"""
Test launching the official Google Chrome executable with stealth settings to bypass Google Meet's bot detection.
"""
import asyncio
import os
from playwright.async_api import async_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MEET_URL = "https://meet.google.com/zer-qtph-qfc"
PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "bot_profile"))
os.makedirs(PROFILE_DIR, exist_ok=True)

async def test_stealth():
    print(f"Testing with Real Google Chrome: {CHROME_PATH}")
    
    # Kill stale processes
    os.system('powershell -Command "Get-Process -Name chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like \'*HackathonGoogle*\' } | Stop-Process -Force" >nul 2>&1')
    await asyncio.sleep(1)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            executable_path=CHROME_PATH,
            headless=False,
            permissions=["microphone"],
            args=[
                "--disable-video-capture",
                "--use-fake-ui-for-media-stream",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ],
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )

        page = await context.new_page()
        # Add stealth script to mask automation
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        print(f"Navigating to {MEET_URL}...")
        await page.goto(MEET_URL, wait_until="domcontentloaded", timeout=45000)

        # Wait for lobby
        print("Waiting for lobby...")
        name_input = page.locator('input[placeholder*="name" i], input[aria-label*="name" i], input[type="text"]').first
        try:
            await name_input.wait_for(state="visible", timeout=25000)
            print("Entering name: AEGIS Copilot")
            await name_input.fill("AEGIS Copilot")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Name input skip: {e}")

        # Dismiss got it
        try:
            got_it = page.locator('button:has-text("Got it"), span:has-text("Got it"), button:has-text("OK")')
            if await got_it.count() > 0 and await got_it.first.is_visible():
                await got_it.first.click(force=True)
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # Click Join/Ask
        btn = page.locator('button:has-text("Ask to join"):not([disabled]), button:has-text("Join now"):not([disabled]), button:has-text("参加をリクエスト"):not([disabled])').first
        await btn.wait_for(state="visible", timeout=10000)
        print("Clicking Ask to join button...")
        await btn.click()
        await asyncio.sleep(2)

        # Handle continue without camera modal
        modal = page.locator('button:has-text("Continue without camera"), span:has-text("Continue without camera"), [role="button"]:has-text("Continue without camera"), button:has-text("カメラなしで続行")')
        if await modal.count() > 0 and await modal.first.is_visible():
            print("Clicking Continue without camera modal...")
            await modal.first.click(force=True)
            await asyncio.sleep(2)

        await page.screenshot(path="stealth_result.png")
        print("Saved stealth_result.png")
        
        # Read text
        txt = await page.inner_text("body")
        print("--- Resulting Page Text ---")
        for line in txt.split("\n"):
            line = line.strip()
            if line:
                print(" >", line)

        await asyncio.sleep(15)
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_stealth())
