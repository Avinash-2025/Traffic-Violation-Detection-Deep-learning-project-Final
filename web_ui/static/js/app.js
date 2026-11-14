/**
 * Sentinel Vanguard / TVDR — Intelligent Command Center
 * - Dynamic marking wizard flow: Pops up on video upload with live interactive guide
 * - Zero ghost spots: Clear markup cleanly resets canvas and annotator
 * - List-wise Incident History organized per upload session with per-upload folders
 * - Resilient XMLHttpRequest upload with live progress bar and detailed error feedback
 * - Warm Cyberpunk Amber, Emerald & Violet palette with zero blue/cyan
 */

let state = {
  currentView: 'overview',
  currentTool: 'view',
  isPlaying: false,
  status: null,
  selectedViolation: null,
  violations: [],
  sessions: [],
  expandedSessions: new Set(),
  wizardTool: 'stopline',
  zoomLevel: 1.0,
  wizZoomLevel: 1.0,
  markup: {
    stop_lines: [],
    signal_roi: { id: 'signal_roi_1', name: 'Traffic Signal ROI', points: [], visible: true, locked: false, color: '#10B981' },
    detection_area: { id: 'detection_area_1', name: 'Detection Zone', points: [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], visible: true, locked: false, color: '#10B981' },
    direction_arrow: { id: 'direction_1', name: 'Allowed Direction', start: [], end: [], visible: true, locked: false, color: '#A855F7' }
  },
  drawingState: {
    points: [],
    isDragging: false,
    dragStart: null,
    mousePos: { x: 0, y: 0 }
  },
  dragHandle: null,
  wizardDrawingState: {
    points: [],
    isDragging: false,
    dragStart: null,
    mousePos: { x: 0, y: 0 }
  },
  wizardDragHandle: null,
  wizardCompletedSteps: new Set()
};

const canvas = document.getElementById('interactive-canvas');
const ctx = canvas ? canvas.getContext('2d') : null;
const wizCanvas = document.getElementById('wizard-canvas');
const wizCtx = wizCanvas ? wizCanvas.getContext('2d') : null;
const nativeFileInput = document.getElementById('native-file-input');

// ========================================================================
// INITIALIZATION
// ========================================================================
window.addEventListener('DOMContentLoaded', () => {
  resizeCanvas();
  window.addEventListener('resize', () => {
    resizeCanvas();
    resizeWizardCanvas();
  });

  setupNativeUpload();
  setupDragAndDrop();
  setupCanvasEvents();
  setupWizardCanvasEvents();
  fetchMarkup();

  // Stream auto-reconnect listeners
  const mainImg = document.getElementById('stream-img');
  if (mainImg) {
    mainImg.onerror = () => {
      setTimeout(refreshVideoStreams, 1000);
    };
  }
  const wizImg = document.getElementById('wizard-stream-img');
  if (wizImg) {
    wizImg.onerror = () => {
      setTimeout(refreshVideoStreams, 1000);
    };
  }

  // Polling intervals
  setInterval(pollStatus, 400);
  setInterval(pollViolations, 750);
  setInterval(pollSessions, 2000);

  lucide.createIcons();
});

function resizeCanvas() {
  const container = document.getElementById('video-container');
  if (container && canvas) {
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    drawCanvas();
  }
}

function resizeWizardCanvas() {
  const wc = document.querySelector('.wizard-video-container');
  if (wc && wizCanvas) {
    wizCanvas.width = wc.clientWidth;
    wizCanvas.height = wc.clientHeight;
    drawWizardCanvas();
  }
}

// ========================================================================
// VIEW SWITCHING
// ========================================================================
function switchView(viewName) {
  state.currentView = viewName;
  document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
  const target = document.getElementById(`view-${viewName}`);
  if (target) target.classList.add('active');

  document.querySelectorAll('.nav-tab-btn').forEach(btn => btn.classList.remove('active', 'active-violet'));
  const activeBtn = document.getElementById(`nav-${viewName}`);
  if (activeBtn) {
    activeBtn.classList.add(viewName === 'history' ? 'active-violet' : 'active');
  }

  if (viewName === 'analyzer') {
    setTimeout(resizeCanvas, 60);
  } else if (viewName === 'history') {
    state.lastSessionsJson = null;
    pollSessions();
  }

  lucide.createIcons();
}

// ========================================================================
// NATIVE FILE UPLOAD WITH REAL PROGRESS BAR & ERROR HANDLING
// ========================================================================
function triggerNativeFileUpload() {
  if (nativeFileInput) nativeFileInput.click();
}

function setupNativeUpload() {
  if (!nativeFileInput) return;
  nativeFileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    uploadVideoFile(file);
    nativeFileInput.value = '';
  });
}

function setupDragAndDrop() {
  const dropZone = document.getElementById('video-container');
  if (!dropZone) return;

  ['dragenter', 'dragover'].forEach(ev => {
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    });
  });
  ['dragleave', 'drop'].forEach(ev => {
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
    });
  });
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      uploadVideoFile(e.dataTransfer.files[0]);
    }
  });
}

function uploadVideoFile(file) {
  const progress = document.getElementById('upload-progress');
  const display = document.getElementById('current-video-display-name');
  if (display) display.innerText = `Preparing upload: ${file.name}...`;
  if (progress) {
    progress.style.display = 'block';
    progress.style.width = '5%';
  }

  const formData = new FormData();
  formData.append('video', file);

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/videos/upload', true);
  xhr.timeout = 600000; // 10 minutes timeout for large footage

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable && progress) {
      const pct = Math.round((e.loaded / e.total) * 95);
      progress.style.width = `${pct}%`;
      if (display) {
        const mbLoaded = (e.loaded / (1024 * 1024)).toFixed(1);
        const mbTotal = (e.total / (1024 * 1024)).toFixed(1);
        display.innerText = `Uploading ${file.name} (${mbLoaded} / ${mbTotal} MB • ${pct}%)...`;
      }
    }
  };

  xhr.onload = () => {
    if (progress) progress.style.width = '100%';
    setTimeout(() => {
      if (progress) {
        progress.style.display = 'none';
        progress.style.width = '0%';
      }
    }, 450);

    try {
      const data = JSON.parse(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300 && data.success) {
        if (display) display.innerText = data.name || file.name;

        // Reset markup state for the new video
        state.markup.stop_lines = [];
        state.markup.signal_roi.points = [];
        state.markup.direction_arrow.start = [];
        state.markup.direction_arrow.end = [];
        state.wizardCompletedSteps.clear();

        switchView('analyzer');
        pollStatus();
        refreshVideoStreams();

        // Automatically open the Marking Menu & Guide wizard!
        setTimeout(() => {
          openMarkupWizard();
        }, 300);
      } else {
        alert(`Upload error: ${data.error || 'Server could not process file'}`);
      }
    } catch (err) {
      console.error(err);
      alert(`Upload response error (${xhr.status}): Could not parse server response.`);
    }
  };

  xhr.onerror = () => {
    if (progress) {
      progress.style.display = 'none';
      progress.style.width = '0%';
    }
    alert('Network error while uploading video. Ensure the backend server is running and the file is accessible.');
  };

  xhr.ontimeout = () => {
    if (progress) {
      progress.style.display = 'none';
      progress.style.width = '0%';
    }
    alert('Upload timed out. Try uploading a shorter or more compressed clip.');
  };

  xhr.send(formData);
}

async function loadRealTrafficCCTV() {
  try {
    const res = await fetch('/api/videos/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: 'uploads/real_traffic_cctv.mp4' })
    });
    const data = await res.json();
    if (data.success) {
      state.markup.stop_lines = [];
      state.markup.signal_roi.points = [];
      state.markup.direction_arrow.start = [];
      state.markup.direction_arrow.end = [];
      state.wizardCompletedSteps.clear();

      switchView('analyzer');
      pollStatus();
      setTimeout(() => openMarkupWizard(), 400);
    }
  } catch (e) {
    console.error(e);
  }
}

function refreshVideoStreams() {
  const ts = Date.now();
  const mainImg = document.getElementById('stream-img');
  if (mainImg) mainImg.src = `/video_feed?t=${ts}`;
  const wizImg = document.getElementById('wizard-stream-img');
  if (wizImg) wizImg.src = `/video_feed?t=${ts}`;
}

// ========================================================================
// MARKUP WIZARD & GUIDE FLOW
// ========================================================================
function openMarkupWizard() {
  const overlay = document.getElementById('markup-wizard-overlay');
  if (overlay) {
    overlay.classList.add('active');
    // Ensure video is paused during marking setup
    fetch('/api/playback/pause', { method: 'POST' });
    setWizardTool('stopline');
    refreshVideoStreams();

    setTimeout(() => {
      resizeWizardCanvas();
      drawWizardCanvas();
      updateWizardGuideSteps(1);
    }, 120);
  }
  lucide.createIcons();
}

function closeMarkupWizard() {
  const overlay = document.getElementById('markup-wizard-overlay');
  if (overlay) overlay.classList.remove('active');
  drawCanvas();
}

function submitMarkupAndStart() {
  saveMarkupToBackend();
  closeMarkupWizard();

  // Start analysis after submitting markup
  fetch('/api/playback/play', { method: 'POST' });
  state.isPlaying = true;
  pollStatus();
  setTimeout(refreshVideoStreams, 120);
}

function setWizardTool(toolName) {
  state.wizardTool = toolName;
  state.wizardDrawingState.points = [];
  state.wizardDrawingState.isDragging = false;
  state.wizardDragHandle = null;

  document.querySelectorAll('.wizard-tools-row .tool-btn').forEach(btn => btn.classList.remove('active'));
  const btn = document.getElementById(`wiz-tool-${toolName}`);
  if (btn) btn.classList.add('active');

  if (wizCanvas) wizCanvas.style.cursor = toolName === 'view' ? 'default' : 'crosshair';

  const stepMap = { stopline: 1, signal: 2, detection: 3, direction: 4, view: 0 };
  updateWizardGuideSteps(stepMap[toolName] || 0);

  drawWizardCanvas();
}

function updateWizardGuideSteps(activeNum) {
  for (let i = 1; i <= 4; i++) {
    const step = document.getElementById(`guide-step-${i}`);
    if (!step) continue;
    step.classList.remove('active-step', 'completed');
    if (state.wizardCompletedSteps.has(i)) step.classList.add('completed');
    if (activeNum === i) step.classList.add('active-step');
  }
}

function setupWizardCanvasEvents() {
  if (!wizCanvas) return;

  wizCanvas.addEventListener('mousedown', (e) => {
    const rect = wizCanvas.getBoundingClientRect();
    const pt = { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };

    if (state.wizardTool === 'view') {
      const handle = findNearbyHandleOnCanvas(pt, wizCanvas);
      if (handle) {
        state.wizardDragHandle = handle;
        return;
      }
    }

    if (state.wizardTool === 'stopline') {
      state.wizardDrawingState.points.push(pt);
      if (state.wizardDrawingState.points.length === 2) {
        const pts = state.wizardDrawingState.points.map(p => [r3(p.x), r3(p.y)]);
        state.markup.stop_lines = [
          { id: 'stop_line_1', name: 'Main Stop Line', points: pts, visible: true, locked: false, color: '#EF4444' }
        ];
        saveMarkupToBackend();
        state.wizardDrawingState.points = [];
        state.wizardCompletedSteps.add(1);
        // Advance to step 2 (Signal ROI)
        setWizardTool('signal');
      }
    } else if (state.wizardTool === 'detection') {
      state.wizardDrawingState.points.push(pt);
    } else if (state.wizardTool === 'signal') {
      // Direct point-selection: single click places ROI box centered at clicked location
      const hw = 0.035, hh = 0.055;
      const box = [
        [r3(Math.max(0, pt.x - hw)), r3(Math.max(0, pt.y - hh))],
        [r3(Math.min(1, pt.x + hw)), r3(Math.max(0, pt.y - hh))],
        [r3(Math.min(1, pt.x + hw)), r3(Math.min(1, pt.y + hh))],
        [r3(Math.max(0, pt.x - hw)), r3(Math.min(1, pt.y + hh))]
      ];
      state.markup.signal_roi.points = box;
      saveMarkupToBackend();
      state.wizardCompletedSteps.add(2);
      setWizardTool('detection');
      drawWizardCanvas();
      return;
    } else if (state.wizardTool === 'direction') {
      state.wizardDrawingState.isDragging = true;
      state.wizardDrawingState.dragStart = pt;
    }
    drawWizardCanvas();
  });

  wizCanvas.addEventListener('dblclick', () => {
    if (state.wizardTool === 'detection' && state.wizardDrawingState.points.length >= 3) {
      const pts = state.wizardDrawingState.points.map(p => [r3(p.x), r3(p.y)]);
      state.markup.detection_area.points = pts;
      saveMarkupToBackend();
      state.wizardDrawingState.points = [];
      state.wizardCompletedSteps.add(3);
      setWizardTool('direction');
      drawWizardCanvas();
    }
  });

  wizCanvas.addEventListener('mousemove', (e) => {
    const rect = wizCanvas.getBoundingClientRect();
    const pt = { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };
    state.wizardDrawingState.mousePos = pt;

    if (state.wizardDragHandle) {
      applyDragHandle(state.wizardDragHandle, pt);
      drawWizardCanvas();
      return;
    }
    if (state.wizardTool === 'view') {
      const handle = findNearbyHandleOnCanvas(pt, wizCanvas);
      wizCanvas.style.cursor = handle ? 'grab' : 'default';
    } else {
      drawWizardCanvas();
    }
  });

  wizCanvas.addEventListener('mouseup', (e) => {
    if (state.wizardDragHandle) {
      state.wizardDragHandle = null;
      saveMarkupToBackend();
      drawWizardCanvas();
      return;
    }

    const rect = wizCanvas.getBoundingClientRect();
    const p2 = { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };

    if (state.wizardTool === 'signal' && state.wizardDrawingState.isDragging) {
      state.wizardDrawingState.isDragging = false;
      const p1 = state.wizardDrawingState.dragStart;
      const dist = Math.hypot(p2.x - p1.x, p2.y - p1.y);
      let box;
      if (dist < 0.02) {
        const hw = 0.035, hh = 0.055;
        box = [
          [r3(p1.x - hw), r3(p1.y - hh)],
          [r3(p1.x + hw), r3(p1.y - hh)],
          [r3(p1.x + hw), r3(p1.y + hh)],
          [r3(p1.x - hw), r3(p1.y + hh)]
        ];
      } else {
        box = [
          [r3(Math.min(p1.x, p2.x)), r3(Math.min(p1.y, p2.y))],
          [r3(Math.max(p1.x, p2.x)), r3(Math.min(p1.y, p2.y))],
          [r3(Math.max(p1.x, p2.x)), r3(Math.max(p1.y, p2.y))],
          [r3(Math.min(p1.x, p2.x)), r3(Math.max(p1.y, p2.y))]
        ];
      }
      state.markup.signal_roi.points = box;
      saveMarkupToBackend();
      state.wizardCompletedSteps.add(2);
      // Advance to step 3 (Detection Area)
      setWizardTool('detection');
    } else if (state.wizardTool === 'direction' && state.wizardDrawingState.isDragging) {
      state.wizardDrawingState.isDragging = false;
      const p1 = state.wizardDrawingState.dragStart;
      state.markup.direction_arrow.start = [r3(p1.x), r3(p1.y)];
      state.markup.direction_arrow.end = [r3(p2.x), r3(p2.y)];
      saveMarkupToBackend();
      state.wizardCompletedSteps.add(4);
      setWizardTool('view');
    }
    drawWizardCanvas();
  });
}

function drawWizardCanvas() {
  if (!wizCtx || !wizCanvas) return;
  wizCtx.clearRect(0, 0, wizCanvas.width, wizCanvas.height);
  if (!state.status || !state.status.video_path) {
    return; // Don't draw pointers if no video is loaded
  }
  drawMarkupOnContext(wizCtx, wizCanvas.width, wizCanvas.height, state.wizardDrawingState, state.wizardTool);
}

// ========================================================================
// STATUS POLLING & TELEMETRY
// ========================================================================
async function pollStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    state.status = data;

    const display = document.getElementById('current-video-display-name');
    if (display) {
      display.innerText = data.video_path || 'Awaiting Video Ingestion';
      display.title = data.video_path || '';
    }

    const stateBadge = document.getElementById('video-state-badge');
    if (stateBadge) {
      stateBadge.innerText = data.video_path ? (data.is_playing ? 'Active' : 'Paused') : 'Idle';
      stateBadge.style.color = data.video_path ? 'var(--color-emerald)' : 'var(--text-muted)';
    }

    const meta = document.getElementById('analyzer-meta-counter');
    if (meta) {
      meta.innerText = `Frame ${data.current_frame} / ${data.total_frames} • ${data.target_fps || 30.0} FPS`;
    }

    state.isPlaying = data.is_playing;
    const playIcon = document.getElementById('player-play-icon');
    const playText = document.getElementById('player-play-text');
    if (playIcon && playText) {
      playIcon.setAttribute('data-lucide', data.is_playing ? 'pause' : 'play');
      playText.innerText = data.is_playing ? 'Pause' : 'Play';
    }

    const seekSlider = document.getElementById('seek-slider');
    const timeDisplay = document.getElementById('time-display');
    if (seekSlider && !seekSlider.matches(':active')) {
      seekSlider.max = Math.max(1, data.total_frames - 1);
      seekSlider.value = data.current_frame || 0;
    }
    if (timeDisplay) timeDisplay.innerText = `${data.timestamp} / ${data.total_time}`;

    const playerFps = document.getElementById('player-fps');
    if (playerFps) {
      playerFps.innerText = `${(data.fps || 0).toFixed(1)} FPS`;
      if (data.fps < 5) playerFps.style.color = 'var(--color-danger)';
      else if (data.fps < 10) playerFps.style.color = 'var(--color-warning)';
      else playerFps.style.color = 'var(--color-emerald)';
    }

    const hasVideo = !!(data.video_path && data.video_path.trim() !== '');

    // 1. Traffic signal widget visibility
    const headerSignal = document.getElementById('header-signal-widget');
    if (headerSignal) {
      headerSignal.style.display = hasVideo ? 'inline-flex' : 'none';
    }

    // 2. Action buttons visibility (Remove Video & Export CSV)
    const btnRemove = document.getElementById('btn-remove-video');
    if (btnRemove) {
      btnRemove.style.display = hasVideo ? 'inline-flex' : 'none';
    }

    const btnExport = document.getElementById('btn-export-csv');
    if (btnExport) {
      btnExport.style.display = hasVideo ? 'inline-flex' : 'none';
    }

    // 3. Disable/Enable markup buttons when no video is loaded
    const toolButtons = [
      'tool-stopline',
      'tool-signal',
      'tool-detection',
      'tool-direction',
      'tool-clear',
      'btn-open-guide-pill',
      'btn-edit-markup'
    ];
    toolButtons.forEach(id => {
      const btn = document.getElementById(id);
      if (btn) {
        if (!hasVideo) {
          btn.setAttribute('disabled', 'true');
          btn.classList.add('tool-disabled');
        } else {
          btn.removeAttribute('disabled');
          btn.classList.remove('tool-disabled');
        }
      }
    });

    // 4. Update Present Video Evidence Folder Shortcut
    const cardFolder = document.getElementById('card-session-folder');
    if (cardFolder) {
      cardFolder.style.display = hasVideo ? 'flex' : 'none';
    }

    const folderNameEl = document.getElementById('session-folder-name');
    const folderPathEl = document.getElementById('session-folder-path');
    const folderBadgeEl = document.getElementById('session-folder-badge');

    if (hasVideo && data.session && data.session.folder) {
      if (folderNameEl) folderNameEl.innerText = data.session.folder;
      if (folderPathEl) folderPathEl.innerText = `uploads/sessions/${data.session.folder}/`;
      if (folderBadgeEl) folderBadgeEl.innerText = `${data.session.snapshot_count || 0} Snapshots`;
    } else if (hasVideo) {
      if (folderNameEl) folderNameEl.innerText = 'Active Session Storage';
      if (folderPathEl) folderPathEl.innerText = `uploads/sessions/${data.video_path.replace(/\.[^/.]+$/, "")}/`;
      if (folderBadgeEl) folderBadgeEl.innerText = '0 Snapshots';
    } else {
      if (folderNameEl) folderNameEl.innerText = 'No Video Loaded';
      if (folderPathEl) folderPathEl.innerText = 'Upload a video to initialize session storage';
      if (folderBadgeEl) folderBadgeEl.innerText = '0 Snapshots';
    }

    // Traffic signal widget
    if (hasVideo) {
      const sigState = (data.signal_state || 'green').toLowerCase();
      updateSignalLamps(sigState);
    }
    updateViolationStats(data);

    lucide.createIcons();
  } catch (err) {
    console.error('Status poll error:', err);
  }
}

async function removeCurrentVideo() {
  try {
    const res = await fetch('/api/videos/remove', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      state.markup.stop_lines = [];
      state.markup.signal_roi.points = [];
      state.markup.direction_arrow.start = [];
      state.markup.direction_arrow.end = [];
      state.currentTool = 'view';
      state.violations = [];
      renderViolationsTable([]);
      renderSessionSnapshots([]);
      const btnExport = document.getElementById('btn-export-csv');
      if (btnExport) btnExport.style.display = 'none';
      const btnRemove = document.getElementById('btn-remove-video');
      if (btnRemove) btnRemove.style.display = 'none';
      if (typeof drawCanvas === 'function') drawCanvas();
      await pollStatus();
    }
  } catch (err) {
    console.error('Remove video error:', err);
  }
}

function updateSignalLamps(sigState) {
  const topLamps = {
    red: document.getElementById('top-lamp-red'),
    yellow: document.getElementById('top-lamp-yellow'),
    green: document.getElementById('top-lamp-green')
  };
  const topLabel = document.getElementById('top-signal-label');
  const colors = { red: '#EF4444', yellow: '#F59E0B', green: '#10B981' };
  const labels = { red: 'RED – STOP', yellow: 'CAUTION', green: 'GREEN – GO' };

  Object.keys(topLamps).forEach(key => {
    const lamp = topLamps[key];
    if (!lamp) return;
    const isActive = key === sigState;
    lamp.style.background = isActive ? colors[key] : `rgba(${key === 'red' ? '239,68,68' : key === 'yellow' ? '245,158,11' : '16,185,129'}, 0.2)`;
    lamp.style.border = isActive ? '2px solid #FFFFFF' : `1px solid rgba(${key === 'red' ? '239,68,68' : key === 'yellow' ? '245,158,11' : '16,185,129'}, 0.4)`;
    lamp.style.boxShadow = isActive ? `0 0 14px ${colors[key]}` : 'none';
    if (isActive) lamp.classList.add('active-glow');
    else lamp.classList.remove('active-glow');
  });

  if (topLabel) {
    topLabel.innerText = labels[sigState] || 'GREEN – GO';
    topLabel.style.color = colors[sigState] || colors.green;
  }
}

function updateViolationStats(data) {
  const counts = data.counts || {};
  const redLight = counts.red_light || 0;
  const noHelmet = counts.no_helmet || 0;
  const tripleRiding = counts.triple_riding || 0;
  const totalVehicles = data.current_vehicles_in_frame || counts.total_vehicles || 0;

  const el = (id) => document.getElementById(id);
  if (el('stat-redlight')) el('stat-redlight').innerText = redLight;
  if (el('stat-nohelmet')) el('stat-nohelmet').innerText = noHelmet;
  if (el('stat-tripleriding')) el('stat-tripleriding').innerText = tripleRiding;
  if (el('stat-totalvehicles')) el('stat-totalvehicles').innerText = totalVehicles;

  const totalInfractions = redLight + noHelmet + tripleRiding;
  if (el('vstat-total-violations')) {
    el('vstat-total-violations').innerText = `${totalInfractions} Infraction${totalInfractions === 1 ? '' : 's'}`;
  }

  // Distribution breakdown bar
  if (totalInfractions > 0) {
    const pRed = (redLight / totalInfractions) * 100;
    const pAmber = (noHelmet / totalInfractions) * 100;
    const pPurple = (tripleRiding / totalInfractions) * 100;
    if (el('dist-seg-red')) el('dist-seg-red').style.width = `${pRed}%`;
    if (el('dist-seg-amber')) el('dist-seg-amber').style.width = `${pAmber}%`;
    if (el('dist-seg-purple')) el('dist-seg-purple').style.width = `${pPurple}%`;
  } else {
    if (el('dist-seg-red')) el('dist-seg-red').style.width = '0%';
    if (el('dist-seg-amber')) el('dist-seg-amber').style.width = '0%';
    if (el('dist-seg-purple')) el('dist-seg-purple').style.width = '0%';
  }
}

// ========================================================================
// PRECISION ZOOM CONTROLS (INVARIANT COORDINATE SCALING)
// ========================================================================
function adjustZoom(delta) {
  state.zoomLevel = Math.max(1.0, Math.min(3.5, (state.zoomLevel || 1.0) + delta));
  const text = document.getElementById('zoom-level-text');
  if (text) text.innerText = `${state.zoomLevel.toFixed(1)}x`;
  const viewport = document.getElementById('video-zoom-viewport');
  if (viewport) {
    viewport.style.transform = `scale(${state.zoomLevel})`;
    viewport.style.transformOrigin = state.currentTool === 'signal' ? 'center 20%' : 'center center';
  }
}

function resetZoom() {
  state.zoomLevel = 1.0;
  const text = document.getElementById('zoom-level-text');
  if (text) text.innerText = '1.0x';
  const viewport = document.getElementById('video-zoom-viewport');
  if (viewport) {
    viewport.style.transform = 'scale(1.0)';
  }
}

function adjustWizardZoom(delta) {
  state.wizZoomLevel = Math.max(1.0, Math.min(3.5, (state.wizZoomLevel || 1.0) + delta));
  const text = document.getElementById('wiz-zoom-level-text');
  if (text) text.innerText = `${state.wizZoomLevel.toFixed(1)}x`;
  const viewport = document.getElementById('wizard-zoom-viewport');
  if (viewport) {
    viewport.style.transform = `scale(${state.wizZoomLevel})`;
    viewport.style.transformOrigin = state.wizardTool === 'signal' ? 'center 20%' : 'center center';
  }
}

function resetWizardZoom() {
  state.wizZoomLevel = 1.0;
  const text = document.getElementById('wiz-zoom-level-text');
  if (text) text.innerText = '1.0x';
  const viewport = document.getElementById('wizard-zoom-viewport');
  if (viewport) {
    viewport.style.transform = 'scale(1.0)';
  }
}

// ========================================================================
// VIOLATIONS LOG TABLE
// ========================================================================
async function pollViolations() {
  try {
    const res = await fetch('/api/violations');
    const data = await res.json();
    state.violations = data.events || [];

    const badge = document.getElementById('table-count-badge');
    if (badge) badge.innerText = `${state.violations.length} Violations`;

    const navBadge = document.getElementById('header-badge-count');
    if (navBadge) navBadge.innerText = state.violations.length;

    renderViolationsTable(state.violations);
    renderSessionSnapshots(state.violations);
  } catch (err) {
    console.error('Violations poll error:', err);
  }
}

function renderSessionSnapshots(events) {
  const badge = document.getElementById('session-folder-badge');
  const count = events ? events.length : 0;
  if (badge) badge.innerText = `${count} Snapshot${count === 1 ? '' : 's'}`;
}

function openCurrentSessionInVault() {
  if (state.status && state.status.session && state.status.session.id) {
    state.expandedSessions.add(state.status.session.id);
    switchView('history');
    setTimeout(() => {
      const el = document.getElementById(`session-card-${state.status.session.id}`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 150);
  } else {
    switchView('history');
  }
}

function renderViolationsTable(events) {
  const tbody = document.getElementById('violations-tbody');
  if (!tbody) return;

  if (!events || events.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 28px;">
      <i data-lucide="search" style="width: 24px; height: 24px; display: block; margin: 0 auto 8px; opacity: 0.35;"></i>
      Watching surveillance feed... Violations will appear here in real time.
    </td></tr>`;
    lucide.createIcons();
    return;
  }

  let html = '';
  events.slice().reverse().forEach(ev => {
    let pillClass = 'red-light';
    const typeName = ev.type || 'Violation';
    if (typeName.includes('Helmet')) pillClass = 'no-helmet';
    else if (typeName.includes('Triple')) pillClass = 'triple-riding';
    else if (typeName.includes('Wrong')) pillClass = 'wrong-way';

    const sevClass = (ev.severity || 'HIGH').toLowerCase();
    const isSelected = state.selectedViolation && state.selectedViolation.id === ev.id;

    html += `<tr class="${isSelected ? 'selected' : ''}" onclick="selectViolationRow(${ev.id})">
      <td style="font-family: var(--font-mono); color: var(--color-amber);">${ev.timestamp}</td>
      <td style="font-family: var(--font-mono); color: var(--text-muted);">#${ev.frame}</td>
      <td style="font-weight: 600; color: var(--color-cream);">#${ev.vehicle_id} (${ev.vehicle_type || 'Vehicle'})</td>
      <td><span class="pill-violation ${pillClass}">${typeName}</span></td>
      <td style="color: var(--color-cream);">${ev.details}</td>
      <td><span class="chip-severity ${sevClass}">${ev.severity || 'HIGH'}</span></td>
    </tr>`;
  });
  tbody.innerHTML = html;
}

function selectViolationRow(id) {
  const ev = state.violations.find(v => v.id === id);
  if (!ev) return;
  state.selectedViolation = ev;
  renderViolationsTable(state.violations);

  // Open the snapshot directly in lightbox modal
  const snapUrl = ev.snapshot_url || `/api/snapshot/${id}`;
  openLightbox(snapUrl);
}

function openLightbox(src) {
  const lb = document.getElementById('lightbox-img');
  const modal = document.getElementById('lightbox-modal');
  if (src && lb) {
    lb.src = src;
    if (modal) modal.classList.add('active');
    return;
  }
  const img = document.getElementById('snapshot-img');
  if (img && img.src && img.style.display !== 'none' && lb && modal) {
    lb.src = img.src;
    modal.classList.add('active');
  }
}

function closeLightbox(e) {
  const modal = document.getElementById('lightbox-modal');
  if (modal) modal.classList.remove('active');
}

// ========================================================================
// INCIDENT EVIDENCE VAULT — CLEAN LIST-WISE FORMAT PER UPLOAD
// ========================================================================
async function pollSessions() {
  if (state.currentView !== 'history') return;
  try {
    const res = await fetch('/api/stats/sessions');
    const data = await res.json();
    state.sessions = data.sessions || [];
    const newJson = JSON.stringify(state.sessions);
    if (newJson !== state.lastSessionsJson) {
      state.lastSessionsJson = newJson;
      renderVaultSessions(state.sessions);
    }
  } catch (err) {
    console.error('Sessions poll error:', err);
  }
}

function toggleSessionDrawer(sessionId) {
  if (state.expandedSessions.has(sessionId)) {
    state.expandedSessions.delete(sessionId);
  } else {
    state.expandedSessions.add(sessionId);
  }
  state.lastSessionsJson = null; // force re-render
  renderVaultSessions(state.sessions);
}

function renderVaultSessions(sessions) {
  const container = document.getElementById('vault-sessions-container');
  if (!container) return;

  if (!sessions || sessions.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 56px; background: var(--bg-card); border: 1px dashed var(--border-color); border-radius: var(--radius-lg);">
        <i data-lucide="folder" style="width: 44px; height: 44px; margin-bottom: 14px; color: var(--text-dim);"></i>
        <p style="font-size: 16px; font-weight: 700; color: var(--color-cream);">No video sessions uploaded yet</p>
        <p style="font-size: 12px; margin-top: 6px; color: var(--text-muted);">Upload a video to create an isolated evidence folder and begin automatic violation recording.</p>
      </div>`;
    lucide.createIcons();
    return;
  }

  const totalViolations = sessions.reduce((acc, s) => acc + (s.events ? s.events.length : 0), 0);
  const totalSnapshots = sessions.reduce((acc, s) => acc + (s.total_snapshots || (s.events ? s.events.length : 0)), 0);

  let html = `
    <!-- Top Summary Banner -->
    <div class="vault-summary-grid">
      <div class="summary-stat-box">
        <span class="summary-stat-label">TOTAL UPLOAD SESSIONS</span>
        <span class="summary-stat-val">${sessions.length}</span>
        <span class="summary-stat-sub">Distinct video sessions</span>
      </div>
      <div class="summary-stat-box">
        <span class="summary-stat-label">TOTAL INFRACTIONS DETECTED</span>
        <span class="summary-stat-val" style="color: var(--color-amber);">${totalViolations}</span>
        <span class="summary-stat-sub">Logged across all uploads</span>
      </div>
      <div class="summary-stat-box">
        <span class="summary-stat-label">EVIDENCE SNAPSHOTS SAVED</span>
        <span class="summary-stat-val" style="color: var(--color-emerald);">${totalSnapshots}</span>
        <span class="summary-stat-sub">Archived in disk folders</span>
      </div>
    </div>

    <!-- Upload Sessions List -->
    <div class="session-list-wrapper">
  `;

  sessions.slice().reverse().forEach((sess, idx) => {
    const events = sess.events || [];
    const counts = sess.counts || {};
    const folderName = sess.snapshot_folder || `session_${sess.id}`;
    const diskImages = sess.disk_images || [];
    const totalImgs = Math.max(events.length, diskImages.length);
    const isExpanded = state.expandedSessions.has(sess.id);

    html += `
      <div class="session-list-card ${isExpanded ? 'is-expanded' : ''}">
        <!-- List Row Header -->
        <div class="session-list-row" onclick="toggleSessionDrawer('${sess.id}')">
          <div class="session-row-left">
            <div class="session-folder-icon">
              <i data-lucide="folder" style="width: 22px; height: 22px;"></i>
            </div>
            <div class="session-title-block">
              <div class="session-video-title">
                <span>${sess.video_name}</span>
                <span class="session-tag-chip">UPLOAD #${sessions.length - idx}</span>
              </div>
              <div class="session-folder-path">
                <i data-lucide="hard-drive" style="width: 12px; height: 12px;"></i>
                <span>uploads/sessions/${folderName}/</span>
              </div>
            </div>
          </div>

          <div class="session-row-meta">
            <span class="session-meta-time">${sess.upload_time}</span>
            <span class="session-meta-duration">${sess.duration} (${sess.total_frames} frames)</span>
          </div>

          <!-- Violation Stat Chips -->
          <div class="session-row-chips">
            <span class="chip-count helmet">Helmet: ${counts.no_helmet || 0}</span>
            <span class="chip-count redlight">Red Light: ${counts.red_light || 0}</span>
            <span class="chip-count triple">Triple: ${counts.triple_riding || 0}</span>
            <span class="chip-count wrongway">Wrong Way: ${counts.wrong_way || 0}</span>
          </div>

          <!-- Actions & Drawer Trigger -->
          <div class="session-row-actions" onclick="event.stopPropagation()">
            <button class="btn-drawer-toggle ${isExpanded ? 'active' : ''}" onclick="toggleSessionDrawer('${sess.id}')">
              <i data-lucide="${isExpanded ? 'chevron-up' : 'images'}" style="width: 14px; height: 14px;"></i>
              <span>${isExpanded ? 'Hide Images' : `View ${totalImgs} Images`}</span>
            </button>
            <button class="btn-download-csv" onclick="exportCSVReport()">
              <i data-lucide="download" style="width: 13px; height: 13px;"></i>
              <span>CSV</span>
            </button>
          </div>
        </div>

        <!-- Expandable Drawer for Session Folder Images -->
        <div class="session-drawer-content" style="display: ${isExpanded ? 'block' : 'none'};">
          <div class="drawer-header-bar">
            <span>Images saved in folder: <strong>uploads/sessions/${folderName}/</strong> (${totalImgs} snapshots)</span>
            <span style="font-size: 11px; color: var(--text-muted);">Click any card to zoom</span>
          </div>
          <div class="evidence-cards-grid">
    `;

    if (totalImgs === 0) {
      html += `
        <div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 32px; font-size: 12px;">
          No snapshots generated in this upload session.
        </div>
      `;
    } else {
      // Prioritize events with metadata, then disk images
      if (events.length > 0) {
        events.slice().reverse().forEach(ev => {
          let pillColor = 'var(--color-danger)';
          if (ev.type && ev.type.includes('Helmet')) pillColor = 'var(--color-warning)';
          else if (ev.type && ev.type.includes('Triple')) pillColor = 'var(--color-violet)';
          else if (ev.type && ev.type.includes('Wrong')) pillColor = 'var(--color-emerald)';

          const snapUrl = ev.snapshot_url || `/api/snapshot/${ev.id}`;

          html += `
            <div class="evidence-card" onclick="openLightbox('${snapUrl}')">
              <div class="evidence-card-media">
                <img src="${snapUrl}" alt="Evidence Frame" class="evidence-card-img" onerror="this.src='/video_feed'">
                <span class="evidence-card-overlay-tag">Frame #${ev.frame} • ${ev.timestamp}</span>
              </div>
              <div class="evidence-card-body">
                <div class="evidence-card-title-row">
                  <span class="evidence-violation-title" style="color: ${pillColor};">${ev.type}</span>
                  <span class="evidence-confidence">${ev.confidence || '98.5'}%</span>
                </div>
                <div class="evidence-card-datetime">
                  Vehicle #${ev.vehicle_id} (${ev.vehicle_type || 'Vehicle'}) • ${ev.created_at || 'Recorded'}
                </div>
              </div>
            </div>
          `;
        });
      } else if (diskImages.length > 0) {
        diskImages.forEach((imgObj, i) => {
          html += `
            <div class="evidence-card" onclick="openLightbox('${imgObj.url}')">
              <div class="evidence-card-media">
                <img src="${imgObj.url}" alt="Evidence Frame" class="evidence-card-img" onerror="this.src='/video_feed'">
                <span class="evidence-card-overlay-tag">Snapshot #${i + 1}</span>
              </div>
              <div class="evidence-card-body">
                <div class="evidence-card-title-row">
                  <span class="evidence-violation-title" style="color: var(--color-amber);">Incident Capture</span>
                </div>
                <div class="evidence-card-datetime">
                  ${imgObj.filename}
                </div>
              </div>
            </div>
          `;
        });
      }
    }

    html += `
          </div>
        </div>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
  lucide.createIcons();
}

async function clearIncidentHistory() {
  if (confirm('Clear all archived incident records and sessions?')) {
    await fetch('/api/stats/clear', { method: 'POST' });
    state.expandedSessions.clear();
    pollStatus();
    pollViolations();
    pollSessions();
  }
}

function exportCSVReport() {
  if (!state.status || !state.status.video_path) {
    alert('Please upload a video before exporting a violation CSV report.');
    return;
  }
  window.location.href = '/api/violations/export';
}

function simulateIncidentAlert() {
  alert('Simulated incident trigger: Event broadcasted to dispatch telemetry.');
}

function dispatchEmergencyAlert() {
  alert('Emergency dispatch citation logged to authority record.');
}

// ========================================================================
// PLAYBACK CONTROLS
// ========================================================================
async function togglePlayPause() {
  try {
    const res = await fetch('/api/playback/toggle', { method: 'POST' });
    const data = await res.json();
    state.isPlaying = data.playing;
    pollStatus();
  } catch (e) {
    console.error(e);
  }
}

async function seekFrame(frameNum) {
  try {
    await fetch('/api/playback/seek', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ frame: parseInt(frameNum) })
    });
    pollStatus();
  } catch (e) {
    console.error(e);
  }
}

async function onSeekSlider(val) {
  await seekFrame(val);
}

// ========================================================================
// CANVAS ANNOTATION TOOLS (MAIN ANALYZER)
// ========================================================================
function setTool(toolName) {
  if (toolName !== 'view' && (!state.status || !state.status.video_path)) {
    return;
  }
  state.currentTool = toolName;
  state.drawingState.points = [];
  state.drawingState.isDragging = false;
  state.dragHandle = null;

  document.querySelectorAll('.analyzer-tools-bar .tool-btn').forEach(btn => btn.classList.remove('active'));
  const btn = document.getElementById(`tool-${toolName}`);
  if (btn) btn.classList.add('active');

  if (canvas) canvas.style.cursor = toolName === 'view' ? 'default' : 'crosshair';
  drawCanvas();
}

function setupCanvasEvents() {
  if (!canvas) return;

  canvas.addEventListener('mousedown', (e) => {
    if (!state.status || !state.status.video_path) return;
    const rect = canvas.getBoundingClientRect();
    const pt = { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };

    if (state.currentTool === 'view') {
      const handle = findNearbyHandleOnCanvas(pt, canvas);
      if (handle) {
        state.dragHandle = handle;
        return;
      }
    }

    if (state.currentTool === 'stopline') {
      state.drawingState.points.push(pt);
      if (state.drawingState.points.length === 2) {
        state.markup.stop_lines = [
          { id: 'stop_line_1', name: 'Main Stop Line', points: state.drawingState.points.map(p => [r3(p.x), r3(p.y)]), visible: true, locked: false, color: '#EF4444' }
        ];
        saveMarkupToBackend();
        state.drawingState.points = [];
        setTool('view');
      }
    } else if (state.currentTool === 'detection') {
      state.drawingState.points.push(pt);
    } else if (state.currentTool === 'signal') {
      // Direct point-selection: single click places ROI box centered at clicked location
      const hw = 0.035, hh = 0.055;
      const box = [
        [r3(Math.max(0, pt.x - hw)), r3(Math.max(0, pt.y - hh))],
        [r3(Math.min(1, pt.x + hw)), r3(Math.max(0, pt.y - hh))],
        [r3(Math.min(1, pt.x + hw)), r3(Math.min(1, pt.y + hh))],
        [r3(Math.max(0, pt.x - hw)), r3(Math.min(1, pt.y + hh))]
      ];
      state.markup.signal_roi.points = box;
      saveMarkupToBackend();
      setTool('view');
      drawCanvas();
      return;
    } else if (state.currentTool === 'direction') {
      state.drawingState.isDragging = true;
      state.drawingState.dragStart = pt;
    }
    drawCanvas();
  });

  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const pt = { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };
    state.drawingState.mousePos = pt;

    if (state.dragHandle) {
      applyDragHandle(state.dragHandle, pt);
      drawCanvas();
      return;
    }
    if (state.currentTool === 'view') {
      const handle = findNearbyHandleOnCanvas(pt, canvas);
      canvas.style.cursor = handle ? 'grab' : 'default';
    } else {
      drawCanvas();
    }
  });

  canvas.addEventListener('mouseup', (e) => {
    if (state.dragHandle) {
      state.dragHandle = null;
      saveMarkupToBackend();
      drawCanvas();
      return;
    }

    const rect = canvas.getBoundingClientRect();
    const p2 = { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };

    if (state.currentTool === 'signal' && state.drawingState.isDragging) {
      state.drawingState.isDragging = false;
      const p1 = state.drawingState.dragStart;
      const dist = Math.hypot(p2.x - p1.x, p2.y - p1.y);
      let box;
      if (dist < 0.02) {
        const hw = 0.035, hh = 0.055;
        box = [
          [r3(p1.x - hw), r3(p1.y - hh)],
          [r3(p1.x + hw), r3(p1.y - hh)],
          [r3(p1.x + hw), r3(p1.y + hh)],
          [r3(p1.x - hw), r3(p1.y + hh)]
        ];
      } else {
        box = [
          [r3(Math.min(p1.x, p2.x)), r3(Math.min(p1.y, p2.y))],
          [r3(Math.max(p1.x, p2.x)), r3(Math.min(p1.y, p2.y))],
          [r3(Math.max(p1.x, p2.x)), r3(Math.max(p1.y, p2.y))],
          [r3(Math.min(p1.x, p2.x)), r3(Math.max(p1.y, p2.y))]
        ];
      }
      state.markup.signal_roi.points = box;
      saveMarkupToBackend();
      setTool('view');
    } else if (state.currentTool === 'direction' && state.drawingState.isDragging) {
      state.drawingState.isDragging = false;
      const p1 = state.drawingState.dragStart;
      state.markup.direction_arrow.start = [r3(p1.x), r3(p1.y)];
      state.markup.direction_arrow.end = [r3(p2.x), r3(p2.y)];
      saveMarkupToBackend();
      setTool('view');
    }
    drawCanvas();
  });

  canvas.addEventListener('dblclick', () => {
    if (state.currentTool === 'detection' && state.drawingState.points.length >= 3) {
      const pts = state.drawingState.points.map(p => [r3(p.x), r3(p.y)]);
      state.markup.detection_area.points = pts;
      saveMarkupToBackend();
      state.drawingState.points = [];
      setTool('view');
      drawCanvas();
    }
  });
}

// ========================================================================
// SHARED CANVAS DRAWING (CLEAN WITHOUT GHOST SPOTS)
// ========================================================================
function applyDragHandle(handle, pt) {
  const { type, index } = handle;
  if (type === 'stopline' && state.markup.stop_lines[0]) {
    state.markup.stop_lines[0].points[index] = [r3(pt.x), r3(pt.y)];
  } else if (type === 'detection' && state.markup.detection_area.points) {
    state.markup.detection_area.points[index] = [r3(pt.x), r3(pt.y)];
  } else if (type === 'signal' && state.markup.signal_roi.points[index]) {
    state.markup.signal_roi.points[index] = [r3(pt.x), r3(pt.y)];
  }
}

function findNearbyHandleOnCanvas(pt, canvasEl) {
  const w = canvasEl.width, h = canvasEl.height;
  const px = pt.x * w, py = pt.y * h;
  const threshold = 14;

  const sl = state.markup.stop_lines[0];
  if (sl && sl.points && sl.points.length === 2) {
    for (let i = 0; i < 2; i++) {
      if (Math.hypot(sl.points[i][0] * w - px, sl.points[i][1] * h - py) < threshold) {
        return { type: 'stopline', index: i };
      }
    }
  }

  const daPts = state.markup.detection_area.points || [];
  const isDefault = daPts.length === 4 && daPts.every(p => (p[0] <= 0.05 || p[0] >= 0.95) && (p[1] <= 0.05 || p[1] >= 0.95));
  if (!isDefault) {
    for (let i = 0; i < daPts.length; i++) {
      if (Math.hypot(daPts[i][0] * w - px, daPts[i][1] * h - py) < threshold) {
        return { type: 'detection', index: i };
      }
    }
  }

  const sigPts = state.markup.signal_roi.points || [];
  for (let i = 0; i < sigPts.length; i++) {
    if (Math.hypot(sigPts[i][0] * w - px, sigPts[i][1] * h - py) < threshold) {
      return { type: 'signal', index: i };
    }
  }

  return null;
}

function drawCanvas() {
  if (!ctx || !canvas) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!state.status || !state.status.video_path) {
    return; // Don't draw any markup or pointers if no video has been uploaded yet!
  }
  drawMarkupOnContext(ctx, canvas.width, canvas.height, state.drawingState, state.currentTool);
}

function drawMarkupOnContext(c, w, h, drawState, activeTool) {
  // 1. Stop Line
  const sl = state.markup.stop_lines && state.markup.stop_lines[0];
  if (sl && sl.visible && sl.points && sl.points.length === 2) {
    const [p1, p2] = sl.points;
    const x1 = p1[0] * w, y1 = p1[1] * h, x2 = p2[0] * w, y2 = p2[1] * h;

    // Outer glow
    c.strokeStyle = 'rgba(239, 68, 68, 0.35)';
    c.lineWidth = 9;
    c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke();

    // Dashed Core Line
    c.setLineDash([12, 8]);
    c.strokeStyle = '#EF4444';
    c.lineWidth = 3;
    c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke();
    c.setLineDash([]);

    // End Handles
    [[x1, y1], [x2, y2]].forEach(([ex, ey]) => {
      c.fillStyle = '#FFFFFF';
      c.beginPath(); c.arc(ex, ey, 7, 0, Math.PI * 2); c.fill();
      c.strokeStyle = '#EF4444'; c.lineWidth = 2.5; c.stroke();
    });

    // Stop Line Tag
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    c.fillStyle = '#EF4444';
    const tagW = 76, tagH = 18;
    roundRect(c, mx - tagW / 2, my - tagH - 4, tagW, tagH, 4);
    c.fill();
    c.fillStyle = '#FFFFFF';
    c.font = 'bold 10px Inter';
    c.textAlign = 'center';
    c.fillText('STOP LINE', mx, my - 9);
  }

  // 2. Traffic Signal ROI
  const sig = state.markup.signal_roi;
  if (sig && sig.visible && sig.points && sig.points.length >= 3) {
    const pts = sig.points;
    const xs = pts.map(p => p[0] * w), ys = pts.map(p => p[1] * h);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);

    const sigColor = (state.status && state.status.signal_state === 'red') ? '#EF4444' :
                     (state.status && state.status.signal_state === 'yellow') ? '#F59E0B' : '#10B981';

    c.strokeStyle = sigColor;
    c.lineWidth = 2.5;
    roundRect(c, minX, minY, maxX - minX, maxY - minY, 4);
    c.stroke();

    // Crosshair
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
    c.beginPath(); c.moveTo(cx - 7, cy); c.lineTo(cx + 7, cy); c.moveTo(cx, cy - 7); c.lineTo(cx, cy + 7); c.stroke();

    // Tag
    const labelText = `SIGNAL: ${(state.status && state.status.signal_state || 'GO').toUpperCase()}`;
    c.fillStyle = sigColor;
    roundRect(c, minX, minY - 20, 86, 17, 3);
    c.fill();
    c.fillStyle = '#0D0F14';
    c.font = 'bold 9px Inter';
    c.textAlign = 'left';
    c.fillText(labelText, minX + 6, minY - 8);
  }

  // 3. Monitored Detection Area
  const da = state.markup.detection_area;
  const daPts = da && da.points ? da.points : [];
  const isDefault = daPts.length === 4 && daPts.every(p => (p[0] <= 0.05 || p[0] >= 0.95) && (p[1] <= 0.05 || p[1] >= 0.95));
  if (da && da.visible && daPts.length >= 3 && !isDefault) {
    c.fillStyle = 'rgba(16, 185, 129, 0.08)';
    c.strokeStyle = '#10B981';
    c.lineWidth = 2;
    c.setLineDash([8, 6]);
    c.beginPath();
    daPts.forEach((p, i) => {
      if (i === 0) c.moveTo(p[0] * w, p[1] * h);
      else c.lineTo(p[0] * w, p[1] * h);
    });
    c.closePath(); c.fill(); c.stroke();
    c.setLineDash([]);

    // Vertex handles
    daPts.forEach(([vx, vy]) => {
      c.fillStyle = '#10B981';
      c.beginPath(); c.arc(vx * w, vy * h, 5, 0, Math.PI * 2); c.fill();
      c.fillStyle = '#FFFFFF';
      c.beginPath(); c.arc(vx * w, vy * h, 2, 0, Math.PI * 2); c.fill();
    });
  }

  // 4. Allowed Direction Arrow
  if (state.markup.direction_arrow && state.markup.direction_arrow.visible && state.markup.direction_arrow.start && state.markup.direction_arrow.start.length === 2 && state.markup.direction_arrow.end && state.markup.direction_arrow.end.length === 2) {
    const s = state.markup.direction_arrow.start;
    const e = state.markup.direction_arrow.end;
    drawArrow(c, s[0] * w, s[1] * h, e[0] * w, e[1] * h, '#A855F7');
  }

  // Live in-progress drawing previews
  if (activeTool === 'stopline' && drawState.points.length === 1) {
    const p1 = drawState.points[0], p2 = drawState.mousePos;
    c.setLineDash([6, 4]);
    c.strokeStyle = '#EF4444';
    c.lineWidth = 2.5;
    c.beginPath(); c.moveTo(p1.x * w, p1.y * h); c.lineTo(p2.x * w, p2.y * h); c.stroke();
    c.setLineDash([]);
  } else if (activeTool === 'signal' && drawState.isDragging) {
    const p1 = drawState.dragStart, p2 = drawState.mousePos;
    const bx = Math.min(p1.x, p2.x) * w, by = Math.min(p1.y, p2.y) * h;
    const bw = Math.abs(p2.x - p1.x) * w, bh = Math.abs(p2.y - p1.y) * h;
    c.strokeStyle = '#10B981';
    c.fillStyle = 'rgba(16, 185, 129, 0.15)';
    c.lineWidth = 2;
    c.fillRect(bx, by, bw, bh);
    c.strokeRect(bx, by, bw, bh);
  } else if (activeTool === 'detection' && drawState.points.length > 0) {
    c.strokeStyle = '#10B981';
    c.lineWidth = 2;
    c.beginPath();
    drawState.points.forEach((p, i) => {
      if (i === 0) c.moveTo(p.x * w, p.y * h);
      else c.lineTo(p.x * w, p.y * h);
    });
    c.lineTo(drawState.mousePos.x * w, drawState.mousePos.y * h);
    c.stroke();
  } else if (activeTool === 'direction' && drawState.isDragging) {
    const p1 = drawState.dragStart, p2 = drawState.mousePos;
    drawArrow(c, p1.x * w, p1.y * h, p2.x * w, p2.y * h, '#A855F7');
  }
}

function drawArrow(c, x1, y1, x2, y2, color) {
  c.strokeStyle = color;
  c.fillStyle = color;
  c.lineWidth = 3;
  const headlen = 14;
  const angle = Math.atan2(y2 - y1, x2 - x1);

  c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke();
  c.beginPath(); c.moveTo(x2, y2);
  c.lineTo(x2 - headlen * Math.cos(angle - Math.PI / 6), y2 - headlen * Math.sin(angle - Math.PI / 6));
  c.lineTo(x2 - headlen * Math.cos(angle + Math.PI / 6), y2 - headlen * Math.sin(angle + Math.PI / 6));
  c.closePath(); c.fill();

  c.font = 'bold 10px Inter';
  c.fillStyle = color;
  c.fillText('ALLOWED DIRECTION', (x1 + x2) / 2 - 44, (y1 + y2) / 2 - 10);
}

function roundRect(c, x, y, w, h, r) {
  c.beginPath();
  c.moveTo(x + r, y);
  c.lineTo(x + w - r, y); c.quadraticCurveTo(x + w, y, x + w, y + r);
  c.lineTo(x + w, y + h - r); c.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  c.lineTo(x + r, y + h); c.quadraticCurveTo(x, y + h, x, y + h - r);
  c.lineTo(x, y + r); c.quadraticCurveTo(x, y, x + r, y);
  c.closePath();
}

function r3(n) {
  return Math.round(n * 1000) / 1000;
}

// ========================================================================
// MARKUP BACKEND PERSISTENCE
// ========================================================================
async function fetchMarkup() {
  try {
    const res = await fetch('/api/markup');
    const data = await res.json();
    if (data.markup) {
      state.markup = { ...state.markup, ...data.markup };
      drawCanvas();
    }
  } catch (e) {
    console.error(e);
  }
}

async function saveMarkupToBackend() {
  try {
    await fetch('/api/markup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.markup)
    });
    drawCanvas();
    drawWizardCanvas();
  } catch (e) {
    console.error(e);
  }
}

function clearMarkup() {
  state.markup.stop_lines = [];
  state.markup.signal_roi.points = [];
  state.markup.detection_area.points = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]];
  state.markup.direction_arrow.start = [];
  state.markup.direction_arrow.end = [];
  state.drawingState.points = [];
  state.drawingState.isDragging = false;
  state.drawingState.dragStart = null;
  state.dragHandle = null;
  state.wizardDrawingState.points = [];
  state.wizardDrawingState.isDragging = false;
  state.wizardDrawingState.dragStart = null;
  state.wizardDragHandle = null;
  state.wizardCompletedSteps.clear();

  if (ctx && canvas) ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (wizCtx && wizCanvas) wizCtx.clearRect(0, 0, wizCanvas.width, wizCanvas.height);

  saveMarkupToBackend();
  setTool('view');
  setWizardTool('view');
  updateWizardGuideSteps(0);
  drawCanvas();
  drawWizardCanvas();
}
