"""
AEGIS Google Meet Session & Account Manager.
Handles persistent Google Account authentication, automated meeting joining with
logged-in credentials, live chat messaging, and screen share triggering.
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, BrowserContext, Page

logger = logging.getLogger("AEGIS-MeetSession")

PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "google_profile"))
os.makedirs(PROFILE_DIR, exist_ok=True)


class MeetSessionManager:
    def __init__(self):
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.active_meeting_url: Optional[str] = None
        self.is_connected_to_meeting = False
        self._login_process_active = False
        self.transcript_callback = None

    async def open_google_account_login(self) -> Dict[str, Any]:
        """
        Opens a visible browser window allowing the user to sign into
        their Google Account (accounts.google.com). Session is permanently
        saved in PROFILE_DIR.
        """
        if self._login_process_active:
            return {"status": "in_progress", "message": "Login window is already open."}

        self._login_process_active = True
        logger.info(f"Opening Google Account login window with profile: {PROFILE_DIR}")

        try:
            if not self.playwright:
                self.playwright = await async_playwright().start()

            if not self.context:
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    headless=False,
                    permissions=["microphone"],
                    args=[
                        "--disable-video-capture",
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox"
                    ],
                    viewport={"width": 1024, "height": 768}
                )

            login_page = await self.context.new_page()
            await login_page.goto("https://accounts.google.com", timeout=30000)
            logger.info("Google Login page loaded. Waiting for user interaction...")
            self._login_process_active = False

            return {
                "status": "opened",
                "message": "Google Login window opened. Log into your Google account and close the window when done. Your session will be saved permanently."
            }
        except Exception as e:
            logger.error(f"Failed to open Google login: {e}")
            self._login_process_active = False
            return {"status": "error", "message": str(e)}

    async def check_account_status(self) -> Dict[str, Any]:
        """Checks if a Google account is actively signed in within the profile."""
        has_account = False
        pref_path = os.path.join(PROFILE_DIR, "Default", "Preferences")
        if os.path.exists(pref_path):
            try:
                import json
                with open(pref_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    accs = d.get("signin", {}).get("accounts_metadata_dict", {})
                    has_account = len(accs) > 0
            except Exception:
                has_account = False

        return {
            "has_saved_account": has_account,
            "profile_path": PROFILE_DIR,
            "in_meeting": self.is_connected_to_meeting,
            "active_meeting": self.active_meeting_url
        }

    async def join_meeting(self, meet_url: str, headless: bool = False) -> Dict[str, Any]:
        """
        Joins a Google Meet using the saved Google Account profile.
        Automatically handles media permissions, entry, and audio stream hooks.
        """
        import re
        # Bulletproof URL normalization
        meet_url = (meet_url or "").strip().strip("'\"")
        code_match = re.search(r'([a-z]{3}-[a-z]{4}-[a-z]{3})', meet_url, re.IGNORECASE)
        if code_match:
            meet_url = f"https://meet.google.com/{code_match.group(1).lower()}"
        else:
            meet_url = re.sub(r'^(https?:?\/*)+', '', meet_url, flags=re.IGNORECASE)
            if not meet_url.startswith("meet.google.com"):
                meet_url = f"meet.google.com/{meet_url}"
            meet_url = f"https://{meet_url}"

        logger.info(f"Joining Google Meet with saved Google Profile: {meet_url}")
        
        try:
            if not self.playwright:
                self.playwright = await async_playwright().start()

            # Reuse existing context if already alive
            if not self.context:
                try:
                    self.context = await self.playwright.chromium.launch_persistent_context(
                        user_data_dir=PROFILE_DIR,
                        headless=headless,
                        permissions=["microphone"],  # Camera completely disabled
                        args=[
                            "--disable-video-capture",
                            "--use-fake-ui-for-media-stream",
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox"
                        ],
                        viewport={"width": 1280, "height": 720}
                    )
                except Exception as launch_err:
                    if "profile is already in use" in str(launch_err) or "existing browser session" in str(launch_err):
                        # Clean orphaned chromium processes
                        os.system("powershell -Command \"Get-Process -Name chrome -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*ms-playwright*' } | Stop-Process -Force\" >nul 2>&1")
                        await asyncio.sleep(1)
                        self.context = await self.playwright.chromium.launch_persistent_context(
                            user_data_dir=PROFILE_DIR,
                            headless=headless,
                            permissions=["microphone"],
                            args=[
                                "--disable-video-capture",
                                "--use-fake-ui-for-media-stream",
                                "--disable-blink-features=AutomationControlled",
                                "--no-sandbox"
                            ],
                            viewport={"width": 1280, "height": 720}
                        )
                    else:
                        raise launch_err

            self.page = await self.context.new_page()
            logger.info(f"Navigating to {meet_url}...")
            await self.page.goto(meet_url, wait_until="domcontentloaded", timeout=45000)

            # 1. Wait for 'Getting ready' spinner to resolve and lobby elements to appear
            logger.info("Waiting for lobby elements to render (bypassing 'Getting ready' spinner)...")
            name_input = self.page.locator('input[placeholder*="name" i], input[aria-label*="name" i], input[type="text"]').first
            join_btn = self.page.locator('button:has-text("Ask to join"), button:has-text("Join now"), button:has-text("今すぐ参加"), button:has-text("参加をリクエスト")')
            
            try:
                # Wait up to 25s for lobby to settle
                await asyncio.wait([
                    asyncio.create_task(name_input.wait_for(state="visible", timeout=25000)),
                    asyncio.create_task(join_btn.first.wait_for(state="visible", timeout=25000))
                ], return_when=asyncio.FIRST_COMPLETED)
            except Exception as e:
                logger.info(f"Lobby wait completed with note: {e}")

            # 2. Dismiss any "Got it" banner / tooltip if present
            try:
                got_it = self.page.locator('button:has-text("Got it"), span:has-text("Got it"), [role="button"]:has-text("Got it")')
                if await got_it.count() > 0 and await got_it.first.is_visible():
                    logger.info("Dismissing 'Got it' banner...")
                    await got_it.first.click(force=True)
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            # 3. Fill name if in Guest mode
            try:
                if await name_input.is_visible():
                    val = await name_input.input_value()
                    if not val:
                        logger.info("Filling participant name: 'AEGIS Copilot'")
                        await name_input.fill("AEGIS Copilot")
                        await asyncio.sleep(1)
            except Exception as e:
                logger.info(f"Name input handling: {e}")

            # 4. Wait for Join / Ask to join button to be ENABLED and click it
            try:
                enabled_join_btn = self.page.locator('button:has-text("Ask to join"):not([disabled]), button:has-text("Join now"):not([disabled]), button:has-text("今すぐ参加"):not([disabled]), button:has-text("参加をリクエスト"):not([disabled])').first
                await enabled_join_btn.wait_for(state="visible", timeout=12000)
                logger.info("Clicking enabled Join / Ask to join button...")
                await enabled_join_btn.click()
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.warning(f"Waiting for enabled join button fallback to force click: {e}")
                if await join_btn.count() > 0:
                    await join_btn.first.click(force=True)
                    await asyncio.sleep(1.5)

            # 5. Handle post-click "Continue without camera" modal if it appears
            try:
                no_cam_after = self.page.locator('button:has-text("Continue without camera"), span:has-text("Continue without camera"), [role="button"]:has-text("Continue without camera"), button:has-text("カメラなしで続行")').first
                if await no_cam_after.is_visible():
                    logger.info("Clicking 'Continue without camera' modal...")
                    await no_cam_after.click(force=True)
                    await asyncio.sleep(2)
            except Exception:
                pass

            # 6. Evaluate Resulting State
            await asyncio.sleep(2)
            body_text = await self.page.inner_text("body")
            
            if "You can't join this video call" in body_text or "このビデオ通話には参加できません" in body_text:
                logger.warning("Google Meet blocked unauthenticated guest. Google Account required.")
                self.is_connected_to_meeting = False
                return {
                    "status": "requires_google_account",
                    "meet_url": meet_url,
                    "message": "Google Meet requires a signed-in Google account for this meeting. Please click 'CONNECT ACCOUNT' in the AEGIS HUD to authenticate, or have the host permit guest access."
                }

            if "Asking to join" in body_text or "Waiting to be admitted" in body_text or "参加をリクエスト中" in body_text:
                logger.info("AEGIS Copilot is asking to join. Waiting for host admission...")
                self.active_meeting_url = meet_url
                self.is_connected_to_meeting = True
                asyncio.create_task(self._monitor_admission_and_captions())
                return {
                    "status": "asking_to_join",
                    "meet_url": meet_url,
                    "message": "AEGIS Copilot has sent an admission request. Please click 'Admit' on your Google Meet host screen to let the agent enter!"
                }

            # 7. Directly inside meeting
            self.active_meeting_url = meet_url
            self.is_connected_to_meeting = True
            logger.info("AEGIS Copilot successfully entered Google Meet!")
            asyncio.create_task(self._monitor_admission_and_captions())

            return {
                "status": "connected",
                "meet_url": meet_url,
                "message": "Connected to Google Meet successfully. AEGIS Copilot is active in the call!"
            }

        except Exception as e:
            logger.error(f"Error joining meet: {e}")
            self.is_connected_to_meeting = False
            return {"status": "error", "message": str(e)}

    async def post_to_chat(self, message: str) -> bool:
        """Sends a clarification message to the active Google Meet chat."""
        if not self.page or not self.is_connected_to_meeting:
            logger.warning("No active Google Meet session to post chat.")
            return False

        try:
            chat_btn = self.page.locator('button[aria-label*="chat" i], button[aria-label*="チャット" i]')
            if await chat_btn.is_visible():
                await chat_btn.click()
                await asyncio.sleep(0.5)

            chat_input = self.page.locator('textarea[aria-label*="Send a message" i], textarea[aria-label*="メッセージを送信" i], textarea')
            if await chat_input.is_visible():
                await chat_input.fill(message)
                await self.page.keyboard.press("Enter")
                logger.info("Message sent to Google Meet chat successfully.")
                return True
        except Exception as e:
            logger.error(f"Failed to post to chat: {e}")
        return False

    async def trigger_screen_share(self) -> bool:
        """Clicks the native Present Screen button in Google Meet."""
        if not self.page or not self.is_connected_to_meeting:
            return False
        try:
            present_btn = self.page.locator('button[aria-label*="Present now" i], button[aria-label*="画面を共有" i]')
            if await present_btn.is_visible():
                await present_btn.click()
                logger.info("Triggered Present Now in Google Meet.")
                return True
        except Exception as e:
            logger.error(f"Error triggering screen share: {e}")
        return False

    async def _monitor_admission_and_captions(self):
        """
        Continuously monitors admission state:
        1. When admitted, activates closed captions (presses 'c').
        2. Sets up a caption listener via DOM MutationObserver.
        3. Calls self.transcript_callback(speaker, text) whenever statements are detected.
        """
        logger.info("Starting admission and captions monitor...")
        for _ in range(60):
            if not self.page or not self.is_connected_to_meeting:
                return
            try:
                body_text = await self.page.inner_text("body")
                if "Meeting details" in body_text or "People" in body_text or "You're the only one here" in body_text:
                    logger.info("Admitted to Google Meet! Activating Closed Captions ('c')...")
                    await self.page.keyboard.press("c")
                    await asyncio.sleep(1)
                    break
            except Exception:
                pass
            await asyncio.sleep(2)

        try:
            if not self.page:
                return
            
            try:
                await self.page.expose_function("aegis_transcript_sink", self._on_js_caption)
            except Exception:
                pass

            await self.page.evaluate("""
                () => {
                    if (window.__aegis_caption_observer) return;
                    window.__last_captured_text = {};

                    const observer = new MutationObserver(() => {
                        const captionDivs = document.querySelectorAll('[jscontroller="D1tHje"], [aria-live="polite"], [aria-live="assertive"], .nM4Bk, .iTTPOb');
                        captionDivs.forEach(container => {
                            const text = (container.innerText || '').trim();
                            if (text && text.length > 3 && text !== window.__last_captured_text[container]) {
                                window.__last_captured_text[container] = text;
                                const lines = text.split('\\n').filter(l => l.trim().length > 0);
                                let speaker = 'Speaker';
                                let utterance = text;
                                if (lines.length >= 2) {
                                    speaker = lines[0];
                                    utterance = lines.slice(1).join(' ');
                                }
                                if (window.aegis_transcript_sink) {
                                    window.aegis_transcript_sink(speaker, utterance);
                                }
                            }
                        });
                    });

                    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
                    window.__aegis_caption_observer = observer;
                    console.log('AEGIS Caption Observer attached to Google Meet DOM.');
                }
            """)
            logger.info("AEGIS Caption Observer successfully installed in Google Meet session.")
        except Exception as e:
            logger.warning(f"Error initializing caption monitor: {e}")

    async def _on_js_caption(self, speaker: str, utterance: str):
        """Callback invoked from browser when a participant speaks."""
        logger.info(f"[MEET CAPTION] {speaker}: {utterance}")
        if self.transcript_callback:
            try:
                await self.transcript_callback(speaker, utterance)
            except Exception as e:
                logger.error(f"Error handling transcript callback: {e}")

    async def leave_meeting(self) -> Dict[str, Any]:
        """Leaves the active Google Meet and releases browser context."""
        if self.page:
            try:
                leave_btn = self.page.locator('button[aria-label*="Leave call" i], button[aria-label*="通話から退出" i]')
                if await leave_btn.is_visible():
                    await leave_btn.click()
                await self.page.close()
            except Exception:
                pass
            self.page = None

        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            self.context = None

        self.is_connected_to_meeting = False
        self.active_meeting_url = None
        logger.info("Left meeting and released browser profile lock.")
        return {"status": "left", "message": "Left the Google Meet session."}


# Global Singleton Instance
meet_session = MeetSessionManager()
