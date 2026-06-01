// ─── State ───────────────────────────────────────────────────────────────────

let words = [];          // full vocab list for this lesson
let currentIndex = 0;
let lessonMeta = null;   // { lesson, start_idx, end_idx, hsk_level }
const hskLevel = window.hskLevel; // injected by Flask template

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadLessons();
    
    // Typing input logic
    const typingInput = document.getElementById('vl-typing-input');
    if (typingInput) {
        typingInput.addEventListener('input', (e) => {
            const word = words[currentIndex];
            if (!word) return;
            if (e.target.value.trim() === word.word) {
                e.target.classList.add('success-highlight');
                playAudio();
            } else {
                e.target.classList.remove('success-highlight');
            }
        });
    }
});

// ─── Lesson Picker ────────────────────────────────────────────────────────────

async function loadLessons() {
    const listEl = document.getElementById('vl-lesson-list');
    const subtitleEl = document.getElementById('vl-level-subtitle');

    try {
        const res = await fetch(`/api/vocab/lessons/${hskLevel}`);
        const data = await res.json();

        if (!res.ok || data.error) {
            listEl.innerHTML = `<p style="color:var(--danger); text-align:center;">Error: ${data.error || 'Failed to load lessons.'}</p>`;
            return;
        }

        const lessons = data.lessons || [];
        if (subtitleEl) subtitleEl.textContent = `${lessons.length} lesson${lessons.length !== 1 ? 's' : ''} available`;

        listEl.innerHTML = '';
        lessons.forEach(lesson => {
            const card = document.createElement('div');
            card.className = 'vl-lesson-card';
            const preview = lesson.preview && lesson.preview.length > 0
                ? lesson.preview.join('  ·  ')
                : '';
            card.innerHTML = `
                <div>
                    <div class="vl-lesson-title">Lesson ${lesson.lesson}</div>
                    <div class="vl-lesson-preview">${preview}</div>
                </div>
                <div class="vl-lesson-badge">${lesson.word_count} words</div>
            `;
            card.addEventListener('click', () => startLesson(lesson));
            listEl.appendChild(card);
        });

    } catch (e) {
        listEl.innerHTML = `<p style="color:var(--danger); text-align:center;">Failed to connect to server.</p>`;
    }
}

// ─── Word Fetching ────────────────────────────────────────────────────────────

async function startLesson(lesson) {
    lessonMeta = { ...lesson, hsk_level: hskLevel };

    // Show loading
    document.getElementById('screen-picker').style.display = 'none';
    const loadingEl = document.getElementById('screen-loading');
    loadingEl.style.display = 'block';

    try {
        // Use the vocab/start API to get the full word list for this lesson
        const res = await fetch('/api/vocab/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: '1',
                hsk_level: hskLevel,
                start_idx: lesson.start_idx,
                end_idx: lesson.end_idx
            })
        });
        const data = await res.json();

        if (!res.ok || data.error) {
            alert(data.error || 'Failed to load words.');
            backToLessons();
            return;
        }

        // Deduplicate tasks → one entry per unique word
        const seen = new Set();
        words = [];
        for (const task of (data.tasks || [])) {
            if (!seen.has(task.word)) {
                seen.add(task.word);
                words.push(task);
            }
        }

        if (words.length === 0) {
            alert('No words found for this lesson.');
            backToLessons();
            return;
        }

        currentIndex = 0;
        loadingEl.style.display = 'none';
        document.getElementById('screen-learning').style.display = 'block';
        renderWord();

    } catch (e) {
        alert('Error connecting to server.');
        backToLessons();
    }
}

// ─── Word Rendering ───────────────────────────────────────────────────────────

function renderWord() {
    const word = words[currentIndex];
    const total = words.length;

    // Progress
    document.getElementById('vl-counter').textContent = `${currentIndex + 1} / ${total}`;
    document.getElementById('vl-progress-fill').style.width = `${((currentIndex + 1) / total) * 100}%`;

    // Content
    document.getElementById('vl-hanzi').textContent = word.word;
    document.getElementById('vl-pinyin').textContent = word.pinyin || '';
    document.getElementById('vl-meaning').textContent = word.meaning_vn || word.meaning_en || '';

    // Clear typing input
    const typingInput = document.getElementById('vl-typing-input');
    if (typingInput) {
        typingInput.value = '';
        typingInput.classList.remove('success-highlight');
    }

    // Navigation buttons
    document.getElementById('btn-prev').disabled = currentIndex === 0;
    const btnNext = document.getElementById('btn-next');
    if (currentIndex === total - 1) {
        btnNext.disabled = false;
        btnNext.textContent = 'Finish →';
    } else {
        btnNext.disabled = false;
        btnNext.textContent = 'Next →';
    }

    // Audio
    const audio = document.getElementById('vl-audio');
    if (word.audio_key) {
        audio.src = `/audio/${word.audio_key}.mp3`;
        audio.play().catch(() => {});
        setAudioPlaying(true);
        audio.onended = () => setAudioPlaying(false);
    } else {
        audio.removeAttribute('src');
        setAudioPlaying(false);
    }
}

function setAudioPlaying(playing) {
    const btn = document.getElementById('btn-audio');
    if (playing) {
        btn.classList.add('playing');
        btn.innerHTML = '🔊 Playing…';
    } else {
        btn.classList.remove('playing');
        btn.innerHTML = '🔊 Play Audio';
    }
}

// ─── Controls ─────────────────────────────────────────────────────────────────

function playAudio() {
    const audio = document.getElementById('vl-audio');
    if (audio.src) {
        audio.currentTime = 0;
        audio.play().catch(() => {});
        setAudioPlaying(true);
        audio.onended = () => setAudioPlaying(false);
    }
}

function prevWord() {
    if (currentIndex > 0) {
        currentIndex--;
        renderWord();
    }
}

function nextWord() {
    if (currentIndex < words.length - 1) {
        currentIndex++;
        renderWord();
    } else {
        showVocabSummary();
    }
}

function backToLessons() {
    words = [];
    currentIndex = 0;
    lessonMeta = null;
    document.getElementById('screen-loading').style.display = 'none';
    document.getElementById('screen-learning').style.display = 'none';
    document.getElementById('screen-summary').style.display = 'none';
    document.getElementById('screen-picker').style.display = 'block';

    const audio = document.getElementById('vl-audio');
    audio.pause();
    audio.removeAttribute('src');
}

function goToTrainer() {
    if (!lessonMeta) return;
    // Deep-link to vocab trainer with URL params so it auto-starts
    const params = new URLSearchParams({
        mode: '1',
        hsk_level: lessonMeta.hsk_level,
        start_idx: lessonMeta.start_idx,
        end_idx: lessonMeta.end_idx
    });
    window.location.href = `/vocab?${params.toString()}`;
}

// ─── Keyboard Shortcuts ───────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
    if (document.getElementById('screen-learning').style.display === 'none') return;
    if (e.key === 'ArrowLeft')  prevWord();
    if (e.key === 'ArrowRight') nextWord();
    if (e.key === ' ')          { e.preventDefault(); playAudio(); }
});

// ─── Summary Table ────────────────────────────────────────────────────────────

let isAudioPlaying = false;
let audioQueue = [];
let tableVocabList = [];

function showVocabSummary() {
    document.getElementById('screen-learning').style.display = 'none';
    document.getElementById('screen-summary').style.display = 'block';
    
    // Stop any learning audio
    const audio = document.getElementById('vl-audio');
    audio.pause();

    tableVocabList = [...words];
    renderVocabTable();
}

function renderVocabTable() {
    const container = document.getElementById('vl-summary-body');
    
    if (!tableVocabList || tableVocabList.length === 0) {
        container.innerHTML = `<div class="vocab-empty">No vocabulary available for this lesson.</div>`;
        return;
    }

    const tableId = 'vl-summary-table';
    let html = `
        <table class="vocab-table" id="${tableId}">
            <thead>
                <tr>
                    <th style="width: 80px;">
                        <button onclick="event.stopPropagation(); playAllVocabAudio()" class="vocab-header-icon-btn" title="Play All">▶</button>
                        <button onclick="event.stopPropagation(); shuffleVocab()" class="vocab-header-icon-btn" title="Shuffle">🔀</button>
                    </th>
                    <th onclick="toggleVocabColumn('cn', '${tableId}')" title="Click to hide/show Character">CHARACTER</th>
                    <th onclick="toggleVocabColumn('py', '${tableId}')" title="Click to hide/show Pinyin">PINYIN</th>
                    <th onclick="toggleVocabColumn('vn', '${tableId}')" title="Click to hide/show Meaning">MEANING (VN)</th>
                </tr>
            </thead>
            <tbody>
    `;

    tableVocabList.forEach((v, index) => {
        html += `
            <tr id="vl-tr-${index}" data-audio="${v.audio_key || ''}">
                <td>
                    ${v.audio_key ? `<button class="vocab-audio-btn" onclick="playSingleVocabAudio('${v.audio_key}')">🔊</button>` : '<span style="color:#666">-</span>'}
                </td>
                <td class="vocab-cn">${v.word || ''}</td>
                <td class="vocab-pinyin">${v.pinyin || ''}</td>
                <td class="vocab-meaning-vn">${v.meaning_vn || v.meaning_en || ''}</td>
            </tr>
        `;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
}

function toggleVocabColumn(colType, tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    table.classList.toggle(`hide-${colType}`);
}

function shuffleVocab() {
    for (let i = tableVocabList.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [tableVocabList[i], tableVocabList[j]] = [tableVocabList[j], tableVocabList[i]];
    }
    renderVocabTable();
}

function playSingleVocabAudio(audioKey) {
    const audio = new Audio(`/audio/${audioKey}.mp3`);
    audio.play().catch(e => console.log('Audio play failed:', e));
}

function playAllVocabAudio() {
    if (isAudioPlaying) return; 

    // Create a queue of words that have audio, store their index
    audioQueue = tableVocabList.map((v, i) => ({...v, originalIndex: i})).filter(v => v.audio_key);
    if (audioQueue.length === 0) return;

    isAudioPlaying = true;
    playNextInQueue();
}

function playNextInQueue() {
    // Clear previous highlights
    document.querySelectorAll('#vl-summary-table tr').forEach(tr => tr.classList.remove('playing-highlight'));

    if (!isAudioPlaying || audioQueue.length === 0) {
        isAudioPlaying = false;
        return;
    }

    const nextWord = audioQueue.shift();
    
    // Highlight the row
    const tr = document.getElementById(`vl-tr-${nextWord.originalIndex}`);
    if (tr) {
        tr.classList.add('playing-highlight');
        tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    const audio = new Audio(`/audio/${nextWord.audio_key}.mp3`);
    
    audio.onended = () => {
        setTimeout(playNextInQueue, 800); 
    };

    audio.onerror = () => {
        setTimeout(playNextInQueue, 300);
    };

    audio.play().catch(e => {
        console.log('Audio play failed:', e);
        setTimeout(playNextInQueue, 300);
    });
}

// ─── Stroke Order Modal ───────────────────────────────────────────────────────

let strokeWriter = null;         // current HanziWriter instance
let strokeChars = [];            // array of individual characters
let strokeCharIndex = 0;         // which character tab is active
let strokeQuizMode = false;

function openStrokeModal() {
    const word = words[currentIndex];
    if (!word || !word.word) return;

    // Split word into individual Chinese characters
    strokeChars = [...word.word].filter(c => /[\u4e00-\u9fff]/.test(c));
    if (strokeChars.length === 0) return;

    strokeCharIndex = 0;
    strokeQuizMode = false;

    // Populate header
    document.getElementById('stroke-modal-word').textContent = word.word;
    document.getElementById('stroke-modal-pinyin').textContent = word.pinyin || '';

    // Build character tabs
    const tabsEl = document.getElementById('stroke-char-tabs');
    if (strokeChars.length <= 1) {
        tabsEl.style.display = 'none';
    } else {
        tabsEl.style.display = 'flex';
        tabsEl.innerHTML = strokeChars.map((ch, i) => `
            <button class="stroke-tab ${i === 0 ? 'active' : ''}" onclick="switchStrokeChar(${i})">${ch}</button>
        `).join('');
    }

    // Show modal
    document.getElementById('stroke-modal-overlay').classList.add('open');

    // Render first character
    renderStrokeChar(strokeCharIndex);
}

function switchStrokeChar(index) {
    strokeCharIndex = index;
    strokeQuizMode = false;

    // Update tab active state
    document.querySelectorAll('.stroke-tab').forEach((t, i) => {
        t.classList.toggle('active', i === index);
    });

    renderStrokeChar(index);
}

function renderStrokeChar(index) {
    const container = document.getElementById('stroke-canvas-container');
    container.innerHTML = ''; // clear previous SVG

    // Destroy old writer
    strokeWriter = null;

    const char = strokeChars[index];
    const size = Math.min(280, window.innerWidth - 80);

    // Create a fresh target div
    const target = document.createElement('div');
    target.id = 'stroke-svg-target';
    container.appendChild(target);

    strokeWriter = HanziWriter.create('stroke-svg-target', char, {
        width: size,
        height: size,
        padding: 16,
        strokeColor: '#e2e8f0',
        radicalColor: '#818cf8',
        outlineColor: 'rgba(255,255,255,0.08)',
        drawingColor: '#4361ee',
        drawingWidth: 4,
        showOutline: true,
        showCharacter: false,    // start hidden; animate reveals it
        delayBetweenStrokes: 300,
    });

    // Auto-animate on open
    strokeWriter.animateCharacter();
}

function strokeAnimate() {
    if (!strokeWriter) return;
    strokeQuizMode = false;
    strokeWriter.animateCharacter();
}

function strokeQuiz() {
    if (!strokeWriter) return;
    strokeQuizMode = true;
    strokeWriter.quiz({
        onMistake(strokeData) {
            console.log('Mistake on stroke', strokeData.strokeNum);
        },
        onCorrectStroke(strokeData) {
            console.log('Correct stroke', strokeData.strokeNum);
        },
        onComplete(summaryData) {
            console.log('Quiz complete! Mistakes:', summaryData.totalMistakes);
        }
    });
}

function strokeReset() {
    if (strokeCharIndex !== undefined) {
        renderStrokeChar(strokeCharIndex);
    }
}

function closeStrokeModal() {
    document.getElementById('stroke-modal-overlay').classList.remove('open');
    strokeWriter = null;
    // Clear canvas to release memory
    const container = document.getElementById('stroke-canvas-container');
    container.innerHTML = '';
}

function closeStrokeModalIfBackground(e) {
    if (e.target.id === 'stroke-modal-overlay') closeStrokeModal();
}

