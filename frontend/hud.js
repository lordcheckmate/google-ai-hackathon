/**
 * AEGIS HUD Frontend Logic
 * Manages WebSocket connection, animated Character Avatar,
 * dynamic diagram/calc rendering, audio synthesis, and screen share toggles.
 */

let ws = null;
let currentTheme = 'jarvis';
let mouthInterval = null;
let audioContext = null;
let micStream = null;

const themes = {
  jarvis: {
    title: "AEGIS // JARVIS STARK HUD",
    border: "border-cyan-500/40",
    glow: "hud-glow-cyan",
    accent: "text-cyan-400",
    headStroke: "#06b6d4"
  },
  cyberpunk: {
    title: "AEGIS // BLADE RUNNER TACTICAL",
    border: "border-emerald-500/40",
    glow: "hud-glow-green",
    accent: "text-emerald-400",
    headStroke: "#10b981"
  },
  palantir: {
    title: "AEGIS // PALANTIR EXECUTIVE OPS",
    border: "border-blue-500/40",
    glow: "hud-glow-blue",
    accent: "text-blue-400",
    headStroke: "#3b82f6"
  },
  monolith: {
    title: "AEGIS // ARRIVAL MONOLITH VOID",
    border: "border-zinc-700",
    glow: "shadow-2xl shadow-zinc-900",
    accent: "text-zinc-200",
    headStroke: "#e4e4e7"
  }
};

function init() {
  connectWebSocket();
  renderDefaultDiagram();
  renderDefaultCalc();
  setTheme('jarvis');
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/hud`;
  
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    document.getElementById('backend-status').innerText = 'SERVER CONNECTED';
    document.getElementById('backend-status').className = 'text-emerald-400';
  };

  ws.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      handleServerEvent(payload);
    } catch (e) {
      console.error('Failed to parse WS event:', e);
    }
  };

  ws.onclose = () => {
    document.getElementById('backend-status').innerText = 'SERVER RECONNECTING';
    document.getElementById('backend-status').className = 'text-amber-400';
    setTimeout(connectWebSocket, 2000);
  };
}

function handleServerEvent(event) {
  const { type, data } = event;

  if (type === 'init') {
    if (data.state) updateCharacterState(data.state, data.speech_text);
    if (data.last_diagram) renderDiagram(data.last_diagram);
    if (data.last_calc) renderCalculation(data.last_calc);
    if (data.last_visual) displayNanoBananaVisual(data.last_visual);
  }
  else if (type === 'state_change') {
    updateCharacterState(data.state, data.speech_text);
  }
  else if (type === 'diagram_update') {
    renderDiagram(data);
  }
  else if (type === 'calc_update') {
    renderCalculation(data);
  }
  else if (type === 'nano_banana_visual') {
    displayNanoBananaVisual(data);
  }
  else if (type === 'contradiction_alert') {
    displayContradictionAlert(data);
  }
  else if (type === 'screen_share_toggle') {
    handleScreenShareState(data.active);
  }
  else if (type === 'voice_response') {
    speakVoiceOutput(data.spoken_text, data.language);
  }
}

function updateCharacterState(state, speechText) {
  const bubble = document.getElementById('char-speech-bubble');
  const mouth = document.getElementById('char-mouth-bar');
  const orbitOuter = document.getElementById('char-orbit-outer');
  const orbitInner = document.getElementById('char-orbit-inner');
  const gem = document.getElementById('char-forehead-gem');

  // Reset eyes
  document.getElementById('char-eyes-listening').classList.add('hidden');
  document.getElementById('char-eyes-thinking').classList.add('hidden');
  document.getElementById('char-eyes-speaking').classList.add('hidden');
  document.getElementById('char-eyes-alert').classList.add('hidden');

  if (mouthInterval) {
    clearInterval(mouthInterval);
    mouthInterval = null;
  }

  orbitOuter.style.animation = 'none';
  orbitInner.style.animation = 'none';

  if (speechText) {
    bubble.innerText = `"${speechText}"`;
  }

  if (state === 'listening') {
    document.getElementById('char-eyes-listening').classList.remove('hidden');
    mouth.setAttribute('height', '3');
    mouth.setAttribute('fill', '#06b6d4');
    gem.className = 'absolute top-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#22d3ee]';
  }
  else if (state === 'thinking') {
    document.getElementById('char-eyes-thinking').classList.remove('hidden');
    mouth.setAttribute('height', '3');
    mouth.setAttribute('fill', '#a855f7');
    orbitOuter.style.animation = 'spin-slow 2s linear infinite';
    orbitInner.style.animation = 'spin-reverse 1.5s linear infinite';
    gem.className = 'absolute top-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-purple-400 shadow-[0_0_10px_#a855f7]';
  }
  else if (state === 'speaking') {
    document.getElementById('char-eyes-speaking').classList.remove('hidden');
    mouth.setAttribute('fill', '#34d399');
    gem.className = 'absolute top-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px_#34d399]';
    
    // Audio-reactive mouth sync
    mouthInterval = setInterval(() => {
      const h = Math.floor(Math.random() * 9) + 3;
      mouth.setAttribute('height', h.toString());
      mouth.setAttribute('y', (41 - h / 2).toString());
    }, 110);
  }
  else if (state === 'alert') {
    document.getElementById('char-eyes-alert').classList.remove('hidden');
    mouth.setAttribute('height', '2');
    mouth.setAttribute('fill', '#ef4444');
    gem.className = 'absolute top-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_12px_#ef4444] animate-ping';
  }
}

function displayContradictionAlert(alert) {
  const box = document.getElementById('contradiction-box');
  const dot = document.getElementById('conflict-dot');
  const header = document.getElementById('conflict-header');
  const desc = document.getElementById('conflict-desc');
  const details = document.getElementById('conflict-details');
  const chatPosted = document.getElementById('conflict-chat-posted');

  box.className = 'bg-red-950/20 border border-red-500/50 rounded-xl p-5 relative overflow-hidden backdrop-blur-md transition-all duration-300';
  dot.className = 'w-2 h-2 rounded-full bg-red-500 animate-ping';
  header.innerText = 'TRUTH SENTINEL: CONFLICT CAUGHT';
  header.className = 'text-xs font-mono font-bold uppercase tracking-wider text-red-400';
  desc.innerText = alert.discrepancy_reason || 'Discrepancy detected between statements:';

  document.getElementById('conflict-old-speaker').innerText = `Earlier (${alert.old_claim.time_str}, ${alert.old_claim.speaker}):`;
  document.getElementById('conflict-old-text').innerText = `"${alert.old_claim.raw_text}"`;
  
  document.getElementById('conflict-new-speaker').innerText = `Just now (${alert.new_claim.time_str}, ${alert.new_claim.speaker}):`;
  document.getElementById('conflict-new-text').innerText = `"${alert.new_claim.raw_text}"`;

  document.getElementById('conflict-chat-msg').innerText = alert.clarification_question;

  details.classList.remove('hidden');
  chatPosted.classList.remove('hidden');
}

function renderDiagram(diagramData) {
  if (diagramData.title) {
    document.getElementById('diagram-title').innerText = diagramData.title;
  }
  const container = document.getElementById('diagram-svg-container');
  const nodes = diagramData.nodes || [];

  if (nodes.length === 0) return;

  let svgHtml = `<svg viewBox="0 0 700 170" class="w-full h-auto text-zinc-300">`;
  
  // Connection paths
  svgHtml += `<path d="M 120 85 L 220 85" stroke="currentColor" stroke-width="2" stroke-dasharray="4" class="text-cyan-500/70" />`;
  svgHtml += `<path d="M 340 85 L 440 45" stroke="currentColor" stroke-width="2" class="text-cyan-500/70" />`;
  svgHtml += `<path d="M 340 85 L 440 125" stroke="currentColor" stroke-width="2" class="text-cyan-500/70" />`;
  svgHtml += `<path d="M 560 45 L 630 75" stroke="currentColor" stroke-width="2" class="text-cyan-500/70" />`;
  svgHtml += `<path d="M 560 125 L 630 95" stroke="currentColor" stroke-width="2" class="text-cyan-500/70" />`;

  const positions = [
    { x: 20, y: 45, w: 100, h: 80 },
    { x: 220, y: 45, w: 120, h: 80 },
    { x: 440, y: 5, w: 120, h: 75 },
    { x: 440, y: 90, w: 120, h: 75 }
  ];

  nodes.forEach((node, idx) => {
    if (idx < positions.length) {
      const pos = positions[idx];
      const stroke = node.color || '#06b6d4';
      svgHtml += `
        <g transform="translate(${pos.x}, ${pos.y})">
          <rect width="${pos.w}" height="${pos.h}" rx="8" fill="#090d16" stroke="${stroke}" stroke-width="1.5" />
          <text x="${pos.w/2}" y="30" font-size="10" font-family="monospace" fill="${stroke}" text-anchor="middle">${node.sub || 'STAGE'}</text>
          <text x="${pos.w/2}" y="56" font-size="11" font-weight="bold" fill="#f8fafc" text-anchor="middle">${node.label}</text>
        </g>
      `;
    }
  });

  // End circle
  svgHtml += `
    <g transform="translate(620, 50)">
      <circle cx="35" cy="35" r="30" fill="#090d16" stroke="#10b981" stroke-width="1.5" />
      <text x="35" y="38" font-size="9" font-family="monospace" fill="#34d399" text-anchor="middle">ACTIVE HUD</text>
    </g>
  `;
  svgHtml += `</svg>`;
  container.innerHTML = svgHtml;
}

function renderDefaultDiagram() {
  renderDiagram({
    title: "REALTIME PROCESS FLOW: PARSED FROM MEETING",
    nodes: [
      { id: "1", label: "Google Meet", sub: "AUDIO STREAM", color: "#06b6d4" },
      { id: "2", label: "Voice Pipeline", sub: "16KHZ STREAM", color: "#06b6d4" },
      { id: "3", label: "Gemini 3.8", sub: "MODALITY CORE", color: "#3b82f6" },
      { id: "4", label: "Truth Sentinel", sub: "CLAIM GRAPH", color: "#f59e0b" }
    ]
  });
}

function renderCalculation(calcData) {
  if (calcData.title) {
    document.getElementById('calc-title').innerText = calcData.title;
  }
  const grid = document.getElementById('calc-grid');
  grid.innerHTML = '';
  const items = calcData.items || [];

  items.forEach(item => {
    const div = document.createElement('div');
    div.className = 'p-3 bg-black/60 rounded-lg border border-zinc-800/80';
    div.innerHTML = `
      <span class="text-[10px] text-zinc-500 uppercase">${item.label}</span>
      <p class="text-base font-bold text-white mt-1">${item.val}</p>
      <span class="text-[10px] text-zinc-400">${item.sub || ''}</span>
    `;
    grid.appendChild(div);
  });
}

function renderDefaultCalc() {
  renderCalculation({
    title: "LIVE CALCULATION DETECTED IN DIALOGUE",
    items: [
      { label: "Quarterly Run Rate", val: "$48,000 / mo", sub: "Target budget" },
      { label: "Growth Velocity", val: "+24.5% YoY", sub: "12-mo projected" },
      { label: "Annualized Total", val: "$576,000", sub: "Computed in 14ms" }
    ]
  });
}

function setTheme(name) {
  currentTheme = name;
  const config = themes[name];
  document.getElementById('agent-title').innerText = config.title;
  document.getElementById('agent-title').className = `font-mono text-sm tracking-widest uppercase font-bold ${config.accent}`;

  const card = document.getElementById('diagram-card');
  card.className = `bg-zinc-950/90 border ${config.border} rounded-xl p-5 ${config.glow} relative overflow-hidden backdrop-blur-md transition-all duration-300`;

  document.getElementById('char-head-border').setAttribute('stroke', config.headStroke);
  document.getElementById('char-ear-l').setAttribute('fill', config.headStroke);
  document.getElementById('char-ear-r').setAttribute('fill', config.headStroke);

  ['jarvis', 'cyberpunk', 'palantir', 'monolith'].forEach(t => {
    const btn = document.getElementById(`tab-${t}`);
    if (t === name) {
      btn.className = 'px-2.5 py-1 text-xs font-mono rounded bg-white/10 text-white border border-white/30';
    } else {
      btn.className = 'px-2.5 py-1 text-xs font-mono rounded text-zinc-400 hover:text-white';
    }
  });
}

function toggleScreenShare() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: 'toggle_screen_share' }));
  } else {
    handleScreenShareState(!document.getElementById('screen-share-text').innerText.includes('ACTIVE'));
  }
}

function handleScreenShareState(active) {
  const btn = document.getElementById('screen-share-btn');
  const text = document.getElementById('screen-share-text');
  const statusDisplay = document.getElementById('screen-display-status');

  if (active) {
    btn.className = 'px-3.5 py-1.5 rounded-lg border border-cyan-500 bg-cyan-950/60 text-cyan-300 hover:bg-cyan-900 transition-all text-xs font-mono font-semibold flex items-center gap-2 shadow-[0_0_15px_rgba(6,182,212,0.4)]';
    text.innerText = 'BROADCASTING TO MEET';
    statusDisplay.innerText = 'BROADCAST ACTIVE';
    statusDisplay.className = 'text-cyan-400 font-bold animate-pulse';
  } else {
    btn.className = 'px-3.5 py-1.5 rounded-lg border border-emerald-500/50 bg-emerald-950/30 text-emerald-300 hover:bg-emerald-900/50 transition-all text-xs font-mono font-semibold flex items-center gap-2';
    text.innerText = 'SHARE SCREEN (STANDBY)';
    statusDisplay.innerText = 'STANDBY';
    statusDisplay.className = 'text-zinc-400';
  }
}

function speakVoiceOutput(text, lang = 'en') {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    if (lang === 'ja') utterance.lang = 'ja-JP';
    else utterance.lang = 'en-US';
    utterance.rate = 1.05;
    window.speechSynthesis.speak(utterance);
  }
}

async function sendDirectQuery() {
  const input = document.getElementById('direct-query-input');
  const q = input.value.trim();
  if (!q) return;
  input.value = '';

  updateCharacterState('thinking', `Analyzing inquiry: "${q}"`);

  try {
    const res = await fetch('/api/direct-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q, speaker: 'You' })
    });
    const data = await res.json();
    console.log('Direct query response:', data);
  } catch (err) {
    console.error('Direct query error:', err);
  }
}

let recognition = null;
let isRecognizing = false;

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn('SpeechRecognition API not available in this browser.');
    return;
  }
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = false;
  // Auto-detect or default to user's browser language
  recognition.lang = navigator.language || 'en-US';

  recognition.onresult = (event) => {
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        const transcript = event.results[i][0].transcript.trim();
        console.log('🎤 Chrome Speech Recognized:', transcript);
        if (transcript.length > 2) {
          updateCharacterState('thinking', `Heard: "${transcript}"`);
          
          const lower = transcript.toLowerCase();
          if (lower.startsWith('hey agent') || lower.includes('show us your screen') || lower.includes('show your screen')) {
            // Direct query or screen share trigger
            fetch('/api/statement', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ speaker: 'You (Host)', text: transcript })
            });
          } else {
            fetch('/api/statement', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ speaker: 'You (Host)', text: transcript })
            }).then(r => r.json()).then(data => {
              console.log('Statement ingested:', data);
            });
          }
        }
      }
    }
  };

  recognition.onerror = (event) => {
    console.warn('Speech recognition status:', event.error);
  };

  recognition.onend = () => {
    if (isRecognizing) {
      try { recognition.start(); } catch(e) {}
    }
  };
}

async function toggleMicrophone() {
  const micBtn = document.getElementById('mic-btn');
  const micText = document.getElementById('mic-text');

  if (isRecognizing) {
    isRecognizing = false;
    if (recognition) {
      try { recognition.stop(); } catch(e) {}
    }
    if (micStream) {
      micStream.getTracks().forEach(t => t.stop());
      micStream = null;
    }
    micText.innerText = 'Mic: Passive';
    micBtn.className = 'px-3 py-1 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 rounded text-zinc-300 flex items-center gap-1.5';
    updateCharacterState('listening', 'Microphone standby.');
    return;
  }

  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (!recognition) {
      initSpeechRecognition();
    }
    isRecognizing = true;
    try { recognition.start(); } catch(e) {}
    micText.innerText = 'Mic: Live (Hearing)';
    micBtn.className = 'px-3 py-1 bg-cyan-900/60 border border-cyan-400 rounded text-cyan-200 flex items-center gap-1.5 animate-pulse shadow-[0_0_10px_rgba(6,182,212,0.4)]';
    updateCharacterState('listening', 'Hearing your live microphone in Chrome!');
  } catch (e) {
    console.warn('Microphone access not available or granted:', e);
    alert('Microphone error: ' + e.message);
  }
}

let tabStream = null;
let isTabCapturing = false;

async function toggleTabAudioCapture() {
  const btn = document.getElementById('tab-audio-btn');
  const text = document.getElementById('tab-audio-text');
  const btnTop = document.getElementById('tab-audio-btn-top');
  const textTop = document.getElementById('tab-audio-text-top');

  if (isTabCapturing) {
    if (tabStream) {
      tabStream.getTracks().forEach(t => t.stop());
      tabStream = null;
    }
    isTabCapturing = false;
    if (text) text.innerText = 'Tab Audio: Off';
    if (btn) btn.className = 'px-3 py-1 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 rounded text-zinc-300 flex items-center gap-1.5 transition-all';
    if (textTop) textTop.innerText = '1. Capture Meeting Tab (Instant)';
    if (btnTop) btnTop.className = 'px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-black font-bold whitespace-nowrap transition-all shadow-[0_0_12px_rgba(16,185,129,0.4)] flex items-center gap-2';
    updateCharacterState('listening', 'Stopped listening to meeting tab.');
    return;
  }

  try {
    tabStream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    const audioTracks = tabStream.getAudioTracks();
    if (audioTracks.length === 0) {
      alert("⚠️ Note: Please make sure to check 'Also share tab audio' in Chrome's tab picker so AEGIS can hear the meeting audio!");
      tabStream.getTracks().forEach(t => t.stop());
      tabStream = null;
      return;
    }

    isTabCapturing = true;
    if (text) text.innerText = '● Tab Audio: Live';
    if (btn) btn.className = 'px-3 py-1 bg-emerald-950/60 border border-emerald-400 rounded text-emerald-200 flex items-center gap-1.5 animate-pulse shadow-[0_0_12px_rgba(16,185,129,0.4)]';
    if (textTop) textTop.innerText = '✓ Capturing Meet Tab Audio';
    if (btnTop) btnTop.className = 'px-3.5 py-1.5 rounded-lg bg-emerald-400 text-black font-bold whitespace-nowrap transition-all shadow-[0_0_15px_rgba(16,185,129,0.6)] flex items-center gap-2';
    
    updateCharacterState('listening', 'Directly listening to Google Meet tab audio!');

    if (!recognition) initSpeechRecognition();
    try { recognition.start(); } catch(e) {}

    audioTracks[0].onended = () => {
      isTabCapturing = false;
      if (text) text.innerText = 'Tab Audio: Off';
      if (btn) btn.className = 'px-3 py-1 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 rounded text-zinc-300 flex items-center gap-1.5 transition-all';
      if (textTop) textTop.innerText = '1. Capture Meeting Tab (Instant)';
      if (btnTop) btnTop.className = 'px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-black font-bold whitespace-nowrap transition-all shadow-[0_0_12px_rgba(16,185,129,0.4)] flex items-center gap-2';
      updateCharacterState('listening', 'Meeting tab audio ended.');
    };
  } catch (err) {
    console.warn("Tab capture canceled:", err);
  }
}

// Google Meet Integration Handlers
async function connectGoogleAccount() {
  updateCharacterState('thinking', 'Opening Google login window...');
  try {
    const res = await fetch('/api/meet/connect-account', { method: 'POST' });
    const data = await res.json();
    alert(data.message || 'Google account window opened. Log in and close the window when done.');
    checkGoogleAccountStatus();
  } catch (e) {
    console.error('Failed to open Google login:', e);
  }
}

async function checkGoogleAccountStatus() {
  try {
    const res = await fetch('/api/meet/account-status');
    const data = await res.json();
    const dot = document.getElementById('google-account-dot');
    const statusText = document.getElementById('google-account-status');
    const joinBtn = document.getElementById('join-meet-btn');
    const leaveBtn = document.getElementById('leave-meet-btn');

    if (data.has_saved_account) {
      dot.className = 'w-2 h-2 rounded-full bg-emerald-400';
      statusText.innerText = 'LINKED (SAVED PROFILE)';
      statusText.className = 'text-emerald-400 font-semibold';
    } else {
      dot.className = 'w-2 h-2 rounded-full bg-amber-500';
      statusText.innerText = 'NOT LINKED';
      statusText.className = 'text-zinc-400';
    }

    if (data.in_meeting) {
      joinBtn.classList.add('hidden');
      leaveBtn.classList.remove('hidden');
    } else {
      joinBtn.classList.remove('hidden');
      leaveBtn.classList.add('hidden');
    }
  } catch (e) {
    console.warn('Could not fetch account status:', e);
  }
}

function normalizeMeetUrl(url) {
  url = (url || '').trim().replace(/^['"]+|['"]+$/g, '');
  const match = url.match(/([a-z]{3}-[a-z]{4}-[a-z]{3})/i);
  if (match) {
    return `https://meet.google.com/${match[1].toLowerCase()}`;
  }
  url = url.replace(/^(https?:?\/*)+/i, '');
  if (!url.startsWith('meet.google.com')) {
    url = 'meet.google.com/' + url;
  }
  return 'https://' + url;
}

async function joinGoogleMeet() {
  const urlInput = document.getElementById('meet-url-input');
  const rawUrl = urlInput.value.trim();
  if (!rawUrl) {
    alert('Please enter a Google Meet link (e.g. https://meet.google.com/xxx-yyyy-zzz)');
    return;
  }

  const meetUrl = normalizeMeetUrl(rawUrl);
  urlInput.value = meetUrl;

  updateCharacterState('thinking', `Joining Google Meet: ${meetUrl}...`);
  try {
    const res = await fetch('/api/meet/join', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ meet_url: meetUrl, headless: false })
    });
    const data = await res.json();
    if (data.status === 'connected') {
      updateCharacterState('listening', 'Connected to Google Meet. Monitoring in background.');
    } else if (data.status === 'asking_to_join') {
      updateCharacterState('listening', 'Admission requested! Please click "Admit" on your Google Meet screen.');
      alert(data.message);
    } else if (data.status === 'requires_google_account') {
      updateCharacterState('alert', 'Google Account required for this meeting.');
      alert(data.message);
    } else {
      alert('Error joining meeting: ' + (data.message || 'Unknown error'));
    }
    checkGoogleAccountStatus();
  } catch (e) {
    console.error('Error joining meet:', e);
  }
}

async function leaveGoogleMeet() {
  try {
    await fetch('/api/meet/leave', { method: 'POST' });
    checkGoogleAccountStatus();
    updateCharacterState('listening', 'Left the meeting. Standing by.');
  } catch (e) {
    console.error('Error leaving meet:', e);
  }
}

function copyMeetBridgeSnippet() {
  const code = "fetch('http://localhost:8000/static/meet_bridge.js').then(r=>r.text()).then(eval)";
  navigator.clipboard.writeText(code).then(() => {
    const btnText = document.getElementById('copy-bridge-text');
    if (btnText) btnText.innerText = "✓ Copied! Paste in Meet (F12)";
    alert("Bridge Code Copied!\n\n1. Go to your Google Meet tab (zer-qtph-qfc)\n2. Press F12 to open Console\n3. Press Ctrl+V and Enter\n\nAEGIS will instantly link to your call in normal Chrome!");
  }).catch(() => {
    prompt("Copy this code and paste into your Google Meet tab console (F12):", code);
  });
}

// Google Cloud Nano Banana Integration
function displayNanoBananaVisual(data) {
  const card = document.getElementById('nano-visual-card');
  const title = document.getElementById('nano-visual-title');
  const engine = document.getElementById('nano-visual-engine');
  const container = document.getElementById('nano-visual-container');
  const promptEl = document.getElementById('nano-visual-prompt');
  const timeEl = document.getElementById('nano-visual-timestamp');

  if (!card || !container) return;

  card.classList.remove('hidden');
  if (data.title) title.innerText = data.title;
  if (data.engine) engine.innerText = data.engine;
  if (data.prompt) promptEl.innerText = `Prompt: "${data.prompt}"`;
  if (data.timestamp) timeEl.innerText = `Generated at ${data.timestamp}`;

  // If URL is SVG or PNG
  if (data.url.endsWith('.svg')) {
    fetch(data.url)
      .then(res => res.text())
      .then(svgText => {
        container.innerHTML = svgText;
      })
      .catch(() => {
        container.innerHTML = `<img src="${data.url}" class="w-full h-auto rounded object-contain max-h-[350px]" />`;
      });
  } else {
    container.innerHTML = `<img src="${data.url}" alt="Nano Banana Schematic" class="w-full h-auto rounded object-contain max-h-[350px] shadow-lg" />`;
  }

  // Smooth scroll into view
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function closeNanoVisualCard() {
  const card = document.getElementById('nano-visual-card');
  if (card) card.classList.add('hidden');
}

function selectNanoPreset(topic) {
  const input = document.getElementById('nano-prompt-input');
  if (input) input.value = topic;
}

async function submitNanoBananaGeneration() {
  const input = document.getElementById('nano-prompt-input');
  const promptVal = input ? input.value.trim() : '';
  if (!promptVal) {
    alert('Please enter an architecture topic or select a preset!');
    return;
  }

  const modal = document.getElementById('nano-modal');
  if (modal) modal.classList.add('hidden');

  updateCharacterState('thinking', `Google Cloud Nano Banana synthesizing: "${promptVal.slice(0, 30)}"...`);

  try {
    const res = await fetch('/api/nano-banana/visualize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: promptVal })
    });
    const data = await res.json();
    console.log('Nano Banana generation result:', data);
    displayNanoBananaVisual(data);
    updateCharacterState('speaking', `Nano Banana schematic synthesized and presented on screen!`);
  } catch (err) {
    console.error('Nano Banana generation error:', err);
    alert('Failed to generate visual: ' + err.message);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  init();
  checkGoogleAccountStatus();
});

