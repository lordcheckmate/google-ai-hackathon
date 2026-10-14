/**
 * Project A.E.G.I.S. Chrome Extension Content Script
 * Runs automatically on any Google Meet call (meet.google.com/*).
 * Captures live captions, detects contradictions, and renders in-call notifications.
 */

(function () {
  if (window.__aegis_extension_loaded) return;
  window.__aegis_extension_loaded = true;

  console.log("%c[A.E.G.I.S.] Chrome Extension active on Google Meet call.", "color: #06b6d4; font-weight: bold; font-size: 13px;");

  let ws = null;
  let serverHost = "localhost:8000";
  let autoChatEnabled = true;

  // Retrieve stored server URL if configured
  if (chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(["serverHost", "autoChat"], (res) => {
      if (res.serverHost) serverHost = res.serverHost;
      if (res.autoChat !== undefined) autoChatEnabled = res.autoChat;
      initAegisWidget();
      connectWs();
    });
  } else {
    initAegisWidget();
    connectWs();
  }

  // 1. In-call Floating Widget UI
  let widget = null;
  let toastContainer = null;

  function initAegisWidget() {
    // Top-right or bottom-left floating badge
    widget = document.createElement("div");
    widget.id = "aegis-ext-badge";
    widget.style.cssText = `
      position: fixed;
      bottom: 85px;
      left: 20px;
      z-index: 999999;
      background: rgba(9, 13, 22, 0.95);
      border: 1px solid #06b6d4;
      border-radius: 20px;
      padding: 6px 14px;
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 8px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6), 0 0 15px rgba(6, 182, 212, 0.3);
      cursor: pointer;
      user-select: none;
      transition: all 0.2s ease;
    `;
    widget.innerHTML = `
      <span id="aegis-dot" style="width: 8px; height: 8px; border-radius: 50%; background: #eab308; box-shadow: 0 0 8px #eab308;"></span>
      <span style="color: #06b6d4;">🛡️ AEGIS COPILOT</span>
      <span id="aegis-status-text" style="color: #9ca3af; font-weight: 400;">CONNECTING...</span>
    `;

    widget.onclick = () => {
      window.open(`http://${serverHost}/`, "_blank");
    };

    document.body.appendChild(widget);

    // Toast Alert Container
    toastContainer = document.createElement("div");
    toastContainer.id = "aegis-toast-container";
    toastContainer.style.cssText = `
      position: fixed;
      top: 75px;
      right: 20px;
      z-index: 999999;
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-width: 380px;
      pointer-events: none;
    `;
    document.body.appendChild(toastContainer);

    // Auto-turn on Closed Captions in Google Meet ('c' key)
    setTimeout(() => {
      const ccBtn = document.querySelector('button[aria-label*="caption" i], button[aria-label*="字幕" i]');
      if (ccBtn && ccBtn.getAttribute("aria-pressed") !== "true") {
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "c", code: "KeyC", keyCode: 67, bubbles: true }));
        console.log("[A.E.G.I.S.] Auto-activated Closed Captions.");
      }
    }, 2000);
  }

  // 2. Connect to AEGIS Backend Engine
  function connectWs() {
    const isSsl = serverHost.startsWith("https://") || serverHost.includes(".run.app");
    const cleanHost = serverHost.replace(/^https?:\/\//, "");
    const wsProto = isSsl ? "wss://" : "ws://";
    const wsUrl = `${wsProto}${cleanHost}/ws/meet-bridge`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log("[A.E.G.I.S.] Linked to Copilot Backend at", wsUrl);
        updateStatus("LIVE IN CALL", "#10b981", true);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.action === "post_chat") {
            showInCallToast(msg.text);
            if (autoChatEnabled) {
              sendMeetChatMessage(msg.text);
            }
          }
        } catch (e) {
          console.error("[A.E.G.I.S.] Message parse error:", e);
        }
      };

      ws.onclose = () => {
        updateStatus("DISCONNECTED", "#ef4444", false);
        setTimeout(connectWs, 3000);
      };

      ws.onerror = () => {
        updateStatus("STANDBY", "#eab308", false);
      };
    } catch (e) {
      console.warn("[A.E.G.I.S.] WebSocket connection failed:", e);
      setTimeout(connectWs, 4000);
    }
  }

  function updateStatus(text, color, pulse) {
    const dot = document.getElementById("aegis-dot");
    const label = document.getElementById("aegis-status-text");
    if (dot && label) {
      dot.style.background = color;
      dot.style.boxShadow = `0 0 10px ${color}`;
      label.innerText = text;
      label.style.color = color;
      if (pulse) {
        dot.style.animation = "aegis-pulse 2s infinite";
      } else {
        dot.style.animation = "none";
      }
    }
  }

  // 3. In-Call Floating Toast Banner
  function showInCallToast(text) {
    if (!toastContainer) return;

    const toast = document.createElement("div");
    toast.style.cssText = `
      background: rgba(9, 13, 22, 0.98);
      border: 1px solid #ef4444;
      border-radius: 12px;
      padding: 12px 16px;
      color: #fff;
      font-family: monospace;
      font-size: 11px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.8), 0 0 20px rgba(239,68,68,0.3);
      pointer-events: auto;
      animation: aegis-slide-in 0.3s ease;
      position: relative;
    `;

    toast.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="color: #ef4444; font-weight: bold; font-size: 12px;">⚠️ TRUTH SENTINEL ALERT</span>
        <button id="close-toast" style="background: none; border: none; color: #9ca3af; cursor: pointer; font-size: 14px;">✕</button>
      </div>
      <div style="color: #fca5a5; line-height: 1.4; margin-bottom: 8px; white-space: pre-wrap;">${text}</div>
      <div style="display: flex; justify-content: flex-end; gap: 8px;">
        <span style="font-size: 10px; color: #10b981;">✓ Dispatched to Meet Chat</span>
      </div>
    `;

    toast.querySelector("#close-toast").onclick = () => {
      toast.remove();
    };

    toastContainer.appendChild(toast);
    setTimeout(() => {
      if (toast.parentNode) toast.remove();
    }, 12000);
  }

  // 4. Send Message to Google Meet Chat
  async function sendMeetChatMessage(text) {
    try {
      const chatPanel = document.querySelector('div[aria-label*="chat" i], div[aria-label*="チャット" i], textarea[aria-label*="Send a message" i], textarea[aria-label*="メッセージ" i]');
      if (!chatPanel) {
        const chatBtn = document.querySelector('button[aria-label*="chat" i], button[aria-label*="チャット" i]');
        if (chatBtn) {
          chatBtn.click();
          await new Promise((r) => setTimeout(r, 600));
        }
      }

      const input = document.querySelector('textarea[aria-label*="Send a message" i], textarea[aria-label*="メッセージ" i], textarea');
      if (input) {
        input.value = text;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        await new Promise((r) => setTimeout(r, 200));

        const sendBtn = document.querySelector('button[aria-label*="Send" i], button[aria-label*="送信" i]');
        if (sendBtn && !sendBtn.disabled) {
          sendBtn.click();
        } else {
          input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, bubbles: true }));
        }
        console.log("[A.E.G.I.S.] Auto-posted contradiction clarification to Google Meet chat.");
      }
    } catch (e) {
      console.warn("[A.E.G.I.S.] Chat posting error:", e);
    }
  }

  // 5. Scrape Live Captions with MutationObserver
  let lastCaptured = new Map();
  const observer = new MutationObserver(() => {
    const containers = document.querySelectorAll('[jscontroller="D1tHje"], [aria-live="polite"], [aria-live="assertive"], .nM4Bk, .iTTPOb');
    containers.forEach((box) => {
      const text = (box.innerText || "").trim();
      if (text && text.length > 3 && lastCaptured.get(box) !== text) {
        lastCaptured.set(box, text);

        const lines = text.split("\n").filter((l) => l.trim().length > 0);
        let speaker = "Speaker";
        let utterance = text;
        if (lines.length >= 2) {
          speaker = lines[0];
          utterance = lines.slice(1).join(" ");
        }

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
})();
