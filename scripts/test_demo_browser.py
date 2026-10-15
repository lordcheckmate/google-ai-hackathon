import time
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path(r"C:\Users\saega\.gemini\antigravity\brain\f3baab2f-8cfd-44bf-96de-54b3e40dd866\browser_test_results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        print("Navigating to http://127.0.0.1:8080?fresh=1...")
        page.goto("http://127.0.0.1:8080?fresh=1")
        page.wait_for_selector("#ws-status")
        time.sleep(2)

        # Helper to send a turn
        def send_turn(text, wait_sec=8):
            print(f"\n--- SENDING: {text[:60]}... ---")
            page.fill("#manual-text", text)
            page.click("#send-manual-btn")
            time.sleep(wait_sec)

        # 1. Turn 1: Process generation
        turn1 = "First we capture images as initial step, then we convert images to text where captured images are processed and text extracted, then we do internal review where an internal review is performed before release, then we share text with client."
        send_turn(turn1, wait_sec=14)
        page.screenshot(path=str(OUTPUT_DIR / "step1_workflow_v1.png"))
        tabs1 = page.locator(".visual-tab-pill").all_text_contents()
        print(f"Tabs after Turn 1: {tabs1}")

        # 2. Turn 2: Illustrate step
        turn2 = "Illustrate convert images to text with Nano Banana"
        send_turn(turn2, wait_sec=14)
        page.screenshot(path=str(OUTPUT_DIR / "step2_illustration.png"))
        tabs2 = page.locator(".visual-tab-pill").all_text_contents()
        print(f"Tabs after Turn 2: {tabs2}")

        # 3. Turn 3: Diagram update (add compliance check)
        turn3 = "Add legal compliance check after convert images to text."
        send_turn(turn3, wait_sec=14)
        page.screenshot(path=str(OUTPUT_DIR / "step3_workflow_v2.png"))
        tabs3 = page.locator(".visual-tab-pill").all_text_contents()
        print(f"Tabs after Turn 3: {tabs3}")

        # 4. Turn 4: Compare options
        turn4 = "Weigh options: Firestore has low cost and sub-10ms latency. Cloud Spanner has high cost and relational SQL joins."
        send_turn(turn4, wait_sec=12)
        page.screenshot(path=str(OUTPUT_DIR / "step4_compare.png"))
        tabs4 = page.locator(".visual-tab-pill").all_text_contents()
        print(f"Tabs after Turn 4: {tabs4}")

        # 5. Turn 5: Calculate
        turn5 = "calculate 75000 * 0.06"
        send_turn(turn5, wait_sec=8)
        page.screenshot(path=str(OUTPUT_DIR / "step5_calculation.png"))
        tabs5 = page.locator(".visual-tab-pill").all_text_contents()
        print(f"Tabs after Turn 5: {tabs5}")

        # 6. Turn 6: Illustrate banana shape agent
        turn6 = "Illustrate a banana shape agent"
        send_turn(turn6, wait_sec=14)
        page.screenshot(path=str(OUTPUT_DIR / "step6_banana_agent.png"))
        tabs6 = page.locator(".visual-tab-pill").all_text_contents()
        print(f"Tabs after Turn 6: {tabs6}")

        # 7. Turn 7: Contradiction
        turn7 = "To hit the deadline we will skip internal review entirely and release directly to client."
        send_turn(turn7, wait_sec=10)
        page.screenshot(path=str(OUTPUT_DIR / "step7_contradiction.png"))
        speech_bubble = page.locator("#char-speech-bubble").text_content()
        print(f"Speech bubble after Turn 7: {speech_bubble}")

        # 8. Turn 8: Checklist
        turn8 = "Sarah to finalize pipeline benchmark, Elena to configure Cloud Run, Ken to notify client."
        send_turn(turn8, wait_sec=12)
        page.screenshot(path=str(OUTPUT_DIR / "step8_checklist.png"))
        tabs8 = page.locator(".visual-tab-pill").all_text_contents()
        print(f"Tabs after Turn 8: {tabs8}")

        browser.close()
        print("\nAll browser test turns completed successfully!")

if __name__ == "__main__":
    run_test()
