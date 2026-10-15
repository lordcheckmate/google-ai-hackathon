import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    out_dir = r"c:\Users\saega\OneDrive - stu.teikyo-u.ac.jp\Documents\HackathonGoogle\submission_screenshots"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        
        await page.goto("https://ai-meeting-assistant-7y3l4a2iba-uc.a.run.app/?user=judge&pass=Aegis2026!&fresh=1", wait_until="commit")
        await page.wait_for_timeout(3500)
        await page.select_option("#lang-select", "ja-JP")
        await page.wait_for_timeout(1000)
        
        async def submit_turn(text: str):
            await page.fill("#manual-text", "")
            await page.fill("#manual-text", text)
            await page.click("#send-manual-btn")
            
        # Comparison Table
        print("Submitting comparison turn...", flush=True)
        await submit_turn("QRコード注文システムと従来の専用タブレット端末のメリット・デメリットをコストと運用の観点で比較してください。")
        await page.wait_for_timeout(9000)
        p_comp = os.path.join(out_dir, "06_compare_table.png")
        await page.screenshot(path=p_comp)
        print(f"Captured: {p_comp}", flush=True)
        
        # Checklist / Action Items
        print("Submitting checklist turn...", flush=True)
        await submit_turn("導入に向けたタスクリストを作成してください。卓上QRコードの印刷、Wi-Fi環境の整備、スタッフへの操作研修の3点です。")
        await page.wait_for_timeout(9000)
        p_check = os.path.join(out_dir, "07_checklist_tasks.png")
        await page.screenshot(path=p_check)
        print(f"Captured: {p_check}", flush=True)
        
        await browser.close()
        print("COMPARISON AND CHECKLIST CAPTURED!", flush=True)

asyncio.run(main())
