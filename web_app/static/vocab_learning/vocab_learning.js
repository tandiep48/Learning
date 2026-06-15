// ─── State ───────────────────────────────────────────────────────────────────

let words = [];          // full vocab list for this lesson
let currentIndex = 0;
let lessonMeta = null;   // { lesson, start_idx, end_idx, hsk_level }
let speakingRecorder = null;
let speakingStream = null;
let speakingChunks = [];
let speakingTimer = null;
let speakingAttemptId = 0;
let speakingWord = "";
const SPEAKING_MAX_MS = 10000;

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const selectedFlashcards = readSelectedFlashcards();
    const params = new URLSearchParams(window.location.search);
    const autoPassageId = params.get('passage_id');
    Picker.init((passage) => {
        startLesson(passage);
    }, "Vocab Learning", !selectedFlashcards && !autoPassageId);

    if (selectedFlashcards) {
        startSelectedFlashcards(selectedFlashcards);
    } else if (autoPassageId) {
        startLesson({ passage_id: autoPassageId });
    }

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

function readSelectedFlashcards() {
    const raw = sessionStorage.getItem('selectedVocabFlashcards');
    if (!raw) return null;

    try {
        const parsed = JSON.parse(raw);
        sessionStorage.removeItem('selectedVocabFlashcards');
        if (!Array.isArray(parsed) || parsed.length === 0) return null;
        return parsed.map(normalizeFlashcardWord).filter(w => w.word);
    } catch (e) {
        sessionStorage.removeItem('selectedVocabFlashcards');
        return null;
    }
}

function normalizeFlashcardWord(row) {
    const word = row.word || row.cn || '';
    return {
        word,
        cn: word,
        pinyin: row.pinyin || '',
        meaning_vn: row.meaning_vn || '',
        meaning_en: row.meaning_en || '',
        audio_key: row.audio_key || '',
        level: row.level || row.hsk_level || ''
    };
}

function startSelectedFlashcards(selectedRows) {
    lessonMeta = {
        source: 'selection',
        selected_words: selectedRows.map(row => row.word)
    };
    words = selectedRows;
    currentIndex = 0;

    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    document.getElementById('screen-loading').style.display = 'none';
    document.getElementById('screen-learning').style.display = 'none';
    // Show summary first
    tableVocabList = [...words];
    renderVocabTable();
    document.getElementById('screen-summary').style.display = 'block';
}

// ─── Word Fetching ────────────────────────────────────────────────────────────

async function startLesson(passage) {
    lessonMeta = { ...passage, hsk_level: passage.hsk_level || "H1" };

    // Show loading
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    const loadingEl = document.getElementById('screen-loading');
    loadingEl.style.display = 'block';
    document.getElementById('screen-summary').style.display = 'none';
    document.getElementById('screen-learning').style.display = 'none';

    try {
        // Use the vocab/start API with mode 6
        const res = await fetch('/api/vocab/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: '6',
                passage_id: passage.passage_id
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
        // Show summary first instead of going straight to flash cards
        tableVocabList = [...words];
        renderVocabTable();
        document.getElementById('screen-summary').style.display = 'block';

    } catch (e) {
        alert('Error connecting to server.');
        backToLessons();
    }
}

// ─── Word Rendering ───────────────────────────────────────────────────────────

function renderWord() {
    resetSpeakingPractice(true);

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

async function toggleSpeakingPractice() {
    if (speakingRecorder && speakingRecorder.state === 'recording') {
        stopSpeakingRecording();
        return;
    }
    await startSpeakingRecording();
}

async function startSpeakingRecording() {
    const word = words[currentIndex];
    if (!word || !word.word) return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
        showSpeakingMessage('Your browser does not support audio recording.', true);
        return;
    }

    resetSpeakingPractice(false);
    speakingAttemptId += 1;
    speakingWord = word.word;
    speakingChunks = [];

    try {
        speakingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mimeType = getSupportedSpeakingMimeType();
        speakingRecorder = mimeType
            ? new MediaRecorder(speakingStream, { mimeType })
            : new MediaRecorder(speakingStream);

        speakingRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) speakingChunks.push(event.data);
        };
        speakingRecorder.onstop = () => submitSpeakingRecording(speakingAttemptId, speakingWord, mimeType);

        speakingRecorder.start();
        setSpeakingButtonState('recording');
        showSpeakingMessage('Recording... say the word clearly.');
        speakingTimer = setTimeout(stopSpeakingRecording, SPEAKING_MAX_MS);
    } catch (e) {
        console.error(e);
        resetSpeakingPractice(false);
        showSpeakingMessage('Microphone access was blocked. Please allow microphone permission and try again.', true);
    }
}

function getSupportedSpeakingMimeType() {
    const types = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/ogg'
    ];
    return types.find(type => MediaRecorder.isTypeSupported(type)) || '';
}

function stopSpeakingRecording() {
    if (speakingTimer) {
        clearTimeout(speakingTimer);
        speakingTimer = null;
    }
    if (speakingRecorder && speakingRecorder.state === 'recording') {
        setSpeakingButtonState('scoring');
        showSpeakingMessage('Scoring your pronunciation...');
        speakingRecorder.stop();
    }
    stopSpeakingStream();
}

function stopSpeakingStream() {
    if (speakingStream) {
        speakingStream.getTracks().forEach(track => track.stop());
        speakingStream = null;
    }
}

async function submitSpeakingRecording(attemptId, targetWord, mimeType) {
    stopSpeakingStream();
    if (attemptId !== speakingAttemptId) return;

    if (!speakingChunks.length) {
        setSpeakingButtonState('idle');
        showSpeakingMessage('No audio was recorded. Please try again.', true);
        return;
    }

    const blobType = mimeType || speakingChunks[0]?.type || 'audio/webm';
    const extension = blobType.includes('ogg') ? 'ogg' : 'webm';
    const blob = new Blob(speakingChunks, { type: blobType });
    const formData = new FormData();
    formData.append('word', targetWord);
    formData.append('audio', blob, `speaking-${Date.now()}.${extension}`);

    try {
        const response = await fetch('/api/vocab/speaking/score', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (attemptId !== speakingAttemptId) return;
        setSpeakingButtonState('idle');

        if (!response.ok || data.error) {
            showSpeakingMessage(data.error || 'Could not score this recording. Please try again.', true);
            return;
        }

        renderSpeakingResult(data);
    } catch (e) {
        console.error(e);
        if (attemptId !== speakingAttemptId) return;
        setSpeakingButtonState('idle');
        showSpeakingMessage('Could not connect to the speaking scorer. Please try again.', true);
    }
}

function resetSpeakingPractice(stopActiveRecording) {
    speakingAttemptId += 1;
    if (speakingTimer) {
        clearTimeout(speakingTimer);
        speakingTimer = null;
    }
    if (stopActiveRecording && speakingRecorder && speakingRecorder.state === 'recording') {
        speakingRecorder.onstop = null;
        speakingRecorder.stop();
    }
    stopSpeakingStream();
    speakingRecorder = null;
    speakingChunks = [];
    speakingWord = "";
    setSpeakingButtonState('idle');

    const panel = document.getElementById('vl-speaking-panel');
    const result = document.getElementById('vl-speaking-result');
    if (panel) panel.style.display = 'none';
    if (result) {
        result.style.display = 'none';
        result.innerHTML = '';
        result.className = 'vl-speaking-result';
    }
}

function setSpeakingButtonState(state) {
    const button = document.getElementById('btn-speak');
    if (!button) return;

    button.classList.toggle('recording', state === 'recording');
    button.disabled = state === 'scoring';
    if (state === 'recording') {
        button.textContent = 'Stop';
    } else if (state === 'scoring') {
        button.textContent = 'Scoring...';
    } else {
        button.textContent = 'Speak';
    }
}

function showSpeakingMessage(message, isError = false) {
    const panel = document.getElementById('vl-speaking-panel');
    const status = document.getElementById('vl-speaking-status');
    const result = document.getElementById('vl-speaking-result');
    if (panel) panel.style.display = 'block';
    if (status) {
        status.textContent = message;
        status.style.color = isError ? 'var(--danger)' : 'var(--text-muted)';
    }
    if (result) {
        result.style.display = 'none';
        result.innerHTML = '';
        result.className = 'vl-speaking-result';
    }
}

function renderSpeakingResult(data) {
    const panel = document.getElementById('vl-speaking-panel');
    const status = document.getElementById('vl-speaking-status');
    const result = document.getElementById('vl-speaking-result');
    if (panel) panel.style.display = 'block';
    if (status) {
        status.textContent = data.message || (data.is_correct ? 'Nice pronunciation.' : 'Try again.');
        status.style.color = data.is_correct ? 'var(--success)' : 'var(--danger)';
    }
    if (!result) return;

    result.className = `vl-speaking-result ${data.is_correct ? 'success' : 'retry'}`;
    result.innerHTML = `
        <div class="speaking-row"><span class="speaking-label">Score</span><strong>${escapeHtml(data.score)} / 100</strong></div>
        <div class="speaking-row"><span class="speaking-label">Heard</span><span>${escapeHtml(data.recognized_text || '-')}</span></div>
        <div class="speaking-row"><span class="speaking-label">Expected pinyin</span><span>${escapeHtml(data.expected_pinyin || '-')}</span></div>
        <div class="speaking-row"><span class="speaking-label">Heard pinyin</span><span>${escapeHtml(data.recognized_pinyin || '-')}</span></div>
    `;
    result.style.display = 'block';
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
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
    resetSpeakingPractice(true);

    if (lessonMeta?.passage_id) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(lessonMeta.passage_id)}`;
        return;
    }
    document.getElementById('screen-learning').style.display = 'none';
    document.getElementById('screen-summary').style.display = 'none';
    document.getElementById('screen-loading').style.display = 'none';
    if (lessonMeta && lessonMeta.source === 'selection') {
        window.location.href = '/vocab';
        return;
    }
    Picker.showLevelPicker();
    words = [];
    currentIndex = 0;
    lessonMeta = null;

    const audio = document.getElementById('vl-audio');
    audio.pause();
    audio.removeAttribute('src');
}

function startLearningCards() {
    // Called from Summary screen – switch to flash card learning view
    currentIndex = 0;
    document.getElementById('screen-summary').style.display = 'none';
    document.getElementById('screen-learning').style.display = 'block';
    renderWord();
}

function goToTrainer() {
    if (!lessonMeta) return;
    if (lessonMeta.source === 'selection') {
        sessionStorage.setItem('selectedVocabTrainerWords', JSON.stringify(lessonMeta.selected_words || []));
        window.location.href = '/vocab';
        return;
    }
    // Deep-link to vocab trainer with URL params so it auto-starts
    const params = new URLSearchParams({
        mode: '6',
        passage_id: lessonMeta.passage_id
    });
    window.location.href = `/vocab-training?${params.toString()}`;
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
    resetSpeakingPractice(true);
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
        const audioCell = v.audio_key ? `<button class="vocab-audio-btn" onclick="playSingleVocabAudio('${v.audio_key}')">🔊</button>` : '<span style="color:#666">-</span>';
        html += `
            <tr id="vl-tr-${index}" data-audio="${v.audio_key || ''}">
                <td class="vocab-audio-cell">${audioCell}</td>
                <td class="vocab-cn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${v.word || ''}</td>
                <td class="vocab-pinyin clickable-cell" onclick="this.classList.toggle('hidden-cell')">${v.pinyin || ''}</td>
                <td class="vocab-meaning-vn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${v.meaning_vn || v.meaning_en || ''}</td>
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
    if (!tableVocabList || tableVocabList.length === 0) return;
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
