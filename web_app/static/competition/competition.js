// Learn Together — a real-time vocabulary competition. The host picks HSK + lessons
// + parts; every participant plays the shared vocab trainer flow (typing / listen
// match / reading match) via VocabTrainer, scored live with a final ranking.

let socket = null;
let currentRoom = null;
let currentSession = null;
let waitingUsers = new Set();
let groupedPassages = {};        // lesson -> [{ passage_id, lesson, part }]

document.addEventListener('DOMContentLoaded', () => {
    if (typeof io !== 'function') {
        showSetupError(t('competition.connect_failed'));
        return;
    }

    socket = io();
    bindSocketEvents();

    MultiSelect.init('create-lesson-ms', t('vocab.select_lesson_option'), onLessonChange);
    MultiSelect.init('create-part-ms', t('vocab.select_part_option'), () => {});

    document.getElementById('create-level')?.addEventListener('change', onLevelChange);
    document.getElementById('chat-input')?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') sendChat();
    });
    document.getElementById('join-room-code')?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') joinRoomFromInput();
    });
});

function bindSocketEvents() {
    socket.on('connect', () => showSetupError(''));
    socket.on('connect_error', () => {
        showSetupError(t('competition.server_connect_failed'));
    });

    socket.on('competition_error', payload => {
        alert(payload?.error || t('competition.error_fallback'));
    });

    socket.on('joined_room', payload => {
        currentRoom = payload.room;
        renderRoom(payload.room);
        showScreen('screen-lobby');
    });

    socket.on('room_state', payload => {
        if (!payload?.room) return;
        currentRoom = payload.room;
        renderRoom(payload.room);
    });

    socket.on('chat_message', message => {
        appendChat(message);
    });

    socket.on('session_started', async payload => {
        currentSession = payload.session;
        waitingUsers = new Set();
        document.getElementById('section-room-code').textContent = currentRoom?.room_code || '';
        document.getElementById('competition-action-bar').innerHTML = '';
        renderScoreList('live-scoreboard', currentSession.scores || []);
        showScreen('screen-section');
        await startTrainer();
    });

    socket.on('score_update', payload => {
        updateLiveScore(payload.scores || []);
        renderScoreList('live-scoreboard', payload.scores || []);
        renderScoreList('waiting-scores', payload.scores || []);
    });

    socket.on('participant_waiting', payload => {
        if (payload?.username) waitingUsers.add(payload.username);
        renderWaitingUsers();
    });

    socket.on('session_finished', payload => {
        renderRanking(payload.scores || payload.session?.scores || []);
        showScreen('screen-ranking');
    });

    socket.on('ranking_update', payload => {
        renderRanking(payload.scores || []);
    });

    socket.on('return_to_lobby', () => {
        showScreen('screen-lobby');
    });
}

function showScreen(id) {
    document.querySelectorAll('.competition-screen').forEach(screen => screen.classList.remove('active'));
    document.getElementById(id)?.classList.add('active');
}

// ── Setup: HSK -> lessons -> parts selection (mirrors the vocab picker) ──────────

async function onLevelChange() {
    const level = document.getElementById('create-level')?.value || '';
    MultiSelect.clear('create-lesson-ms');
    MultiSelect.clear('create-part-ms');
    groupedPassages = {};
    if (!level) return;

    showSetupError('');
    try {
        const res = await fetch(`/api/lesson/passages?hsk_level=HSK${encodeURIComponent(level)}`);
        const data = await res.json();
        (data.passages || []).forEach(passage => {
            const parts = String(passage.passage_id || '').split('_');
            const lesson = parts.length >= 2 ? parts[1] : 'Other';
            const part = parts.length >= 3 ? parts[2] : passage.passage_id;
            if (!groupedPassages[lesson]) groupedPassages[lesson] = [];
            groupedPassages[lesson].push({ ...passage, lesson, part });
        });

        const lessonOptions = Object.keys(groupedPassages).sort(numericSort).map(lesson => ({
            value: lesson,
            label: lesson === 'Other' ? t('vocab.other_label') : `${t('picker.lesson_prefix')} ${lesson}`,
        }));
        MultiSelect.setOptions('create-lesson-ms', lessonOptions);
        if (!lessonOptions.length) showSetupError(t('vocab.no_lessons_found'));
    } catch (e) {
        showSetupError(t('picker.failed_load_lessons'));
    }
}

function onLessonChange() {
    const selectedLessons = MultiSelect.values('create-lesson-ms');
    if (!selectedLessons.length) {
        MultiSelect.clear('create-part-ms');
        return;
    }

    // Each part option carries its full passage_id; group parts by lesson when several
    // lessons are selected so they stay distinguishable.
    const showGroups = selectedLessons.length > 1;
    const partOptions = [];
    selectedLessons.sort(numericSort).forEach(lesson => {
        const passages = groupedPassages[lesson];
        if (!passages || !passages.length) return;
        const groupLabel = lesson === 'Other' ? t('vocab.other_label') : `${t('picker.lesson_prefix')} ${lesson}`;
        [...passages].sort((a, b) => Number(a.part) - Number(b.part)).forEach(passage => {
            partOptions.push({
                value: passage.passage_id,
                label: `${t('picker.part_prefix')} ${passage.part}`,
                group: showGroups ? groupLabel : null,
            });
        });
    });
    MultiSelect.setOptions('create-part-ms', partOptions);
}

async function createRoom() {
    const level = document.getElementById('create-level')?.value;
    const passageIds = MultiSelect.values('create-part-ms');
    if (!level || !passageIds.length) {
        showSetupError(t('competition.select_hsk_lesson_part'));
        return;
    }
    showSetupError('');
    const body = {
        level: Number(level),
        passage_ids: passageIds,
        max_users: document.getElementById('create-max-users').value,
        section_timeout_minutes: document.getElementById('create-timeout').value
    };

    const res = await fetch('/api/competition/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) {
        showSetupError(data.error || t('competition.could_not_create_room'));
        return;
    }
    socket.emit('join_room', { room_code: data.room.room_code });
}

function joinRoomFromInput() {
    const code = document.getElementById('join-room-code').value.trim().toUpperCase();
    if (!code) return;
    socket.emit('join_room', { room_code: code });
}

function leaveRoom() {
    if (!currentRoom) return;
    socket.emit('leave_room', { room_code: currentRoom.room_code });
    currentRoom = null;
    currentSession = null;
    showScreen('screen-setup');
}

// ── Lobby ────────────────────────────────────────────────────────────────────────

function renderRoom(room) {
    document.getElementById('room-code-display').textContent = room.room_code;

    const passageIds = room.passage_ids || [];
    const lessonCount = new Set(passageIds.map(id => String(id).split('_')[1])).size;
    document.getElementById('room-summary').innerHTML = `
        <div><strong>HSK ${escapeHtml(room.level)}</strong></div>
        <div>${escapeHtml(t('competition.lessons_parts_count', { lessons: lessonCount, parts: passageIds.length }))}</div>
        <div>${escapeHtml(t('competition.words_count', { count: room.word_count || 0 }))}</div>
        <div>${escapeHtml(t('competition.users_count', { count: room.members?.length || 0, max: room.max_users }))}</div>
        <div>${escapeHtml(t('competition.time_limit_value', { n: room.section_timeout_minutes }))}</div>
    `;

    const members = document.getElementById('member-list');
    members.innerHTML = (room.members || []).map(member => `
        <div class="member-row">
            <strong>${escapeHtml(member.username)}</strong>
            <span class="member-role">${escapeHtml(member.role)}</span>
        </div>
    `).join('');

    const startBtn = document.getElementById('host-start-btn');
    const isHost = Number(room.host_user_id) === Number(window.currentUser.id);
    startBtn.style.display = isHost && room.status !== 'running' ? '' : 'none';

    const chat = document.getElementById('chat-list');
    chat.innerHTML = '';
    (room.chat || []).forEach(appendChat);
}

function appendChat(message) {
    const chat = document.getElementById('chat-list');
    if (!chat) return;
    const row = document.createElement('div');
    row.className = 'chat-message';
    row.innerHTML = `<strong>${escapeHtml(message.username || t('competition.user_fallback'))}</strong><span>${escapeHtml(message.message || '')}</span>`;
    chat.appendChild(row);
    chat.scrollTop = chat.scrollHeight;
}

function sendChat() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message || !currentRoom) return;
    socket.emit('chat_message', { room_code: currentRoom.room_code, message });
    input.value = '';
}

function startSession() {
    if (!currentRoom) return;
    socket.emit('host_start_session', { room_code: currentRoom.room_code });
}

// ── In-room trainer ──────────────────────────────────────────────────────────────

async function startTrainer() {
    const words = await resolveRoomWords();
    const container = document.getElementById('competition-trainer');
    if (!words.length) {
        container.innerHTML = `<div class="competition-empty">${escapeHtml(t('competition.no_words'))}</div>`;
        return;
    }
    VocabTrainer.start({
        container,
        words,
        autoAdvance: true,        // competition: no Check/Next buttons — flow automatically
        keyboardShortcuts: true,  // 1-5 pick source cards, y-u-i-o-p pick match cards
        onAnswer: emitVocabAnswer,
        onProgress: updateTrainerProgress,
        mountAction: mountCompetitionAction,
        onFinish: finishTrainer,
    });
}

async function resolveRoomWords() {
    try {
        const res = await fetch('/api/vocab/words', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ passage_ids: currentRoom?.passage_ids || [] })
        });
        const data = await res.json();
        return Array.isArray(data.words) ? data.words.filter(w => w && w.word) : [];
    } catch (e) {
        return [];
    }
}

function emitVocabAnswer(row, type, userAnswer, isCorrect, responseMs, wrongAttempts) {
    if (!currentRoom || !currentSession) return;
    socket.emit('vocab_answer', {
        room_code: currentRoom.room_code,
        session_id: currentSession.id,
        word: row.word,
        activity_type: type,
        is_correct: isCorrect,
        response_time_ms: responseMs,
        wrong_attempts: wrongAttempts || 0,
    });
}

function updateTrainerProgress({ groupIndex, totalGroups }) {
    const el = document.getElementById('competition-progress');
    if (el) el.textContent = t('vocab_trainer.group_counter', { current: groupIndex + 1, total: totalGroups });
}

function mountCompetitionAction(btn) {
    const bar = document.getElementById('competition-action-bar');
    if (!bar) return;
    bar.querySelectorAll('.bt-primary-action').forEach(el => el.remove());
    bar.appendChild(btn);
}

function finishTrainer() {
    if (currentRoom && currentSession) {
        socket.emit('participant_finished', { room_code: currentRoom.room_code, session_id: currentSession.id });
    }
    document.getElementById('waiting-title').textContent = t('competition.you_finished');
    renderWaitingUsers();
    showScreen('screen-waiting');
}

// ── Scores / ranking ─────────────────────────────────────────────────────────────

function updateLiveScore(scores) {
    const mine = scores.find(score => Number(score.user_id) === Number(window.currentUser.id));
    document.getElementById('live-score').textContent = t('competition.points', { n: mine?.total_points || 0 });
}

function renderScoreList(targetId, scores) {
    const target = document.getElementById(targetId);
    if (!target) return;
    target.innerHTML = (scores || []).map((score, index) => `
        <div class="ranking-row">
            <span class="ranking-rank">#${score.rank || index + 1}</span>
            <strong>${escapeHtml(score.username)}</strong>
            <span>${score.total_points || 0} pts</span>
        </div>
    `).join('');
}

function renderWaitingUsers() {
    const subtitle = document.getElementById('waiting-subtitle');
    if (!subtitle) return;
    subtitle.textContent = waitingUsers.size
        ? t('competition.finished_list', { names: Array.from(waitingUsers).join(', ') })
        : t('competition.waiting_others');
}

function renderRanking(scores) {
    renderScoreList('ranking-list', scores);
}

function returnToLobby() {
    if (!currentRoom) return;
    socket.emit('return_to_lobby', { room_code: currentRoom.room_code });
    showScreen('screen-lobby');
}

// ── Helpers ──────────────────────────────────────────────────────────────────────

function numericSort(a, b) {
    if (a === 'Other') return 1;
    if (b === 'Other') return -1;
    return Number(a) - Number(b) || String(a).localeCompare(String(b));
}

function showSetupError(message) {
    const error = document.getElementById('setup-error');
    if (!error) {
        if (message) alert(message);
        return;
    }
    error.textContent = message || '';
    error.hidden = !message;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Enter advances the current activity via its Check/Continue button (typing inputs
// manage their own Enter), matching the solo trainer's keyboard flow.
document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    if (!document.getElementById('screen-section')?.classList.contains('active')) return;
    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;
    const action = document.querySelector('#competition-action-bar .bt-primary-action:not([disabled])');
    if (action) { e.preventDefault(); action.click(); }
});
