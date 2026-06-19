let sessionData = null;
let currentTaskIndex = 0;
let missedTasks = [];
let taskStartTime = 0;
let currentReorderTokens = [];
let currentPassageId = null;
let isLessonPartFlow = false;

// Fetch passages on load
window.onload = async () => {
    const params = new URLSearchParams(window.location.search);
    isLessonPartFlow = params.get('flow') === 'lesson-part';

    Picker.init((passage) => {
        startSession(passage.passage_id);
    }, "Lesson Practice", !params.get('passage_id'));

    const autoPassage = params.get('passage_id');
    if (autoPassage) {
        startSession(autoPassage);
    }
};

function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

function goHome() {
    if (currentPassageId) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(currentPassageId)}`;
        return;
    }
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    Picker.showLevelPicker();
    sessionData = null;
    currentTaskIndex = 0;
    missedTasks = [];
    closeQuitModal();
}

async function startSession(passage_id) {
    currentPassageId = passage_id;
    switchScreen('screen-loading');

    try {
        const response = await fetch('/api/lesson/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ passage_id: passage_id, limit: 12 })
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

function loadTask() {
    if (currentTaskIndex >= sessionData.tasks.length) {
        finishRound();
        return;
    }

    switchScreen('screen-training');

    const task = sessionData.tasks[currentTaskIndex];
    const total = sessionData.tasks.length;

    // Progress
    document.getElementById('progress-fill').style.width = `${(currentTaskIndex / total) * 100}%`;
    document.getElementById('task-counter').innerText = `Task ${currentTaskIndex + 1}/${total}`;

    // Reset all areas
    document.getElementById('word-display').style.display = 'none';
    document.getElementById('audio-controls').style.display = 'none';
    document.getElementById('mc-area').style.display = 'none';
    document.getElementById('mc-area').innerHTML = '';
    document.getElementById('typing-area').style.display = 'none';
    document.getElementById('reorder-area').style.display = 'none';
    document.getElementById('wrong-answer-next').style.display = 'none';

    const typingInput = document.getElementById('typing-input');
    typingInput.value = '';
    typingInput.disabled = false;

    const typingFeedback = document.getElementById('typing-feedback');
    typingFeedback.style.display = 'none';
    typingFeedback.innerHTML = '';

    const reorderFeedback = document.getElementById('reorder-feedback');
    reorderFeedback.style.display = 'none';

    // Instruction
    const instructionEl = document.getElementById('task-instruction');

    // Audio setup
    const audioEl = document.getElementById('audio-player');
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
        document.getElementById('audio-controls').style.display = 'flex';
        if (task.audio_key) {
            audioEl.play().catch(e => console.warn("Audio playback failed:", e));
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
        document.getElementById('typing-input').focus();
    } else if (task.type === "reorder") {
        instructionEl.innerHTML = '<i class="fa-solid fa-arrows-up-down-left-right" aria-hidden="true"></i><span>Reorder the words to form the correct sentence:</span>';
        setupReorder(task);
    }
}

function setupMultipleChoice(task) {
    const mcArea = document.getElementById('mc-area');
    mcArea.innerHTML = '';
    mcArea.style.display = 'grid';

    task.options.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'btn';
        btn.innerText = opt;
        btn.onclick = (e) => submitMC(opt, task, e.target);
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
        chip.className = 'chip';
        chip.innerText = token;
        chip.onclick = () => {
            if (chip.parentElement.id === 'reorder-source') {
                targetContainer.appendChild(chip);
                currentReorderTokens.push(token);
            } else {
                sourceContainer.appendChild(chip);
                const idx = currentReorderTokens.indexOf(token);
                if (idx > -1) currentReorderTokens.splice(idx, 1);
            }
        };
        sourceContainer.appendChild(chip);
    });
}

function playCurrentAudio() {
    const audioEl = document.getElementById('audio-player');
    if (audioEl.src) {
        audioEl.play().catch(e => console.warn("Audio playback failed:", e));
    }
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
    const btnElement = document.querySelector('#reorder-area .primary');
    checkAnswer(task, userSentence, task.correct_answer, btnElement);
}

async function checkAnswer(task, userAnswer, correctAnswer, element) {
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
                if (btn.innerText === correctAnswer) {
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
            is_correct: isCorrect,
            response_time_ms: responseTime,
            game_info: gameInfo
        })
    }).catch(e => console.error("DB Log failed", e));

    if (isCorrect) {
        setTimeout(() => {
            resetTaskUI(element, isCorrect, task);
            nextTask();
        }, 3000);
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

    // Show the animated success popup
    SuccessPopup.show({
        total,
        correct,
        continueLabel: 'View Results',
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
        document.getElementById('recap-area').style.display = 'block';
        document.getElementById('perfect-area').style.display = 'none';

        const list = document.getElementById('recap-list');
        list.innerHTML = '';

        missedTasks.forEach(t => {
            const li = document.createElement('li');
            li.innerHTML = `<strong>${t.type}</strong> | ${t.content || 'Audio'} <br>
                    <span style="color:var(--danger)">Your Answer: ${t.user_answer}</span> <br>
                    <span style="color:var(--success)">Correct Answer: ${t.correct_answer}</span>`;
            list.appendChild(li);
        });
    } else {
        document.getElementById('recap-area').style.display = 'none';
        document.getElementById('perfect-area').style.display = 'flex';
    }
}

function _showLessonCompleteScreen() {
    switchScreen('screen-complete');
}

function markLessonPartComplete() {
    if (!isLessonPartFlow || !currentPassageId) return;
    fetch('/api/lesson/part-complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ passage_id: currentPassageId })
    }).catch(e => console.error("Lesson part progress save failed", e));
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

    window.location.href = `/learning?passage_id=${encodeURIComponent(currentPassageId)}`;
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

// Add Enter key listener for typing
document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && document.getElementById('screen-training').classList.contains('active')) {
        if (document.getElementById('typing-area').style.display !== 'none') {
            const typingInput = document.getElementById('typing-input');
            if (!typingInput.disabled) {
                submitTyping();
            }
        }
    }
});

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
