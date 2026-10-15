/**
 * AEGIS Live AI Meeting Assistant Client
 * Features:
 * - Reactive Robot Avatar with 4 dynamic states (Listening, Thinking, Speaking, Alert)
 * - Single Big Neon Square (四角形) Viewport for all generated visuals
 * - Autonomous Nano Banana & Shape Rendering (Flow, Compare, Checklist, Answer)
 * - Speak-Over Contradiction Interruptions & Real-Time TTS
 * - AudioWorklet 16kHz PCM Live Microphone Streaming
 */

let ws = null;
let audioContext = null;
let mediaStream = null;
let pcmNode = null;
let isRecording = false;

// Store blocks locally: block_id -> block object
const blocksStore = new Map();
let activeBlockId = null;

// DOM Elements
const charWrapper = document.getElementById('character-wrapper');
const eyesListening = document.getElementById('char-eyes-listening');
const eyesThinking = document.getElementById('char-eyes-thinking');
const eyesSpeaking = document.getElementById('char-eyes-speaking');
const eyesAlert = document.getElementById('char-eyes-alert');
const mouthBar = document.getElementById('char-mouth-bar');
const speechBubble = document.getElementById('char-speech-bubble');
const wsDot = document.getElementById('ws-dot');
const wsStatus = document.getElementById('ws-status');
const micBtn = document.getElementById('mic-btn');
const micIcon = document.getElementById('mic-icon');
const micText = document.getElementById('mic-text');
const resetBtn = document.getElementById('reset-btn');
const exportBtn = document.getElementById('export-btn');
const exportModal = document.getElementById('export-modal');
const closeExportModal = document.getElementById('close-export-modal');
const exportMdBtn = document.getElementById('export-md-btn');
const exportSvgBtn = document.getElementById('export-svg-btn');
const exportHtmlBtn = document.getElementById('export-html-btn');
const exportJsonBtn = document.getElementById('export-json-btn');
const manualTextInput = document.getElementById('manual-text');
const sendManualBtn = document.getElementById('send-manual-btn');

// Neon Square Elements
const neonSquareFrame = document.getElementById('neon-square-frame');
const activeVisualTitle = document.getElementById('active-visual-title');
const activeVisualBadge = document.getElementById('active-visual-badge');
const visualTabs = document.getElementById('visual-tabs');
const neonStandby = document.getElementById('neon-standby');
const neonCanvasContent = document.getElementById('neon-canvas-content');

// =========================================================================
// Reactive Character Avatar States
// =========================================================================

function setAvatarState(state) {
  // state: 'listening' | 'thinking' | 'speaking' | 'alert'
  eyesListening.classList.add('hidden');
  eyesThinking.classList.add('hidden');
  eyesSpeaking.classList.add('hidden');
  eyesAlert.classList.add('hidden');

  charWrapper.classList.remove('thinking', 'speaking', 'alert');
  neonSquareFrame.classList.remove('thinking', 'speaking', 'alert');
  mouthBar.classList.remove('speaking-mouth');
  speechBubble.classList.remove('thinking', 'speaking', 'alert');

  if (state === 'thinking') {
    eyesThinking.classList.remove('hidden');
    charWrapper.classList.add('thinking');
    neonSquareFrame.classList.add('thinking');
    speechBubble.classList.add('thinking');
  } else if (state === 'speaking') {
    eyesSpeaking.classList.remove('hidden');
    charWrapper.classList.add('speaking');
    neonSquareFrame.classList.add('speaking');
    mouthBar.classList.add('speaking-mouth');
    speechBubble.classList.add('speaking');
  } else if (state === 'alert') {
    eyesAlert.classList.remove('hidden');
    charWrapper.classList.add('alert');
    neonSquareFrame.classList.add('alert');
    speechBubble.classList.add('alert');
  } else {
    // Default: 'listening'
    eyesListening.classList.remove('hidden');
  }
}

function setSpeechBubble(text, mode = '') {
  speechBubble.textContent = text ? `"${text}"` : '"Listening to meeting audio..."';
  if (mode) {
    speechBubble.className = `speech-bubble ${mode}`;
  }
}

// =========================================================================
// WebSocket Connection & Dispatcher
// =========================================================================

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const urlParams = new URLSearchParams(window.location.search);
  let sessionId = urlParams.get('session_id') || localStorage.getItem('aegis_session_id');
  if (!sessionId) {
    sessionId = 'default_session';
    localStorage.setItem('aegis_session_id', sessionId);
  }
  const freshQuery = urlParams.has('fresh') ? '&fresh=1' : '';
  const wsUrl = `${protocol}//${window.location.host}/ws?session_id=${encodeURIComponent(sessionId)}${freshQuery}`;

  ws = new WebSocket(wsUrl);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    wsDot.className = 'status-dot active';
    wsStatus.textContent = 'Connected';
    console.log('[WS] Connected to AEGIS meeting engine');
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleServerMessage(msg);
    } catch (err) {
      console.error('[WS] Parse error:', err);
    }
  };

  ws.onclose = () => {
    wsDot.className = 'status-dot';
    wsStatus.textContent = 'Disconnected';
    console.log('[WS] Disconnected, reconnecting in 2s...');
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = (err) => {
    console.error('[WS] Error:', err);
  };
}

function handleServerMessage(msg) {
  if (msg.type === 'transcript') {
    if (msg.is_final) {
      setAvatarState('thinking');
      setSpeechBubble(`Processed: ${msg.text.slice(0, 45)}...`, 'thinking');
    }
  } else if (msg.type === 'status') {
    wsStatus.textContent = msg.status || 'Active';
  } else if (msg.type === 'block_upsert') {
    storeAndRenderBlock(msg.block);
    // Return to listening unless currently speaking audio
    if (!mouthBar.classList.contains('speaking-mouth')) {
      setAvatarState('listening');
    }
  } else if (msg.type === 'block_remove') {
    removeBlock(msg.block_id);
  } else if (msg.type === 'canvas_cleared') {
    blocksStore.clear();
    activeBlockId = null;
    renderNeonSquare();
  } else if (msg.type === 'speak') {
    setAvatarState('speaking');
    setSpeechBubble(msg.text, 'speaking');
    if (msg.audio) {
      playAudio(msg.audio, () => {
        setAvatarState('listening');
        setSpeechBubble('Listening to meeting audio...');
      });
    } else {
      setTimeout(() => {
        setAvatarState('listening');
        setSpeechBubble('Listening to meeting audio...');
      }, 3500);
    }
  } else if (msg.type === 'contradiction') {
    // SPEAKS OVER IMMEDIATELY ON CONTRADICTION
    setAvatarState('alert');
    const warningText = msg.question || `Contradiction: ${msg.earlier} vs ${msg.now}`;
    setSpeechBubble(`⚠️ ${warningText}`, 'alert');
    if (msg.audio) {
      playAudio(msg.audio, () => {
        setTimeout(() => {
          setAvatarState('listening');
          setSpeechBubble('Listening to meeting audio...');
        }, 1500);
      });
    }
  }
}

// =========================================================================
// Audio Player (TTS & Speak-Over)
// =========================================================================

function playAudio(base64Audio, onEndCallback) {
  try {
    const audio = new Audio('data:audio/mp3;base64,' + base64Audio);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'tts_playing', playing: true }));
    }
    audio.onended = () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'tts_playing', playing: false }));
      }
      if (onEndCallback) onEndCallback();
    };
    audio.play().catch(e => {
      console.warn('Audio auto-play blocked, click page to enable audio:', e);
      if (onEndCallback) setTimeout(onEndCallback, 3000);
    });
  } catch (e) {
    console.warn('Audio playback error:', e);
    if (onEndCallback) onEndCallback();
  }
}

// =========================================================================
// Visual Store & Neon Square (四角形) Rendering
// =========================================================================

function storeAndRenderBlock(block) {
  blocksStore.set(block.id, block);
  activeBlockId = block.id; // Switch active view to the newest/updated block
  renderNeonSquare();
}

function removeBlock(blockId) {
  blocksStore.delete(blockId);
  if (activeBlockId === blockId) {
    const remaining = Array.from(blocksStore.keys());
    activeBlockId = remaining.length > 0 ? remaining[remaining.length - 1] : null;
  }
  renderNeonSquare();
}

function renderNeonSquare() {
  if (blocksStore.size === 0 || !activeBlockId) {
    neonStandby.classList.remove('hidden');
    neonCanvasContent.classList.add('hidden');
    neonCanvasContent.innerHTML = '';
    activeVisualTitle.textContent = 'NEON VISUAL CANVAS';
    activeVisualBadge.textContent = 'STANDBY';
    visualTabs.innerHTML = '';
    return;
  }

  neonStandby.classList.add('hidden');
  neonCanvasContent.classList.remove('hidden');

  const currentBlock = blocksStore.get(activeBlockId);
  if (!currentBlock) return;

  // Header update
  activeVisualTitle.textContent = currentBlock.title || currentBlock.kind.toUpperCase();
  const kindBadge = currentBlock.kind === 'flow' ? 'FLOW // NANO BANANA' : currentBlock.kind.toUpperCase();
  activeVisualBadge.textContent = kindBadge;

  // Render Tabs if more than 1 block exists
  renderTabs();

  // Render HTML / SVG content directly inside the single Neon Square
  neonCanvasContent.innerHTML = currentBlock.html || '';
}

function renderTabs() {
  visualTabs.innerHTML = '';
  if (blocksStore.size <= 1) return;

  blocksStore.forEach((block, id) => {
    const tab = document.createElement('button');
    tab.className = `visual-tab-pill ${id === activeBlockId ? 'active' : ''}`;
    tab.textContent = block.title || block.kind;
    tab.onclick = () => {
      activeBlockId = id;
      renderNeonSquare();
    };
    visualTabs.appendChild(tab);
  });
}

// =========================================================================
// Interactive Click / Drill-In Listener
// =========================================================================

neonCanvasContent.addEventListener('click', (event) => {
  const refElem = event.target.closest('[data-ref]');
  if (!refElem || !activeBlockId) return;

  const ref = refElem.getAttribute('data-ref');
  refElem.classList.add('pending');

  if (ref.startsWith('item:')) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'toggle_item',
        block_id: activeBlockId,
        ref: ref,
      }));
    }
  } else {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'inspect',
        block_id: activeBlockId,
        ref: ref,
      }));
    }
  }
});

// =========================================================================
// Audio Recording & AudioWorklet Streaming (16kHz PCM)
// =========================================================================

let speechRec = null;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

async function startRecording() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: 16000,
    });

    await audioContext.audioWorklet.addModule('/static/pcm-worklet.js');

    const source = audioContext.createMediaStreamSource(mediaStream);
    pcmNode = new AudioWorkletNode(audioContext, 'pcm-worklet');

    pcmNode.port.onmessage = (event) => {
      if (ws && ws.readyState === WebSocket.OPEN && isRecording) {
        ws.send(event.data);
      }
    };

    source.connect(pcmNode);
    pcmNode.connect(audioContext.destination);

    // Browser local SpeechRecognition for instant visual speech responsiveness
    if (SpeechRecognition && !speechRec) {
      speechRec = new SpeechRecognition();
      speechRec.continuous = true;
      speechRec.interimResults = true;
      speechRec.lang = 'en-US';

      speechRec.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const res = event.results[i];
          if (res.isFinal) {
            const text = res[0].transcript.trim();
            if (text) {
              setAvatarState('thinking');
              setSpeechBubble(`Heard: "${text}"`, 'thinking');
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'transcript_event', text: text, is_final: true }));
              }
            }
          } else {
            interim += res[0].transcript;
          }
        }
        if (interim) {
          setAvatarState('listening');
          setSpeechBubble(`Listening: "${interim.slice(-35)}"`, 'listening');
        }
      };

      speechRec.onerror = (e) => console.warn('[SpeechRec] Event:', e.error);
      speechRec.onend = () => {
        if (isRecording && speechRec) {
          try { speechRec.start(); } catch (_) {}
        }
      };

      try {
        speechRec.start();
      } catch (err) {
        console.warn('[SpeechRec] Start error:', err);
      }
    }

    isRecording = true;
    micBtn.classList.add('recording');
    micIcon.textContent = '⏹️';
    micText.textContent = 'Mic: Listening';
    wsDot.className = 'status-dot listening';
    setAvatarState('listening');
    setSpeechBubble('Listening to meeting audio...');
  } catch (err) {
    console.error('[Mic] Error accessing microphone:', err);
    alert('Microphone access error: ' + err.message);
  }
}

async function stopRecording() {
  isRecording = false;
  if (speechRec) {
    try { speechRec.stop(); } catch (_) {}
    speechRec = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  if (audioContext) {
    await audioContext.close();
    audioContext = null;
  }
  micBtn.classList.remove('recording');
  micIcon.textContent = '🎙️';
  micText.textContent = 'Mic: Passive';
  wsDot.className = 'status-dot active';
  setAvatarState('listening');
  setSpeechBubble('Mic paused. Ready for speech or input.');
}

micBtn.addEventListener('click', () => {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

// =========================================================================
// Manual Input / Test Dispatcher
// =========================================================================

function sendManualTurn() {
  const text = manualTextInput.value.trim();
  if (!text) return;

  setAvatarState('thinking');
  setSpeechBubble(`Sent: "${text}"`, 'thinking');

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'transcript_event', text: text, is_final: true }));
  }
  manualTextInput.value = '';
}

sendManualBtn.addEventListener('click', sendManualTurn);
manualTextInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    sendManualTurn();
  }
});

// =========================================================================
// Canvas Reset / Refresh Dispatcher (Dual-Path + Session Generation)
// =========================================================================

async function resetCanvas() {
  console.log('[AEGIS] Resetting canvas and generating fresh session...');
  
  // 1. Wipe local store & neon square immediately
  blocksStore.clear();
  activeBlockId = null;
  renderNeonSquare();
  setAvatarState('listening');
  setSpeechBubble('Canvas & memory reset to fresh state.');

  const oldSid = localStorage.getItem('aegis_session_id') || 'default_session';

  // 2. Clear old session in backend via WebSocket
  if (ws && ws.readyState === WebSocket.OPEN) {
    try {
      ws.send(JSON.stringify({ type: 'command', name: 'clear', args: {} }));
    } catch (_) {}
  }

  // 3. Dual-path: Also invoke HTTP endpoint /command to guarantee Firestore clear
  try {
    await fetch('/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'clear', sid: oldSid })
    });
  } catch (err) {
    console.warn('[AEGIS] HTTP reset failed (WS will handle):', err);
  }

  // 4. Generate a brand new unique session ID so reload or reconnect is 100% clean
  const newSid = 'sess_' + Date.now().toString(36) + '_' + Math.random().toString(36).substring(2, 6);
  localStorage.setItem('aegis_session_id', newSid);
  console.log(`[AEGIS] New clean session active: ${newSid}`);

  // 5. Reconnect WebSocket to the fresh session
  if (ws) {
    try { ws.close(); } catch (_) {}
  }
  connectWebSocket();
}

if (resetBtn) {
  resetBtn.addEventListener('click', resetCanvas);
}

// =========================================================================
// Export Artifacts Suite (Markdown, SVG, HTML, JSON)
// =========================================================================

function downloadBlobFile(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function openExportModal() {
  if (blocksStore.size === 0) {
    setSpeechBubble('No visuals to export yet. Discuss or generate a diagram first!');
    alert('No visuals or diagrams on canvas yet. Generate or speak meeting turns first!');
    return;
  }
  exportModal.classList.remove('hidden');
}

function closeExportModalDialog() {
  exportModal.classList.add('hidden');
}

function exportMarkdown() {
  const blocks = Array.from(blocksStore.values());
  const dateStr = new Date().toLocaleString();
  let md = `# AEGIS Meeting Summary & Visual Artifacts\n\n`;
  md += `*Generated by AEGIS AI Meeting Co-Pilot on ${dateStr}*\n\n`;
  md += `---\n\n`;

  blocks.forEach((b, idx) => {
    const kind = (b.kind || 'Visual').toUpperCase();
    const title = b.title || `Block #${idx + 1}`;
    md += `## ${idx + 1}. [${kind}] ${title}\n\n`;
    
    const j = b.json || {};
    if (j.summary) {
      md += `**Summary:** ${j.summary}\n\n`;
    }
    if (j.question && j.calculated_value) {
      md += `**Question:** ${j.question}\n\n`;
      md += `**Calculation / Answer:** \`${j.calculated_value}\`\n\n`;
    }
    if (j.explanation) {
      md += `> ${j.explanation}\n\n`;
    }

    if (j.nodes && Array.isArray(j.nodes)) {
      md += `### Steps & Workflow:\n`;
      j.nodes.forEach((n, nIdx) => {
        md += `- **Step ${nIdx + 1}: ${n.label || n.id}**`;
        if (n.caption) md += ` — *${n.caption}*`;
        md += `\n`;
      });
      md += `\n`;
    }

    if (j.options && Array.isArray(j.options)) {
      md += `### Comparison Options:\n`;
      j.options.forEach(opt => {
        md += `- **${opt}**\n`;
      });
      md += `\n`;
    }

    if (j.items && Array.isArray(j.items)) {
      md += `### Action Items / Checklist:\n`;
      j.items.forEach(it => {
        const check = it.done ? '[x]' : '[ ]';
        const owner = it.owner ? ` (@${it.owner})` : '';
        md += `- ${check} ${it.text}${owner}\n`;
      });
      md += `\n`;
    }

    md += `---\n\n`;
  });

  downloadBlobFile(`meeting-summary-${Date.now()}.md`, md, 'text/markdown;charset=utf-8');
  closeExportModalDialog();
  setSpeechBubble('Exported meeting summary as Markdown (.md).');
}

function exportCurrentSvg() {
  if (!activeBlockId || !blocksStore.has(activeBlockId)) {
    alert('No active diagram to export.');
    return;
  }
  const currentBlock = blocksStore.get(activeBlockId);
  const container = document.getElementById('neon-canvas-content');
  const svgEl = container ? container.querySelector('svg') : null;
  if (!svgEl) {
    downloadBlobFile(`diagram-${activeBlockId}.html`, currentBlock.html || '', 'text/html;charset=utf-8');
    closeExportModalDialog();
    return;
  }
  const svgData = new XMLSerializer().serializeToString(svgEl);
  downloadBlobFile(`meeting-diagram-${activeBlockId}.svg`, svgData, 'image/svg+xml;charset=utf-8');
  closeExportModalDialog();
  setSpeechBubble('Exported active visual diagram as SVG (.svg).');
}

function exportHtml() {
  const blocks = Array.from(blocksStore.values());
  let html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>AEGIS Meeting Export</title>`;
  html += `<style>body{background:#040711;color:#f1f5f9;font-family:system-ui,sans-serif;padding:2rem;} .block-card{background:#090e1a;border:1px solid #06b6d4;border-radius:12px;padding:1.5rem;margin-bottom:2rem;box-shadow:0 0 20px rgba(6,182,212,0.15);} h1,h2{color:#22d3ee;font-family:monospace;} svg{max-width:100%;height:auto;}</style></head><body>`;
  html += `<h1>AEGIS // Meeting Visual Canvas Export</h1><p>Exported: ${new Date().toLocaleString()}</p>`;
  blocks.forEach((b, idx) => {
    html += `<div class="block-card"><h2>#${idx + 1} - ${b.title || b.kind}</h2>${b.html}</div>`;
  });
  html += `</body></html>`;
  downloadBlobFile(`meeting-canvas-${Date.now()}.html`, html, 'text/html;charset=utf-8');
  closeExportModalDialog();
  setSpeechBubble('Exported standalone HTML canvas (.html).');
}

function exportJson() {
  const blocks = Array.from(blocksStore.values());
  const data = {
    exported_at: new Date().toISOString(),
    session_id: localStorage.getItem('aegis_session_id') || 'default_session',
    block_count: blocks.length,
    blocks: blocks.map(b => ({
      id: b.id,
      kind: b.kind,
      title: b.title,
      json: b.json,
      parent: b.parent
    }))
  };
  downloadBlobFile(`meeting-data-${Date.now()}.json`, JSON.stringify(data, null, 2), 'application/json;charset=utf-8');
  closeExportModalDialog();
  setSpeechBubble('Exported structured JSON data (.json).');
}

if (exportBtn) {
  exportBtn.addEventListener('click', openExportModal);
}
if (closeExportModal) {
  closeExportModal.addEventListener('click', closeExportModalDialog);
}
if (exportModal) {
  exportModal.addEventListener('click', (e) => {
    if (e.target === exportModal) closeExportModalDialog();
  });
}
if (exportMdBtn) exportMdBtn.addEventListener('click', exportMarkdown);
if (exportSvgBtn) exportSvgBtn.addEventListener('click', exportCurrentSvg);
if (exportHtmlBtn) exportHtmlBtn.addEventListener('click', exportHtml);
if (exportJsonBtn) exportJsonBtn.addEventListener('click', exportJson);

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
  connectWebSocket();
  setAvatarState('listening');
});
