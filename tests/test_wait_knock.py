"""
Check page state 5s after clicking 参加をリクエスト
"""
import asyncio
from playwright.async_api import async_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MEET_URL = "https://meet.google.com/zer-qtph-qfc"

async def test_wait_knock():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(permissions=["microphone"], locale="ja-JP")
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        await page.goto(MEET_URL, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(3)

        # 1. Dismiss 'カメラを使用せずに続行'
        try:
            no_cam = page.locator('button:has-text("カメラを使用せずに続行"), span:has-text("カメラを使用せずに続行"), [role="button"]:has-text("カメラを使用せずに続行"), button:has-text("Continue without camera")')
            await no_cam.first.wait_for(state="visible", timeout=6000)
            await no_cam.first.click(force=True)
            await asyncio.sleep(1.5)
        except Exception:
            pass

        # 2. Enter name
        name_input = page.locator('input[placeholder*="名前" i], input[aria-label*="名前" i], input[type="text"]').first
        await name_input.wait_for(state="visible", timeout=10000)
        await name_input.fill("AEGIS Copilot")
        await asyncio.sleep(1)

        # 3. Click '参加をリクエスト'
        btn = page.locator('button:has-text("参加をリクエスト"):not([disabled]), button:has-text("Ask to join"):not([disabled])').first
        await btn.wait_for(state="visible", timeout=10000)
        await btn.click(force=True)
        print("Clicked 参加をリクエスト!")

        # 4. Wait 4 seconds for Google Meet response
        await asyncio.sleep(4)
        await page.screenshot(path="waiting_knock_4s.png")
        print("Saved waiting_knock_4s.png")

        txt = await page.inner_text("body")
        print("Page text at 4s:")
        print(repr(txt[:300]))

        await asyncio.sleep(6)
        await page.screenshot(path="waiting_knock_10s.png")
        print("Saved waiting_knock_10s.png")

        await context.close()

if __name__ == "__main__":
    asyncio.run(test_wait_knock())
