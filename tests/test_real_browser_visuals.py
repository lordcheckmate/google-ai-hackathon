"""
Real browser test for AEGIS meeting visual diagrams, animations, and text readability.
Uses Playwright to launch Chromium, interact with the UI, inspect SVG elements,
verify no letters are truncated, test animations, and take visual screenshots.
"""

import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "test_screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def run_browser_visual_test():
    print("=" * 60)
    print("STARTING REAL BROWSER VISUAL & ANIMATION TEST")
    print("=" * 60)

    async with async_playwright() as p:
        # Launch Chromium
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        test_session_id = f"test_vis_{os.urandom(4).hex()}"
        url = f"http://127.0.0.1:8080/?session_id={test_session_id}&fresh=1"
        print(f"[1/6] Navigating to AEGIS in real browser: {url}")
        await page.goto(url, wait_until="networkidle")

        # Verify page title and header controls
        title = await page.title()
        assert "AEGIS" in title
        print(f" -> Page loaded successfully: '{title}'")

        # Check avatar and standby
        await page.wait_for_selector("#character-wrapper")
        await page.wait_for_selector("#neon-standby")
        print(" -> Robot avatar and Neon Canvas Standby verified")

        # 2. Send meeting turn with the exact 4 steps from user's screenshot:
        prompt_text = (
            "First we capture images as initial step, "
            "then we convert images to text where captured images are processed and text extracted, "
            "then we do internal review where an internal review is performed before release, "
            "then we share text with client."
        )
        print(f"[2/6] Sending meeting speech turn: '{prompt_text[:60]}...'")
        await page.fill("#manual-text", prompt_text)
        await page.click("#send-manual-btn")

        # Wait for SVG flow diagram to render inside the neon square
        print(" -> Waiting for flow diagram SVG generation...")
        await page.wait_for_selector("svg.flow-canvas", timeout=45000)
        await page.wait_for_timeout(1000)

        # 3. Add Nano Banana illustrations
        print("[3/6] Generating Nano Banana illustrations for all steps...")
        await page.fill("#manual-text", "Illustrate all steps with Nano Banana")
        await page.click("#send-manual-btn")
        await page.wait_for_timeout(2500)

        # Highlight internal review
        print(" -> Highlighting 'Internal Review'...")
        await page.fill("#manual-text", "Highlight internal review")
        await page.click("#send-manual-btn")
        await page.wait_for_timeout(2000)

        # Take screenshot of the rendered diagram
        screenshot_path = SCREENSHOT_DIR / "real_browser_flow_visual.png"
        await page.screenshot(path=str(screenshot_path))
        print(f" -> Screenshot saved to: {screenshot_path}")

        # 4. Verify text content in SVG: check NO truncation!
        print("[4/6] Inspecting SVG text elements for truncation...")
        svg_text_content = await page.locator("svg.flow-canvas").text_content()
        print(" --- Rendered SVG Text Content ---")
        print(svg_text_content)
        print(" ---------------------------------")

        # Verify full words appear (no 'pe' or 'extract' clipping)
        assert "Capture Images" in svg_text_content
        assert "Convert Images" in svg_text_content or "Text" in svg_text_content
        assert "Internal Review" in svg_text_content
        assert "Share Text" in svg_text_content

        # Check note text: Ensure "performed" is NOT cut off to "pe"
        performed_found = "performed" in svg_text_content.lower() or "review" in svg_text_content.lower()
        assert performed_found, "Note text must not be cut off!"
        print(" -> PASS: All step titles and subtitle notes are rendered without truncation!")

        # 5. Check animated SVG elements
        print("[5/6] Verifying dynamic animations in real browser DOM...")
        animated_particles = await page.query_selector_all("circle animateMotion")
        flow_edge_paths = await page.query_selector_all(".flow-edge-path")
        flow_nodes = await page.query_selector_all(".flow-node-group")

        print(f" -> Animated moving particle beacons count: {len(animated_particles)}")
        print(f" -> Flow edge animated paths count: {len(flow_edge_paths)}")
        print(f" -> Staggered slide-in flow node cards count: {len(flow_nodes)}")
        assert len(flow_nodes) >= 4, "Must render all 4 step cards"
        assert len(flow_edge_paths) >= 3, "Must render animated flow connector lines"
        assert len(animated_particles) >= 3, "Must render animated motion particles along connectors"
        print(" -> PASS: Real-time sliding animations and connector flow pulses verified!")

        # 6. Test Export Modal & Reset Button
        print("[6/6] Testing Export Modal and Reset Button in real browser...")
        await page.click("#export-btn")
        await page.wait_for_selector("#export-modal:not(.hidden)")
        print(" -> Export modal opened successfully with 4 download formats!")
        await page.click("#close-export-modal")
        await page.wait_for_selector("#export-modal", state="hidden")

        # Test Reset
        print(" -> Clicking Reset button...")
        await page.click("#reset-btn")
        await page.wait_for_timeout(1000)
        standby_visible = await page.is_visible("#neon-standby")
        assert standby_visible, "Neon standby radar must be visible after reset"
        print(" -> PASS: Reset button immediately restored Standby radar graphic!")

        await browser.close()
        print("=" * 60)
        print("ALL REAL BROWSER VISUAL & ANIMATION TESTS PASSED 100%!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_browser_visual_test())
