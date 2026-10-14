/**
 * AEGIS Google Meet Live Bridge
 * Injected into the user's real Google Meet tab in normal Chrome.
 * Directly captures meeting captions and posts contradiction alerts to Google Meet chat.
 */

(function () {
  if (window.__aegis_bridge_installed) {
    alert("AEGIS Meeting Bridge is already active in this tab!");
    return;
  }
  window.__aegis_bridge_installed = true;

  console.log("%c[AEGIS] Initializing Google Meet Live Bridge...", "color: #06b6d4; font-weight: bold; font-size: 14px;");

  // 1. Create floating status badge in Google Meet UI
  const badge = document.createElement("div");
  badge.id = "aegis-bridge-badge";
  badge.style.position = "fixed";
  badge.style.bottom = "85px";
  badge.style.left = "20px";
  badge.style.zIndex = "999999";
  badge.style.background = "rgba(9, 13, 22, 0.95)";
  badge.style.border = "1px solid #06b6d4";
  badge.style.borderRadius = "10px";
  badge.style.padding = "8px 14px";
  badge.style.color = "#fff";
  badge.style.fontFamily = "monospace";
  badge.style.fontSize = "12px";
  badge.style.boxShadow = "0 0 15px rgba(6, 182, 212, 0.4)";
  badge.style.display = "flex";
  badge.style.alignItems = "center";
  badge.style.gap = "8px";
  badge.innerHTML = `
    <span style="width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981; animation: pulse 2s infinite;"></span>
    <span style="color: #06b6d4; font-weight: bold;">AEGIS COPILOT</span>
    <span style="color: #9ca3af;">• BRIDGE CONNECTED</span>
  `;
  document.body.appendChild(badge);

  // 2. Connect to local AEGIS WebSocket server
  let ws = null;
  function connectWs() {
    ws = new WebSocket("ws://127.0.0.1:8000/ws/meet-bridge");

    ws.onopen = () => {
      console.log("%c[AEGIS] WebSocket connected to 127.0.0.1:8000", "color: #10b981;");
      badge.innerHTML = `
        <span style="width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981;"></span>
        <span style="color: #06b6d4; font-weight: bold;">AEGIS COPILOT</span>
        <span style="color: #10b981;">• LIVE IN CALL</span>
      `;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.action === "post_chat") {
          sendMeetChatMessage(msg.text);
        }
      } catch (e) {
        console.error("[AEGIS] Failed to parse message:", e);
      }
    };

    ws.onclose = () => {
      badge.innerHTML = `
        <span style="width: 8px; height: 8px; border-radius: 50%; background: #ef4444;"></span>
        <span style="color: #ef4444; font-weight: bold;">AEGIS COPILOT</span>
        <span style="color: #9ca3af;">• DISCONNECTED</span>
      `;
      setTimeout(connectWs, 3000);
    };
  }
  connectWs();

  // 3. Post to Google Meet Chat
  async function sendMeetChatMessage(text) {
    try {
      // Find and click chat toggle if chat panel is not already open
      const chatPanel = document.querySelector('div[aria-label*="chat" i], div[aria-label*="チャット" i], textarea[aria-label*="Send a message" i], textarea[aria-label*="メッセージ" i]');
      if (!chatPanel) {
        const chatBtn = document.querySelector('button[aria-label*="chat" i], button[aria-label*="チャット" i]');
        if (chatBtn) chatBtn.click();
        await new Promise(r => setTimeout(r, 600));
      }

      const input = document.querySelector('textarea[aria-label*="Send a message" i], textarea[aria-label*="メッセージ" i], textarea');
      if (input) {
        input.value = text;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        await new Promise(r => setTimeout(r, 200));

        // Send by clicking submit or pressing Enter
        const sendBtn = document.querySelector('button[aria-label*="Send" i], button[aria-label*="送信" i]');
        if (sendBtn && !sendBtn.disabled) {
          sendBtn.click();
        } else {
          input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, bubbles: true }));
        }
        console.log("%c[AEGIS] Posted contradiction alert to Google Meet chat!", "color: #f59e0b;");
      }
    } catch (e) {
      console.warn("[AEGIS] Chat posting error:", e);
    }
  }

  // 4. Auto turn on Closed Captions in Meet if off
  setTimeout(() => {
    const ccBtn = document.querySelector('button[aria-label*="caption" i], button[aria-label*="字幕" i]');
    if (ccBtn && ccBtn.getAttribute("aria-pressed") !== "true") {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "c", code: "KeyC", keyCode: 67, bubbles: true }));
      console.log("[AEGIS] Requested Closed Captions in Google Meet.");
    }
  }, 1500);

  // 5. Scrape captions via MutationObserver
  let lastCaptured = new Map();
  const observer = new MutationObserver(() => {
    // Look for caption containers
    const containers = document.querySelectorAll('[jscontroller="D1tHje"], [aria-live="polite"], [aria-live="assertive"], .nM4Bk, .iTTPOb');
    containers.forEach(box => {
      const text = (box.innerText || "").trim();
      if (text && text.length > 3 && lastCaptured.get(box) !== text) {
        lastCaptured.set(box, text);

        const lines = text.split("\n").filter(l => l.trim().length > 0);
        let speaker = "Speaker";
        let utterance = text;
        if (lines.length >= 2) {
          speaker = lines[0];
          utterance = lines.slice(1).join(" ");
        }

        console.log(`%c[AEGIS CAPTION] ${speaker}: ${utterance}`, "color: #38bdf8;");

        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            action: "caption",
            speaker: speaker,
            text: utterance
          }));
        }
      }
    });
  });

  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  console.log("%c[AEGIS] Caption listener successfully attached to DOM!", "color: #10b981;");
})();
