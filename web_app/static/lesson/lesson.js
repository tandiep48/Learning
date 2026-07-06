let sessionData = null;
let currentTaskIndex = 0;
let missedTasks = [];
let taskStartTime = 0;
let currentReorderTokens = [];
let currentPassageId = null;
let lessonWideTrainingMeta = null;
let isLessonPartFlow = false;
let answerSubmitted = false;

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
            ? { passage_ids: passage_ids, limit: 0 }
            : { passage_id: passage_id, limit: 12 };
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
    document.getElementById('wrong-answer-next').style.display = 'none';
    const skipBtn = document.getElementById('btn-skip-task');
    const typingSubmitBtn = document.getElementById('typing-submit-btn');
    const reorderSubmitBtn = document.getElementById('reorder-submit-btn');
    if (skipBtn) skipBtn.style.display = '';
    if (typingSubmitBtn) typingSubmitBtn.style.display = 'none';
    if (reorderSubmitBtn) reorderSubmitBtn.style.display = 'none';

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
        instructionEl.innerHTML = '<i class="fa-solid fa-headphones-simple" aria-hidden="true"></i><span>Listen and choose the correct translation:</span>';
        document.getElementById('audio-controls').style.display = 'block';
        if (task.audio_key) {
            playTrainerAudio(audioEl);
        }
        setupMultipleChoice(task);
    } else if (task.type === "meaning") {
        instructionEl.innerHTML = '<i class="fa-solid fa-book-open" aria-hidden="true"></i><span>What is the meaning of this sentence?</span>';
        document.getElementById('word-display').innerText = task.content;
        document.getElementById('word-display').style.display = 'block';
        setupMultipleChoice(task);
    } else if (task.type === "typing") {
        instructionEl.innerHTML = '<i class="fa-solid fa-keyboard" aria-hidden="true"></i><span>Type the following sentence in Chinese:</span>';
        document.getElementById('word-display').innerText = task.content;
        document.getElementById('word-display').style.display = 'block';
        document.getElementById('typing-area').style.display = 'flex';
        if (typingSubmitBtn) typingSubmitBtn.style.display = 'inline-flex';
        document.getElementById('typing-input').focus();
    } else if (task.type === "reorder") {
        instructionEl.innerHTML = '<i class="fa-solid fa-arrows-up-down-left-right" aria-hidden="true"></i><span>Reorder the words to form the correct sentence:</span>';
        if (reorderSubmitBtn) reorderSubmitBtn.style.display = 'inline-flex';
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
            if (currentReorderTokens.join('') === task.correct_answer) {
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
    const btnElement = document.getElementById('reorder-submit-btn');
    checkAnswer(task, userSentence, task.correct_answer, btnElement);
}

function skipTask() {
    const task = sessionData?.tasks[currentTaskIndex];
    if (!task) return;

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
            is_correct: false,
            response_time_ms: Date.now() - taskStartTime,
            game_info: gameInfo
        })
    }).catch(e => console.error("DB skip log failed", e));

    nextTask();
}

async function checkAnswer(task, userAnswer, correctAnswer, element) {
    if (answerSubmitted) return;
    answerSubmitted = true;
    const responseTime = Date.now() - taskStartTime;
    const isCorrect = (userAnswer === correctAnswer);

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
                if (textContent === correctAnswer) {
                    btn.style.backgroundColor = "var(--success)";
                    btn.style.color = "white";
                    btn.style.borderColor = "var(--success)";
                }
            });
        } else if (task.type === "reorder") {
            const reorderFeedback = document.getElementById('reorder-feedback');
            if (reorderFeedback) {
                reorderFeedback.innerHTML = `<span style="color:var(--text-muted); font-size:16px;">Correct Answer:</span><br><span style="color:var(--success)">${task.correct_answer}</span>`;
                reorderFeedback.style.display = 'block';
            }
        }
    }

    if (task.type === "typing") {
        const typingFeedback = document.getElementById('typing-feedback');
        if (typingFeedback && task.pinyin) {
            let htmlContent = `<span style="color:var(--text-muted); font-size:16px;">Pinyin:</span><br><span style="color:var(--primary)">${task.pinyin}</span>`;
            if (!isCorrect) {
                htmlContent += `<br><span style="color:var(--text-muted); font-size:16px; margin-top: 5px; display:inline-block;">Correct Answer:</span><br><span style="color:var(--success)">${task.correct_answer}</span>`;
            }
            typingFeedback.innerHTML = htmlContent;
            typingFeedback.style.display = 'block';
        }
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
    const skipBtn = document.getElementById('btn-skip-task');
    if (skipBtn) skipBtn.style.display = 'none';

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
            is_correct: isCorrect,
            response_time_ms: responseTime,
            game_info: gameInfo
        })
    }).catch(e => console.error("DB Log failed", e));

    if (isCorrect) {
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
        document.getElementById('wrong-answer-next').style.display = 'block';
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
    const skipBtn = document.getElementById('btn-skip-task');
    if (skipBtn) skipBtn.style.display = '';

    document.getElementById('wrong-answer-next').style.display = 'none';
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
    const passageIds = lessonWideTrainingMeta?.passage_ids?.length
        ? lessonWideTrainingMeta.passage_ids
        : (isLessonPartFlow && currentPassageId ? [currentPassageId] : []);
    if (!passageIds.length) return;

    Promise.all(passageIds.map(passageId => fetch('/api/lesson/part-complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ passage_id: passageId })
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
