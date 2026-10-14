import asyncio
import os
from playwright.async_api import async_playwright

PROFILE_DIR = os.path.abspath("data/google_profile")
MEET_URL = "https://meet.google.com/zer-qtph-qfc"

async def test_full_join():
    print("[*] Starting test_full_join...")
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
    print(f"[*] Navigating to {MEET_URL}...")
    await page.goto(MEET_URL, wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(3)

    # 1. Fill name if prompted
    name_inputs = page.locator('input[type="text"], input[aria-label*="name" i], input[placeholder*="name" i]')
    if await name_inputs.count() > 0:
        val = await name_inputs.first.input_value()
        if not val:
            print("[+] Filling name: 'AEGIS Copilot'")
            await name_inputs.first.fill("AEGIS Copilot")
            await asyncio.sleep(1)

    # 2. Click Join / Ask to join
    join_btn = page.locator('button:has-text("Ask to join"), button:has-text("Join now"), button:has-text("今すぐ参加"), button:has-text("参加をリクエスト")')
    if await join_btn.count() > 0:
        print("[+] Clicking Ask to join / Join now...")
        await join_btn.first.click(force=True)
        await asyncio.sleep(2)

    # 3. Handle "Do you want people to see you in the meeting?" modal -> Click "Continue without camera"
    no_cam_btn = page.locator('button:has-text("Continue without camera"), button:has-text("カメラなしで続行"), [role="button"]:has-text("Continue without camera"), [role="button"]:has-text("カメラなしで続行")')
    if await no_cam_btn.count() > 0:
        print("[+] Found 'Continue without camera' modal! Clicking it...")
        await no_cam_btn.first.click(force=True)
        await asyncio.sleep(2)

    # 4. Take final screenshot
    screenshot_path = os.path.abspath("debug_final_state.png")
    await page.screenshot(path=screenshot_path)
    print(f"[+] Final screenshot saved to {screenshot_path}")

    # Keep open a bit so user can see it in meeting
    print("[+] Successfully requested to join! Holding session...")
    await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(test_full_join())
