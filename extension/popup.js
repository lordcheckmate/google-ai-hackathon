document.addEventListener("DOMContentLoaded", () => {
  const hostInput = document.getElementById("server-host");
  const autoChatCheckbox = document.getElementById("auto-chat");
  const saveBtn = document.getElementById("save-btn");
  const openHudBtn = document.getElementById("open-hud-btn");

  // Load saved settings
  if (chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(["serverHost", "autoChat"], (data) => {
      if (data.serverHost) hostInput.value = data.serverHost;
      if (data.autoChat !== undefined) autoChatCheckbox.checked = data.autoChat;
    });
  }

  // Save settings
  saveBtn.addEventListener("click", () => {
    const hostVal = hostInput.value.trim() || "localhost:8000";
    const autoChatVal = autoChatCheckbox.checked;

    if (chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({ serverHost: hostVal, autoChat: autoChatVal }, () => {
        saveBtn.innerText = "✓ Saved!";
        setTimeout(() => {
          saveBtn.innerText = "Save Settings";
        }, 1500);
      });
    }
  });

  // Open HUD
  openHudBtn.addEventListener("click", () => {
    let hostVal = hostInput.value.trim() || "localhost:8000";
    if (!hostVal.startsWith("http://") && !hostVal.startsWith("https://")) {
      hostVal = "http://" + hostVal;
    }
    chrome.tabs.create({ url: hostVal });
  });
});
