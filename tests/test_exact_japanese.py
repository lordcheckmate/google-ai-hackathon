"""
Test with exact Japanese string: 'カメラを使用せずに続行'
"""
import asyncio
from playwright.async_api import async_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MEET_URL = "https://meet.google.com/zer-qtph-qfc"

async def test_exact():
    print("Launching clean Chrome with Japanese locale...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(permissions=["microphone"], locale="ja-JP")
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        print("Navigating to meet...")
        await page.goto(MEET_URL, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(3)

        # 1. Dismiss 'カメラを使用せずに続行' if shown
        print("1. Checking for 'カメラを使用せずに続行'...")
        no_cam = page.locator('button:has-text("カメラを使用せずに続行"), span:has-text("カメラを使用せずに続行"), [role="button"]:has-text("カメラを使用せずに続行"), button:has-text("Continue without camera")')
        try:
            await no_cam.first.wait_for(state="visible", timeout=6000)
            print(">>> Found 'カメラを使用せずに続行'! Clicking...")
            await no_cam.first.click(force=True)
            await asyncio.sleep(1.5)
        except Exception as e:
            print("No initial camera modal:", e)

        # 2. Dismiss 'OK' or '閉じる' if any tooltip
        try:
            ok_btn = page.locator('button:has-text("OK"), button:has-text("閉じる"), button:has-text("Got it")')
            if await ok_btn.count() > 0 and await ok_btn.first.is_visible():
                await ok_btn.first.click(force=True)
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # 3. Enter name
        print("3. Entering name...")
        name_input = page.locator('input[placeholder*="名前" i], input[aria-label*="名前" i], input[type="text"]').first
        await name_input.wait_for(state="visible", timeout=10000)
        await name_input.fill("AEGIS Copilot")
        print(">>> Filled name: AEGIS Copilot")
        await asyncio.sleep(1)

        # 4. Click '参加をリクエスト'
        print("4. Clicking '参加をリクエスト'...")
        btn = page.locator('button:has-text("参加をリクエスト"):not([disabled]), button:has-text("Ask to join"):not([disabled])').first
        await btn.wait_for(state="visible", timeout=10000)
        await btn.click(force=True)
        print(">>> Clicked '参加をリクエスト'!")
        await asyncio.sleep(2)

        # 5. Check if 'カメラを使用せずに続行' popped up post-click
        try:
            if await no_cam.first.is_visible():
                print(">>> Clicking post-click 'カメラを使用せずに続行'...")
                await no_cam.first.click(force=True)
                await asyncio.sleep(2)
        except Exception:
            pass

        await page.screenshot(path="exact_japanese_result.png")
        print("Saved exact_japanese_result.png")

        # 6. Read page text
        txt = await page.inner_text("body")
        print("--- Resulting text excerpt ---")
        for line in txt.split("\n")[:10]:
            if line.strip():
                print(" >", line.strip())

        if "許可するまでお待ちください" in txt or "Waiting to be admitted" in txt or "参加をリクエスト中" in txt:
            print(">>> 🎉🎉🎉 BINGO! Knocking screen successfully reached!")

        print("Keeping open for 20 seconds so you can see Admit button on host screen...")
        await asyncio.sleep(20)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_exact())
