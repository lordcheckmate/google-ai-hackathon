"""
Direct Playwright Test for Joining Google Meet with Precise Lobby Timing & Handling.
"""

import asyncio
import os
from playwright.async_api import async_playwright

MEET_URL = "https://meet.google.com/zer-qtph-qfc"
PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "google_profile"))

async def test_join():
    print(f"=== Starting Precise Join Test on {MEET_URL} ===")
    
    # Kill any stale chromium instances
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
        print(f"1. Navigating to {MEET_URL}...")
        await page.goto(MEET_URL, wait_until="domcontentloaded", timeout=45000)

        # 2. Wait for either name input OR Join button (past 'Getting ready...' spinner)
        print("2. Waiting for 'Getting ready' spinner to resolve and lobby elements to appear...")
        name_input = page.locator('input[placeholder*="name" i], input[aria-label*="name" i], input[type="text"]').first
        
        # Wait up to 25s for name input
        try:
            await name_input.wait_for(state="visible", timeout=25000)
            print(">>> Name input is now visible!")
        except Exception as e:
            print(f"Name input wait notice: {e}")

        # 3. Dismiss 'Got it' banner if present
        try:
            got_it = page.locator('button:has-text("Got it"), span:has-text("Got it"), [role="button"]:has-text("Got it")')
            if await got_it.count() > 0 and await got_it.first.is_visible():
                print(">>> Dismissing 'Got it' banner...")
                await got_it.first.click(force=True)
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Got it dismiss skip: {e}")

        # 4. Fill name if visible and empty
        if await name_input.is_visible():
            val = await name_input.input_value()
            if not val:
                print(">>> Filling name: 'AEGIS Copilot'...")
                await name_input.fill("AEGIS Copilot")
                await asyncio.sleep(1)

        await page.screenshot(path="test_precise_1_named.png")
        print("Saved test_precise_1_named.png")

        # 5. Wait for enabled Ask to join / Join now button
        print("5. Waiting for enabled 'Ask to join' / 'Join now' button...")
        enabled_btn = page.locator('button:has-text("Ask to join"):not([disabled]), button:has-text("Join now"):not([disabled]), button:has-text("今すぐ参加"):not([disabled]), button:has-text("参加をリクエスト"):not([disabled])').first
        try:
            await enabled_btn.wait_for(state="visible", timeout=10000)
            print(">>> Found enabled join button! Clicking...")
            await enabled_btn.click()
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Wait for enabled join button fallback: {e}")
            fallback_btn = page.locator('button:has-text("Ask to join"), button:has-text("Join now")').first
            await fallback_btn.click(force=True)
            await asyncio.sleep(2)

        await page.screenshot(path="test_precise_2_after_join_click.png")
        print("Saved test_precise_2_after_join_click.png")

        # 6. Check for "Continue without camera" modal
        print("6. Checking for 'Continue without camera' modal...")
        no_cam = page.locator('button:has-text("Continue without camera"), span:has-text("Continue without camera"), [role="button"]:has-text("Continue without camera"), button:has-text("カメラなしで続行")')
        try:
            await no_cam.first.wait_for(state="visible", timeout=5000)
            print(">>> Found 'Continue without camera' modal! Clicking...")
            await no_cam.first.click(force=True)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"No camera modal appeared or timed out: {e}")

        await page.screenshot(path="test_precise_3_submitted.png")
        print("Saved test_precise_3_submitted.png")

        # 7. Check status
        for sec in range(5):
            body_txt = await page.inner_text("body")
            if "Asking to join" in body_txt or "参加をリクエスト中" in body_txt or "Waiting to be admitted" in body_txt:
                print(f">>> SUCCESS: Bot is asking to join (Waiting for host admission) at second {sec}!")
                break
            elif "You're the only one here" in body_txt or "People" in body_txt or "Meeting details" in body_txt:
                print(f">>> SUCCESS: Bot is directly INSIDE the meeting at second {sec}!")
                break
            await asyncio.sleep(1)

        await page.screenshot(path="test_precise_4_final.png")
        print("Saved test_precise_4_final.png")
        print("Keeping open for 15s to allow observation...")
        await asyncio.sleep(15)
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_join())
