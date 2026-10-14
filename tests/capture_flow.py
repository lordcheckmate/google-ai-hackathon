"""
Capture progressive screenshots of Google Meet lobby to see what is happening.
"""
import asyncio
import os
from playwright.async_api import async_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MEET_URL = "https://meet.google.com/zer-qtph-qfc"
PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "bot_profile"))

async def capture_flow():
    os.system('powershell -Command "Get-Process -Name chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like \'*bot_profile*\' } | Stop-Process -Force" >nul 2>&1')
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
                "--no-sandbox"
            ],
            viewport={"width": 1280, "height": 720}
        )

        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        print("Navigating...")
        await page.goto(MEET_URL, wait_until="domcontentloaded", timeout=45000)

        for i in range(1, 10):
            await asyncio.sleep(2)
            await page.screenshot(path=f"flow_step_{i}.png")
            txt = await page.inner_text("body")
            print(f"Step {i} ({i*2}s) text: {repr(txt[:150])}")
            if "許可するまでお待ちください" in txt or "Your name" in txt or "Ask to join" in txt or "What's your name" in txt:
                print(f"--> Found key state at step {i}!")
                break

        await context.close()

if __name__ == "__main__":
    asyncio.run(capture_flow())
