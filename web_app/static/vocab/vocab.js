let currentMode = "1";
let sessionData = null;
let currentTaskIndex = 0;
let missedTasks = [];
let taskStartTime = 0;
let selectedHskLevel = null;

// ─── Auto-start from URL params (e.g. from vocab-learning "Train This Lesson") ─

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('mode') === '1' && params.get('hsk_level')) {
        const hskLevel  = params.get('hsk_level');
        const startIdx  = parseInt(params.get('start_idx') || '0', 10);
        const endIdx    = parseInt(params.get('end_idx')   || '9', 10);
        // Remove params from URL without reloading
        history.replaceState(null, '', '/vocab');
        // Auto-start the session
        startSession('1', { hsk_level: hskLevel, start_idx: startIdx, end_idx: endIdx });
    }
});

// ─── Screen Navigation ───────────────────────────────────────────────────────

function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

function goHome() {
    closeQuitModal();
    switchScreen('screen-menu');
    sessionData = null;
    currentTaskIndex = 0;
    missedTasks = [];
    selectedHskLevel = null;
}

// ─── Quit Confirmation Modal ──────────────────────────────────────────────────

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

// ─── Standard Mode: Level → Lesson Picker ────────────────────────────────────

function showLevelPicker() {
    currentMode = "1";
    switchScreen('screen-level-picker');
}

async function showLessonPicker(hskLevel) {
    selectedHskLevel = hskLevel;
    const levelNum = hskLevel.replace('HSK', '');

    document.getElementById('lesson-picker-title').innerText = `${hskLevel} — Select a Lesson`;
    document.getElementById('lesson-picker-sub').innerText = '';
    document.getElementById('lesson-list').innerHTML = '<p style="color:var(--text-muted); text-align:center;">Loading lessons…</p>';
    switchScreen('screen-lesson-picker');

    try {
        const res = await fetch(`/api/vocab/lessons/${hskLevel}`);
        const data = await res.json();

        if (!res.ok || data.error) {
            document.getElementById('lesson-list').innerHTML = `<p style="color:var(--danger);">Error: ${data.error || 'Failed to load.'}</p>`;
            return;
        }

        const lessons = data.lessons || [];
        document.getElementById('lesson-picker-sub').innerText = `${lessons.length} lesson${lessons.length !== 1 ? 's' : ''} available`;

        const listEl = document.getElementById('lesson-list');
        listEl.innerHTML = '';

        lessons.forEach(lesson => {
            const card = document.createElement('div');
            card.className = 'lesson-card';
            const previewWords = lesson.preview && lesson.preview.length > 0
                ? lesson.preview.join('  ·  ')
                : '';
            card.innerHTML = `
                <div class="lesson-card-left">
                    <div class="lesson-card-title">Lesson ${lesson.lesson}</div>
                    <div class="lesson-card-preview">${previewWords}</div>
                </div>
                <div class="lesson-card-count">${lesson.word_count} words</div>
            `;
            card.addEventListener('click', () => {
                startSession('1', {
                    hsk_level: hskLevel,
                    start_idx: lesson.start_idx,
                    end_idx: lesson.end_idx
                });
            });
            listEl.appendChild(card);
        });

    } catch (e) {
        console.error(e);
        document.getElementById('lesson-list').innerHTML = `<p style="color:var(--danger);">Failed to connect to server.</p>`;
    }
}

// ─── Other Modes Setup ────────────────────────────────────────────────────────

async function showSetup(mode) {
    currentMode = mode;
    const titles = {
        "2": "Unlearned Words Setup",
        "3": "Unsure Words Setup",
        "4": "Hard Semantic Setup",
        "5": "Hard Stroke Setup"
    };
    document.getElementById('other-setup-title').innerText = titles[mode];

    // Show loading screen while fetching preview
    switchScreen('screen-loading');

    try {
        const response = await fetch('/api/vocab/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode })
        });
        const data = await response.json();

        if (data.error) {
            alert(data.error);
            goHome();
            return;
        }

        const words = data.words || [];
        document.getElementById('preview-count').innerText = `Found ${words.length} words in your history.`;

        const listEl = document.getElementById('preview-list');
        listEl.innerHTML = '';
        words.forEach(w => {
            const li = document.createElement('li');
            li.innerHTML = `<strong>${w.word}</strong> | ${w.pinyin} <br> <span style="color:var(--text-muted)">${w.meaning_vn}</span>`;
            listEl.appendChild(li);
        });

        if (words.length === 0) {
            listEl.innerHTML = '<li>No words found.</li>';
            document.getElementById('btn-start-other').disabled = true;
        } else {
            document.getElementById('btn-start-other').disabled = false;
        }

        switchScreen('screen-setup-other');

    } catch (e) {
        console.error(e);
        alert("Failed to fetch preview.");
        goHome();
    }
}

// ─── Session Start ────────────────────────────────────────────────────────────

async function startSession(mode, extraParams = {}) {
    switchScreen('screen-loading');

    const payload = { mode: mode, ...extraParams };

    // For other modes, also pick up limit from input if visible
    if (mode !== "1") {
        payload.limit = document.getElementById('input-limit').value;
    }

    try {
        const response = await fetch('/api/vocab/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Failed to start session.");
            goHome();
            return;
        }

        sessionData = data;
        currentTaskIndex = 0;
        missedTasks = [];

        loadTask();
    } catch (e) {
        alert("Error connecting to server.");
        goHome();
    }
}

// ─── Task Loading ─────────────────────────────────────────────────────────────

function loadTask() {
    if (currentTaskIndex >= sessionData.tasks.length) {
        finishRound();
        return;
    }

    switchScreen('screen-training');

    const task = sessionData.tasks[currentTaskIndex];
    const total = sessionData.tasks.length;

    // Update progress
    document.getElementById('progress-fill').style.width = `${((currentTaskIndex) / total) * 100}%`;
    document.getElementById('task-counter').innerText = `Task ${currentTaskIndex + 1}/${total}`;

    // Reset visibility
    document.getElementById('word-display').style.display = 'none';
    document.getElementById('audio-controls').style.display = 'none';
    document.getElementById('mc-area').style.display = 'none';
    document.getElementById('typing-area').style.display = 'none';
    document.getElementById('typing-input').value = '';

    const mcFeedback = document.getElementById('mc-feedback');
    if (mcFeedback) { mcFeedback.style.display = 'none'; mcFeedback.innerHTML = ''; }

    const typingFeedback = document.getElementById('typing-feedback');
    if (typingFeedback) { typingFeedback.style.display = 'none'; typingFeedback.innerHTML = ''; }

    const instructionEl = document.getElementById('task-instruction');
    const audioEl = document.getElementById('audio-player');

    if (task.audio_key) {
        audioEl.src = `/audio/${task.audio_key}.mp3`;
    } else {
        audioEl.removeAttribute('src');
    }

    taskStartTime = Date.now();

    if (task.type === "listen") {
        instructionEl.innerText = "🎧 Listen to the audio and choose the correct meaning:";
        document.getElementById('audio-controls').style.display = 'block';
        if (task.audio_key) {
            audioEl.play().catch(e => console.warn("Audio playback failed:", e));
        }
        setupMultipleChoice(task);
    }
    else if (task.type === "typing") {
        instructionEl.innerText = "⌨️ Type the following word:";
        document.getElementById('word-display').innerText = task.word;
        document.getElementById('word-display').style.display = 'block';
        document.getElementById('typing-area').style.display = 'flex';
        document.getElementById('typing-input').focus();
    }
    else if (task.type === "meaning") {
        instructionEl.innerText = "📖 What is the meaning of this word?";
        document.getElementById('word-display').innerText = task.word;
        document.getElementById('word-display').style.display = 'block';
        setupMultipleChoice(task);
    }
}

// ─── Multiple Choice with Keyboard Hints ──────────────────────────────────────

function setupMultipleChoice(task) {
    const mcArea = document.getElementById('mc-area');
    mcArea.innerHTML = '';
    mcArea.style.display = 'grid';

    task.options.forEach((opt, idx) => {
        const btn = document.createElement('button');
        btn.className = 'btn';
        btn.dataset.optionIndex = idx;

        // Inject keyboard hint badge [1]–[4]
        const keyNum = idx + 1;
        btn.innerHTML = `<span class="mc-btn-inner"><span class="key-hint">${keyNum}</span>${opt}</span>`;
        btn.addEventListener('click', (e) => submitMC(opt, task, btn));
        mcArea.appendChild(btn);
    });
}

// ─── Audio ───────────────────────────────────────────────────────────────────

function playCurrentAudio() {
    const audioEl = document.getElementById('audio-player');
    if (audioEl.src) {
        audioEl.play().catch(e => console.warn("Audio playback failed:", e));
    }
}

// ─── Answer Submission ────────────────────────────────────────────────────────

function submitTyping() {
    const input = document.getElementById('typing-input').value.trim();
    if (!input) return;

    const task = sessionData.tasks[currentTaskIndex];
    const btn = document.getElementById('typing-submit-btn');
    checkAnswer(task, input, task.word, btn);
}

function submitMC(selected, task, btnElement) {
    checkAnswer(task, selected, task.meaning_vn, btnElement);
}

async function checkAnswer(task, userAnswer, correctAnswer, element) {
    const responseTime = Date.now() - taskStartTime;
    const isCorrect = (userAnswer === correctAnswer);

    // Highlight the submitted element
    if (element) {
        element.style.transition = "background-color 0.3s, color 0.3s";
        element.style.backgroundColor = isCorrect ? "var(--success)" : "var(--danger)";
        element.style.color = "white";
        element.style.borderColor = isCorrect ? "var(--success)" : "var(--danger)";
    }

    // Handle feedback div
    if (task.type === "typing") {
        const fb = document.getElementById('typing-feedback');
        if (fb) {
            let html = `<span style="color:var(--primary); font-weight:bold;">${task.pinyin}</span><br><span style="color:var(--text-muted)">${task.meaning_vn}</span>`;
            if (!isCorrect) {
                html += `<br><span style="color:var(--danger); font-size:16px;">Correct Answer: ${task.word}</span>`;
            }
            fb.innerHTML = html;
            fb.style.display = 'block';
        }
    } else {
        const fb = document.getElementById('mc-feedback');
        if (fb) {
            let html = `<span style="color:var(--primary); font-weight:bold;">${task.pinyin}</span><br><span style="color:var(--text-muted)">${task.meaning_vn}</span>`;
            if (task.type === "listen") {
                html = `<span style="color:white; font-size:24px; font-weight:bold;">${task.word}</span><br>` + html;
            }
            fb.innerHTML = html;
            fb.style.display = 'block';
        }
    }

    // Add to missed if incorrect
    if (!isCorrect) {
        missedTasks.push(task);
        if (task.options) {
            const mcBtns = document.querySelectorAll('#mc-area .btn');
            mcBtns.forEach(btn => {
                // Get text content without the key-hint number
                const textContent = btn.querySelector('.mc-btn-inner')
                    ? btn.querySelector('.mc-btn-inner').textContent.slice(1).trim()
                    : btn.innerText.slice(1).trim();
                if (textContent === correctAnswer) {
                    btn.style.backgroundColor = "var(--success)";
                    btn.style.color = "white";
                    btn.style.borderColor = "var(--success)";
                }
            });
        }
    }

    // Play audio on answer reveal
    if (task.audio_key) {
        const audioEl = document.getElementById('audio-player');
        if (audioEl.src) {
            audioEl.play().catch(e => console.warn("Audio playback failed:", e));
        }
    }

    // Disable all inputs
    const allBtns = document.querySelectorAll('#screen-training .btn');
    allBtns.forEach(b => b.disabled = true);
    const typingInput = document.getElementById('typing-input');
    if (typingInput) typingInput.disabled = true;

    // Send to DB async
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
    }).catch(e => console.error("DB Log failed", e));

    // Wait before next
    setTimeout(() => {
        allBtns.forEach(b => b.disabled = false);
        if (typingInput) typingInput.disabled = false;

        if (element) {
            element.style.backgroundColor = "";
            element.style.color = "";
            element.style.borderColor = "";
        }
        if (!isCorrect && task.options) {
            const mcBtns = document.querySelectorAll('#mc-area .btn');
            mcBtns.forEach(btn => {
                btn.style.backgroundColor = "";
                btn.style.color = "";
                btn.style.borderColor = "";
            });
        }

        nextTask();
    }, 3000);
}

// ─── Navigation ───────────────────────────────────────────────────────────────

function nextTask() {
    currentTaskIndex++;
    loadTask();
}

function finishRound() {
    switchScreen('screen-complete');

    if (missedTasks.length > 0) {
        document.getElementById('recap-area').style.display = 'block';
        document.getElementById('perfect-area').style.display = 'none';

        const list = document.getElementById('recap-list');
        list.innerHTML = '';

        const uniqueMissed = [...new Set(missedTasks.map(t => t.word))];

        uniqueMissed.forEach(wordStr => {
            const t = missedTasks.find(x => x.word === wordStr);
            const li = document.createElement('li');
            li.innerHTML = `<strong>${t.word}</strong> | ${t.pinyin} <br> <span style="color:var(--text-muted)">${t.meaning_vn}</span>`;
            list.appendChild(li);
        });
    } else {
        document.getElementById('recap-area').style.display = 'none';
        document.getElementById('perfect-area').style.display = 'flex';
    }
}

function retryMissed() {
    // Shuffle missed and set as current tasks
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

// ─── Keyboard Shortcuts ───────────────────────────────────────────────────────

document.addEventListener('keydown', function (e) {
    const trainingActive = document.getElementById('screen-training').classList.contains('active');
    if (!trainingActive) return;

    // Enter → submit typing
    if (e.key === 'Enter') {
        if (document.getElementById('typing-area').style.display !== 'none') {
            const typingInput = document.getElementById('typing-input');
            if (!typingInput.disabled) {
                submitTyping();
            }
        }
        return;
    }

    // 1–4 → click MC option
    const keyMap = { '1': 0, '2': 1, '3': 2, '4': 3 };
    if (e.key in keyMap) {
        const mcArea = document.getElementById('mc-area');
        if (mcArea.style.display === 'none') return;

        const btns = mcArea.querySelectorAll('.btn');
        const idx = keyMap[e.key];
        if (idx < btns.length && !btns[idx].disabled) {
            btns[idx].click();
        }
    }
});
