"""
Test joining in the true order:
1. Click 'Continue without camera' modal first
2. Fill name
3. Click 'Ask to join'
4. Verify '会議の主催者が通話への参加を許可するまでお待ちください'
"""
import asyncio
import os
from playwright.async_api import async_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MEET_URL = "https://meet.google.com/zer-qtph-qfc"
PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "bot_profile"))

async def test_order():
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
        print("1. Navigating...")
        await page.goto(MEET_URL, wait_until="domcontentloaded", timeout=45000)

        # 2. Check and click 'Continue without camera' modal first
        print("2. Checking for early 'Continue without camera' modal...")
        try:
            no_cam = page.locator('button:has-text("Continue without camera"), span:has-text("Continue without camera"), [role="button"]:has-text("Continue without camera"), button:has-text("カメラなしで続行")').first
            await no_cam.wait_for(state="visible", timeout=10000)
            print(">>> Found early modal! Clicking 'Continue without camera'...")
            await no_cam.click(force=True)
            await asyncio.sleep(1.5)
        except Exception as e:
            print(f"Early modal not shown: {e}")

        # 3. Dismiss 'Got it' banner if present
        try:
            got_it = page.locator('button:has-text("Got it"), span:has-text("Got it")')
            if await got_it.count() > 0 and await got_it.first.is_visible():
                print(">>> Dismissing Got it banner...")
                await got_it.first.click(force=True)
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # 4. Fill name
        print("4. Locating name input...")
        name_input = page.locator('input[placeholder*="name" i], input[aria-label*="name" i], input[type="text"]').first
        await name_input.wait_for(state="visible", timeout=10000)
        print(">>> Filling name: AEGIS Copilot...")
        await name_input.fill("AEGIS Copilot")
        await asyncio.sleep(1)

        await page.screenshot(path="order_step_1_named.png")
        print("Saved order_step_1_named.png")

        # 5. Click enabled Ask to join
        print("5. Clicking Ask to join...")
        btn = page.locator('button:has-text("Ask to join"):not([disabled]), button:has-text("Join now"):not([disabled]), button:has-text("今すぐ参加"):not([disabled]), button:has-text("参加をリクエスト"):not([disabled])').first
        await btn.wait_for(state="visible", timeout=10000)
        await btn.click()
        await asyncio.sleep(2)

        # 6. Any secondary modal?
        try:
            no_cam2 = page.locator('button:has-text("Continue without camera"), span:has-text("Continue without camera"), [role="button"]:has-text("Continue without camera"), button:has-text("カメラなしで続行")').first
            if await no_cam2.is_visible():
                print("Found secondary camera modal, clicking...")
                await no_cam2.click(force=True)
                await asyncio.sleep(1)
        except Exception:
            pass

        await page.screenshot(path="order_step_2_knocked.png")
        print("Saved order_step_2_knocked.png")

        # 7. Check for host admission screen
        print("Checking state for 10 seconds...")
        for sec in range(10):
            txt = await page.inner_text("body")
            if "許可するまでお待ちください" in txt or "Waiting to be admitted" in txt or "Asking to join" in txt or "参加をリクエスト中" in txt:
                print(f">>> 🎉 SUCCESS! Host admission prompt active at {sec}s!")
                print(f"Excerpt: {repr(txt[:200])}")
                break
            await asyncio.sleep(1)

        await page.screenshot(path="order_step_3_final.png")
        print("Saved order_step_3_final.png")
        print("Keeping open for 15s so host can see Admit prompt...")
        await asyncio.sleep(15)
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_order())
