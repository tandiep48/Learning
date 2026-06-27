let currentPassage = null;
let pinyinVisible = false;
let meaningVisible = false;
let currentAudio = null;
let vocabLoaded = false;
let currentVocabList = [];
let isPlayingAll = false;
let isLessonPartFlow = false;
let isLessonLearnerMode = false;
let currentLessonLineIndex = 0;
let lessonSummaryPinyinVisible = false;
let lessonSummaryMeaningVisible = false;
let lessonSpeakingRecorder = null;
let lessonSpeakingStream = null;
let lessonSpeakingChunks = [];
let lessonSpeakingTimer = null;
let lessonSpeakingAttemptId = 0;
const LESSON_SPEAKING_MAX_MS = 15000;

// ── Init ─────────────────────────────────────────────
window.onload = async () => {
    const params = new URLSearchParams(window.location.search);
    const autoPassage = params.get('passage_id');
    isLessonPartFlow = params.get('flow') === 'lesson-part';
    isLessonLearnerMode = isLessonPartFlow && params.get('mode') === 'lesson-learner';

    Picker.init((passage) => {
        loadPassage(passage.passage_id);
    }, isLessonLearnerMode ? "Lesson Learning" : "Reading Lesson", !autoPassage);

    const lessonTypingInput = document.getElementById('lesson-card-typing-input');
    if (lessonTypingInput) {
        lessonTypingInput.addEventListener('input', (e) => {
            const line = getCurrentLessonLine();
            if (!line) return;
            e.target.classList.toggle('success-highlight', e.target.value.trim() === line.content);
        });
    }

    if (autoPassage) {
        await loadPassage(autoPassage);
    }
};

// ── Screen helpers ────────────────────────────────────
function switchScreen(id) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    if (currentAudio) currentAudio.pause();
}

function goHome() {
    resetLessonSpeakingPractice(true);
    if (currentPassage?.passage_id) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(currentPassage.passage_id)}`;
        return;
    }
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    Picker.showLevelPicker();
    currentPassage = null;
    vocabLoaded = false;
}

// ── Load & render passage ─────────────────────────────
async function loadPassage(passage_id) {
    switchScreen('screen-loading');
    vocabLoaded = false;
    currentVocabList = [];
    try {
        const res = await fetch(`/api/lesson/passage/${passage_id}`);
        const data = await res.json();
        if (!res.ok) { alert(data.error || "Failed to load passage."); goHome(); return; }
        currentPassage = data.passage;
        if (isLessonLearnerMode) {
            renderLessonSummary();
            switchScreen('screen-lesson-summary');
        } else {
            renderPassage();
            switchScreen('screen-reading');
        }
    } catch (e) {
        alert("Error connecting to server.");
        goHome();
    }
}

function renderPassage() {
    document.getElementById('reading-title').innerText = currentPassage.passage_id;

    const contentDiv = document.getElementById('reading-content');
    contentDiv.innerHTML = '';

    currentPassage.lines.forEach(line => {
        const lineDiv = document.createElement('div');
        lineDiv.className = 'reading-line';

        let audioHTML = '';
        if (line.audio_key) {
            const hskLevel = currentPassage.hsk_level || 'H1';
            const src = `/lesson_audio/${hskLevel}/${line.audio_key}.mp3`;
            audioHTML = `<button class="audio-btn" onclick="playAudio('${src}')" title="Play Audio" aria-label="Play Audio"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>`;
        }

        const pinyinClass = pinyinVisible ? 'pinyin-text show' : 'pinyin-text';
        const meaningClass = meaningVisible ? 'meaning-text show' : 'meaning-text';

        const textHTML = `
            <div class="reading-text">
                <div class="hanzi-text">${line.content}</div>
                <div class="${pinyinClass}">${line.pinyin || ''}</div>
                <div class="${meaningClass}">${line.translations.vi || line.translations.en || ''}</div>
            </div>`;

        lineDiv.innerHTML = textHTML + audioHTML;
        contentDiv.appendChild(lineDiv);
    });

    updatePinyinBtnText();
    updateMeaningBtnText();
}

// ── Audio ─────────────────────────────────────────────
function playAudio(src) {
    if (currentAudio) currentAudio.pause();
    currentAudio = new Audio(src);
    currentAudio.play().catch(e => console.warn("Audio failed", e));
}

// ── Pinyin / Meaning toggles ──────────────────────────
function togglePinyin() {
    pinyinVisible = !pinyinVisible;
    document.querySelectorAll('.pinyin-text').forEach(el =>
        el.classList.toggle('show', pinyinVisible));
    updatePinyinBtnText();
}

function toggleMeaning() {
    meaningVisible = !meaningVisible;
    document.querySelectorAll('.meaning-text').forEach(el =>
        el.classList.toggle('show', meaningVisible));
    updateMeaningBtnText();
}

function updatePinyinBtnText() {
    const btn = document.getElementById('toggle-pinyin-btn');
    if (btn) {
        btn.innerText = pinyinVisible ? "Hide Pinyin" : "Show Pinyin";
        btn.classList.toggle('primary', pinyinVisible);
    }
}

function updateMeaningBtnText() {
    const btn = document.getElementById('toggle-meaning-btn');
    if (btn) {
        btn.innerText = meaningVisible ? "Hide Meaning" : "Show Meaning";
        btn.classList.toggle('primary', meaningVisible);
    }
}

// ── Passage search (menu screen) ──────────────────────
function filterPassages() {
    const q = document.getElementById('search-input').value.toLowerCase();
    document.querySelectorAll('.passage-section').forEach(sec => {
        let any = false;
        sec.querySelectorAll('.dash-card').forEach(card => {
            const match = card.querySelector('.dash-title').innerText.toLowerCase().includes(q);
            card.style.display = match ? 'flex' : 'none';
            if (match) any = true;
        });
        sec.style.display = any ? 'block' : 'none';
    });
}

// ── Vocab Panel ───────────────────────────────────────
async function openVocabPanel() {
    if (!currentPassage) return;
    const overlay = document.getElementById('vocab-panel-overlay');
    overlay.classList.add('open');

    if (vocabLoaded) return;

    const body = document.getElementById('vocab-panel-body');
    body.innerHTML = '<div class="vocab-loading">Loading vocabulary…</div>';

    try {
        const res = await fetch(`/api/lesson/vocab/${currentPassage.passage_id}`);
        const data = await res.json();
        vocabLoaded = true;
        currentVocabList = data.vocab || [];
        renderVocabTable(currentVocabList);
    } catch (e) {
        body.innerHTML = '<div class="vocab-empty">Failed to load vocabulary.</div>';
    }
}

function closeVocabPanel() {
    document.getElementById('vocab-panel-overlay').classList.remove('open');
}

function closeVocabIfBackground(e) {
    if (e.target.id === 'vocab-panel-overlay') closeVocabPanel();
}

function renderVocabTable(vocab) {
    const body = document.getElementById('vocab-panel-body');

    if (!vocab.length) {
        body.innerHTML = '<div class="vocab-empty">No vocabulary linked to this passage.</div>';
        return;
    }

    const table = document.createElement('table');
    table.className = 'vocab-table vocab-canonical-table';
    table.innerHTML = `
        <thead>
            <tr>
                <th class="vocab-tools-col">
                    <button type="button" class="vocab-header-icon-btn" onclick="playAllVocabAudio()"
                        title="Play all vocabulary audio" aria-label="Play all vocabulary audio">
                        <i class="fa-solid fa-play" aria-hidden="true"></i>
                    </button>
                    <button type="button" class="vocab-header-icon-btn" onclick="shuffleVocab()"
                        title="Shuffle vocabulary" aria-label="Shuffle vocabulary">
                        <i class="fa-solid fa-shuffle" aria-hidden="true"></i>
                    </button>
                </th>
                <th onclick="toggleVocabColumn('cn')">CHARACTER</th>
                <th onclick="toggleVocabColumn('py')">PINYIN</th>
                <th onclick="toggleVocabColumn('vn')">MEANING (VN)</th>
            </tr>
        </thead>
        <tbody id="vocab-tbody"></tbody>`;

    const tbody = table.querySelector('#vocab-tbody');

    vocab.forEach((w, index) => {
        const tr = document.createElement('tr');
        tr.id = `reading-vocab-tr-${index}`;
        const audioCell = w.audio_key
            ? `<button type="button" class="vocab-audio-btn" onclick="playVocabAudio('${escapeAttr(w.audio_key)}')" title="Play word audio" aria-label="Play audio for ${escapeAttr(w.word || w.cn || 'word')}"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>`
            : '<span class="vocab-no-audio">-</span>';
        tr.innerHTML = `
            <td class="vocab-tools-cell">${audioCell}</td>
            <td class="vocab-cn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${escapeHtml(w.word || w.cn || '')}</td>
            <td class="vocab-pinyin clickable-cell" onclick="this.classList.toggle('hidden-cell')">${escapeHtml(w.pinyin || '')}</td>
            <td class="vocab-meaning-vn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${escapeHtml(w.meaning_vn || w.meaning_en || '')}</td>`;
        tbody.appendChild(tr);
    });

    body.innerHTML = '';
    body.appendChild(table);
}

function playVocabAudio(audioKey) {
    const src = `/audio/${audioKey}.mp3`;
    playAudio(src);
}

function toggleVocabColumn(col) {
    const table = document.querySelector('.vocab-table');
    if (table) {
        table.classList.toggle(`hide-${col}`);
    }
}

function shuffleVocab() {
    const popSound = new Audio("data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
    popSound.play().catch(e => console.log('Sound error', e));

    currentVocabList.sort(() => Math.random() - 0.5);
    const oldTable = document.querySelector('.vocab-table');
    const hiddenClasses = Array.from(oldTable?.classList || []).filter(c => c.startsWith('hide-'));

    renderVocabTable(currentVocabList);

    const newTable = document.querySelector('.vocab-table');
    if (newTable) hiddenClasses.forEach(c => newTable.classList.add(c));
}

async function playAllVocabAudio() {
    if (isPlayingAll) {
        isPlayingAll = false;
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
        return;
    }
    isPlayingAll = true;
    for (let i = 0; i < currentVocabList.length; i++) {
        let w = currentVocabList[i];
        if (!isPlayingAll) break;
        if (w.audio_key) {
            document.querySelectorAll('.vocab-table tr').forEach(tr => tr.classList.remove('playing-highlight'));

            const tr = document.getElementById(`reading-vocab-tr-${i}`);
            if (tr) {
                tr.classList.add('playing-highlight');
                tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

            await new Promise(resolve => {
                const src = `/audio/${w.audio_key}.mp3`;
                if (currentAudio) currentAudio.pause();
                currentAudio = new Audio(src);
                currentAudio.onended = resolve;
                currentAudio.onerror = resolve;
                currentAudio.play().catch(resolve);
            });
            if (!isPlayingAll) break;
            await new Promise(resolve => setTimeout(resolve, 600));
        }
    }
    document.querySelectorAll('.vocab-table tr').forEach(tr => tr.classList.remove('playing-highlight'));
    isPlayingAll = false;
}

// ── Start Lesson Practice ─────────────────────────────
function startLessonPractice() {
    openReadingFlashcards();
}

async function openReadingFlashcards() {
    if (!currentPassage) return;

    try {
        let vocab = currentVocabList || [];
        if (!vocab.length) {
            const res = await fetch(`/api/lesson/vocab/${currentPassage.passage_id}`);
            const data = await res.json();
            vocab = data.vocab || [];
        }

        const selectedRows = vocab.map(w => ({
            word: w.word || w.cn || '',
            cn: w.word || w.cn || '',
            pinyin: w.pinyin || '',
            meaning_vn: w.meaning_vn || '',
            meaning_en: w.meaning_en || '',
            audio_key: w.audio_key || '',
            level: w.level || w.hsk_level || currentPassage.hsk_level || ''
        })).filter(w => w.word);

        if (!selectedRows.length) {
            alert('No vocabulary linked to this passage.');
            return;
        }

        sessionStorage.setItem('selectedVocabFlashcards', JSON.stringify(selectedRows));
        window.location.href = '/vocab-learning?source=reading';
    } catch (e) {
        alert('Failed to open flash cards.');
    }
}

function getLessonLines() {
    return Array.isArray(currentPassage?.lines) ? currentPassage.lines : [];
}

function getCurrentLessonLine() {
    return getLessonLines()[currentLessonLineIndex] || null;
}

function getLessonAudioSrc(line) {
    if (!line?.audio_key) return '';
    const rawLevel = String(currentPassage?.hsk_level || 'HSK1');
    const hskLevel = rawLevel.startsWith('HSK') ? rawLevel : `HSK${rawLevel.replace(/^H/i, '')}`;
    return `/lesson_audio/${hskLevel}/${line.audio_key}.mp3`;
}

// ── Lesson Summary ────────────────────────────────────
function renderLessonSummary() {
    const title = document.getElementById('lesson-learner-title');
    const preview = document.getElementById('lesson-learner-preview');
    if (title) {
        title.textContent = window.formatPassageLabel?.(currentPassage?.passage_id, 'Lesson Summary') || 'Lesson Summary';
    }
    if (!preview) return;

    const lines = getLessonLines();
    if (!lines.length) {
        preview.innerHTML = '<div class="lesson-learner-empty">No passage lines found for this lesson part.</div>';
        return;
    }

    prefetchTokens(lines);
    preview.innerHTML = lines.map((line, index) => {
        const audioSrc = getLessonAudioSrc(line);
        const audioBtn = audioSrc
            ? `<button type="button" class="lesson-passage-audio-btn" onclick="playPassageLineAudio(${index})" title="Play passage line ${index + 1}" aria-label="Play passage line ${index + 1}"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>`
            : `<span class="lesson-passage-audio-btn lesson-passage-audio-empty" title="No audio available"></span>`;
        return `
        <div class="lesson-preview-line" id="lesson-preview-line-${index}">
            ${audioBtn}
            <div class="lesson-preview-text">
                <div class="hanzi-text">${renderTokens(line)}</div>
                <div class="pinyin-text lesson-summary-pinyin ${lessonSummaryPinyinVisible ? 'show' : ''}">${escapeHtml(line.pinyin || '')}</div>
                <div class="meaning-text lesson-summary-meaning ${lessonSummaryMeaningVisible ? 'show' : ''}">${escapeHtml(line.translations?.vi || line.translations?.en || '')}</div>
            </div>
        </div>`;
    }).join('');
    updateLessonSummaryToggleText();
}

function playPassageLineAudio(index) {
    const lines = getLessonLines();
    const line = lines[index];
    if (!line) return;
    const src = getLessonAudioSrc(line);
    if (src) {
        document.querySelectorAll('.lesson-preview-line').forEach(el => el.classList.remove('playing-highlight'));
        const lineEl = document.getElementById(`lesson-preview-line-${index}`);
        if (lineEl) lineEl.classList.add('playing-highlight');

        if (currentAudio) {
            currentAudio.pause();
            currentAudio.onended = null;
            currentAudio.onerror = null;
        }
        currentAudio = new Audio(src);
        currentAudio.onended = () => { if (lineEl) lineEl.classList.remove('playing-highlight'); };
        currentAudio.onerror = () => { if (lineEl) lineEl.classList.remove('playing-highlight'); };
        currentAudio.play().catch(e => {
            if (lineEl) lineEl.classList.remove('playing-highlight');
            console.warn("Audio failed", e);
        });
    }
}

function backToPartPicker() {
    resetLessonSpeakingPractice(true);
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    if (currentPassage?.passage_id) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(currentPassage.passage_id)}&show_parts=true`;
        return;
    }
    goHome();
}

function showLessonSummary() {
    resetLessonSpeakingPractice(true);
    renderLessonSummary();
    switchScreen('screen-lesson-summary');
}

function toggleLessonSummaryPinyin() {
    lessonSummaryPinyinVisible = !lessonSummaryPinyinVisible;
    document.querySelectorAll('.lesson-summary-pinyin').forEach(el => {
        el.classList.toggle('show', lessonSummaryPinyinVisible);
    });
    updateLessonSummaryToggleText();
}

function toggleLessonSummaryMeaning() {
    lessonSummaryMeaningVisible = !lessonSummaryMeaningVisible;
    document.querySelectorAll('.lesson-summary-meaning').forEach(el => {
        el.classList.toggle('show', lessonSummaryMeaningVisible);
    });
    updateLessonSummaryToggleText();
}

function updateLessonSummaryToggleText() {
    const pinyinBtn = document.getElementById('lesson-toggle-pinyin-btn');
    const meaningBtn = document.getElementById('lesson-toggle-meaning-btn');
    if (pinyinBtn) {
        pinyinBtn.textContent = lessonSummaryPinyinVisible ? 'Hide Pinyin' : 'Show Pinyin';
        pinyinBtn.classList.toggle('primary', lessonSummaryPinyinVisible);
    }
    if (meaningBtn) {
        meaningBtn.textContent = lessonSummaryMeaningVisible ? 'Hide Meaning' : 'Show Meaning';
        meaningBtn.classList.toggle('primary', lessonSummaryMeaningVisible);
    }
}

// ── Lesson Cards ──────────────────────────────────────
function startLessonCards() {
    currentLessonLineIndex = 0;
    renderLessonCard();
    switchScreen('screen-lesson-card');
}

function renderLessonCard() {
    resetLessonSpeakingPractice(true);
    const line = getCurrentLessonLine();
    const lines = getLessonLines();
    if (!line || !lines.length) {
        showLessonSummary();
        return;
    }

    document.getElementById('lesson-card-counter').textContent = `${currentLessonLineIndex + 1} / ${lines.length}`;
    document.getElementById('lesson-card-progress-fill').style.width = `${((currentLessonLineIndex + 1) / lines.length) * 100}%`;
    document.getElementById('lesson-card-hanzi').textContent = line.content || '';
    document.getElementById('lesson-card-pinyin').textContent = line.pinyin || '';
    document.getElementById('lesson-card-meaning').textContent = line.translations?.vi || line.translations?.en || '';

    const input = document.getElementById('lesson-card-typing-input');
    if (input) {
        input.value = '';
        input.classList.remove('success-highlight');
    }

    const audio = document.getElementById('lesson-card-audio');
    const src = getLessonAudioSrc(line);
    if (src) {
        audio.src = src;
        document.getElementById('lesson-card-audio-btn').disabled = false;
        audio.play().catch(() => { });
    } else {
        audio.removeAttribute('src');
        document.getElementById('lesson-card-audio-btn').disabled = true;
    }

    document.getElementById('lesson-card-prev').disabled = currentLessonLineIndex === 0;
    const nextBtn = document.getElementById('lesson-card-next');
    nextBtn.textContent = currentLessonLineIndex === lines.length - 1 ? 'Finish' : 'Next';
}

function prevLessonCard() {
    if (currentLessonLineIndex <= 0) return;
    currentLessonLineIndex--;
    renderLessonCard();
}

function nextLessonCard() {
    const lines = getLessonLines();
    if (currentLessonLineIndex < lines.length - 1) {
        currentLessonLineIndex++;
        renderLessonCard();
        return;
    }
    showLessonSummary();
}

function playLessonCardAudio() {
    const audio = document.getElementById('lesson-card-audio');
    if (audio?.src) {
        audio.currentTime = 0;
        audio.play().catch(e => console.warn("Audio failed", e));
    }
}

// ── Lesson Trainer & navigation ───────────────────────
async function toggleLessonSpeakingPractice() {
    if (lessonSpeakingRecorder?.state === 'recording') {
        stopLessonSpeakingRecording();
        return;
    }

    const line = getCurrentLessonLine();
    if (!line?.content) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        showLessonSpeakingMessage('Your browser does not support audio recording.', true);
        return;
    }

    resetLessonSpeakingPractice(false);
    const attemptId = ++lessonSpeakingAttemptId;
    lessonSpeakingChunks = [];

    try {
        lessonSpeakingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mimeType = getLessonSpeakingMimeType();
        lessonSpeakingRecorder = mimeType
            ? new MediaRecorder(lessonSpeakingStream, { mimeType })
            : new MediaRecorder(lessonSpeakingStream);
        lessonSpeakingRecorder.ondataavailable = event => {
            if (event.data?.size) lessonSpeakingChunks.push(event.data);
        };
        lessonSpeakingRecorder.onstop = () => submitLessonSpeakingRecording(
            attemptId,
            line.content,
            mimeType
        );
        lessonSpeakingRecorder.start();
        setLessonSpeakingButtonState('recording');
        showLessonSpeakingMessage('Recording... say the sentence clearly.');
        lessonSpeakingTimer = setTimeout(stopLessonSpeakingRecording, LESSON_SPEAKING_MAX_MS);
    } catch (error) {
        console.error(error);
        resetLessonSpeakingPractice(false);
        showLessonSpeakingMessage('Microphone access was blocked. Allow microphone permission and try again.', true);
    }
}

function getLessonSpeakingMimeType() {
    return [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/ogg'
    ].find(type => MediaRecorder.isTypeSupported(type)) || '';
}

function stopLessonSpeakingRecording() {
    if (lessonSpeakingTimer) {
        clearTimeout(lessonSpeakingTimer);
        lessonSpeakingTimer = null;
    }
    if (lessonSpeakingRecorder?.state === 'recording') {
        setLessonSpeakingButtonState('scoring');
        showLessonSpeakingMessage('Scoring your pronunciation...');
        lessonSpeakingRecorder.stop();
    }
    stopLessonSpeakingStream();
}

function stopLessonSpeakingStream() {
    if (!lessonSpeakingStream) return;
    lessonSpeakingStream.getTracks().forEach(track => track.stop());
    lessonSpeakingStream = null;
}

async function submitLessonSpeakingRecording(attemptId, targetSentence, mimeType) {
    stopLessonSpeakingStream();
    if (attemptId !== lessonSpeakingAttemptId) return;
    if (!lessonSpeakingChunks.length) {
        setLessonSpeakingButtonState('idle');
        showLessonSpeakingMessage('No audio was recorded. Please try again.', true);
        return;
    }

    const blobType = mimeType || lessonSpeakingChunks[0]?.type || 'audio/webm';
    const extension = blobType.includes('ogg') ? 'ogg' : 'webm';
    const formData = new FormData();
    formData.append('word', targetSentence);
    formData.append('audio', new Blob(lessonSpeakingChunks, { type: blobType }), `lesson-speaking.${extension}`);

    try {
        const response = await fetch('/api/vocab/speaking/score', { method: 'POST', body: formData });
        const data = await response.json();
        if (attemptId !== lessonSpeakingAttemptId) return;
        setLessonSpeakingButtonState('idle');
        if (!response.ok || data.error) {
            showLessonSpeakingMessage(data.error || 'Could not score this recording. Please try again.', true);
            return;
        }
        renderLessonSpeakingResult(data);
    } catch (error) {
        console.error(error);
        if (attemptId !== lessonSpeakingAttemptId) return;
        setLessonSpeakingButtonState('idle');
        showLessonSpeakingMessage('Could not connect to the speaking scorer. Please try again.', true);
    }
}

function resetLessonSpeakingPractice(stopActiveRecording) {
    lessonSpeakingAttemptId += 1;
    if (lessonSpeakingTimer) {
        clearTimeout(lessonSpeakingTimer);
        lessonSpeakingTimer = null;
    }
    if (stopActiveRecording && lessonSpeakingRecorder?.state === 'recording') {
        lessonSpeakingRecorder.onstop = null;
        lessonSpeakingRecorder.stop();
    }
    stopLessonSpeakingStream();
    lessonSpeakingRecorder = null;
    lessonSpeakingChunks = [];
    setLessonSpeakingButtonState('idle');

    const panel = document.getElementById('lesson-speaking-panel');
    const result = document.getElementById('lesson-speaking-result');
    if (panel) panel.style.display = 'none';
    if (result) {
        result.style.display = 'none';
        result.innerHTML = '';
        result.className = 'vl-speaking-result';
    }
}

function setLessonSpeakingButtonState(state) {
    const button = document.getElementById('lesson-card-speak-btn');
    if (!button) return;
    button.classList.toggle('recording', state === 'recording');
    button.disabled = state === 'scoring';
    const label = button.querySelector('span');
    if (label) label.textContent = state === 'recording' ? 'Stop' : state === 'scoring' ? 'Scoring...' : 'Speak';
}

function showLessonSpeakingMessage(message, isError = false) {
    const panel = document.getElementById('lesson-speaking-panel');
    const status = document.getElementById('lesson-speaking-status');
    const result = document.getElementById('lesson-speaking-result');
    if (panel) panel.style.display = 'block';
    if (status) {
        status.textContent = message;
        status.style.color = isError ? 'var(--danger)' : 'var(--text-muted)';
    }
    if (result) {
        result.style.display = 'none';
        result.innerHTML = '';
    }
}

function renderLessonSpeakingResult(data) {
    const panel = document.getElementById('lesson-speaking-panel');
    const status = document.getElementById('lesson-speaking-status');
    const result = document.getElementById('lesson-speaking-result');
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

function goToLessonTrainer() {
    if (!currentPassage?.passage_id) return;
    const params = new URLSearchParams({ passage_id: currentPassage.passage_id });
    if (isLessonPartFlow) params.set('flow', 'lesson-part');
    window.location.href = `/lesson?${params.toString()}`;
}

function goToWordSummary() {
    if (!currentPassage?.passage_id) return;
    window.location.href = `/vocab-learning?passage_id=${encodeURIComponent(currentPassage.passage_id)}&flow=lesson-part`;
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

// ── Token rendering ───────────────────────────────────────────────────────────
const PUNCT_RE = /^[　-〿＀-￯。，、；：？！…—～·「」『』【】《》〈〉""''()（）\[\]{}<>,.!?;:'"\/\\|\s]+$/;
const _wordCache = new Map();

function renderTokens(line) {
    const tokens = line.tokens;
    if (!tokens || tokens.length === 0) return escapeHtml(line.content || '');
    return tokens.map(tok => {
        if (PUNCT_RE.test(tok)) {
            return `<span class="line-token">${escapeHtml(tok)}</span>`;
        }
        return `<span class="line-token clickable" onclick="showWordPopup('${escapeAttr(tok)}')">${escapeHtml(tok)}</span>`;
    }).join('');
}

async function prefetchTokens(lines) {
    const words = [...new Set(
        lines.flatMap(l => (l.tokens || []).filter(t => !PUNCT_RE.test(t)))
    )].filter(w => !_wordCache.has(w));
    if (!words.length) return;
    try {
        const res = await fetch(`/api/vocab/lookup-batch?words=${encodeURIComponent(words.join(','))}`);
        const data = await res.json();
        for (const [word, info] of Object.entries(data)) {
            _wordCache.set(word, info);
        }
        words.forEach(w => { if (!_wordCache.has(w)) _wordCache.set(w, null); });
    } catch (e) {
        words.forEach(w => _wordCache.set(w, null));
    }
}

// ── Word popup ────────────────────────────────────────────────────────────────
let _popupAudioKey = null;
let _popupWord = null;
let _popupWriters = [];
let _popupStrokeOpen = false;
let _popupActiveCharIdx = 0;

function showWordPopup(word) {
    _popupWord = word;
    _popupAudioKey = null;
    _popupWriters = [];
    _popupStrokeOpen = false;
    _popupActiveCharIdx = 0;

    const cached = _wordCache.get(word);
    const notFound = cached === null || cached === undefined;
    const pinyin    = cached?.pinyin     || '';
    const meaningVn = cached?.meaning_vn || '';
    const meaningEn = cached?.meaning_en || '';
    _popupAudioKey  = cached?.audio_key  || null;

    document.getElementById('word-popup-hanzi').textContent = word;
    document.getElementById('word-popup-pinyin').textContent = pinyin;
    document.getElementById('word-popup-meaning-vn').textContent = notFound ? '' : meaningVn;
    document.getElementById('word-popup-meaning-en').textContent = meaningEn;
    if (notFound) {
        document.getElementById('word-popup-meaning-vn').innerHTML = '<span class="word-popup-not-found">Not found in vocabulary</span>';
    }
    document.getElementById('word-popup-stroke-area').style.display = 'none';
    document.getElementById('word-stroke-tabs').innerHTML = '';
    document.getElementById('word-stroke-container').innerHTML = '';
    document.getElementById('word-popup-stroke-btn').classList.remove('active');
    document.getElementById('word-popup-overlay').classList.add('open');
}

function closeWordPopup() {
    document.getElementById('word-popup-overlay').classList.remove('open');
    _popupWriters.forEach(w => { try { w.cancelAnimation(); } catch(_) {} });
    _popupWriters = [];
    _popupStrokeOpen = false;
}

function playWordPopupAudio() {
    if (!_popupAudioKey) return;
    const hskLevel = currentPassage?.hsk_level || 'HSK1';
    const src = `/audio/${_popupAudioKey}.mp3`;
    playAudio(src);
}

function toggleWordStroke() {
    _popupStrokeOpen = !_popupStrokeOpen;
    const area = document.getElementById('word-popup-stroke-area');
    const btn = document.getElementById('word-popup-stroke-btn');
    btn.classList.toggle('active', _popupStrokeOpen);
    if (_popupStrokeOpen) {
        area.style.display = 'block';
        _buildWordStroke(_popupWord || '', 0);
    } else {
        area.style.display = 'none';
        _popupWriters.forEach(w => { try { w.cancelAnimation(); } catch(_) {} });
        _popupWriters = [];
    }
}

function _buildWordStroke(word, charIdx) {
    const chars = [...word];
    if (!chars.length) return;
    _popupActiveCharIdx = charIdx;

    const tabs = document.getElementById('word-stroke-tabs');
    tabs.innerHTML = chars.map((ch, i) =>
        `<button class="stroke-tab${i === charIdx ? ' active' : ''}" onclick="_buildWordStroke('${escapeAttr(word)}', ${i})">${escapeHtml(ch)}</button>`
    ).join('');

    const container = document.getElementById('word-stroke-container');
    container.innerHTML = '';
    _popupWriters.forEach(w => { try { w.cancelAnimation(); } catch(_) {} });
    _popupWriters = [];

    const writer = HanziWriter.create(container, chars[charIdx], {
        width: 200, height: 200,
        padding: 10,
        showOutline: true,
        strokeColor: '#576856',
        outlineColor: 'rgba(87,104,86,0.15)',
    });
    _popupWriters = [writer];
}

function wordStrokeAnimate() {
    _popupWriters.forEach(w => w.animateCharacter());
}

function wordStrokeQuiz() {
    _popupWriters.forEach(w => w.quiz());
}

function wordStrokeReset() {
    const word = _popupWord || '';
    const chars = [...word];
    if (chars[_popupActiveCharIdx]) _buildWordStroke(word, _popupActiveCharIdx);
}
