"""
AEGIS Google Meet Participant Bot (Playwright-based).
Joins Google Meet meetings, streams audio to the AEGIS Agent backend,
monitors and posts to the Meet chat when contradictions are detected,
and initiates screen sharing when commanded.
"""

import sys
import asyncio
import logging
from typing import Optional
import httpx
from playwright.async_api import async_playwright, Browser, Page

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AEGIS-MeetBot")


class GoogleMeetBot:
    def __init__(self, agent_server_url: str = "http://localhost:8000"):
        self.server_url = agent_server_url
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.in_meeting = False

    async def join_meeting(self, meet_url: str, bot_name: str = "AEGIS Copilot", headless: bool = False):
        """Launches browser, grants permissions, enters meet name, and joins."""
        logger.info(f"Connecting to Google Meet: {meet_url} as '{bot_name}'...")

        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-video-capture",
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )

        context = await self.browser.new_context(
            permissions=["microphone"],
            viewport={"width": 1280, "height": 720}
        )
        self.page = await context.new_page()

        try:
            await self.page.goto(meet_url, timeout=30000)
            await asyncio.sleep(2)

            # Turn off camera & microphone before entering
            try:
                mic_btn = self.page.locator('div[aria-label*="microphone" i], div[aria-label*="マイク" i]')
                if await mic_btn.is_visible():
                    await mic_btn.click()
                
                cam_btn = self.page.locator('div[aria-label*="camera" i], div[aria-label*="カメラ" i]')
                if await cam_btn.is_visible():
                    await cam_btn.click()
            except Exception as e:
                logger.warning(f"Could not toggle initial media buttons: {e}")

            # Fill name input if present
            name_input = self.page.locator('input[aria-label*="name" i], input[placeholder*="name" i], input[type="text"]')
            if await name_input.is_visible():
                await name_input.fill(bot_name)
                await asyncio.sleep(1)

            # Click Join / Ask to join button
            join_btn = self.page.locator('button:has-text("Ask to join"), button:has-text("Join now"), button:has-text("今すぐ参加")')
            if await join_btn.is_visible():
                await join_btn.click()
                logger.info("Clicked Join button. Entering meeting room...")
                self.in_meeting = True
            else:
                logger.info("Join button not immediately found; waiting for meeting room load...")

        except Exception as e:
            logger.error(f"Error joining meet: {e}")

    async def post_to_chat(self, message: str):
        """Opens Google Meet chat panel and sends a message."""
        if not self.page:
            logger.warning("No active Meet page to post chat.")
            return False

        try:
            logger.info(f"Posting clarification to Google Meet chat: {message}")
            
            # Click chat icon if chat window not already open
            chat_icon = self.page.locator('button[aria-label*="chat" i], button[aria-label*="チャット" i]')
            if await chat_icon.is_visible():
                await chat_icon.click()
                await asyncio.sleep(0.5)

            # Chat input area in Google Meet
            chat_box = self.page.locator('textarea[aria-label*="Send a message" i], textarea[aria-label*="メッセージを送信" i], textarea')
            if await chat_box.is_visible():
                await chat_box.fill(message)
                await self.page.keyboard.press("Enter")
                logger.info("Message successfully sent to Google Meet chat.")
                return True
            else:
                logger.warning("Chat textarea not found.")
                return False
        except Exception as e:
            logger.error(f"Error posting to meet chat: {e}")
            return False

    async def trigger_screen_share(self):
        """Triggers Google Meet screen share button when commanded."""
        if not self.page:
            return False
        try:
            logger.info("Triggering Screen Share in Google Meet...")
            present_btn = self.page.locator('button[aria-label*="Present now" i], button[aria-label*="画面を共有" i]')
            if await present_btn.is_visible():
                await present_btn.click()
                logger.info("Screen presentation initiated.")
                return True
        except Exception as e:
            logger.error(f"Error triggering screen share: {e}")
            return False

    async def close(self):
        if self.browser:
            await self.browser.close()
            logger.info("Google Meet bot session terminated.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        bot = GoogleMeetBot()
        asyncio.run(bot.join_meeting(target_url))
    else:
        print("Usage: python meet_bot.py <google_meet_url>")
