import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    out_dir = r"c:\Users\saega\OneDrive - stu.teikyo-u.ac.jp\Documents\HackathonGoogle\submission_screenshots"
    os.makedirs(out_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        
        print("1. Loading AEGIS on Google Cloud Run...", flush=True)
        await page.goto("https://ai-meeting-assistant-7y3l4a2iba-uc.a.run.app/?user=judge&pass=Aegis2026!&fresh=1", wait_until="commit")
        await page.wait_for_timeout(3500)
        
        # Switch to Japanese
        await page.select_option("#lang-select", "ja-JP")
        await page.wait_for_timeout(1000)
        
        # Shot 1: Standby Dashboard
        p1 = os.path.join(out_dir, "01_dashboard_standby.png")
        await page.screenshot(path=p1)
        print(f"Captured: {p1}", flush=True)
        
        async def submit_turn(text: str):
            print(f"Submitting: {text[:45]}...", flush=True)
            await page.fill("#manual-text", "")
            await page.fill("#manual-text", text)
            await page.click("#send-manual-btn")
            
        # Turn 1: Restaurant QR Ordering (Steps 1-3)
        await submit_turn("レストランのモバイルオーダーの流れを整理しましょう。まずお客様が卓上のQRコードをスマホで読み取り、アプリ不要でWebメニューを開いて料理を選びます。")
        print("Waiting 8s for flow v1 generation...", flush=True)
        await page.wait_for_timeout(8000)
        p2 = os.path.join(out_dir, "02_flow_v1_restaurant.png")
        await page.screenshot(path=p2)
        print(f"Captured: {p2}", flush=True)
        
        # Turn 2: Kitchen Relay (Steps 4-6)
        await submit_turn("続いて、お客様が料理をカートに入れて注文を確定し、厨房のキッチンディスプレイにデータが即座に届き、調理後に料理が配膳されます。")
        print("Waiting 8s for flow v2 update...", flush=True)
        await page.wait_for_timeout(8000)
        p3 = os.path.join(out_dir, "03_flow_v2_restaurant.png")
        await page.screenshot(path=p3)
        print(f"Captured: {p3}", flush=True)
        
        # Turn 3: Nano Banana Illustration
        await submit_turn("エイジス、QRコード読み取りステップのイラストを描いて")
        print("Waiting 10s for Nano Banana illustration...", flush=True)
        await page.wait_for_timeout(10000)
        p4 = os.path.join(out_dir, "04_nano_banana_illustrated.png")
        await page.screenshot(path=p4)
        print(f"Captured: {p4}", flush=True)
        
        # Turn 4: Contradiction Alert Trigger
        await submit_turn("ちょっと待ってください。うちの店はスマホ注文は禁止で、レジで現金払いのみです。")
        print("Waiting 8s for Contradiction Alert...", flush=True)
        await page.wait_for_timeout(8000)
        p5 = os.path.join(out_dir, "05_contradiction_alert.png")
        await page.screenshot(path=p5)
        print(f"Captured: {p5}", flush=True)
        
        # Turn 5: Click a node to open drilldown modal
        nodes = page.locator(".flow-node, g.node, .flow-step-card")
        count = await nodes.count()
        print(f"Nodes found on page: {count}", flush=True)
        if count > 0:
            print("Clicking first node to open detail drilldown modal...", flush=True)
            await nodes.first.click()
            await page.wait_for_timeout(2000)
            p6 = os.path.join(out_dir, "06_node_drilldown_modal.png")
            await page.screenshot(path=p6)
            print(f"Captured: {p6}", flush=True)
            
        await browser.close()
        print("SUCCESS! ALL SUBMISSION SCREENSHOTS CAPTURED FROM CLOUD RUN!", flush=True)

asyncio.run(main())
