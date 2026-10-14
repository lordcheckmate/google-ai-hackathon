import asyncio
import os
from playwright.async_api import async_playwright

PROFILE_DIR = os.path.abspath("data/google_profile")
MEET_URL = "https://meet.google.com/zer-qtph-qfc"

async def test_stable_join():
    print("[*] Launching Chromium to join Meet...")
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
    await asyncio.sleep(4)

    # 1. Dismiss any "Got it" banner
    got_it = page.locator('button:has-text("Got it"), button:has-text("OK"), button:has-text("閉じる")')
    if await got_it.count() > 0:
        print("[+] Dismissing 'Got it' banner...")
        await got_it.first.click(force=True)
        await asyncio.sleep(1)

    # 2. Wait and fill name
    name_input = page.locator('input[type="text"]').first
    try:
        await name_input.wait_for(state="visible", timeout=8000)
        print("[+] Name input found! Filling 'AEGIS Copilot'...")
        await name_input.fill("AEGIS Copilot")
        await asyncio.sleep(1)
    except Exception:
        print("[*] No name input, proceeding...")

    # 3. Dismiss any camera popup before clicking
    no_cam = page.locator('button:has-text("Continue without camera"), button:has-text("カメラなしで続行")')
    if await no_cam.count() > 0:
        print("[+] Dismissing pre-click camera popup...")
        await no_cam.first.click(force=True)
        await asyncio.sleep(1)

    # 4. Click Ask to join
    ask_btn = page.locator('button:has-text("Ask to join"), button:has-text("Join now"), button:has-text("今すぐ参加"), button:has-text("参加をリクエスト")')
    if await ask_btn.count() > 0:
        print("[+] Clicking Ask to join...")
        await ask_btn.first.click(force=True)
        await asyncio.sleep(2)

        # 5. Dismiss any post-click "Continue without camera" popup
        no_cam_after = page.locator('button:has-text("Continue without camera"), button:has-text("カメラなしで続行")')
        if await no_cam_after.count() > 0:
            print("[+] Clicking 'Continue without camera' modal...")
            await no_cam_after.first.click(force=True)
            await asyncio.sleep(3)

    # 6. Wait for meeting room or admission state
    await asyncio.sleep(5)
    await page.screenshot(path=os.path.abspath("debug_meeting_state.png"))
    print("[+] Saved debug_meeting_state.png")

    # Keep browser session running!
    print("[+] Agent is now actively holding the Google Meet session!")
    print("[+] Browser will stay alive for the meeting...")
    try:
        while True:
            await asyncio.sleep(10)
    except Exception:
        pass

if __name__ == "__main__":
    asyncio.run(test_stable_join())
