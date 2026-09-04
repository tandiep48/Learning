// Learn Together — a real-time vocabulary competition. The host picks one or more HSK
// levels and then any mix of their lessons + parts (parts may span several levels);
// every participant plays the shared vocab trainer flow (typing / listen match /
// reading match) via VocabTrainer, scored live with a final ranking.

let socket = null;
let currentRoom = null;
let currentSession = null;
let waitingUsers = new Set();
let passagesByLevel = {};        // hsk level number -> [passage,...] (fetch cache)
let groupedPassages = {};        // lessonKey ("HSK1_2") -> [{ passage_id, hsk, level, lesson, part, lessonKey }]
let editing = false;             // host editing an existing room's settings in place

const HSK_LEVELS = [1, 2, 3, 4, 5, 6];

document.addEventListener('DOMContentLoaded', () => {
    if (typeof io !== 'function') {
        showSetupError(t('competition.connect_failed'));
        return;
    }

    socket = io();
    bindSocketEvents();

    MultiSelect.init('create-type-ms', t('competition.type_all'), () => {});
    MultiSelect.init('create-level-ms', t('vocab.select_hsk'), onLevelChange);
    MultiSelect.setOptions('create-level-ms', HSK_LEVELS.map(n => ({ value: String(n), label: `HSK ${n}` })));
    MultiSelect.init('create-lesson-ms', t('vocab.select_lesson_option'), onLessonChange);
    MultiSelect.init('create-part-ms', t('vocab.select_part_option'), () => {});

    document.getElementById('create-mode')?.addEventListener('change', onModeChange);
    onModeChange();
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

    socket.on('room_settings_saved', payload => {
        if (payload?.room) currentRoom = payload.room;
        exitEditMode();
        showScreen('screen-lobby');
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

// ── Setup: mode / type + HSK -> lessons -> parts selection ───────────────────────

// Maps each selectable vocab type onto the trainer's internal activity type.
const VOCAB_TYPE_TO_ACTIVITY = { typing: 'typing', listening: 'listen', reading: 'reading' };

// The Type selector offers a different skill set per mode: the vocab competition picks
// among typing/listening/reading; the lesson trainer picks among its four task types.
const TYPE_OPTIONS = {
    vocab: [
        { value: 'typing', key: 'competition.type_typing' },
        { value: 'listening', key: 'competition.type_listening' },
        { value: 'reading', key: 'competition.type_reading' },
    ],
    lesson: [
        { value: 'listening', key: 'competition.type_listening' },
        { value: 'meaning', key: 'competition.type_meaning' },
        { value: 'typing', key: 'competition.type_typing' },
        { value: 'reorder', key: 'competition.type_reorder' },
    ],
};

// Parse a stored activity_type ("all" or a CSV of type values) into a value array,
// expanding "all" to every option available for the mode.
function parseTypeValues(activityType, mode) {
    const all = TYPE_OPTIONS[mode].map(o => o.value);
    if (!activityType || activityType === 'all') return all;
    const wanted = new Set(String(activityType).split(',').map(s => s.trim()).filter(Boolean));
    const picked = all.filter(v => wanted.has(v));
    return picked.length ? picked : all;
}

// Resolve the room's vocab type selection into the trainer's internal activity types.
function vocabActivityTypes(activityType) {
    return parseTypeValues(activityType, 'vocab').map(v => VOCAB_TYPE_TO_ACTIVITY[v]);
}

// Repopulate the Type multi-select for the current mode; defaults to all selected so a
// room always has at least one type.
function onModeChange() {
    const mode = document.getElementById('create-mode')?.value || 'vocab';
    const options = TYPE_OPTIONS[mode].map(o => ({ value: o.value, label: t(o.key) }));
    MultiSelect.setOptions('create-type-ms', options);
    MultiSelect.setValues('create-type-ms', options.map(o => o.value));
}

// Parse a passage_id ("HSK1_2_2") into its pieces. `lessonKey` scopes a lesson to its
// HSK level ("HSK1_2") so lesson numbers never collide across levels.
function parsePassageId(passageId) {
    const parts = String(passageId || '').split('_');
    const hsk = parts[0] || '';
    const level = Number(String(hsk).replace(/\D/g, '')) || 0;
    const hasStructure = parts.length >= 2;
    return {
        passage_id: passageId,
        hsk,
        level,
        lesson: hasStructure ? parts[1] : 'Other',
        part: parts.length >= 3 ? parts[2] : passageId,
        lessonKey: hasStructure ? `${hsk}_${parts[1]}` : String(passageId),
    };
}

// Sort lessonKeys ("HSK1_2") by HSK level, then by lesson number.
function lessonKeySort(a, b) {
    const pa = String(a).split('_');
    const pb = String(b).split('_');
    const la = Number(pa[0].replace(/\D/g, '')) || 0;
    const lb = Number(pb[0].replace(/\D/g, '')) || 0;
    return la - lb || numericSort(pa[1], pb[1]);
}

// Load lessons/parts for every selected HSK level, accumulated so a host can mix parts
// across levels (e.g. HSK 1 Lesson 2 Part 2 + HSK 2 Lesson 1 Part 3). Prior lesson/part
// picks are preserved across level changes when they still exist.
async function onLevelChange() {
    const levels = MultiSelect.values('create-level-ms').map(Number).filter(Boolean);
    const prevLessons = MultiSelect.values('create-lesson-ms');
    const prevParts = MultiSelect.values('create-part-ms');

    if (!levels.length) {
        MultiSelect.clear('create-lesson-ms');
        MultiSelect.clear('create-part-ms');
        groupedPassages = {};
        return;
    }

    showSetupError('');
    try {
        await Promise.all(levels
            .filter(n => !passagesByLevel[n])
            .map(async n => {
                const res = await fetch(`/api/lesson/passages?hsk_level=HSK${encodeURIComponent(n)}`);
                const data = await res.json();
                passagesByLevel[n] = data.passages || [];
            }));

        // Rebuild from the currently-selected levels only, so deselecting a level drops
        // its lessons.
        groupedPassages = {};
        levels.forEach(n => {
            (passagesByLevel[n] || []).forEach(passage => {
                const info = parsePassageId(passage.passage_id);
                if (!groupedPassages[info.lessonKey]) groupedPassages[info.lessonKey] = [];
                groupedPassages[info.lessonKey].push({ ...passage, ...info });
            });
        });

        const showGroups = levels.length > 1;
        const lessonOptions = Object.keys(groupedPassages).sort(lessonKeySort).map(key => {
            const info = groupedPassages[key][0];
            return {
                value: key,
                label: info.lesson === 'Other' ? t('vocab.other_label') : `${t('picker.lesson_prefix')} ${info.lesson}`,
                group: showGroups ? `HSK ${info.level}` : null,
            };
        });
        MultiSelect.setOptions('create-lesson-ms', lessonOptions);
        if (!lessonOptions.length) {
            showSetupError(t('vocab.no_lessons_found'));
            return;
        }

        // Restore prior picks that survive the level change.
        MultiSelect.setValues('create-lesson-ms', prevLessons);
        onLessonChange();
        MultiSelect.setValues('create-part-ms', prevParts);
    } catch (e) {
        showSetupError(t('picker.failed_load_lessons'));
    }
}

function onLessonChange() {
    const selectedKeys = MultiSelect.values('create-lesson-ms');
    if (!selectedKeys.length) {
        MultiSelect.clear('create-part-ms');
        return;
    }

    // Each part option carries its full passage_id; group parts by HSK + lesson when
    // several lessons are selected so they stay distinguishable across levels.
    const showGroups = selectedKeys.length > 1;
    const partOptions = [];
    selectedKeys.sort(lessonKeySort).forEach(key => {
        const passages = groupedPassages[key];
        if (!passages || !passages.length) return;
        const info = passages[0];
        const groupLabel = info.lesson === 'Other'
            ? t('vocab.other_label')
            : `HSK ${info.level} · ${t('picker.lesson_prefix')} ${info.lesson}`;
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

// The primary setup button either creates a new room or, when the host is editing an
// existing one, saves the changes over the socket without leaving the room.
function submitRoom() {
    if (editing) saveRoomSettings();
    else createRoom();
}

// Read + validate the setup form into a room-settings payload (shared by create/edit).
// Returns null (and shows an error) when the required fields are missing.
function collectRoomBody() {
    const passageIds = MultiSelect.values('create-part-ms');
    if (!passageIds.length) {
        showSetupError(t('competition.select_hsk_lesson_part'));
        return null;
    }
    showSetupError('');
    const mode = document.getElementById('create-mode')?.value || 'vocab';
    // Send the selected types as a CSV; "all" (every option) is normalized server-side.
    const selectedTypes = MultiSelect.values('create-type-ms');
    // The parts can span multiple HSK levels; `level` is display metadata server-side, so
    // send the lowest level involved to keep the column meaningful and non-null.
    const levels = passageIds.map(id => parsePassageId(id).level).filter(Boolean);
    return {
        category: mode,
        activity_type: selectedTypes.length ? selectedTypes.join(',') : 'all',
        level: levels.length ? Math.min(...levels) : 1,
        passage_ids: passageIds,
        max_users: document.getElementById('create-max-users').value,
        section_timeout_minutes: document.getElementById('create-timeout').value
    };
}

async function createRoom() {
    const body = collectRoomBody();
    if (!body) return;

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

// ── Host: edit an existing room's settings in place ──────────────────────────────

// Reopen the setup form pre-filled with the current room, in edit mode. The host stays
// in the room the whole time; saving broadcasts the new settings to everyone.
async function editRoomSettings() {
    if (!currentRoom) return;
    editing = true;
    showSetupError('');

    document.getElementById('create-mode').value = currentRoom.category || 'vocab';
    onModeChange();
    MultiSelect.setValues('create-type-ms',
        parseTypeValues(currentRoom.activity_type, currentRoom.category || 'vocab'));
    document.getElementById('create-max-users').value = currentRoom.max_users || 8;
    document.getElementById('create-timeout').value = String(currentRoom.section_timeout_minutes || 15);

    // Rebuild lesson/part options for every HSK level the room's parts span, then
    // re-check the room's current picks.
    const passageIds = currentRoom.passage_ids || [];
    const infos = passageIds.map(parsePassageId);
    const levels = Array.from(new Set(infos.map(i => String(i.level)).filter(v => v !== '0')));
    MultiSelect.setValues('create-level-ms', levels);
    await onLevelChange();
    const lessonKeys = Array.from(new Set(infos.map(i => i.lessonKey)));
    MultiSelect.setValues('create-lesson-ms', lessonKeys);
    onLessonChange();
    MultiSelect.setValues('create-part-ms', passageIds);

    enterEditMode();
    showScreen('screen-setup');
}

function saveRoomSettings() {
    if (!currentRoom) return;
    const body = collectRoomBody();
    if (!body) return;
    socket.emit('host_edit_room', { room_code: currentRoom.room_code, ...body });
}

function cancelEdit() {
    exitEditMode();
    showScreen('screen-lobby');
}

// Swap the setup screen between "create a room" and "edit this room" affordances.
function enterEditMode() {
    editing = true;
    document.getElementById('create-submit-btn').textContent = t('competition.save_changes');
    document.getElementById('edit-cancel-btn').style.display = '';
    const joinPanel = document.getElementById('join-panel');
    if (joinPanel) joinPanel.style.display = 'none';
}

function exitEditMode() {
    editing = false;
    document.getElementById('create-submit-btn').textContent = t('competition.create_room');
    document.getElementById('edit-cancel-btn').style.display = 'none';
    const joinPanel = document.getElementById('join-panel');
    if (joinPanel) joinPanel.style.display = '';
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
    exitEditMode();
    showScreen('screen-setup');
}

// ── Lobby ────────────────────────────────────────────────────────────────────────

function renderRoom(room) {
    document.getElementById('room-code-display').textContent = room.room_code;

    const passageIds = room.passage_ids || [];
    const infos = passageIds.map(parsePassageId);
    const lessonCount = new Set(infos.map(i => i.lessonKey)).size;
    const hskLevels = Array.from(new Set(infos.map(i => i.level).filter(Boolean))).sort((a, b) => a - b);
    const hskLabel = hskLevels.length ? hskLevels.map(n => `HSK ${n}`).join(', ') : `HSK ${room.level}`;
    const isLesson = room.category === 'lesson';
    const countLine = isLesson
        ? t('competition.tasks_source_count', { count: room.word_count || 0 })
        : t('competition.words_count', { count: room.word_count || 0 });
    document.getElementById('room-summary').innerHTML = `
        <div><strong>${escapeHtml(hskLabel)}</strong></div>
        <div>${escapeHtml(modeSummaryLabel(room))}</div>
        <div>${escapeHtml(t('competition.lessons_parts_count', { lessons: lessonCount, parts: passageIds.length }))}</div>
        <div>${escapeHtml(countLine)}</div>
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

    const isHost = Number(room.host_user_id) === Number(window.currentUser.id);
    const canManage = isHost && room.status !== 'running';
    document.getElementById('host-start-btn').style.display = canManage ? '' : 'none';
    const editBtn = document.getElementById('host-edit-btn');
    if (editBtn) editBtn.style.display = canManage ? '' : 'none';

    const chat = document.getElementById('chat-list');
    chat.innerHTML = '';
    (room.chat || []).forEach(appendChat);
}

// "Vocabulary · Typing, Listening" / "Lesson · Typing" — the room's mode and its
// selected skill focus (all types collapse to the "All-rounder" label).
function modeSummaryLabel(room) {
    const mode = room.category === 'lesson' ? 'lesson' : 'vocab';
    const modeLabel = t(mode === 'lesson' ? 'competition.mode_lesson' : 'competition.mode_vocab');
    const at = room.activity_type || 'all';
    let typeLabel;
    if (at === 'all') {
        typeLabel = t('competition.type_all');
    } else {
        const byValue = Object.fromEntries(TYPE_OPTIONS[mode].map(o => [o.value, o.key]));
        typeLabel = String(at).split(',')
            .map(v => byValue[v.trim()] ? t(byValue[v.trim()]) : v.trim())
            .join(', ');
    }
    return `${modeLabel} · ${typeLabel}`;
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
    const container = document.getElementById('competition-trainer');
    if (currentRoom?.category === 'lesson') {
        startLessonTrainer(container);
        return;
    }

    const words = await resolveRoomWords();
    if (!words.length) {
        container.innerHTML = `<div class="competition-empty">${escapeHtml(t('competition.no_words'))}</div>`;
        return;
    }
    VocabTrainer.start({
        container,
        words,
        activityTypes: vocabActivityTypes(currentRoom?.activity_type),
        autoAdvance: true,        // competition: no Check/Next buttons — flow automatically
        keyboardShortcuts: true,  // 1-5 pick source cards, y-u-i-o-p pick match cards
        onAnswer: emitVocabAnswer,
        onProgress: updateTrainerProgress,
        mountAction: mountCompetitionAction,
        onFinish: finishTrainer,
    });
}

// Lesson mode plays the shared task set generated server-side at session start.
function startLessonTrainer(container) {
    const tasks = currentSession?.lesson_tasks || [];
    if (!tasks.length) {
        container.innerHTML = `<div class="competition-empty">${escapeHtml(t('competition.no_tasks'))}</div>`;
        return;
    }
    LessonTrainer.start({
        container,
        tasks,
        onAnswer: emitLessonAnswer,
        onProgress: updateLessonProgress,
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

function emitLessonAnswer(task, isCorrect, responseMs) {
    if (!currentRoom || !currentSession) return;
    socket.emit('lesson_answer', {
        room_code: currentRoom.room_code,
        session_id: currentSession.id,
        item_key: `${task.passage_id || ''}:${task.line_id != null ? task.line_id : ''}`,
        task_type: task.type,
        is_correct: isCorrect,
        response_time_ms: responseMs,
    });
}

function updateTrainerProgress({ groupIndex, totalGroups }) {
    const el = document.getElementById('competition-progress');
    if (el) el.textContent = t('vocab_trainer.group_counter', { current: groupIndex + 1, total: totalGroups });
}

function updateLessonProgress({ index, total }) {
    const el = document.getElementById('competition-progress');
    if (el) el.textContent = t('trainer.task_counter', { current: index + 1, total });
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
