/**
 * Live Meeting Assistant Frontend Client
 * Handles AudioWorklet 16kHz PCM streaming, live hearing box, interactive canvas, and TTS.
 */

let ws = null;
let audioContext = null;
let mediaStream = null;
let pcmNode = null;
let isRecording = false;

// DOM Elements
const wsDot = document.getElementById('ws-dot');
const wsStatus = document.getElementById('ws-status');
const micBtn = document.getElementById('mic-btn');
const micIcon = document.getElementById('mic-icon');
const micText = document.getElementById('mic-text');
const undoBtn = document.getElementById('undo-btn');
const clearBtn = document.getElementById('clear-btn');
const sttStatus = document.getElementById('stt-status');
const transcriptBox = document.getElementById('transcript-box');
const transcriptFinal = document.getElementById('transcript-final');
const transcriptInterim = document.getElementById('transcript-interim');
const canvasStack = document.getElementById('canvas-stack');
const canvasEmpty = document.getElementById('canvas-empty');
const canvasStats = document.getElementById('canvas-stats');
const contradictionBanner = document.getElementById('contradiction-banner');
const contradictionText = document.getElementById('contradiction-text');
const dismissContradiction = document.getElementById('dismiss-contradiction');
const manualTextInput = document.getElementById('manual-text');
const sendManualBtn = document.getElementById('send-manual-btn');

// Connect WebSocket
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    wsDot.className = 'status-dot active';
    wsStatus.textContent = 'Connected';
    console.log('[WS] Connected to meeting backend');
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleServerMessage(msg);
    } catch (err) {
      console.error('[WS] Failed to parse message:', err);
    }
  };

  ws.onclose = () => {
    wsDot.className = 'status-dot';
    wsStatus.textContent = 'Disconnected';
    console.log('[WS] Disconnected, retrying in 2s...');
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = (err) => {
    console.error('[WS] Error:', err);
  };
}

// Handle Server Messages
function handleServerMessage(msg) {
  if (msg.type === 'transcript') {
    if (msg.is_final) {
      transcriptFinal.textContent += (transcriptFinal.textContent ? ' ' : '') + msg.text;
      transcriptInterim.textContent = '';
    } else {
      transcriptInterim.textContent = ' ' + msg.text;
    }
    transcriptBox.scrollTop = transcriptBox.scrollHeight;
  } else if (msg.type === 'status') {
    sttStatus.textContent = msg.status;
  } else if (msg.type === 'block_upsert') {
    renderOrUpdateBlock(msg.block);
    // Remove pending pulse from any clicked elements
    document.querySelectorAll('[data-ref].pending').forEach(el => el.classList.remove('pending'));
  } else if (msg.type === 'block_remove') {
    removeBlock(msg.block_id);
  } else if (msg.type === 'canvas_cleared') {
    canvasStack.innerHTML = '';
    if (canvasEmpty) {
      canvasEmpty.style.display = 'block';
      canvasStack.appendChild(canvasEmpty);
    }
    updateStats();
  } else if (msg.type === 'speak') {
    if (msg.audio) {
      playAudio(msg.audio);
    }
  } else if (msg.type === 'contradiction') {
    if (contradictionBanner && contradictionText) {
      contradictionText.textContent = msg.question || `${msg.earlier} vs ${msg.now}`;
      contradictionBanner.style.display = 'flex';
    }
    if (msg.audio) {
      playAudio(msg.audio);
    }
  }
}

// Audio Player with Echo Suppression Notification
function playAudio(base64Audio) {
  try {
    const audio = new Audio('data:audio/mp3;base64,' + base64Audio);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'tts_playing', playing: true }));
    }
    audio.onended = () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'tts_playing', playing: false }));
      }
    };
    audio.play().catch(e => console.warn('Audio play auto-block:', e));
  } catch (e) {
    console.warn('Audio play failed:', e);
  }
}

// Start Microphone & AudioWorklet (16kHz LINEAR16 PCM)
let speechRec = null;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

async function startRecording() {
  try {
    sttStatus.textContent = 'Initializing mic...';
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
              appendFinalTranscript(text);
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'transcript_event', text: text, is_final: true }));
              }
            }
          } else {
            interim += res[0].transcript;
          }
        }
        transcriptInterim.textContent = interim ? ' ' + interim : '';
        transcriptBox.scrollTop = transcriptBox.scrollHeight;
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
        console.warn('[SpeechRec] Could not start:', err);
      }
    }

    isRecording = true;
    micBtn.classList.add('recording');
    micIcon.textContent = '⏹️';
    micText.textContent = 'Pause Mic';
    wsDot.className = 'status-dot listening';
    sttStatus.textContent = 'Listening (16kHz PCM Live)...';
  } catch (err) {
    console.error('[Mic] Error accessing microphone:', err);
    sttStatus.textContent = 'Mic Error: ' + err.message;
    alert('Microphone access error: ' + err.message);
  }
}

function appendFinalTranscript(text) {
  transcriptFinal.textContent += (transcriptFinal.textContent ? ' ' : '') + text;
  transcriptInterim.textContent = '';
  transcriptBox.scrollTop = transcriptBox.scrollHeight;
}

// Stop Microphone
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
  micText.textContent = 'Start Mic';
  wsDot.className = 'status-dot active';
  sttStatus.textContent = 'Paused';
}

micBtn.addEventListener('click', () => {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

// Section 6b & 8: Delegated click listener on the canvas
canvasStack.addEventListener('click', (event) => {
  const refElem = event.target.closest('[data-ref]');
  if (!refElem) return;

  const blockElem = refElem.closest('.canvas-block');
  if (!blockElem) return;

  const blockId = blockElem.getAttribute('data-block-id');
  const ref = refElem.getAttribute('data-ref');

  // Immediate pending feedback (Section 6b rule)
  refElem.classList.add('pending');

  if (ref.startsWith('item:')) {
    // Checklist toggle
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'toggle_item',
        block_id: blockId,
        ref: ref,
      }));
    }
  } else {
    // Drill in / inspect
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'inspect',
        block_id: blockId,
        ref: ref,
      }));
    }
  }
});

// Block rendering & DOM placement
function renderOrUpdateBlock(block) {
  if (canvasEmpty) {
    canvasEmpty.style.display = 'none';
  }

  let blockElem = document.querySelector(`.canvas-block[data-block-id="${block.id}"]`);
  const isNew = !blockElem;

  if (isNew) {
    blockElem = document.createElement('div');
    blockElem.className = 'canvas-block';
    blockElem.setAttribute('data-block-id', block.id);

    if (block.parent && block.parent.block_id) {
      blockElem.setAttribute('data-parent-id', block.parent.block_id);
      blockElem.classList.add('attached-child');

      // Place child attached immediately beneath its source block
      const parentElem = document.querySelector(`.canvas-block[data-block-id="${block.parent.block_id}"]`);
      if (parentElem && parentElem.nextSibling) {
        canvasStack.insertBefore(blockElem, parentElem.nextSibling);
      } else {
        canvasStack.appendChild(blockElem);
      }
    } else {
      canvasStack.appendChild(blockElem);
    }
  }

  blockElem.innerHTML = `
    <div class="block-top">
      <span class="block-title">${block.title || 'Block'}</span>
      <span class="block-kind-badge">${block.kind}</span>
    </div>
    <div class="block-content">${block.html || ''}</div>
  `;

  updateStats();
}

function removeBlock(blockId) {
  const blockElem = document.querySelector(`.canvas-block[data-block-id="${blockId}"]`);
  if (blockElem) {
    blockElem.remove();
  }
  updateStats();
}

function updateStats() {
  const count = document.querySelectorAll('.canvas-block').length;
  if (canvasStats) {
    canvasStats.textContent = `${count} block${count === 1 ? '' : 's'}`;
  }
  if (count === 0 && canvasEmpty) {
    canvasEmpty.style.display = 'block';
  }
}

// Undo and Clear buttons
undoBtn.addEventListener('click', () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'command', name: 'undo' }));
  }
});

clearBtn.addEventListener('click', () => {
  if (confirm('Clear all blocks from the canvas?')) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'command', name: 'clear' }));
    }
  }
});

if (dismissContradiction) {
  dismissContradiction.addEventListener('click', () => {
    contradictionBanner.style.display = 'none';
  });
}

// Manual turn sender for testing
function sendManualTurn() {
  const text = manualTextInput.value.trim();
  if (!text) return;
  appendFinalTranscript(text);
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

window.addEventListener('DOMContentLoaded', () => {
  connectWebSocket();
});
