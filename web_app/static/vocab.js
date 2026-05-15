let currentMode = "1";
let sessionData = null;
let currentTaskIndex = 0;
let missedTasks = [];
let taskStartTime = 0;

function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

function goHome() {
    switchScreen('screen-menu');
    sessionData = null;
    currentTaskIndex = 0;
    missedTasks = [];
}

async function showSetup(mode) {
    currentMode = mode;
    if (mode === "1") {
        switchScreen('screen-setup-standard');
    } else {
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
            document.getElementById('preview-count').innerText = `Found ${words.length} words in database history.`;
            
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
}

async function startSession(mode) {
    switchScreen('screen-loading');

    const payload = { mode: mode };
    
    if (mode === "1") {
        payload.hsk_level = document.getElementById('input-hsk').value;
        payload.start_idx = document.getElementById('input-start-idx').value;
        payload.end_idx = document.getElementById('input-end-idx').value;
    } else {
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

function playCurrentAudio() {
    const audioEl = document.getElementById('audio-player');
    if (audioEl.src) {
        audioEl.play().catch(e => console.warn("Audio playback failed:", e));
    }
}

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
                if (btn.innerText === correctAnswer) {
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

// Add Enter key listener for typing
document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && document.getElementById('screen-training').classList.contains('active')) {
        if (document.getElementById('typing-area').style.display !== 'none') {
            const typingInput = document.getElementById('typing-input');
            if (!typingInput.disabled) {
                submitTyping();
            }
        }
    }
});
