import asyncio
import os
from playwright.async_api import async_playwright

PROFILE_DIR = os.path.abspath("data/google_profile")
MEET_URL = "https://meet.google.com/zer-qtph-qfc"

async def test_click_ask():
    print("[*] Starting test_click_ask...")
    playwright = await async_playwright().start()

    os.system("powershell -Command \"Get-Process -Name chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*ms-playwright*' } | Stop-Process -Force\" >nul 2>&1")
    await asyncio.sleep(1)

    context = await playwright.chromium.launch_persistent_context(
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
    await page.goto(MEET_URL, wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(3)

    # Dismiss "Got it" tooltip if present
    got_it = page.locator('button:has-text("Got it"), button:has-text("OK"), button:has-text("閉じる")')
    if await got_it.count() > 0:
        print("[+] Dismissing 'Got it' banner...")
        await got_it.first.click(force=True)
        await asyncio.sleep(1)

    # Wait for name input or join button to be visible
    try:
        name_input = page.locator('input[type="text"]')
        await name_input.wait_for(state="visible", timeout=15000)
        print("[+] Name input found! Filling 'AEGIS Copilot'...")
        await name_input.fill("AEGIS Copilot")
        await asyncio.sleep(1)
    except Exception as e:
        print(f"[*] Name input wait skipped: {e}")

    # Dismiss any camera popup
    no_cam = page.locator('button:has-text("Continue without camera"), button:has-text("カメラなしで続行")')
    if await no_cam.count() > 0:
        await no_cam.first.click(force=True)
        await asyncio.sleep(1)

    # Click Ask to join
    ask_btn = page.locator('button:has-text("Ask to join"), button:has-text("Join now"), button:has-text("今すぐ参加"), button:has-text("参加をリクエスト")')
    if await ask_btn.count() > 0:
        print("[+] Clicking Ask to join button...")
        await ask_btn.first.click(force=True)
        await asyncio.sleep(2)

        # Check for "Continue without camera" dialog appearing AFTER click
        no_cam_after = page.locator('button:has-text("Continue without camera"), button:has-text("カメラなしで続行")')
        if await no_cam_after.count() > 0:
            print("[+] Clicking 'Continue without camera' after Join click...")
            await no_cam_after.first.click(force=True)
            await asyncio.sleep(2)

    await page.screenshot(path=os.path.abspath("debug_after_ask.png"))
    print("[+] Screenshot saved to debug_after_ask.png")
    
    # Check page state text
    body_text = await page.inner_text("body")
    print(f"[*] Page status text: {body_text[:300]}...")

if __name__ == "__main__":
    asyncio.run(test_click_ask())
