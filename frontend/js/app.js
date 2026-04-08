// frontend/js/app.js

let timers = [];
let presets = [];

// --- Initialization ---

window.addEventListener('pywebviewready', async () => {
    const state = await pywebview.api.get_state();
    presets = await pywebview.api.get_presets();
    timers = state.timers;

    renderTimerCards();
    updateWsStatus(state.ws_status);
    setupEventListeners();
});

// --- Rendering ---

function renderTimerCards() {
    const panel = document.getElementById('timer-panel');
    panel.innerHTML = '';

    timers.forEach((timer, i) => {
        const card = document.createElement('div');
        card.className = `timer-card state-${timer.state}`;
        card.id = `timer-card-${i}`;
        card.innerHTML = `
            <div class="card-header">
                <span class="timer-name">${escapeHtml(timer.name)}</span>
                <span class="timer-state ${timer.state}">${timer.state}</span>
            </div>
            <div class="timer-display" id="timer-display-${i}">${timer.formatted}</div>
            <div class="card-controls">
                <button class="btn btn-start" data-timer="${i}" data-action="start"
                    ${timer.state === 'running' || (presets[i] && presets[i].duration <= 0) ? 'disabled' : ''}
                    ${presets[i] && presets[i].duration <= 0 ? 'title="Set a duration > 0 to start"' : ''}>Start</button>
                <button class="btn btn-pause" data-timer="${i}" data-action="pause"
                    ${timer.state !== 'running' && timer.state !== 'paused' ? 'disabled' : ''}>
                    ${timer.state === 'paused' ? 'Resume' : 'Pause'}</button>
                <button class="btn btn-stop" data-timer="${i}" data-action="stop"
                    ${timer.state === 'idle' ? 'disabled' : ''}>Stop</button>
                <button class="btn btn-edit" data-timer="${i}" data-action="edit"
                    title="Edit preset">&#9881;</button>
            </div>
        `;
        panel.appendChild(card);
    });
}

function updateTimerCard(timer) {
    const card = document.getElementById(`timer-card-${timer.id}`);
    if (!card) return;

    // Update card class
    card.className = `timer-card state-${timer.state}`;

    // Update state badge
    const stateBadge = card.querySelector('.timer-state');
    stateBadge.className = `timer-state ${timer.state}`;
    stateBadge.textContent = timer.state;

    // Update name
    card.querySelector('.timer-name').textContent = timer.name;

    // Update display
    document.getElementById(`timer-display-${timer.id}`).textContent = timer.formatted;

    // Update buttons
    const startBtn = card.querySelector('[data-action="start"]');
    const pauseBtn = card.querySelector('[data-action="pause"]');
    const stopBtn = card.querySelector('[data-action="stop"]');

    const preset = presets[timer.id];
    startBtn.disabled = timer.state === 'running' || (preset && preset.duration <= 0);
    if (preset && preset.duration <= 0) {
        startBtn.title = 'Set a duration > 0 to start';
    } else {
        startBtn.removeAttribute('title');
    }
    pauseBtn.disabled = timer.state !== 'running' && timer.state !== 'paused';
    stopBtn.disabled = timer.state === 'idle';
    pauseBtn.textContent = timer.state === 'paused' ? 'Resume' : 'Pause';

    // Update local state
    timers[timer.id] = timer;
}

function updateWsStatus(status) {
    const indicator = document.getElementById('ws-indicator');
    const label = document.getElementById('ws-label');

    indicator.className = `ws-indicator ${status}`;

    const labels = {
        connected: 'Connected',
        disconnected: 'Disconnected',
        connecting: 'Connecting...',
        reconnecting: 'Reconnecting...',
        error: 'Connection Error',
    };
    label.textContent = labels[status] || status;
}

// --- Event Listeners ---

function setupEventListeners() {
    // Timer controls (event delegation)
    document.getElementById('timer-panel').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn || btn.disabled) return;

        const timerId = parseInt(btn.dataset.timer);
        const action = btn.dataset.action;

        if (action === 'start') pywebview.api.start_timer(timerId);
        else if (action === 'pause') pywebview.api.pause_timer(timerId);
        else if (action === 'stop') pywebview.api.stop_timer(timerId);
        else if (action === 'edit') openEditModal(timerId);
    });

    // Log viewer
    document.getElementById('btn-logs').addEventListener('click', openLogViewer);
    document.getElementById('btn-close-logs').addEventListener('click', closeLogViewer);
    document.getElementById('btn-refresh-logs').addEventListener('click', refreshLogs);
    document.getElementById('log-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeLogViewer();
    });

    // Edit modal
    document.getElementById('btn-close-edit').addEventListener('click', closeEditModal);
    document.getElementById('btn-cancel-edit').addEventListener('click', closeEditModal);
    document.getElementById('edit-form').addEventListener('submit', savePreset);
    document.getElementById('edit-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeEditModal();
    });

    // Keyboard: Escape closes modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeLogViewer();
            closeEditModal();
        }
    });
}

// --- Log Viewer ---

async function openLogViewer() {
    document.getElementById('log-modal').style.display = 'flex';
    await refreshLogs();
}

function closeLogViewer() {
    document.getElementById('log-modal').style.display = 'none';
}

async function refreshLogs() {
    const severity = document.getElementById('log-severity').value;
    const logs = await pywebview.api.get_logs(severity, 100);
    document.querySelector('#log-content pre').textContent = logs.join('');
}

// --- Edit Modal ---

function openEditModal(timerId) {
    const preset = presets[timerId];
    document.getElementById('edit-timer-id').value = timerId;
    document.getElementById('edit-name').value = preset.name;
    document.getElementById('edit-duration').value = preset.duration;
    document.getElementById('edit-end-message').value = preset.end_message || '';
    document.getElementById('edit-trigger-seconds').value = preset.trigger_seconds || '';
    document.getElementById('edit-trigger-action').value = preset.trigger_action || '';
    document.getElementById('edit-output-file').value = preset.output_file;
    document.getElementById('edit-modal').style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('edit-modal').style.display = 'none';
}

async function savePreset(e) {
    e.preventDefault();
    const timerId = parseInt(document.getElementById('edit-timer-id').value);
    const triggerSeconds = document.getElementById('edit-trigger-seconds').value;
    const triggerAction = document.getElementById('edit-trigger-action').value;

    const updates = {
        name: document.getElementById('edit-name').value,
        duration: parseInt(document.getElementById('edit-duration').value),
        end_message: document.getElementById('edit-end-message').value,
        trigger_seconds: triggerSeconds ? parseInt(triggerSeconds) : null,
        trigger_action: triggerAction || null,
        output_file: document.getElementById('edit-output-file').value,
    };

    await pywebview.api.update_preset(timerId, updates);
    presets[timerId] = { ...presets[timerId], ...updates };
    // Re-render so the Start button reflects the new duration
    const updatedState = await pywebview.api.get_state();
    timers = updatedState.timers;
    renderTimerCards();
    closeEditModal();
}

// --- Python Push Handlers ---

window.onTimerUpdate = function(timerState) {
    updateTimerCard(timerState);
};

window.onWsStatusUpdate = function(status) {
    updateWsStatus(status);
};

// --- Utils ---

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
