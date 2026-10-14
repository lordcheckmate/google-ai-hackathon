import asyncio
import os
from playwright.async_api import async_playwright

PROFILE_DIR = os.path.abspath("data/google_profile")
MEET_URL = "https://meet.google.com/zer-qtph-qfc"

async def test_join():
    print(f"[*] Launching Chromium with profile: {PROFILE_DIR}")
    playwright = await async_playwright().start()
    
    # Ensure any lingering chrome is stopped
    os.system("powershell -Command \"Get-Process -Name chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*ms-playwright*' } | Stop-Process -Force\" >nul 2>&1")
    await asyncio.sleep(1)

    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        permissions=["microphone"],
        args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox"
        ],
        viewport={"width": 1280, "height": 720}
    )

    page = await context.new_page()
    print(f"[*] Navigating to {MEET_URL}...")
    await page.goto(MEET_URL, wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(4)

    # Take screenshot of lobby
    screenshot_path = os.path.abspath("debug_lobby.png")
    await page.screenshot(path=screenshot_path)
    print(f"[*] Screenshot saved to {screenshot_path}")

    # Inspect all buttons and inputs
    buttons = await page.locator("button").all()
    print(f"[*] Found {len(buttons)} buttons:")
    for i, btn in enumerate(buttons):
        txt = (await btn.text_content() or "").strip()
        aria = await btn.get_attribute("aria-label") or ""
        disabled = await btn.get_attribute("disabled") is not None
        if txt or aria:
            print(f"   [{i}] Text: '{txt}' | Aria: '{aria}' | Disabled: {disabled}")

    inputs = await page.locator("input").all()
    print(f"[*] Found {len(inputs)} inputs:")
    for j, inp in enumerate(inputs):
        placeholder = await inp.get_attribute("placeholder") or ""
        aria = await inp.get_attribute("aria-label") or ""
        val = await inp.input_value()
        print(f"   [{j}] Placeholder: '{placeholder}' | Aria: '{aria}' | Val: '{val}'")

    # Dismiss any "Dismiss" / "Got it" dialogs
    dismiss_buttons = page.locator('button:has-text("Dismiss"), button:has-text("Got it"), button:has-text("閉じる")')
    if await dismiss_buttons.count() > 0:
        print("[*] Dismissing notification dialog...")
        await dismiss_buttons.first.click()
        await asyncio.sleep(1)

    # If name input exists and is empty, fill it
    name_inputs = page.locator('input[type="text"], input[aria-label*="name" i], input[placeholder*="name" i], input[aria-label*="名前" i]')
    if await name_inputs.count() > 0:
        val = await name_inputs.first.input_value()
        if not val:
            print("[*] Filling name with 'AEGIS Copilot'...")
            await name_inputs.first.fill("AEGIS Copilot")
            await asyncio.sleep(1)

    # Re-evaluate join buttons
    await asyncio.sleep(2)
    await page.screenshot(path=os.path.abspath("debug_after_name.png"))

    # Try clicking join
    join_target = page.locator('button:has-text("Join now"), button:has-text("Ask to join"), button:has-text("今すぐ参加"), button:has-text("参加をリクエスト")')
    if await join_target.count() > 0:
        btn = join_target.first
        txt = await btn.text_content()
        is_disabled = await btn.get_attribute("disabled") is not None
        print(f"[*] Found Join Target: '{txt}' (Disabled: {is_disabled})")
        
        # If disabled, wait up to 10s for it to become enabled
        if is_disabled:
            print("[*] Waiting for join button to become enabled...")
            for _ in range(20):
                await asyncio.sleep(0.5)
                if await btn.get_attribute("disabled") is None:
                    print("[+] Button is now enabled!")
                    break
        
        await btn.click(force=True)
        print("[+] Clicked join button!")
        await asyncio.sleep(4)
        await page.screenshot(path=os.path.abspath("debug_joined.png"))
    else:
        print("[-] Join button not found in selectors!")

if __name__ == "__main__":
    asyncio.run(test_join())
