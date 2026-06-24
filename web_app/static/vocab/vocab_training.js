let sessionData = null;
let currentTaskIndex = 0;
let missedTasks = [];
let taskStartTime = 0;
let currentTrainingPassageId = null;
let isLessonPartFlow = false;

// ── Speaking state ───────────────────────────────────────────────────────────
let speakingRecorder = null;
let speakingStream = null;
let speakingChunks = [];
let speakingTimer = null;
let speakingAttemptId = 0;
const SPEAKING_MAX_MS = 10000;

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    isLessonPartFlow = params.get('flow') === 'lesson-part';

    const trainerWords = readSelectedTrainerWords();
    if (trainerWords.length) {
        startSession('7', { words: trainerWords });
        return;
    }

    if (params.get('mode') === '6' && params.get('passage_id')) {
        const passageId = params.get('passage_id');
        startSession('6', { passage_id: passageId });
        return;
    }

    window.location.href = '/vocab';
});

function setCurrentAudioButtonPlaying(playing) {
    const button = document.getElementById('btn-current-audio');
    const icon = button?.querySelector('.fa-solid');
    if (!button || !icon) return;
    icon.classList.toggle('fa-play', !playing);
    icon.classList.toggle('fa-pause', playing);
    icon.classList.toggle('play-icon', !playing);
    button.title = playing ? 'Pause audio' : 'Play audio';
    button.setAttribute('aria-label', button.title);
}

function wireCurrentAudioEvents(audioEl) {
    if (!audioEl) return;
    audioEl.onended = () => setCurrentAudioButtonPlaying(false);
    audioEl.onerror = () => setCurrentAudioButtonPlaying(false);
    audioEl.onpause = () => setCurrentAudioButtonPlaying(false);
    audioEl.onplay = () => setCurrentAudioButtonPlaying(true);
}

function playTrainerAudio(audioEl) {
    if (!audioEl?.src) return;
    wireCurrentAudioEvents(audioEl);
    audioEl.play().catch(e => {
        setCurrentAudioButtonPlaying(false);
        console.warn('Audio playback failed:', e);
    });
}

function readSelectedTrainerWords() {
    const raw = sessionStorage.getItem('selectedVocabTrainerWords');
    if (!raw) return [];
    sessionStorage.removeItem('selectedVocabTrainerWords');
    try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
    } catch (e) {
        return [];
    }
}

function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    if (screenId) document.getElementById(screenId)?.classList.add('active');
}

function goHome() {
    resetSpeakingTask(true);
    if (currentTrainingPassageId) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(currentTrainingPassageId)}`;
        return;
    }
    closeQuitModal();
    window.location.href = '/vocab';
}

async function startSession(mode, extraParams = {}) {
    currentTrainingPassageId = mode === "6" && extraParams.passage_id ? extraParams.passage_id : null;
    sessionData = null;
    currentTaskIndex = 0;
    missedTasks = [];
    switchScreen('screen-loading');

    const bodyData = { mode };
    if (mode === "6") bodyData.passage_id = extraParams.passage_id;
    if (mode === "7") bodyData.words = extraParams.words || [];

    try {
        const response = await fetch('/api/vocab/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bodyData)
        });
        const data = await response.json();

        if (!response.ok) {
            alert(data.error || 'Failed to start session.');
            goHome();
            return;
        }

        sessionData = data;
        currentTaskIndex = 0;
        missedTasks = [];
        loadTask();
    } catch (e) {
        alert('Error connecting to server.');
        goHome();
    }
}

function loadTask() {
    if (currentTaskIndex >= sessionData.tasks.length) {
        finishRound();
        return;
    }

    // Reset speaking state between tasks
    resetSpeakingTask(false);

    switchScreen('screen-training');
    const task = sessionData.tasks[currentTaskIndex];
    const total = sessionData.tasks.length;

    document.getElementById('progress-fill').style.width = `${(currentTaskIndex / total) * 100}%`;
    document.getElementById('task-counter').innerText = `Task ${currentTaskIndex + 1}/${total}`;
    document.getElementById('word-display').style.display = 'none';
    document.getElementById('audio-controls').style.display = 'none';
    document.getElementById('mc-area').style.display = 'none';
    document.getElementById('typing-area').style.display = 'none';
    document.getElementById('speaking-area').style.display = 'none';
    document.getElementById('typing-input').value = '';
    const typingSubmitBtn = document.getElementById('typing-submit-btn');
    if (typingSubmitBtn) typingSubmitBtn.style.display = 'none';

    const mcFeedback = document.getElementById('mc-feedback');
    if (mcFeedback) { mcFeedback.style.display = 'none'; mcFeedback.innerHTML = ''; }
    const typingFeedback = document.getElementById('typing-feedback');
    if (typingFeedback) { typingFeedback.style.display = 'none'; typingFeedback.innerHTML = ''; }

    // Show/hide skip button (always visible during training)
    const skipBtn = document.getElementById('btn-skip-task');
    if (skipBtn) skipBtn.style.display = '';

    const instructionEl = document.getElementById('task-instruction');
    const audioEl = document.getElementById('audio-player');
    setCurrentAudioButtonPlaying(false);
    if (audioEl) audioEl.pause();
    if (task.audio_key) audioEl.src = `/audio/${task.audio_key}.mp3`;
    else audioEl.removeAttribute('src');

    taskStartTime = Date.now();

    if (task.type === "listen") {
        instructionEl.innerText = 'Listen to the audio and choose the correct meaning:';
        document.getElementById('audio-controls').style.display = 'block';
        if (task.audio_key) playTrainerAudio(audioEl);
        setupMultipleChoice(task);
    } else if (task.type === "typing") {
        instructionEl.innerText = 'Type the following word:';
        document.getElementById('word-display').innerText = task.word;
        document.getElementById('word-display').style.display = 'block';
        document.getElementById('typing-area').style.display = 'flex';
        if (typingSubmitBtn) typingSubmitBtn.style.display = 'inline-flex';
        document.getElementById('typing-input').focus();
    } else if (task.type === "meaning") {
        instructionEl.innerText = 'What is the meaning of this word?';
        document.getElementById('word-display').innerText = task.word;
        document.getElementById('word-display').style.display = 'block';
        setupMultipleChoice(task);
    } else if (task.type === "speaking") {
        instructionEl.innerText = 'Read and pronounce this word:';
        document.getElementById('speaking-prompt').textContent = task.word || '';
        document.getElementById('speaking-word-reveal').style.display = 'none';
        document.getElementById('speaking-reveal-hanzi').textContent = '';
        document.getElementById('speaking-reveal-pinyin').textContent = '';
        setSpeakingTaskStatus('');
        document.getElementById('speaking-area').style.display = 'flex';
    }
}

function setupMultipleChoice(task) {
    const mcArea = document.getElementById('mc-area');
    mcArea.innerHTML = '';
    mcArea.style.display = 'grid';

    task.options.forEach((opt, idx) => {
        const btn = document.createElement('button');
        btn.className = 'btn';
        btn.dataset.optionIndex = idx;
        btn.innerHTML = `<span class="mc-btn-inner"><span class="key-hint">${idx + 1}</span>${escapeHtml(opt)}</span>`;
        btn.addEventListener('click', () => submitMC(opt, task, btn));
        mcArea.appendChild(btn);
    });
}

function playCurrentAudio() {
    const audioEl = document.getElementById('audio-player');
    if (!audioEl.src) return;
    if (!audioEl.paused) {
        audioEl.pause();
        setCurrentAudioButtonPlaying(false);
        return;
    }
    audioEl.currentTime = 0;
    playTrainerAudio(audioEl);
}

function submitTyping() {
    const input = document.getElementById('typing-input').value.trim();
    if (!input) return;
    const task = sessionData.tasks[currentTaskIndex];
    checkAnswer(task, input, task.word, document.getElementById('typing-submit-btn'));
}

function submitMC(selected, task, btnElement) {
    checkAnswer(task, selected, task.meaning_vn, btnElement);
}

async function checkAnswer(task, userAnswer, correctAnswer, element) {
    const responseTime = Date.now() - taskStartTime;
    const isCorrect = userAnswer === correctAnswer;

    if (element) {
        element.style.transition = 'background-color 0.3s, color 0.3s';
        element.style.backgroundColor = isCorrect ? 'var(--success)' : 'var(--danger)';
        element.style.color = 'white';
        element.style.borderColor = isCorrect ? 'var(--success)' : 'var(--danger)';
    }

    renderFeedback(task, isCorrect);
    if (!isCorrect) markMissed(task, correctAnswer);

    if (task.audio_key) {
        const audioEl = document.getElementById('audio-player');
        if (audioEl.src) {
            audioEl.currentTime = 0;
            playTrainerAudio(audioEl);
        }
    }

    const allBtns = document.querySelectorAll('#screen-training .btn');
    allBtns.forEach(b => b.disabled = true);
    const typingInput = document.getElementById('typing-input');
    if (typingInput) typingInput.disabled = true;

    // Hide skip while answering
    const skipBtn = document.getElementById('btn-skip-task');
    if (skipBtn) skipBtn.style.display = 'none';

    const gameInfo = { pinyin: task.pinyin, meaning_en: task.meaning_en };
    if (task.options) gameInfo.options = task.options;
    fetch('/api/vocab/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionData.session_id,
            type: task.type,
            word: task.word,
            round_num: sessionData.is_retry ? 2 : 1,
            user_answer: userAnswer,
            is_correct: isCorrect,
            response_time_ms: responseTime,
            game_info: gameInfo
        })
    }).catch(e => console.error('DB Log failed', e));

    setTimeout(() => {
        allBtns.forEach(b => b.disabled = false);
        if (typingInput) typingInput.disabled = false;
        if (element) {
            element.style.backgroundColor = '';
            element.style.color = '';
            element.style.borderColor = '';
        }
        nextTask();
    }, 3000);
}

function renderFeedback(task, isCorrect) {
    const targetId = task.type === "typing" ? 'typing-feedback' : 'mc-feedback';
    const fb = document.getElementById(targetId);
    if (!fb) return;
    let html = `<span style="color:var(--primary); font-weight:bold;">${escapeHtml(task.pinyin)}</span><br><span style="color:var(--text-muted)">${escapeHtml(task.meaning_vn)}</span>`;
    if (task.type === "listen") {
        html = `<span style="color:white; font-size:24px; font-weight:bold;">${escapeHtml(task.word)}</span><br>` + html;
    }
    if (task.type === "typing" && !isCorrect) {
        html += `<br><span style="color:var(--danger); font-size:16px;">Correct Answer: ${escapeHtml(task.word)}</span>`;
    }
    fb.innerHTML = html;
    fb.style.display = 'block';
}

function markMissed(task, correctAnswer) {
    missedTasks.push(task);
    if (!task.options) return;
    document.querySelectorAll('#mc-area .btn').forEach(btn => {
        const textContent = btn.querySelector('.mc-btn-inner')
            ? btn.querySelector('.mc-btn-inner').textContent.slice(1).trim()
            : btn.innerText.slice(1).trim();
        if (textContent === correctAnswer) {
            btn.style.backgroundColor = 'var(--success)';
            btn.style.color = 'white';
            btn.style.borderColor = 'var(--success)';
        }
    });
}

function nextTask() {
    currentTaskIndex++;
    loadTask();
}

// ── Skip ─────────────────────────────────────────────────────────────────────

function skipTask() {
    const task = sessionData?.tasks[currentTaskIndex];
    if (!task) return;

    const responseTime = Date.now() - taskStartTime;

    // Always log skip as is_correct=false to vocab_records
    fetch('/api/vocab/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionData.session_id,
            type: task.type,
            word: task.word,
            round_num: sessionData.is_retry ? 2 : 1,
            user_answer: '',
            is_correct: false,
            response_time_ms: responseTime,
            game_info: { pinyin: task.pinyin, meaning_en: task.meaning_en, skipped: true }
        })
    }).catch(e => console.error('DB skip log failed', e));

    // Mark as missed for non-speaking tasks (they show in retry list)
    if (task.type !== 'speaking') {
        missedTasks.push(task);
    }

    // Reset speaking state if we're skipping mid-recording
    if (task.type === 'speaking') {
        resetSpeakingTask(true);
    }

    nextTask();
}

// ── Speaking Task ─────────────────────────────────────────────────────────────

function getSupportedMimeType() {
    const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg'];
    return types.find(t => MediaRecorder.isTypeSupported(t)) || '';
}

function setSpeakingTaskStatus(msg, isError = false) {
    const el = document.getElementById('speaking-task-status');
    if (!el) return;
    el.textContent = msg;
    el.style.color = isError ? 'var(--danger)' : 'var(--text-muted)';
}

function setSpeakTaskBtnState(state) {
    const btn = document.getElementById('btn-speak-task');
    const label = document.getElementById('speak-task-label');
    if (!btn || !label) return;
    btn.classList.toggle('recording', state === 'recording');
    btn.disabled = (state === 'scoring');
    if (state === 'recording') {
        label.textContent = 'Stop';
    } else if (state === 'scoring') {
        label.textContent = 'Scoring...';
    } else {
        label.textContent = 'Speak';
    }
}

async function toggleSpeakingTask() {
    if (speakingRecorder && speakingRecorder.state === 'recording') {
        stopSpeakingTask();
        return;
    }
    await startSpeakingTask();
}

async function startSpeakingTask() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        setSpeakingTaskStatus('Your browser does not support audio recording.', true);
        return;
    }

    speakingAttemptId++;
    speakingChunks = [];
    setSpeakingTaskStatus('Recording... say the word clearly.');
    setSpeakTaskBtnState('recording');

    try {
        speakingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mimeType = getSupportedMimeType();
        speakingRecorder = mimeType
            ? new MediaRecorder(speakingStream, { mimeType })
            : new MediaRecorder(speakingStream);

        speakingRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) speakingChunks.push(e.data);
        };

        const capturedAttemptId = speakingAttemptId;
        const capturedMime = mimeType;
        speakingRecorder.onstop = () => submitSpeakingTask(capturedAttemptId, capturedMime);

        speakingRecorder.start();
        speakingTimer = setTimeout(stopSpeakingTask, SPEAKING_MAX_MS);
    } catch (e) {
        console.error(e);
        resetSpeakingTask(false);
        setSpeakingTaskStatus('Microphone access denied. Please allow microphone and try again.', true);
    }
}

function stopSpeakingTask() {
    if (speakingTimer) { clearTimeout(speakingTimer); speakingTimer = null; }
    if (speakingRecorder && speakingRecorder.state === 'recording') {
        setSpeakTaskBtnState('scoring');
        setSpeakingTaskStatus('Processing...');
        speakingRecorder.stop();
    }
    if (speakingStream) {
        speakingStream.getTracks().forEach(t => t.stop());
        speakingStream = null;
    }
}

async function submitSpeakingTask(attemptId, mimeType) {
    if (attemptId !== speakingAttemptId) return;
    if (!speakingChunks.length) {
        setSpeakTaskBtnState('idle');
        setSpeakingTaskStatus('No audio was recorded. Please try again.', true);
        return;
    }

    const task = sessionData.tasks[currentTaskIndex];
    const responseTime = Date.now() - taskStartTime;
    const blobType = mimeType || speakingChunks[0]?.type || 'audio/webm';
    const extension = blobType.includes('ogg') ? 'ogg' : 'webm';
    const blob = new Blob(speakingChunks, { type: blobType });
    const formData = new FormData();
    formData.append('word', task.word);
    formData.append('audio', blob, `speaking-${Date.now()}.${extension}`);

    try {
        const response = await fetch('/api/vocab/speaking/score', { method: 'POST', body: formData });
        const data = await response.json();

        if (attemptId !== speakingAttemptId) return;
        setSpeakTaskBtnState('idle');

        const isCorrect = !response.ok ? false : (data.is_correct || false);

        // Log result to vocab_records
        fetch('/api/vocab/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionData.session_id,
                type: 'speaking',
                word: task.word,
                round_num: sessionData.is_retry ? 2 : 1,
                user_answer: data.recognized_text || '',
                is_correct: isCorrect,
                response_time_ms: responseTime,
                game_info: { pinyin: task.pinyin, score: data.score }
            })
        }).catch(e => console.error('DB speaking log failed', e));

        // Reveal Hanzi + pinyin regardless of result
        revealSpeakingWord(task, isCorrect, data);

    } catch (e) {
        console.error(e);
        if (attemptId !== speakingAttemptId) return;
        setSpeakTaskBtnState('idle');
        setSpeakingTaskStatus('Could not score recording. Please try again.', true);
    }
}

function revealSpeakingWord(task, isCorrect, data) {
    // Show pinyin + meaning (Hanzi is already visible as the prompt)
    document.getElementById('speaking-reveal-hanzi').textContent = task.pinyin || '';
    document.getElementById('speaking-reveal-pinyin').textContent = task.meaning_vn || task.meaning_en || '';
    document.getElementById('speaking-word-reveal').style.display = 'flex';

    const statusMsg = isCorrect ? '✓ Great pronunciation!' : '✗ Try again next time';
    setSpeakingTaskStatus(statusMsg, !isCorrect);

    // Hide speak button
    const speakBtn = document.getElementById('btn-speak-task');
    if (speakBtn) speakBtn.style.display = 'none';

    // Hide skip button
    const skipBtn = document.getElementById('btn-skip-task');
    if (skipBtn) skipBtn.style.display = 'none';

    // Play audio
    const audioEl = document.getElementById('audio-player');
    if (task.audio_key && audioEl.src) {
        audioEl.currentTime = 0;
        playTrainerAudio(audioEl);
    }

    // Auto-advance after 2.5s
    setTimeout(() => {
        if (speakBtn) speakBtn.style.display = '';
        nextTask();
    }, 2500);
}

function resetSpeakingTask(stopActive) {
    speakingAttemptId++;
    if (speakingTimer) { clearTimeout(speakingTimer); speakingTimer = null; }
    if (stopActive && speakingRecorder && speakingRecorder.state === 'recording') {
        speakingRecorder.onstop = null;
        speakingRecorder.stop();
    }
    if (speakingStream) {
        speakingStream.getTracks().forEach(t => t.stop());
        speakingStream = null;
    }
    speakingRecorder = null;
    speakingChunks = [];
    setSpeakTaskBtnState('idle');
}

// ── Finish & Success Popup ─────────────────────────────────────────────────
function finishRound() {
    const total   = sessionData.tasks.length;
    const missed  = missedTasks.length;
    const correct = total - missed;

    SuccessPopup.show({
        total,
        correct,
        continueLabel: 'View Results',
        onContinue: () => _showCompleteScreen(),
        onRetry: missed > 0 ? () => retryMissed() : null,
        onHome:  () => goHome(),
    });
}

function _showCompleteScreen() {
    switchScreen('screen-complete');
    const tableBody    = document.getElementById('recap-table-body');
    const retryBtn     = document.getElementById('btn-retry');
    const startLessonBtn = document.getElementById('btn-start-lesson');
    const emptyState   = document.getElementById('perfect-area');
    tableBody.innerHTML = '';

    if (startLessonBtn) {
        startLessonBtn.style.display = isLessonPartFlow && currentTrainingPassageId ? 'inline-flex' : 'none';
    }

    if (missedTasks.length > 0) {
        emptyState.style.display = 'none';
        retryBtn.style.display = 'inline-flex';
        const uniqueMissed = [...new Set(missedTasks.map(t => t.word))];
        uniqueMissed.forEach(wordStr => {
            const t = missedTasks.find(x => x.word === wordStr);
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="complete-word">${escapeHtml(t.word)}</td>
                <td>${escapeHtml(t.pinyin)}</td>
                <td>${escapeHtml(t.meaning_vn)}</td>
            `;
            tableBody.appendChild(row);
        });
    } else {
        emptyState.style.display = 'block';
        retryBtn.style.display = 'none';
    }
}

function startLearnLesson() {
    if (!currentTrainingPassageId) return;
    const params = new URLSearchParams({
        passage_id: currentTrainingPassageId,
        flow: 'lesson-part',
        mode: 'lesson-learner'
    });
    window.location.href = `/reading?${params.toString()}`;
}

function retryMissed() {
    for (let i = missedTasks.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [missedTasks[i], missedTasks[j]] = [missedTasks[j], missedTasks[i]];
    }
    sessionData.tasks = [...missedTasks];
    sessionData.is_retry = true;
    currentTaskIndex = 0;
    missedTasks = [];
    loadTask();
}

function confirmQuit() {
    document.getElementById('quit-modal-overlay').classList.add('open');
}

function closeQuitModal() {
    document.getElementById('quit-modal-overlay').classList.remove('open');
}

function closeQuitModalIfBackground(event) {
    if (event.target === document.getElementById('quit-modal-overlay')) closeQuitModal();
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

document.addEventListener('keydown', function (e) {
    const trainingActive = document.getElementById('screen-training').classList.contains('active');
    if (!trainingActive) return;

    if (e.key === 'Enter') {
        if (document.getElementById('typing-area').style.display !== 'none') {
            const typingInput = document.getElementById('typing-input');
            if (!typingInput.disabled) submitTyping();
        }
        return;
    }

    const keyMap = { '1': 0, '2': 1, '3': 2, '4': 3 };
    if (e.key in keyMap) {
        const mcArea = document.getElementById('mc-area');
        if (mcArea.style.display === 'none') return;
        const btns = mcArea.querySelectorAll('.btn');
        const idx = keyMap[e.key];
        if (idx < btns.length && !btns[idx].disabled) btns[idx].click();
    }
});
