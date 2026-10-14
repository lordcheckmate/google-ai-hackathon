"""
Test joining in fresh Incognito mode (matching user's exact working setup).
"""
import asyncio
import os
from playwright.async_api import async_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MEET_URL = "https://meet.google.com/zer-qtph-qfc"

async def test_incognito():
    print("Launching clean Incognito Chrome...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = await browser.new_context(
            permissions=["microphone"],
            locale="ja-JP"
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        print("Navigating to meet...")
        await page.goto(MEET_URL, wait_until="domcontentloaded", timeout=45000)

        # Wait for either lobby input or camera dialog
        await asyncio.sleep(4)
        await page.screenshot(path="incog_1_load.png")

        # Click Continue without camera / カメラなしで続行 if present
        try:
            no_cam = page.locator('button:has-text("Continue without camera"), button:has-text("カメラなしで続行"), [role="button"]:has-text("カメラなしで続行")').first
            if await no_cam.is_visible():
                print("Clicking 'カメラなしで続行'...")
                await no_cam.click(force=True)
                await asyncio.sleep(1)
        except Exception as e:
            print("No early camera modal:", e)

        # Name input
        name_input = page.locator('input[placeholder*="name" i], input[placeholder*="お名前" i], input[aria-label*="名前" i], input[type="text"]').first
        if await name_input.is_visible():
            print("Filling name: AEGIS Copilot...")
            await name_input.fill("AEGIS Copilot")
            await asyncio.sleep(1)

        await page.screenshot(path="incog_2_named.png")

        # Click Ask to join / 参加をリクエスト
        btn = page.locator('button:has-text("Ask to join"):not([disabled]), button:has-text("参加をリクエスト"):not([disabled])').first
        await btn.wait_for(state="visible", timeout=10000)
        print("Clicking 参加をリクエスト (Ask to join)...")
        await btn.click()
        await asyncio.sleep(3)

        # Secondary modal check
        try:
            no_cam2 = page.locator('button:has-text("Continue without camera"), button:has-text("カメラなしで続行"), [role="button"]:has-text("カメラなしで続行")').first
            if await no_cam2.is_visible():
                print("Clicking secondary 'カメラなしで続行'...")
                await no_cam2.click(force=True)
                await asyncio.sleep(2)
        except Exception:
            pass

        await page.screenshot(path="incog_3_knocked.png")
        txt = await page.inner_text("body")
        print("Body text excerpt:", repr(txt[:250]))

        if "許可するまでお待ちください" in txt or "Waiting to be admitted" in txt:
            print(">>> 🎉🎉🎉 SUCCESS! Knocking screen reached: '会議の主催者が通話への参加を許可するまでお待ちください'!")
        else:
            print(">>> Resulting text did not match admission screen.")

        print("Keeping open for 20 seconds so user can see it...")
        await asyncio.sleep(20)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_incognito())
