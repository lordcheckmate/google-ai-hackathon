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
let blocksOrder = []; // Chronological sequence of visual block IDs
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
const langSelect = document.getElementById('lang-select');

let currentLanguage = localStorage.getItem('aegis_language') || 'en-US';
if (langSelect) {
  langSelect.value = currentLanguage;
  langSelect.addEventListener('change', () => {
    currentLanguage = langSelect.value;
    localStorage.setItem('aegis_language', currentLanguage);
    console.log(`[AEGIS] Language set to: ${currentLanguage}`);

    if (speechRec) {
      speechRec.lang = currentLanguage;
      if (isRecording) {
        try { speechRec.stop(); } catch (_) {}
      }
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'set_language', language: currentLanguage }));
    }

    const langName = currentLanguage === 'ja-JP' ? '日本語' : 'English';
    setSpeechBubble(`Language: ${langName}`);
  });
}


// Element Modal Elements
const elementModal = document.getElementById('element-modal');
const closeElementModalBtn = document.getElementById('close-element-modal');
const elementModalShapeBadge = document.getElementById('element-modal-shape-badge');
const elementModalTitle = document.getElementById('element-modal-title');
const elementModalDesc = document.getElementById('element-modal-desc');
const elementModalImgContainer = document.getElementById('element-modal-img-container');
const elementModalImg = document.getElementById('element-modal-img');
const elementIllustrateBtn = document.getElementById('element-illustrate-btn');
const elementExplainBtn = document.getElementById('element-explain-btn');
let currentModalElement = null;

// Sidebar Elements
const sidebar = document.getElementById('sidebar');
const sidebarBackdrop = document.getElementById('sidebar-backdrop');
const sidebarCollapseBtn = document.getElementById('sidebar-collapse-btn');
const sidebarOpenBtn = document.getElementById('sidebar-open-btn');
const newMeetingBtn = document.getElementById('new-meeting-btn');
const sessionsList = document.getElementById('sessions-list');
const guestIdDisplay = document.getElementById('guest-id-display');

// Neon Square Elements
const neonSquareFrame = document.getElementById('neon-square-frame');
const activeVisualTitle = document.getElementById('active-visual-title');
const activeVisualBadge = document.getElementById('active-visual-badge');
const timelineBar = document.getElementById('timeline-bar');
const timelinePrevBtn = document.getElementById('timeline-prev-btn');
const timelineNextBtn = document.getElementById('timeline-next-btn');
const timelineScrubber = document.getElementById('timeline-scrubber');
const timelineLatestBtn = document.getElementById('timeline-latest-btn');
const neonStandby = document.getElementById('neon-standby');
const neonCanvasContent = document.getElementById('neon-canvas-content');

// =========================================================================
// Private Guest Session State & Management
// =========================================================================

let currentSessions = [];

function getOrCreateUserId() {
  let uid = localStorage.getItem('aegis_user_id');
  if (!uid) {
    uid = 'guest_' + Math.random().toString(36).substring(2, 10);
    localStorage.setItem('aegis_user_id', uid);
  }
  return uid;
}

function getCurrentSessionId() {
  const urlParams = new URLSearchParams(window.location.search);
  let sid = urlParams.get('session_id') || localStorage.getItem('aegis_session_id');
  if (!sid) {
    sid = 'sess_' + Math.random().toString(36).substring(2, 10);
    localStorage.setItem('aegis_session_id', sid);
  }
  return sid;
}

function formatRelativeTime(ts) {
  if (!ts) return '';
  const now = Date.now() / 1000;
  const diff = Math.max(0, now - ts);
  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  const d = new Date(ts * 1000);
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

async function fetchSessions() {
  const uid = getOrCreateUserId();
  try {
    const res = await fetch(`/api/sessions?user_id=${encodeURIComponent(uid)}`);
    if (res.ok) {
      currentSessions = await res.json();
      renderSidebarSessions();
    }
  } catch (err) {
    console.warn('[AEGIS] Fetch sessions error:', err);
  }
}

function renderSidebarSessions() {
  if (!sessionsList) return;
  sessionsList.innerHTML = '';

  const activeSid = getCurrentSessionId();

  if (currentSessions.length === 0) {
    const emptyEl = document.createElement('div');
    emptyEl.style.padding = '1.5rem 0.5rem';
    emptyEl.style.color = '#475569';
    emptyEl.style.fontSize = '0.78rem';
    emptyEl.style.textAlign = 'center';
    emptyEl.textContent = 'No meetings yet. Click "+ New Meeting" to start!';
    sessionsList.appendChild(emptyEl);
    return;
  }

  currentSessions.forEach(sess => {
    const item = document.createElement('div');
    item.className = 'session-item' + (sess.sid === activeSid ? ' active' : '');
    item.title = sess.title || 'Untitled Meeting';

    const left = document.createElement('div');
    left.className = 'session-item-left';

    const icon = document.createElement('span');
    icon.className = 'session-item-icon';
    icon.textContent = '💬';

    const titleWrap = document.createElement('div');
    titleWrap.style.minWidth = '0';
    titleWrap.style.flex = '1';

    const titleEl = document.createElement('div');
    titleEl.className = 'session-item-title';
    titleEl.textContent = sess.title || 'New Meeting';

    const timeEl = document.createElement('div');
    timeEl.className = 'session-item-time';
    timeEl.textContent = formatRelativeTime(sess.updated_at || sess.created_at);

    titleWrap.appendChild(titleEl);
    titleWrap.appendChild(timeEl);

    left.appendChild(icon);
    left.appendChild(titleWrap);

    const actions = document.createElement('div');
    actions.className = 'session-item-actions';

    const delBtn = document.createElement('button');
    delBtn.className = 'session-del-btn';
    delBtn.innerHTML = '🗑️';
    delBtn.title = 'Delete meeting';
    delBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (confirm(`Delete meeting "${sess.title || 'Untitled'}"?`)) {
        await deleteMeetingSession(sess.sid);
      }
    });

    actions.appendChild(delBtn);

    item.appendChild(left);
    item.appendChild(actions);

    item.addEventListener('click', () => {
      if (sess.sid !== activeSid) {
        switchToSession(sess.sid);
      }
    });

    sessionsList.appendChild(item);
  });
}

async function switchToSession(sid) {
  console.log(`[AEGIS] Switching to session: ${sid}`);
  localStorage.setItem('aegis_session_id', sid);
  const url = new URL(window.location);
  url.searchParams.set('session_id', sid);
  window.history.pushState({}, '', url);

  // Clear in-memory canvas
  blocksStore.clear();
  blocksOrder = [];
  activeBlockId = null;
  renderNeonSquare();
  renderSidebarSessions();

  // Reconnect WebSocket for the new session
  if (ws) {
    try { ws.close(); } catch (_) {}
  }
  connectWebSocket();

  // On mobile, close drawer automatically
  closeSidebarDrawer();
}

async function createNewMeeting() {
  const uid = getOrCreateUserId();
  try {
    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: uid, title: 'New Meeting' })
    });
    if (res.ok) {
      const newSess = await res.json();
      currentSessions.unshift(newSess);
      await switchToSession(newSess.sid);
      setSpeechBubble('Started fresh meeting session.');
    }
  } catch (err) {
    console.error('[AEGIS] Create new meeting error:', err);
  }
}

async function deleteMeetingSession(sid) {
  const uid = getOrCreateUserId();
  try {
    await fetch(`/api/sessions/${encodeURIComponent(sid)}?user_id=${encodeURIComponent(uid)}`, {
      method: 'DELETE'
    });
    currentSessions = currentSessions.filter(s => s.sid !== sid);
    if (getCurrentSessionId() === sid) {
      if (currentSessions.length > 0) {
        await switchToSession(currentSessions[0].sid);
      } else {
        await createNewMeeting();
      }
    } else {
      renderSidebarSessions();
    }
  } catch (err) {
    console.error('[AEGIS] Delete session error:', err);
  }
}

function closeSidebarDrawer() {
  if (sidebar) sidebar.classList.remove('open');
  if (sidebarBackdrop) sidebarBackdrop.classList.add('hidden');
}

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
  const sessionId = getCurrentSessionId();
  const userId = getOrCreateUserId();
  const freshQuery = urlParams.has('fresh') ? '&fresh=1' : '';
  const wsUrl = `${protocol}//${window.location.host}/ws?session_id=${encodeURIComponent(sessionId)}&user_id=${encodeURIComponent(userId)}${freshQuery}`;

  ws = new WebSocket(wsUrl);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    wsDot.className = 'status-dot active';
    wsStatus.textContent = 'Connected';
    console.log('[WS] Connected to AEGIS meeting engine');
    try {
      ws.send(JSON.stringify({ type: 'set_language', language: currentLanguage }));
    } catch (_) {}
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

let thinkingTimeout = null;

function handleServerMessage(msg) {
  if (msg.type === 'transcript') {
    if (msg.is_final) {
      setAvatarState('thinking');
      setSpeechBubble(`Processed: "${msg.text.slice(0, 45)}..."`, 'thinking');
      if (thinkingTimeout) clearTimeout(thinkingTimeout);
      thinkingTimeout = setTimeout(() => {
        if (!mouthBar.classList.contains('speaking-mouth') && avatarIcon.classList.contains('avatar-thinking')) {
          setAvatarState('listening');
          setSpeechBubble('Listening to meeting audio...');
        }
      }, 6000);
    }
  } else if (msg.type === 'turn_complete') {
    if (thinkingTimeout) clearTimeout(thinkingTimeout);
    if (!mouthBar.classList.contains('speaking-mouth')) {
      setAvatarState('listening');
      setSpeechBubble('Listening to meeting audio...');
    }
  } else if (msg.type === 'status') {
    wsStatus.textContent = msg.status || 'Active';
  } else if (msg.type === 'block_upsert') {
    if (thinkingTimeout) clearTimeout(thinkingTimeout);
    storeAndRenderBlock(msg.block);
    // Return to listening unless currently speaking audio
    if (!mouthBar.classList.contains('speaking-mouth')) {
      setAvatarState('listening');
      setSpeechBubble('Canvas visual updated.');
      setTimeout(() => {
        if (!mouthBar.classList.contains('speaking-mouth')) {
          setSpeechBubble('Listening to meeting audio...');
        }
      }, 2500);
    }
    // Refresh sessions to keep timestamps/counts accurate
    fetchSessions();
  } else if (msg.type === 'session_title_updated') {
    const sess = currentSessions.find(s => s.sid === msg.session_id);
    if (sess) {
      sess.title = msg.title;
      renderSidebarSessions();
    } else {
      fetchSessions();
    }
  } else if (msg.type === 'block_remove') {
    removeBlock(msg.block_id);
  } else if (msg.type === 'canvas_cleared') {
    blocksStore.clear();
    blocksOrder = [];
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

let isAudioPlaying = false;

function playAudio(base64Audio, onEndCallback) {
  try {
    isAudioPlaying = true;
    const audio = new Audio('data:audio/mp3;base64,' + base64Audio);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'tts_playing', playing: true }));
    }
    const finishAudio = () => {
      setTimeout(() => {
        isAudioPlaying = false;
      }, 900);
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'tts_playing', playing: false }));
      }
      if (onEndCallback) onEndCallback();
    };
    audio.onended = finishAudio;
    audio.onerror = finishAudio;
    audio.play().catch(e => {
      console.warn('Audio auto-play blocked, click page to enable audio:', e);
      finishAudio();
    });
  } catch (e) {
    console.warn('Audio playback error:', e);
    isAudioPlaying = false;
    if (onEndCallback) onEndCallback();
  }
}

// =========================================================================
// Visual Store & Neon Square (四角形) Rendering with Timeline
// =========================================================================

function storeAndRenderBlock(block) {
  if (!blocksOrder.includes(block.id)) {
    blocksOrder.push(block.id);
  }
  blocksStore.set(block.id, block);
  // Always automatically advance to the latest visual generation
  activeBlockId = block.id;
  renderNeonSquare();
}

function removeBlock(blockId) {
  blocksStore.delete(blockId);
  blocksOrder = blocksOrder.filter(id => id !== blockId);
  if (activeBlockId === blockId) {
    activeBlockId = blocksOrder.length > 0 ? blocksOrder[blocksOrder.length - 1] : null;
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
    if (timelineBar) timelineBar.classList.add('hidden');
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

  // Render Timeline Bar (Single-viewport model with history scrubber)
  renderTimeline();

  // Render HTML / SVG content directly inside the single Neon Square
  neonCanvasContent.innerHTML = currentBlock.html || '';
}

function renderTimeline() {
  if (!timelineBar || !timelineScrubber) return;

  if (blocksOrder.length <= 1) {
    timelineBar.classList.add('hidden');
    return;
  }

  timelineBar.classList.remove('hidden');
  timelineScrubber.innerHTML = '';

  let currentIndex = blocksOrder.indexOf(activeBlockId);
  if (currentIndex === -1) {
    currentIndex = blocksOrder.length - 1;
    activeBlockId = blocksOrder[currentIndex];
  }

  // Update button enabled/disabled states
  if (timelinePrevBtn) {
    timelinePrevBtn.disabled = currentIndex <= 0;
  }
  if (timelineNextBtn) {
    timelineNextBtn.disabled = currentIndex >= blocksOrder.length - 1;
  }
  if (timelineLatestBtn) {
    if (currentIndex < blocksOrder.length - 1) {
      timelineLatestBtn.classList.remove('hidden');
    } else {
      timelineLatestBtn.classList.add('hidden');
    }
  }

  // Render dots for each generation in chronological sequence
  blocksOrder.forEach((id, idx) => {
    const block = blocksStore.get(id);
    const dot = document.createElement('div');
    const isLatest = idx === blocksOrder.length - 1;
    const isActive = idx === currentIndex;

    dot.className = `timeline-dot ${isActive ? 'active' : ''} ${isLatest ? 'latest' : ''}`;
    const title = block ? (block.title || block.kind) : `Version ${idx + 1}`;
    dot.title = `Step ${idx + 1} of ${blocksOrder.length}: ${title}${isLatest ? ' (Latest)' : ''}`;

    dot.addEventListener('click', () => {
      activeBlockId = id;
      renderNeonSquare();
    });

    timelineScrubber.appendChild(dot);
  });

  // Step counter label
  const counterLabel = document.createElement('span');
  counterLabel.className = 'timeline-label';
  counterLabel.textContent = `${currentIndex + 1}/${blocksOrder.length}`;
  timelineScrubber.appendChild(counterLabel);
}

// Timeline Navigation Click Handlers
if (timelinePrevBtn) {
  timelinePrevBtn.addEventListener('click', () => {
    const currentIndex = blocksOrder.indexOf(activeBlockId);
    if (currentIndex > 0) {
      activeBlockId = blocksOrder[currentIndex - 1];
      renderNeonSquare();
    }
  });
}

if (timelineNextBtn) {
  timelineNextBtn.addEventListener('click', () => {
    const currentIndex = blocksOrder.indexOf(activeBlockId);
    if (currentIndex >= 0 && currentIndex < blocksOrder.length - 1) {
      activeBlockId = blocksOrder[currentIndex + 1];
      renderNeonSquare();
    }
  });
}

if (timelineLatestBtn) {
  timelineLatestBtn.addEventListener('click', () => {
    if (blocksOrder.length > 0) {
      activeBlockId = blocksOrder[blocksOrder.length - 1];
      renderNeonSquare();
    }
  });
}

// =========================================================================
// Interactive Click / Drill-In Listener & Element Modal
// =========================================================================

function openElementModal(data) {
  currentModalElement = data;
  if (!elementModal) return;

  if (elementModalTitle) {
    elementModalTitle.textContent = data.label || `STEP: ${data.id}`;
  }
  if (elementModalShapeBadge) {
    elementModalShapeBadge.textContent = (data.shape || 'STEP').toUpperCase();
  }
  if (elementModalDesc) {
    elementModalDesc.textContent = data.note || 'No additional details provided for this element.';
  }
  if (elementModalImgContainer && elementModalImg) {
    if (data.img && data.img !== 'loading' && (data.img.startsWith('http') || data.img.startsWith('/'))) {
      elementModalImg.src = data.img;
      elementModalImgContainer.classList.remove('hidden');
    } else {
      elementModalImgContainer.classList.add('hidden');
    }
  }

  elementModal.classList.remove('hidden');
}

function closeElementModal() {
  if (elementModal) {
    elementModal.classList.add('hidden');
  }
  currentModalElement = null;
}

if (closeElementModalBtn) {
  closeElementModalBtn.addEventListener('click', closeElementModal);
}
if (elementModal) {
  elementModal.addEventListener('click', (e) => {
    if (e.target === elementModal) closeElementModal();
  });
}

if (elementIllustrateBtn) {
  elementIllustrateBtn.addEventListener('click', () => {
    if (!currentModalElement) return;
    const { blockId, id, label, note } = currentModalElement;
    closeElementModal();

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'illustrate_step',
        block_id: blockId,
        node_label: label || id,
        visual_description: note,
      }));
      setSpeechBubble(`🎨 Generating Nano Banana visual illustration for "${label || id}"...`);
      setAvatarState('thinking');
    }
  });
}

if (elementExplainBtn) {
  elementExplainBtn.addEventListener('click', () => {
    if (!currentModalElement) return;
    const { blockId, id, label } = currentModalElement;
    closeElementModal();

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'inspect',
        block_id: blockId,
        ref: id,
        mode: 'words',
      }));
      setSpeechBubble(`💬 Generating verbal explanation for "${label || id}"...`);
      setAvatarState('thinking');
    }
  });
}

neonCanvasContent.addEventListener('click', (event) => {
  if (!activeBlockId) return;

  // Check if click was on "Show more ▾" or on a Flow node card
  const showMoreBtn = event.target.closest('[data-action="show-more"]');
  const nodeGroup = event.target.closest('.flow-node-group') || event.target.closest('[data-node-id]');

  if (showMoreBtn || nodeGroup) {
    event.stopPropagation();
    const elem = showMoreBtn || nodeGroup;
    const nodeId = elem.getAttribute('data-node-id') || elem.getAttribute('data-ref') || '';
    const nodeLabel = elem.getAttribute('data-node-label') || '';
    const nodeNote = elem.getAttribute('data-node-note') || '';
    const nodeShape = elem.getAttribute('data-node-shape') || 'step';
    const nodeImg = elem.getAttribute('data-node-img') || '';

    openElementModal({
      id: nodeId,
      label: nodeLabel,
      note: nodeNote,
      shape: nodeShape,
      img: nodeImg,
      blockId: activeBlockId,
    });
    return;
  }

  const refElem = event.target.closest('[data-ref]');
  if (!refElem) return;

  const ref = refElem.getAttribute('data-ref');

  // If a tab for this specific step already exists, switch to it immediately!
  const matchingTabId = Array.from(blocksStore.keys()).find(k => k.includes(`_${ref}`) || k.includes(`_${ref}_`));
  if (matchingTabId && matchingTabId !== activeBlockId) {
    activeBlockId = matchingTabId;
    renderNeonSquare();
    return;
  }

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
    // For general elements (e.g. table cells or answers), open detail modal
    const cellText = refElem.textContent ? refElem.textContent.trim() : '';
    openElementModal({
      id: ref,
      label: `Element: ${ref}`,
      note: cellText || 'Detailed element inspection.',
      shape: 'detail',
      img: '',
      blockId: activeBlockId,
    });
  }
});

// =========================================================================
// Audio Recording & AudioWorklet Streaming (16kHz PCM)
// =========================================================================

let speechRec = null;
let speechDebounceTimer = null;
let speechTurnStartTime = 0;
let accumulatedSpeechTurn = '';

function flushSpeechTurn(reason) {
  if (speechDebounceTimer) {
    clearTimeout(speechDebounceTimer);
    speechDebounceTimer = null;
  }
  speechTurnStartTime = 0;
  const finalUtterance = accumulatedSpeechTurn.trim();
  accumulatedSpeechTurn = '';

  if (finalUtterance && !isAudioPlaying) {
    console.log(`[SpeechRec] Flushing turn (${reason}): "${finalUtterance}"`);
    setAvatarState('thinking');
    setSpeechBubble(`Heard: "${finalUtterance.slice(-45)}"`, 'thinking');
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'transcript_event',
        text: finalUtterance,
        is_final: true,
        immediate: true
      }));
    }
  }
}

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
      // Echo suppression: do not stream mic audio while robot is speaking
      if (ws && ws.readyState === WebSocket.OPEN && isRecording && !isAudioPlaying) {
        ws.send(event.data);
      }
    };

    source.connect(pcmNode);
    pcmNode.connect(audioContext.destination);

    // Browser local SpeechRecognition with silence accumulation & debouncing
    if (SpeechRecognition && !speechRec) {
      speechRec = new SpeechRecognition();
      speechRec.continuous = true;
      speechRec.interimResults = true;
      speechRec.lang = currentLanguage || 'en-US';

      speechRec.onresult = (event) => {

        // Echo suppression: ignore microphone while robot is speaking aloud
        if (isAudioPlaying) return;

        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const res = event.results[i];
          if (res.isFinal) {
            const text = res[0].transcript.trim();
            if (text) {
              if (!speechTurnStartTime) {
                speechTurnStartTime = Date.now();
              }
              accumulatedSpeechTurn = (accumulatedSpeechTurn + ' ' + text).trim();
            }
          } else {
            interim += res[0].transcript;
            if (!speechTurnStartTime && interim.trim()) {
              speechTurnStartTime = Date.now();
            }
          }
        }

        if (interim || accumulatedSpeechTurn) {
          setAvatarState('listening');
          const currentDisplay = (accumulatedSpeechTurn ? accumulatedSpeechTurn + ' ' : '') + interim;
          setSpeechBubble(`Listening: "${currentDisplay.slice(-45)}"`, 'listening');
        }

        // Rule: Start generating ONLY on speech stop (2s silence) OR every 15 seconds of continuous speech
        if (accumulatedSpeechTurn) {
          const elapsed = Date.now() - speechTurnStartTime;

          // Condition 1: 15 seconds of continuous speech elapsed
          if (speechTurnStartTime && elapsed >= 15000) {
            flushSpeechTurn('15s continuous speech threshold');
            return;
          }

          // Condition 2: Wait for speech stop (2.0s of silence after speech stops)
          if (speechDebounceTimer) {
            clearTimeout(speechDebounceTimer);
          }
          speechDebounceTimer = setTimeout(() => {
            flushSpeechTurn('speech stop detected (2s silence)');
          }, 2000);
        }
      };

      // Browser VAD: fires when voice activity pauses/stops in microphone
      speechRec.onspeechend = () => {
        if (accumulatedSpeechTurn) {
          console.log('[SpeechRec] onspeechend event triggered');
          if (speechDebounceTimer) {
            clearTimeout(speechDebounceTimer);
          }
          // Allow 2.0s silence to confirm speech stop
          speechDebounceTimer = setTimeout(() => {
            flushSpeechTurn('onspeechend (speech stopped for 2s)');
          }, 2000);
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
  if (accumulatedSpeechTurn) {
    flushSpeechTurn('mic stopped');
  }
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

let chatDebounceTimer = null;
let chatStartTime = 0;

function sendManualTurn() {
  if (chatDebounceTimer) {
    clearTimeout(chatDebounceTimer);
    chatDebounceTimer = null;
  }
  chatStartTime = 0;
  const text = manualTextInput.value.trim();
  if (!text) return;

  setAvatarState('thinking');
  setSpeechBubble(`Sent: "${text}"`, 'thinking');

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'transcript_event', text: text, is_final: true, immediate: true }));
  }
  manualTextInput.value = '';
}

// Rule: Send to Gemini every 15s or when chat typing stops for 2 seconds
manualTextInput.addEventListener('input', () => {
  const text = manualTextInput.value.trim();
  if (!text) {
    if (chatDebounceTimer) clearTimeout(chatDebounceTimer);
    chatStartTime = 0;
    return;
  }

  if (!chatStartTime) {
    chatStartTime = Date.now();
  }

  const elapsed = Date.now() - chatStartTime;

  // Condition 1: 15 seconds of continuous typing
  if (elapsed >= 15000) {
    console.log('[Chat] 15s continuous typing limit reached -> sending to Gemini');
    sendManualTurn();
    return;
  }

  // Condition 2: Chat input stops typing for 2 seconds
  if (chatDebounceTimer) {
    clearTimeout(chatDebounceTimer);
  }
  chatDebounceTimer = setTimeout(() => {
    console.log('[Chat] Chat typing stopped for 2 seconds -> sending to Gemini');
    sendManualTurn();
  }, 2000);
});

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
  const uid = getOrCreateUserId();
  if (guestIdDisplay) {
    guestIdDisplay.textContent = 'ID: ' + uid;
  }

  // Sidebar Controls
  if (newMeetingBtn) {
    newMeetingBtn.addEventListener('click', createNewMeeting);
  }
  if (sidebarCollapseBtn) {
    sidebarCollapseBtn.addEventListener('click', () => {
      sidebar.classList.add('collapsed');
      closeSidebarDrawer();
    });
  }
  if (sidebarOpenBtn) {
    sidebarOpenBtn.addEventListener('click', () => {
      sidebar.classList.remove('collapsed');
      sidebar.classList.add('open');
      if (sidebarBackdrop) sidebarBackdrop.classList.remove('hidden');
    });
  }
  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', closeSidebarDrawer);
  }

  // Connect WebSocket & fetch meetings history
  connectWebSocket();
  fetchSessions();
  setAvatarState('listening');
});
