let sessionData = null;
let currentTaskIndex = 0;
let missedTasks = [];
let taskStartTime = 0;
let currentReorderTokens = [];
let currentPassageId = null;
let lessonWideTrainingMeta = null;
let isLessonPartFlow = false;
let answerSubmitted = false;
let skipButtonMode = 'skip';

// Fetch passages on load
window.onload = async () => {
    const params = new URLSearchParams(window.location.search);
    isLessonPartFlow = params.get('flow') === 'lesson-part';

    Picker.init((passage) => {
        startSession(passage.passage_id);
    }, t('lesson.picker_title'), !params.get('passage_id'));

    const lessonWideLesson = readLessonWideLessonTrainer();
    if (lessonWideLesson?.passage_ids?.length) {
        lessonWideTrainingMeta = lessonWideLesson;
        startSession(lessonWideLesson.passage_ids[0], lessonWideLesson.passage_ids);
        return;
    }

    const autoPassage = params.get('passage_id');
    if (autoPassage) {
        startSession(autoPassage);
    }
};

function readLessonWideLessonTrainer() {
    const raw = sessionStorage.getItem('lessonWideLessonTrainer');
    if (!raw) return null;
    sessionStorage.removeItem('lessonWideLessonTrainer');
    try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed?.passage_ids) ? parsed : null;
    } catch (e) {
        return null;
    }
}


function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

function goHome() {
    if (lessonWideTrainingMeta?.passage_ids?.length) {
        window.location.href = lessonWidePickerUrl(lessonWideTrainingMeta);
        return;
    }
    if (currentPassageId) {
        const params = new URLSearchParams({
            passage_id: currentPassageId,
            flow: 'lesson-part',
            mode: 'lesson-learner'
        });
        window.location.href = `/reading?${params.toString()}`;
        return;
    }
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    Picker.showLevelPicker();
    sessionData = null;
    currentTaskIndex = 0;
    missedTasks = [];
    closeQuitModal();
}

function lessonWidePickerUrl(meta) {
    const passageId = meta?.passage_ids?.[0] || '';
    return passageId
        ? `/learning?passage_id=${encodeURIComponent(passageId)}&show_parts=true`
        : '/learning';
}

async function startSession(passage_id, passage_ids = null) {
    if (passage_id === 'H1_1_1') {
        window.location.href = '/lesson/basic-pinyin';
        return;
    } else if (passage_id === 'H1_1_2') {
        window.location.href = '/lesson/advanced-pinyin';
        return;
    } else if (passage_id === 'H1_5_99') {
        window.location.href = `/reading?passage_id=${encodeURIComponent(passage_id)}&mode=lesson-learner&flow=lesson-part`;
        return;
    }

    currentPassageId = passage_id;
    switchScreen('screen-loading');

    try {
        const bodyData = passage_ids?.length
            ? { passage_ids: passage_ids, mode: 'master' }
            : { passage_id: passage_id, mode: 'part' };
        const response = await fetch('/api/lesson/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bodyData)
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || t('lesson.failed_start_session'));
            goHome();
            return;
        }

        sessionData = data;
        currentTaskIndex = 0;
        missedTasks = [];
        answerSubmitted = false;

        loadTask();
    } catch (e) {
        alert(t('lesson.error_connecting'));
        goHome();
    }
}

function loadTask() {
    if (currentTaskIndex >= sessionData.tasks.length) {
        finishRound();
        return;
    }

    switchScreen('screen-training');

    const task = sessionData.tasks[currentTaskIndex];
    const total = sessionData.tasks.length;
    answerSubmitted = false;

    // Progress
    document.getElementById('progress-fill').style.width = `${(currentTaskIndex / total) * 100}%`;
    document.getElementById('task-counter').innerText = t('trainer.task_counter', { current: currentTaskIndex + 1, total });

    // Reset all areas
    document.getElementById('word-display').style.display = 'none';
    document.getElementById('audio-controls').style.display = 'none';
    document.getElementById('mc-area').style.display = 'none';
    document.getElementById('mc-area').innerHTML = '';
    document.getElementById('typing-area').style.display = 'none';
    document.getElementById('reorder-area').style.display = 'none';
    setSkipButtonMode('skip');
    updateTrainerSubtitle(task);

    const typingInput = document.getElementById('typing-input');
    typingInput.value = '';
    typingInput.disabled = false;
    typingInput.oninput = () => {
        const activeTask = sessionData?.tasks?.[currentTaskIndex];
        if (!activeTask || activeTask.type !== 'typing' || answerSubmitted) return;
        if (typingInput.value.trim() === activeTask.correct_answer) {
            submitTyping();
        }
    };

    const typingFeedback = document.getElementById('typing-feedback');
    typingFeedback.style.display = 'none';
    typingFeedback.innerHTML = '';

    const passagePinyin = document.getElementById('passage-pinyin');
    if (passagePinyin) {
        passagePinyin.style.display = 'none';
        passagePinyin.textContent = '';
    }

    const reorderFeedback = document.getElementById('reorder-feedback');
    reorderFeedback.style.display = 'none';

    // Instruction
    const instructionEl = document.getElementById('task-instruction');

    // Audio setup
    const audioEl = document.getElementById('audio-player');
    setCurrentAudioButtonPlaying(false);
    if (audioEl) audioEl.pause();
    if (task.audio_key) {
        let hskLevel = task.hsk_level || 'HSK1';
        if (!hskLevel.startsWith('HSK')) {
            hskLevel = 'HSK' + hskLevel.replace('H', '');
        }
        audioEl.src = `/lesson_audio/${hskLevel}/${task.audio_key}.mp3`;
    } else {
        audioEl.removeAttribute('src');
    }

    taskStartTime = Date.now();

    if (task.type === "listening" || task.type === "listen") {
        instructionEl.innerHTML = `<i class="fa-solid fa-headphones-simple" aria-hidden="true"></i><span>${escapeHtml(t('lesson.instruction_listen'))}</span>`;
        document.getElementById('audio-controls').style.display = 'block';
        if (task.audio_key) {
            playTrainerAudio(audioEl);
        }
        setupMultipleChoice(task);
    } else if (task.type === "meaning") {
        instructionEl.innerHTML = `<i class="fa-solid fa-book-open" aria-hidden="true"></i><span>${escapeHtml(t('lesson.instruction_meaning'))}</span>`;
        document.getElementById('word-display').innerText = task.content;
        document.getElementById('word-display').style.display = 'block';
        setupMultipleChoice(task);
    } else if (task.type === "typing") {
        instructionEl.innerHTML = `<i class="fa-solid fa-keyboard" aria-hidden="true"></i><span>${escapeHtml(t('lesson.instruction_typing'))}</span>`;
        document.getElementById('word-display').innerText = task.content;
        document.getElementById('word-display').style.display = 'block';
        document.getElementById('typing-area').style.display = 'flex';
        document.getElementById('typing-input').focus();
    } else if (task.type === "reorder") {
        instructionEl.innerHTML = `<i class="fa-solid fa-arrows-up-down-left-right" aria-hidden="true"></i><span>${escapeHtml(t('lesson.instruction_reorder'))}</span>`;
        setupReorder(task);
    }

    applyLessonHanText(task);
}

function applyLessonHanText(task) {
    const container = document.getElementById('screen-training');
    if (window.HanText && container) {
        window.HanText.apply(container, task?.hsk_level);
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
        btn.onclick = () => submitMC(opt, task, btn);
        mcArea.appendChild(btn);
    });
}

function setupReorder(task) {
    document.getElementById('reorder-area').style.display = 'block';
    const sourceContainer = document.getElementById('reorder-source');
    const targetContainer = document.getElementById('reorder-target');

    sourceContainer.innerHTML = '';
    targetContainer.innerHTML = '';
    currentReorderTokens = [];

    task.shuffled_tokens.forEach(token => {
        const chip = document.createElement('div');
        chip.className = 'chip lesson-reorder-chip';
        chip.innerText = token;
        chip.onclick = () => {
            if (answerSubmitted) return;
            if (chip.parentElement.id === 'reorder-source') {
                targetContainer.appendChild(chip);
                currentReorderTokens.push(token);
            } else {
                sourceContainer.appendChild(chip);
                const idx = currentReorderTokens.indexOf(token);
                if (idx > -1) currentReorderTokens.splice(idx, 1);
            }
            if (reorderMatches(currentReorderTokens, task.tokens)) {
                submitReorder();
            }
        };
        sourceContainer.appendChild(chip);
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

function setCurrentAudioButtonPlaying(playing) {
    const button = document.getElementById('btn-current-audio');
    const icon = button?.querySelector('.fa-solid');
    if (!button || !icon) return;
    icon.classList.toggle('fa-play', !playing);
    icon.classList.toggle('fa-stop', playing);
    icon.classList.toggle('play-icon', !playing);
    button.title = playing ? t('lesson.stop_audio') : t('lesson.play_audio');
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
        console.warn("Audio playback failed:", e);
    });
}

function playCurrentAudioToEnd() {
    const audioEl = document.getElementById('audio-player');
    if (!audioEl?.src) {
        return new Promise(resolve => setTimeout(resolve, 900));
    }

    return new Promise(resolve => {
        let finished = false;
        const fallbackMs = Number.isFinite(audioEl.duration) && audioEl.duration > 0
            ? Math.min(Math.max((audioEl.duration + 0.5) * 1000, 1500), 12000)
            : 5000;

        const finish = () => {
            if (finished) return;
            finished = true;
            audioEl.removeEventListener('ended', finish);
            audioEl.removeEventListener('error', finish);
            clearTimeout(fallbackTimer);
            resolve();
        };
        const fallbackTimer = setTimeout(finish, fallbackMs);

        audioEl.addEventListener('ended', finish, { once: true });
        audioEl.addEventListener('error', finish, { once: true });
        audioEl.currentTime = 0;
        audioEl.play().catch(e => {
            console.warn("Audio playback failed:", e);
            finish();
        });
    });
}

function submitTyping() {
    const input = document.getElementById('typing-input');
    const val = input.value.trim();
    if (!val) return;

    const task = sessionData.tasks[currentTaskIndex];
    checkAnswer(task, val, task.correct_answer, input);
}

function submitMC(selected, task, btnElement) {
    checkAnswer(task, selected, task.correct_answer, btnElement);
}

function submitReorder() {
    const task = sessionData.tasks[currentTaskIndex];
    const userSentence = currentReorderTokens.join('');
    checkAnswer(task, userSentence, task.correct_answer, null);
}

// Sole bottom-bar button. In "skip" mode it reveals the answer (scored as a fail);
// after revealing it morphs into "Next" so a second click advances the task.
function skipTask() {
    if (skipButtonMode === 'next') {
        nextTaskManual();
        return;
    }

    const task = sessionData?.tasks[currentTaskIndex];
    if (!task || answerSubmitted) return;
    answerSubmitted = true;

    task.user_answer = '';
    missedTasks.push(task);

    const gameInfo = { skipped: true };
    if (task.options) gameInfo.options = task.options;
    if (task.shuffled_tokens) gameInfo.tokens = task.shuffled_tokens;

    fetch('/api/lesson/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionData.session_id,
            passage_id: task.passage_id,
            line_id: task.line_id,
            type: task.type,
            user_answer: '',
            correct_answer: task.correct_answer,
            is_correct: false,
            response_time_ms: Date.now() - taskStartTime,
            game_info: gameInfo
        })
    }).catch(e => console.error("DB skip log failed", e));

    revealCorrectAnswer(task);
    setSkipButtonMode('next');
}

// Toggle the single bottom-bar button between "Skip" (attempt) and "Next" (advance).
function setSkipButtonMode(mode) {
    skipButtonMode = mode;
    const skipBtn = document.getElementById('btn-skip-task');
    if (!skipBtn) return;
    skipBtn.textContent = mode === 'next' ? t('lesson.next') : t('trainer.skip');
    skipBtn.style.display = '';
}

// Show a "HSK · Lesson N · Part M" heading so the learner knows the current part.
function updateTrainerSubtitle(task) {
    const el = document.getElementById('trainer-subtitle');
    if (!el) return;
    const parts = String(task?.passage_id || '').split('_');
    const lessonNum = parts.length >= 2 ? parts[1] : '';
    const partNum = parts.length >= 3 ? parts[2] : '';
    let hsk = task?.hsk_level || '';
    if (hsk && !String(hsk).startsWith('HSK')) hsk = 'HSK' + String(hsk).replace('H', '');
    const lessonLabel = lessonNum ? `${t('picker.lesson_prefix')} ${lessonNum}` : '';
    const partLabel = partNum ? `${t('picker.part_prefix')} ${partNum}` : '';
    el.textContent = [hsk, lessonLabel, partLabel].filter(Boolean).join(' · ');
}

// Reveal the correct answer and lock the task inputs (used by Skip and wrong answers).
function revealCorrectAnswer(task) {
    if (task.options) {
        const mcBtns = document.querySelectorAll('#mc-area .btn');
        mcBtns.forEach(btn => {
            const textContent = btn.querySelector('.mc-btn-inner')
                ? btn.querySelector('.mc-btn-inner').textContent.slice(1).trim()
                : btn.innerText.slice(1).trim();
            if (answersMatch(textContent, task.correct_answer)) {
                btn.style.backgroundColor = "var(--success)";
                btn.style.color = "white";
                btn.style.borderColor = "var(--success)";
            }
        });
    } else if (task.type === "reorder") {
        const reorderFeedback = document.getElementById('reorder-feedback');
        if (reorderFeedback) {
            reorderFeedback.innerHTML = `<span style="color:var(--text-muted); font-size:16px;">${t('lesson.correct_answer_label')}</span><br><span style="color:var(--success)">${task.correct_answer}</span>`;
            reorderFeedback.style.display = 'block';
        }
    }

    if (task.type === "typing") {
        showTypingPinyin(task);
    }

    applyLessonHanText(task);

    const allBtns = document.querySelectorAll('#screen-training .btn');
    allBtns.forEach(b => {
        if (!b.classList.contains('warning') && !b.classList.contains('secondary')) {
            b.disabled = true;
        }
    });
    const typingInput = document.getElementById('typing-input');
    if (typingInput) typingInput.disabled = true;
}

// The Chinese sentence is already shown for the learner to type, so after answering
// we only reveal its pinyin (below the passage) — no separate "correct answer".
function showTypingPinyin(task) {
    const el = document.getElementById('passage-pinyin');
    if (!el || task.type !== 'typing' || !task.pinyin) return;
    el.textContent = task.pinyin;
    el.style.display = 'block';
}

// Reorder/typing answers can mix full-width & half-width punctuation, ideographic
// punctuation (。、《》「」), and stray whitespace between tokens. Two answers that
// look identical can therefore differ byte-for-byte, so we normalize both sides
// before comparing: unify width via NFKC, fold CJK punctuation onto its ASCII
// equivalent, then drop every space / zero-width character.
const ANSWER_PUNCT_MAP = {
    '、': ',', '。': '.', '｡': '.',
    '【': '[', '】': ']', '《': '<', '》': '>',
    '「': '"', '」': '"', '『': '"', '』': '"',
    '“': '"', '”': '"', '‘': "'", '’': "'",
    '～': '~', '—': '-', '–': '-', '‧': '', '·': '', '・': ''
};

function normalizeAnswer(value) {
    if (value == null) return '';
    return String(value)
        .normalize('NFKC')
        .replace(/[、。｡【】《》「」『』“”‘’～—–‧·・]/g, ch => ANSWER_PUNCT_MAP[ch] ?? ch)
        .replace(/[\s\u200b\u200c\u200d\ufeff]/g, '');
}

function answersMatch(a, b) {
    return normalizeAnswer(a) === normalizeAnswer(b);
}

// Reorder answers were compared as one concatenated string, which is fragile for long
// sentences (a single normalized blob can mis-compare on multi-token / astral-plane
// characters). Compare token-by-token in order instead: same length, and each chip
// normalizes equal to the expected token at that position.
function reorderMatches(userTokens, correctTokens) {
    if (!Array.isArray(userTokens) || !Array.isArray(correctTokens)) return false;
    if (userTokens.length !== correctTokens.length) return false;
    return correctTokens.every((token, i) => normalizeAnswer(userTokens[i]) === normalizeAnswer(token));
}

async function checkAnswer(task, userAnswer, correctAnswer, element) {
    if (answerSubmitted) return;
    answerSubmitted = true;
    const responseTime = Date.now() - taskStartTime;
    const isCorrect = task.type === "reorder"
        ? reorderMatches(currentReorderTokens, task.tokens)
        : answersMatch(userAnswer, correctAnswer);

    if (element) {
        element.style.transition = "background-color 0.3s, color 0.3s";
        element.style.backgroundColor = isCorrect ? "var(--success)" : "var(--danger)";
        element.style.color = "white";
        element.style.borderColor = isCorrect ? "var(--success)" : "var(--danger)";
    }

    if (!isCorrect) {
        task.user_answer = userAnswer;
        missedTasks.push(task);
        if (task.options) {
            const mcBtns = document.querySelectorAll('#mc-area .btn');
            mcBtns.forEach(btn => {
                const textContent = btn.querySelector('.mc-btn-inner')
                    ? btn.querySelector('.mc-btn-inner').textContent.slice(1).trim()
                    : btn.innerText.slice(1).trim();
                if (answersMatch(textContent, correctAnswer)) {
                    btn.style.backgroundColor = "var(--success)";
                    btn.style.color = "white";
                    btn.style.borderColor = "var(--success)";
                }
            });
        } else if (task.type === "reorder") {
            const reorderFeedback = document.getElementById('reorder-feedback');
            if (reorderFeedback) {
                reorderFeedback.innerHTML = `<span style="color:var(--text-muted); font-size:16px;">${t('lesson.correct_answer_label')}</span><br><span style="color:var(--success)">${task.correct_answer}</span>`;
                reorderFeedback.style.display = 'block';
            }
        }
    }

    if (task.type === "typing") {
        showTypingPinyin(task);
    }

    applyLessonHanText(task);

    const allBtns = document.querySelectorAll('#screen-training .btn');
    allBtns.forEach(b => {
        if (!b.classList.contains('warning') && !b.classList.contains('secondary')) {
            b.disabled = true;
        }
    });
    const typingInput = document.getElementById('typing-input');
    if (typingInput) typingInput.disabled = true;

    const gameInfo = {};
    if (task.options) gameInfo.options = task.options;
    if (task.shuffled_tokens) gameInfo.tokens = task.shuffled_tokens;

    fetch('/api/lesson/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionData.session_id,
            passage_id: task.passage_id,
            line_id: task.line_id,
            type: task.type,
            user_answer: userAnswer,
            correct_answer: correctAnswer,
            is_correct: isCorrect,
            response_time_ms: responseTime,
            game_info: gameInfo
        })
    }).catch(e => console.error("DB Log failed", e));

    if (isCorrect) {
        const skipBtn = document.getElementById('btn-skip-task');
        if (skipBtn) skipBtn.style.display = 'none';
        if (task.type === "typing" || task.type === "reorder") {
            await playCurrentAudioToEnd();
            resetTaskUI(element, isCorrect, task);
            nextTask();
        } else {
            setTimeout(() => {
                resetTaskUI(element, isCorrect, task);
                nextTask();
            }, 3000);
        }
    } else {
        setSkipButtonMode('next');
    }
}

function resetTaskUI(element, isCorrect, task) {
    const allBtns = document.querySelectorAll('#screen-training .btn');
    allBtns.forEach(b => {
        b.disabled = false;
        b.style.backgroundColor = "";
        b.style.color = "";
        b.style.borderColor = "";
    });

    const typingInput = document.getElementById('typing-input');
    if (typingInput) {
        typingInput.disabled = false;
        typingInput.style.backgroundColor = "";
        typingInput.style.color = "";
        typingInput.style.borderColor = "";
    }
    setSkipButtonMode('skip');
}

function nextTaskManual() {
    const task = sessionData.tasks[currentTaskIndex];
    resetTaskUI(null, false, task);
    nextTask();
}

function nextTask() {
    currentTaskIndex++;
    loadTask();
}

// ── Finish & Success Popup ─────────────────────────────────────
function finishRound() {
    const total = sessionData.tasks.length;
    const missed = missedTasks.length;
    const correct = total - missed;
    const progressFill = document.getElementById('progress-fill');
    if (progressFill) progressFill.style.width = '100%';

    // Show the animated success popup
    SuccessPopup.show({
        total,
        correct,
        continueLabel: t('lesson.view_results'),
        onContinue: () => _showLessonCompleteScreen(),
        onRetry: missed > 0 ? () => retryMissed() : null,
        onHome: () => goHome(),
    });

    // Pre-build the complete screen in the background
    _buildLessonCompleteScreen();
}

function _buildLessonCompleteScreen() {
    document.querySelectorAll('.lesson-flow-continue').forEach(btn => {
        btn.style.display = isLessonPartFlow && currentPassageId ? 'inline-flex' : 'none';
    });

    // Save progress every finished round; the server only stores it at/above the
    // pass threshold and grants word mastery only on a perfect round.
    markLessonPartComplete();

    if (missedTasks.length > 0) {
        document.getElementById('recap-table-wrap').style.display = 'block';
        document.getElementById('training-complete-title').style.display = 'block';
        document.getElementById('recap-actions').style.display = 'flex';
        document.getElementById('perfect-area').style.display = 'none';

        const list = document.getElementById('recap-list');
        list.innerHTML = '';

        missedTasks.forEach(task => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${task.type}</strong></td>
                <td>${task.content || t('lesson.audio_fallback')}</td>
                <td style="color:var(--danger)">${task.user_answer}</td>
                <td style="color:var(--success); font-weight:bold;">${task.correct_answer}</td>
            `;
            list.appendChild(tr);
        });
    } else {
        document.getElementById('recap-table-wrap').style.display = 'none';
        document.getElementById('training-complete-title').style.display = 'none';
        document.getElementById('recap-actions').style.display = 'none';
        document.getElementById('perfect-area').style.display = 'block';
    }
}

function _showLessonCompleteScreen() {
    switchScreen('screen-complete');
}

function markLessonPartComplete() {
    // Master runs cover every part; a single-part run marks just its own passage.
    const isMaster = !!lessonWideTrainingMeta?.passage_ids?.length;
    const passageIds = isMaster
        ? lessonWideTrainingMeta.passage_ids
        : (currentPassageId ? [currentPassageId] : []);
    if (!passageIds.length) return;

    // Send the real score. Master records it as a % progress; part (child) runs
    // complete at the pass threshold. Word mastery is server-gated to perfect rounds.
    const total = sessionData?.tasks?.length || 0;
    const correct = Math.max(0, total - missedTasks.length);
    const mode = isMaster ? 'master' : 'part';
    Promise.all(passageIds.map(passageId => fetch('/api/lesson/part-complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ passage_id: passageId, total, correct, mode })
    }))).catch(e => console.error("Lesson part progress save failed", e));
}

async function continueAfterLessonTraining() {
    if (!currentPassageId) return;

    try {
        const response = await fetch(`/api/lesson/grammar/${encodeURIComponent(currentPassageId)}`);
        const data = await response.json();
        if (response.ok && data.grammar && data.grammar.length > 0) {
            window.location.href = `/grammar?passage_id=${encodeURIComponent(currentPassageId)}&flow=lesson-part`;
            return;
        }
    } catch (e) {
        console.warn("Grammar check failed", e);
    }

    const params = new URLSearchParams({
        passage_id: currentPassageId,
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
    currentTaskIndex = 0;
    missedTasks = [];

    loadTask();
}

document.addEventListener('keydown', function (e) {
    const trainingActive = document.getElementById('screen-training').classList.contains('active');
    if (!trainingActive) return;

    if (e.key === 'Enter') {
        if (document.getElementById('typing-area').style.display !== 'none') {
            const typingInput = document.getElementById('typing-input');
            if (!typingInput.disabled) {
                submitTyping();
            }
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

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function filterPassages() {
    const query = document.getElementById('search-input').value.toLowerCase();
    const sections = document.querySelectorAll('.passage-section');

    sections.forEach(section => {
        const cards = section.querySelectorAll('.dash-card');
        let hasVisible = false;
        cards.forEach(card => {
            const title = card.querySelector('.dash-title').innerText.toLowerCase();
            if (title.includes(query)) {
                card.style.display = 'flex';
                hasVisible = true;
            } else {
                card.style.display = 'none';
            }
        });

        if (hasVisible) {
            section.style.display = 'block';
        } else {
            section.style.display = 'none';
        }
    });
}

// --- Quit Confirmation Modal ---
function confirmQuit() {
    document.getElementById('quit-modal-overlay').classList.add('open');
}

function closeQuitModal() {
    document.getElementById('quit-modal-overlay').classList.remove('open');
}

function closeQuitModalIfBackground(event) {
    if (event.target === document.getElementById('quit-modal-overlay')) {
        closeQuitModal();
    }
}
