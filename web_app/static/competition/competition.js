let socket = null;
let currentRoom = null;
let currentSession = null;
let currentQuestions = [];
let currentQuestionIndex = 0;
let currentAnswer = "";
let questionStartMs = 0;
let waitingUsers = new Set();
let availableQuestionSets = [];

document.addEventListener('DOMContentLoaded', () => {
    if (typeof io !== 'function') {
        showSetupError('Could not load the live room connection. Refresh the page and try again.');
        return;
    }

    socket = io();
    bindSocketEvents();
    loadQuestionSets();

    document.getElementById('create-category')?.addEventListener('change', loadQuestionSets);
    document.getElementById('create-level')?.addEventListener('change', populateLessonOptions);
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
        showSetupError('Could not connect to the live room server. Restart the app and refresh this page.');
    });

    socket.on('competition_error', payload => {
        alert(payload?.error || 'Competition error');
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

    socket.on('section_started', payload => {
        currentSession = payload.session;
        currentQuestions = currentSession.questions || [];
        currentQuestionIndex = 0;
        waitingUsers = new Set();
        renderQuestion();
        showScreen('screen-section');
    });

    socket.on('answer_result', payload => {
        const feedback = document.getElementById('answer-feedback');
        if (!feedback) return;
        if (payload.error) {
            feedback.textContent = payload.error;
            feedback.className = 'answer-feedback wrong';
        } else {
            feedback.textContent = payload.is_correct
                ? `Correct +${payload.points} points`
                : 'Wrong +0 points';
            feedback.className = `answer-feedback ${payload.is_correct ? 'correct' : 'wrong'}`;
            document.getElementById('submit-answer-btn').style.display = 'none';
            document.getElementById('next-question-btn').style.display = '';
        }
    });

    socket.on('score_update', payload => {
        updateLiveScore(payload.scores || []);
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

async function loadQuestionSets() {
    const category = document.getElementById('create-category')?.value || 'practice';
    const levelSelect = document.getElementById('create-level');
    const lessonSelect = document.getElementById('create-lesson');
    if (!levelSelect || !lessonSelect) return;
    availableQuestionSets = [];
    showSetupError('');
    levelSelect.disabled = true;
    levelSelect.innerHTML = '<option value="">Loading...</option>';
    lessonSelect.disabled = true;
    lessonSelect.innerHTML = '<option value="">Select Lesson</option>';

    try {
        const res = await fetch(`/api/competition/question-sets?category=${encodeURIComponent(category)}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to load question sets');
        availableQuestionSets = data.sets || [];
        const levels = [...new Set(availableQuestionSets.map(set => String(set.level)))].sort(numericSort);
        levelSelect.innerHTML = '<option value="">Select HSK</option>';
        levels.forEach(level => {
            const option = document.createElement('option');
            option.value = level;
            option.textContent = `HSK ${level}`;
            levelSelect.appendChild(option);
        });
        levelSelect.disabled = levels.length === 0;
        if (!levels.length) {
            levelSelect.innerHTML = '<option value="">No HSK sets found</option>';
        }
    } catch (e) {
        levelSelect.innerHTML = '<option value="">Failed to load</option>';
        showSetupError(e.message);
    }
}

function populateLessonOptions() {
    const level = document.getElementById('create-level')?.value || '';
    const lessonSelect = document.getElementById('create-lesson');
    if (!lessonSelect) return;

    lessonSelect.innerHTML = '<option value="">Select Lesson</option>';
    const lessons = availableQuestionSets
        .filter(set => String(set.level) === level)
        .sort((a, b) => numericSort(a.lesson, b.lesson));

    lessons.forEach(set => {
        const option = document.createElement('option');
        option.value = String(set.lesson);
        option.textContent = `Lesson ${set.lesson} (${set.listening_count} listening, ${set.reading_count} reading)`;
        lessonSelect.appendChild(option);
    });
    lessonSelect.disabled = lessons.length === 0;
}

async function createRoom() {
    const category = document.getElementById('create-category')?.value || 'practice';
    const level = document.getElementById('create-level')?.value;
    const lesson = document.getElementById('create-lesson')?.value;
    if (!level || !lesson) {
        showSetupError('Select an HSK level and lesson first.');
        return;
    }
    showSetupError('');
    const body = {
        category,
        level,
        lesson,
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
        alert(data.error || 'Could not create room');
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

function renderRoom(room) {
    document.getElementById('room-code-display').textContent = room.room_code;
    document.getElementById('room-summary').innerHTML = `
        <div><strong>${escapeHtml(room.category === 'exam' ? 'Exam' : 'Exercise')}</strong></div>
        <div>HSK ${escapeHtml(room.level)} - Lesson ${escapeHtml(room.lesson)}</div>
        <div>${escapeHtml(room.members?.length || 0)} / ${escapeHtml(room.max_users)} users</div>
        <div>Timer: ${escapeHtml(room.section_timeout_minutes)} minutes per section</div>
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
    row.innerHTML = `<strong>${escapeHtml(message.username || 'User')}</strong><span>${escapeHtml(message.message || '')}</span>`;
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

function renderQuestion() {
    const question = currentQuestions[currentQuestionIndex];
    if (!question) {
        finishSection();
        return;
    }
    currentAnswer = "";
    questionStartMs = Date.now();

    document.getElementById('section-label').textContent = titleCase(currentSession.current_section);
    document.getElementById('question-counter').textContent = `${currentQuestionIndex + 1} / ${currentQuestions.length}`;
    document.getElementById('submit-answer-btn').style.display = '';
    document.getElementById('submit-answer-btn').disabled = false;
    document.getElementById('next-question-btn').style.display = 'none';

    const card = document.getElementById('competition-question-card');
    const audioKeys = parseAudioKeys(question.audio_key);
    const options = parseOptions(question.options);
    const image = question.image || '';

    let html = '';
    if (audioKeys.length) {
        html += `<button class="btn secondary" onclick="playCompetitionAudio('${escapeAttr(audioKeys[0])}')">Play Audio</button>`;
    }
    if (question.content) {
        html += `<div class="competition-content">${escapeHtml(question.content)}</div>`;
    }
    if (question.question && !isImageFilename(question.question)) {
        html += `<div class="competition-question-text">${escapeHtml(question.question)}</div>`;
    }
    if (image) {
        html += `<img class="competition-image" src="${imageUrl(question.level, image, question.category)}" alt="">`;
    }

    const optionEntries = Object.entries(options);
    if (optionEntries.length) {
        html += '<div class="competition-option-list">';
        optionEntries.forEach(([key, value]) => {
            const label = isImageFilename(String(value))
                ? `<img class="competition-image" src="${imageUrl(question.level, value, question.category)}" alt="">`
                : escapeHtml(String(value));
            html += `
                <label class="competition-option">
                    <input type="radio" name="competition-answer" value="${escapeAttr(key)}" onchange="currentAnswer=this.value">
                    <span>${label}</span>
                </label>
            `;
        });
        html += '</div>';
    } else {
        html += '<input class="competition-text-answer" id="competition-text-answer" type="text" placeholder="Type your answer" autocomplete="off">';
    }
    html += '<div id="answer-feedback" class="answer-feedback"></div>';
    card.innerHTML = html;

    const textInput = document.getElementById('competition-text-answer');
    if (textInput) {
        textInput.addEventListener('input', () => {
            currentAnswer = textInput.value;
        });
        textInput.addEventListener('keydown', event => {
            if (event.key === 'Enter') submitAnswer();
        });
        textInput.focus();
    }
}

function submitAnswer() {
    const question = currentQuestions[currentQuestionIndex];
    if (!question || !currentSession || !currentAnswer.trim()) return;
    document.getElementById('submit-answer-btn').disabled = true;
    socket.emit('answer_submitted', {
        room_code: currentRoom.room_code,
        session_id: currentSession.id,
        session_question_id: question.session_question_id,
        user_answer: currentAnswer.trim(),
        response_time_ms: Date.now() - questionStartMs
    });
}

function nextQuestion() {
    currentQuestionIndex += 1;
    renderQuestion();
}

function finishSection() {
    socket.emit('section_finished', {
        room_code: currentRoom.room_code,
        session_id: currentSession.id,
        section: currentSession.current_section
    });
    document.getElementById('waiting-title').textContent = `${titleCase(currentSession.current_section)} Complete`;
    document.getElementById('waiting-subtitle').textContent = 'Waiting for the next section.';
    renderScoreList('waiting-scores', currentSession.scores || []);
    showScreen('screen-waiting');
}

function updateLiveScore(scores) {
    const mine = scores.find(score => Number(score.user_id) === Number(window.currentUser.id));
    document.getElementById('live-score').textContent = `${mine?.total_points || 0} pts`;
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
    const suffix = waitingUsers.size ? ` Finished: ${Array.from(waitingUsers).join(', ')}` : '';
    document.getElementById('waiting-subtitle').textContent = `Waiting for the next section.${suffix}`;
}

function renderRanking(scores) {
    renderScoreList('ranking-list', scores);
}

function returnToLobby() {
    if (!currentRoom) return;
    socket.emit('return_to_lobby', { room_code: currentRoom.room_code });
    showScreen('screen-lobby');
}

function playCompetitionAudio(key) {
    const audio = document.getElementById('competition-audio');
    audio.src = `/practice_audio/${currentQuestions[currentQuestionIndex].level}/${key}.mp3?category=${currentQuestions[currentQuestionIndex].category || 'practice'}`;
    audio.play().catch(() => {});
}

function parseOptions(raw) {
    if (!raw) return {};
    if (typeof raw === 'object') return raw;
    try {
        const parsed = JSON.parse(raw);
        return typeof parsed === 'object' && parsed ? parsed : {};
    } catch (e) {
        return {};
    }
}

function parseAudioKeys(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    if (typeof raw !== 'string') return [];
    const text = raw.trim();
    if (!text) return [];
    if (text.startsWith('[')) {
        try {
            const parsed = JSON.parse(text);
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [text];
        }
    }
    return [text];
}

function imageUrl(level, filename, category) {
    return `/practice_image/${level}/${filename}?category=${category || 'practice'}`;
}

function isImageFilename(value) {
    return typeof value === 'string' && /\.(jpg|jpeg|png|gif|webp)$/i.test(value.trim());
}

function progressLabel(progress) {
    if (!progress) return 'Questions';
    const text = String(progress);
    if (text.includes('-')) {
        const [a, b] = text.split('-');
        return `Questions ${a}-${b}`;
    }
    return `Question ${text}`;
}

function numericSort(a, b) {
    return Number(a) - Number(b) || String(a).localeCompare(String(b));
}

function showSetupError(message) {
    const error = document.getElementById('setup-error');
    if (!error) {
        alert(message);
        return;
    }
    error.textContent = message || '';
    error.hidden = !message;
}

function titleCase(value) {
    const text = String(value || '');
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, '&#096;');
}
