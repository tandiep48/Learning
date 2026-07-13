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
let isLessonPartFlow = false;

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const selectedFlashcards = readSelectedFlashcards();
    const params = new URLSearchParams(window.location.search);
    const autoPassageId = params.get('passage_id');
    isLessonPartFlow = params.get('flow') === 'lesson-part';
    Picker.init((passage) => {
        startLesson(passage);
    }, t('vocab_learning.picker_title'), !selectedFlashcards && !autoPassageId);

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
    updateLessonSummaryNavigation();
    updateWordSummaryTitle();
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
        const passageId = encodeURIComponent(passage.passage_id);
        const res = await fetch(`/api/lesson/vocab/${passageId}`);
        const data = await res.json();

        if (!res.ok || data.error) {
            alert(data.error || t('vocab_learning.failed_load_words'));
            backToLessons();
            return;
        }

        // Deduplicate tasks → one entry per unique word
        const seen = new Set();
        words = [];
        for (const row of (data.vocab || [])) {
            const word = normalizeFlashcardWord(row);
            if (word.word && !seen.has(word.word)) {
                seen.add(word.word);
                words.push(word);
            }
        }

        if (words.length === 0) {
            alert(t('vocab_learning.no_words_found'));
            backToLessons();
            return;
        }

        currentIndex = 0;
        loadingEl.style.display = 'none';
        // Show summary first instead of going straight to flash cards
        tableVocabList = [...words];
        renderVocabTable();
        updateLessonSummaryNavigation();
        updateWordSummaryTitle();
        showWordSummaryScreen();

    } catch (e) {
        console.error('Failed to load Word Summary:', e);
        alert(t('lesson.error_connecting'));
        backToLessons();
    }
}

function showWordSummaryScreen() {
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    document.getElementById('screen-loading').style.display = 'none';
    document.getElementById('screen-learning').style.display = 'none';
    updateWordSummaryTitle();
    document.getElementById('screen-summary').style.display = 'block';
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
        setAudioPlaying(true);
        audio.onended = () => setAudioPlaying(false);
        audio.onerror = () => setAudioPlaying(false);
        audio.play().catch(() => setAudioPlaying(false));
    } else {
        audio.removeAttribute('src');
        setAudioPlaying(false);
    }
}

function setAudioPlaying(playing) {
    const btn = document.getElementById('btn-audio');
    if (playing) {
        btn.classList.add('playing');
        btn.innerHTML = '<i class="fa-solid fa-pause" aria-hidden="true"></i><span>Pause Audio</span>';
    } else {
        btn.classList.remove('playing');
        btn.innerHTML = '<i class="fa-solid fa-play" aria-hidden="true"></i><span>Play Audio</span>';
    }
}

// ─── Controls ─────────────────────────────────────────────────────────────────

function playAudio() {
    const audio = document.getElementById('vl-audio');
    if (audio.src) {
        if (!audio.paused) {
            audio.pause();
            setAudioPlaying(false);
            return;
        }
        audio.currentTime = 0;
        audio.play().catch(() => { });
        setAudioPlaying(true);
        audio.onended = () => setAudioPlaying(false);
        audio.onerror = () => setAudioPlaying(false);
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
        showSpeakingMessage(t('vocab_trainer.no_audio_support'), true);
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
        showSpeakingMessage(t('vocab_trainer.recording_status'));
        speakingTimer = setTimeout(stopSpeakingRecording, SPEAKING_MAX_MS);
    } catch (e) {
        console.error(e);
        resetSpeakingPractice(false);
        showSpeakingMessage(t('reading.mic_blocked'), true);
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
        showSpeakingMessage(t('reading.scoring_pronunciation'));
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
        showSpeakingMessage(t('vocab_trainer.no_audio_recorded'), true);
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
            showSpeakingMessage(data.error || t('reading.score_failed_sentence'), true);
            return;
        }

        renderSpeakingResult(data);
    } catch (e) {
        console.error(e);
        if (attemptId !== speakingAttemptId) return;
        setSpeakingButtonState('idle');
        showSpeakingMessage(t('reading.scorer_connect_failed'), true);
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
        button.textContent = t('vocab_trainer.stop');
    } else if (state === 'scoring') {
        button.textContent = t('vocab_trainer.scoring');
    } else {
        button.textContent = t('vocab_trainer.speak');
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
        status.textContent = data.message || (data.is_correct ? t('reading.nice_pronunciation') : t('reading.try_again'));
        status.style.color = data.is_correct ? 'var(--success)' : 'var(--danger)';
    }
    if (!result) return;

    result.className = `vl-speaking-result ${data.is_correct ? 'success' : 'retry'}`;
    result.innerHTML = `
        <div class="speaking-row"><span class="speaking-label">${t('reading.score_label')}</span><strong>${escapeHtml(data.score)} / 100</strong></div>
        <div class="speaking-row"><span class="speaking-label">${t('reading.heard_label')}</span><span>${escapeHtml(data.recognized_text || '-')}</span></div>
        <div class="speaking-row"><span class="speaking-label">${t('reading.expected_pinyin_label')}</span><span>${escapeHtml(data.expected_pinyin || '-')}</span></div>
        <div class="speaking-row"><span class="speaking-label">${t('reading.heard_pinyin_label')}</span><span>${escapeHtml(data.recognized_pinyin || '-')}</span></div>
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

function shuffleLearningWords() {
    if (!words || words.length <= 1) return;
    resetSpeakingPractice(true);
    const audio = document.getElementById('vl-audio');
    if (audio) {
        audio.pause();
        audio.currentTime = 0;
    }
    for (let i = words.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [words[i], words[j]] = [words[j], words[i]];
    }
    currentIndex = 0;
    renderWord();
}

function backToLessons() {
    resetSpeakingPractice(true);
    stopSummaryAudio();

    if (lessonMeta?.passage_id) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(lessonMeta.passage_id)}&show_parts=true`;
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
    if (audio) {
        audio.pause();
        audio.removeAttribute('src');
    }
}

function startLearningCards() {
    stopSummaryAudio();
    // Called from Summary screen – switch to flash card learning view
    currentIndex = 0;
    document.getElementById('screen-summary').style.display = 'none';
    document.getElementById('screen-learning').style.display = 'block';
    renderWord();
}

function showVocabSummary() {
    resetSpeakingPractice(true);
    document.getElementById('screen-learning').style.display = 'none';
    document.getElementById('screen-summary').style.display = 'block';
}

function goToTrainer() {
    if (!lessonMeta) return;
    if (lessonMeta.source === 'selection') {
        sessionStorage.setItem('selectedVocabTrainerWords', JSON.stringify(lessonMeta.selected_words || []));
        window.location.href = '/vocab-training';
        return;
    }
    // Deep-link to vocab trainer with URL params so it auto-starts
    const params = new URLSearchParams({
        mode: '6',
        passage_id: lessonMeta.passage_id
    });
    if (isLessonPartFlow) params.set('flow', 'lesson-part');
    window.location.href = `/vocab-training?${params.toString()}`;
}

function goToLessonSummary() {
    if (!lessonMeta?.passage_id) return;
    window.location.href = `/reading?passage_id=${encodeURIComponent(lessonMeta.passage_id)}&mode=lesson-learner&flow=lesson-part`;
}

// ─── Keyboard Shortcuts ───────────────────────────────────────────────────────

function updateLessonSummaryNavigation() {
    const button = document.getElementById('lesson-summary-nav-btn');
    if (!button) return;
    button.hidden = !lessonMeta?.passage_id;
}

function updateWordSummaryTitle() {
    if (window.buildBreadcrumb) {
        window.buildBreadcrumb('vocab-breadcrumb', lessonMeta?.passage_id);
    }
}

document.addEventListener('keydown', (e) => {
    if (document.getElementById('screen-learning').style.display === 'none') return;
    if (e.key === 'ArrowLeft') prevWord();
    if (e.key === 'ArrowRight') nextWord();
    if (e.key === ' ') { e.preventDefault(); playAudio(); }
});

// ─── Summary Table ────────────────────────────────────────────────────────────

let isAudioPlaying = false;
let audioQueue = [];
let tableVocabList = [];
let summaryAudio = null;
let summaryHiddenCells = new Set();
let summaryHiddenColumns = new Set();
let summaryRevealedColumnCells = new Set();
let activeSummaryAudioButton = null;
let activeSummaryAudioRevealRow = null;

function showVocabSummary() {
    resetSpeakingPractice(true);
    document.getElementById('screen-learning').style.display = 'none';
    document.getElementById('screen-summary').style.display = 'block';

    // Stop any learning audio
    const audio = document.getElementById('vl-audio');
    audio.pause();

    tableVocabList = [...words];
    renderVocabTable();
    updateLessonSummaryNavigation();
}

function renderVocabTable() {
    const container = document.getElementById('vl-summary-body');

    if (!tableVocabList || tableVocabList.length === 0) {
        container.innerHTML = `<div class="vocab-empty">No vocabulary available for this lesson.</div>`;
        return;
    }

    const tableId = 'vl-summary-table';
    let html = `
        <table class="vocab-table vocab-canonical-table" id="${tableId}">
            <thead>
                <tr>
                    <th class="vocab-tools-col">
                        <button type="button" onclick="event.stopPropagation(); strokeOrderAllSummary()"
                            id="vl-summary-stroke-all-btn" class="vocab-header-icon-btn" title="${t('vocab.stroke_all_aria')}"
                            aria-label="${t('vocab.stroke_all_aria')}"><i class="fa-solid fa-paintbrush" aria-hidden="true"></i></button>
                        <button type="button" onclick="event.stopPropagation(); playAllVocabAudio()"
                            id="vl-summary-play-all-btn" class="vocab-header-icon-btn" title="${t('reading.play_all_vocab_audio')}"
                            aria-label="${t('reading.play_all_vocab_audio')}"><i class="fa-solid fa-play" aria-hidden="true"></i></button>
                    </th>
                    <th class="vocab-no-col">
                        <button type="button" onclick="event.stopPropagation(); shuffleVocab()"
                            class="vocab-header-icon-btn" title="${t('reading.shuffle_vocab_audio')}"
                            aria-label="${t('reading.shuffle_vocab_audio')}"><i class="fa-solid fa-shuffle" aria-hidden="true"></i></button>
                    </th>
                    <th>${renderSummaryColumnHeader('cn', t('dashboard.table_character').toUpperCase(), tableId)}</th>
                    <th>${renderSummaryColumnHeader('py', t('dashboard.table_pinyin').toUpperCase(), tableId)}</th>
                    <th>${renderSummaryColumnHeader('vn', t('dashboard.table_meaning_vn').toUpperCase(), tableId)}</th>
                </tr>
            </thead>
            <tbody>
    `;

    tableVocabList.forEach((v, index) => {
        const word = v.word || '';
        const audioBtn = v.audio_key
            ? `<button type="button" class="vocab-audio-btn" onclick="playSingleVocabAudio('${escapeAttr(v.audio_key)}', ${escapeJsArg(word)}, this)" title="${t('reading.play_word_audio')}" aria-label="${escapeAttr(t('reading.play_audio_for', { word: v.word || 'word' }))}"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>`
            : `<span class="vocab-no-audio" title="${t('reading.no_audio_available')}">-</span>`;
        const hasChineseChars = /[\u4e00-\u9fff]/.test(v.word || '');
        const strokeBtn = hasChineseChars
            ? `<button type="button" class="vocab-stroke-row-btn" onclick="openStrokeModalForWord('${escapeAttr(v.word)}', '${escapeAttr(v.pinyin || '')}')" title="${t('vocab_learning.show_stroke_order_aria')}" aria-label="${t('vocab_learning.show_stroke_order_aria')}"><i class="fa-solid fa-paintbrush" aria-hidden="true"></i></button>`
            : '';
        html += `
            <tr id="vl-tr-${index}" data-audio="${escapeAttr(v.audio_key || '')}">
                <td class="vocab-tools-cell">${strokeBtn}${audioBtn}</td>
                <td class="vocab-no-cell">${index + 1}</td>
                <td class="vocab-cn clickable-cell ${getSummaryCellClasses(word, 'cn')}" onclick="toggleSummaryVocabCell(this, 'cn', ${escapeJsArg(word)}, '${tableId}')">${escapeHtml(v.word || '')}</td>
                <td class="vocab-pinyin clickable-cell ${getSummaryCellClasses(word, 'py')}" onclick="toggleSummaryVocabCell(this, 'py', ${escapeJsArg(word)}, '${tableId}')">${escapeHtml(v.pinyin || '')}</td>
                <td class="vocab-meaning-vn clickable-cell ${getSummaryCellClasses(word, 'vn')}" onclick="toggleSummaryVocabCell(this, 'vn', ${escapeJsArg(word)}, '${tableId}')">${escapeHtml(v.meaning_vn || v.meaning_en || '')}</td>
            </tr>
        `;
    });

    html += `
            </tbody>
        </table>`;
    container.innerHTML = html;
    const table = document.getElementById(tableId);
    ['cn', 'py', 'vn'].forEach(col => table?.classList.toggle(`hide-${col}`, summaryHiddenColumns.has(col)));
}

function escapeAttr(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
        .replace(/`/g, '&#096;');
}

function escapeJsArg(value) {
    return JSON.stringify(String(value ?? '')).replace(/"/g, '&quot;');
}

function renderSummaryColumnHeader(colType, label, tableId) {
    const isHidden = summaryHiddenColumns.has(colType);
    return `
        <span class="vocab-column-header-label">${escapeHtml(label)}</span>
        <button type="button" class="vocab-column-toggle" data-summary-col="${colType}" onclick="event.stopPropagation(); toggleVocabColumn('${colType}', '${tableId}')" title="${isHidden ? t('vocab.show') : t('vocab.hide')} ${escapeAttr(label)}" aria-label="${isHidden ? t('vocab.show') : t('vocab.hide')} ${escapeAttr(label)}">
            <i class="fa-solid ${isHidden ? 'fa-eye' : 'fa-eye-slash'}" aria-hidden="true"></i>
        </button>
    `;
}

function toggleVocabColumn(colType, tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    tableVocabList.forEach(row => summaryRevealedColumnCells.delete(getSummaryHiddenCellKey(row.word || '', colType)));
    if (summaryHiddenColumns.has(colType)) summaryHiddenColumns.delete(colType);
    else {
        summaryHiddenColumns.add(colType);
        tableVocabList.forEach(row => summaryHiddenCells.delete(getSummaryHiddenCellKey(row.word || '', colType)));
    }
    table.classList.toggle(`hide-${colType}`, summaryHiddenColumns.has(colType));
    updateSummaryColumnToggleIcon(colType);
    refreshSummaryCellVisibility();
}

function toggleSummaryVocabCell(cell, colType, word, tableId) {
    const table = document.getElementById(tableId);
    const key = getSummaryHiddenCellKey(word, colType);
    if (table?.classList.contains(`hide-${colType}`)) {
        const shouldReveal = !summaryRevealedColumnCells.has(key);
        if (shouldReveal) summaryRevealedColumnCells.add(key);
        else summaryRevealedColumnCells.delete(key);
        cell.classList.toggle('column-cell-revealed', shouldReveal);
        return;
    }
    const shouldHide = !cell.classList.contains('hidden-cell');
    cell.classList.toggle('hidden-cell', shouldHide);
    if (shouldHide) summaryHiddenCells.add(key);
    else summaryHiddenCells.delete(key);
}

function updateSummaryColumnToggleIcon(colType) {
    const button = document.querySelector(`.vocab-column-toggle[data-summary-col="${colType}"]`);
    if (!button) return;
    const icon = button.querySelector('.fa-solid');
    const isHidden = summaryHiddenColumns.has(colType);
    icon?.classList.toggle('fa-eye', isHidden);
    icon?.classList.toggle('fa-eye-slash', !isHidden);
    button.title = `${isHidden ? t('vocab.show') : t('vocab.hide')} ${t('vocab.column_label')}`;
    button.setAttribute('aria-label', button.title);
}

function getSummaryHiddenCellKey(word, colType) {
    return `${word || ''}::${colType}`;
}

function getSummaryCellClasses(word, colType) {
    const key = getSummaryHiddenCellKey(word, colType);
    return [
        summaryHiddenCells.has(key) ? 'hidden-cell' : '',
        summaryRevealedColumnCells.has(key) ? 'column-cell-revealed' : ''
    ].filter(Boolean).join(' ');
}

function refreshSummaryCellVisibility() {
    tableVocabList.forEach((row, index) => {
        const word = row.word || '';
        const tr = document.getElementById(`vl-tr-${index}`);
        if (!tr) return;
        [
            ['cn', '.vocab-cn'],
            ['py', '.vocab-pinyin'],
            ['vn', '.vocab-meaning-vn']
        ].forEach(([colType, selector]) => {
            const cell = tr.querySelector(selector);
            const key = getSummaryHiddenCellKey(word, colType);
            cell?.classList.toggle('hidden-cell', summaryHiddenCells.has(key));
            cell?.classList.toggle('column-cell-revealed', summaryHiddenColumns.has(colType) && summaryRevealedColumnCells.has(key));
        });
    });
}

function revealSummaryRowForAudio(rowIndex) {
    restoreSummaryAudioReveal();
    const row = document.getElementById(`vl-tr-${rowIndex}`);
    if (!row) return;
    row.classList.add('audio-revealed');
    activeSummaryAudioRevealRow = row;
}

function restoreSummaryAudioReveal() {
    activeSummaryAudioRevealRow?.classList.remove('audio-revealed');
    activeSummaryAudioRevealRow = null;
}

function shuffleVocab() {
    if (!tableVocabList || tableVocabList.length === 0) return;
    stopSummaryAudio();
    for (let i = tableVocabList.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [tableVocabList[i], tableVocabList[j]] = [tableVocabList[j], tableVocabList[i]];
    }
    renderVocabTable();
}

function setSummaryAudioButtonPlaying(button, playing) {
    const icon = button?.querySelector('.fa-solid');
    if (!icon) return;
    // Row buttons show a speaker icon at rest; the header "play all" button shows a play icon.
    const isRowButton = button.classList.contains('vocab-audio-btn');
    const restIcon = isRowButton ? 'fa-volume-high' : 'fa-play';
    icon.classList.toggle(restIcon, !playing);
    icon.classList.toggle('fa-pause', playing);
    icon.classList.toggle('play-icon', !playing && !isRowButton);
}

function resetSummaryAudioButtons() {
    if (activeSummaryAudioButton) setSummaryAudioButtonPlaying(activeSummaryAudioButton, false);
    activeSummaryAudioButton = null;
    setSummaryAudioButtonPlaying(document.getElementById('vl-summary-play-all-btn'), false);
    restoreSummaryAudioReveal();
}

function playSingleVocabAudio(audioKey, word = '', button = null) {
    stopSummaryAudio();
    const rowIndex = tableVocabList.findIndex(row => (row.word || '') === word);
    if (rowIndex !== -1) revealSummaryRowForAudio(rowIndex);
    summaryAudio = new Audio(`/audio/${audioKey}.mp3`);
    activeSummaryAudioButton = button;
    setSummaryAudioButtonPlaying(button, true);
    summaryAudio.onended = resetSummaryAudioButtons;
    summaryAudio.onerror = resetSummaryAudioButtons;
    summaryAudio.play().catch(e => {
        resetSummaryAudioButtons();
        console.log('Audio play failed:', e);
    });
}

function playAllVocabAudio() {
    if (isAudioPlaying) {
        stopSummaryAudio();
        return;
    }

    // Create a queue of words that have audio, store their index
    audioQueue = tableVocabList.map((v, i) => ({ ...v, originalIndex: i })).filter(v => v.audio_key);
    if (audioQueue.length === 0) return;

    isAudioPlaying = true;
    resetSummaryAudioButtons();
    setSummaryAudioButtonPlaying(document.getElementById('vl-summary-play-all-btn'), true);
    playNextInQueue();
}

function playNextInQueue() {
    // Clear previous highlights
    document.querySelectorAll('#vl-summary-table tr').forEach(tr => tr.classList.remove('playing-highlight'));

    if (!isAudioPlaying || audioQueue.length === 0) {
        isAudioPlaying = false;
        resetSummaryAudioButtons();
        return;
    }

    const nextWord = audioQueue.shift();

    // Highlight the row
    const tr = document.getElementById(`vl-tr-${nextWord.originalIndex}`);
    if (tr) {
        tr.classList.add('playing-highlight');
        tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    revealSummaryRowForAudio(nextWord.originalIndex);

    summaryAudio = new Audio(`/audio/${nextWord.audio_key}.mp3`);

    summaryAudio.onended = () => {
        restoreSummaryAudioReveal();
        setTimeout(playNextInQueue, 800);
    };

    summaryAudio.onerror = () => {
        restoreSummaryAudioReveal();
        setTimeout(playNextInQueue, 300);
    };

    summaryAudio.play().catch(e => {
        console.log('Audio play failed:', e);
        restoreSummaryAudioReveal();
        setTimeout(playNextInQueue, 300);
    });
}

function stopSummaryAudio() {
    isAudioPlaying = false;
    audioQueue = [];
    if (summaryAudio) {
        summaryAudio.pause();
        summaryAudio = null;
    }
    resetSummaryAudioButtons();
    document.querySelectorAll('#vl-summary-table tr').forEach(tr => tr.classList.remove('playing-highlight'));
}

// ─── Stroke Order Modal ───────────────────────────────────────────────────────

let strokeWriter = null;         // current HanziWriter instance
let strokeChars = [];            // array of individual characters
let strokeCharIndex = 0;         // which character tab is active
let strokeQuizMode = false;

// Open stroke modal for a specific word/pinyin (used from summary table rows)
function openStrokeModalForWord(word, pinyin) {
    if (!word) return;
    stopStrokeOrderAllSummary();
    strokeChars = [...word].filter(c => /[\u4e00-\u9fff]/.test(c));
    if (strokeChars.length === 0) return;

    strokeCharIndex = 0;
    strokeQuizMode = false;

    document.getElementById('stroke-modal-word').textContent = word;
    document.getElementById('stroke-modal-pinyin').textContent = pinyin || '';

    const tabsEl = document.getElementById('stroke-char-tabs');
    if (strokeChars.length <= 1) {
        tabsEl.style.display = 'none';
    } else {
        tabsEl.style.display = 'flex';
        tabsEl.innerHTML = strokeChars.map((ch, i) =>
            `<button class="stroke-tab ${i === 0 ? 'active' : ''}" onclick="switchStrokeChar(${i})">${ch}</button>`
        ).join('');
    }

    document.getElementById('stroke-modal-overlay').classList.add('open');
    renderStrokeChar(strokeCharIndex);
}

function openStrokeModal() {
    const word = words[currentIndex];
    if (!word || !word.word) return;
    stopStrokeOrderAllSummary();

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

    if (!window.HanziWriter) {
        container.innerHTML = '<div class="vocab-empty">Stroke order is temporarily unavailable.</div>';
        return;
    }

    // Create a fresh target div
    const target = document.createElement('div');
    target.id = 'stroke-svg-target';
    container.appendChild(target);

    strokeWriter = HanziWriter.create('stroke-svg-target', char, {
        width: size,
        height: size,
        padding: 16,
        strokeColor: '#e2e8f0',
        radicalColor: '#738a72',
        outlineColor: 'rgba(255,255,255,0.08)',
        drawingColor: '#576856',
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
    stopStrokeOrderAllSummary();
    document.getElementById('stroke-modal-overlay').classList.remove('open');
    strokeWriter = null;
    // Clear canvas to release memory
    const container = document.getElementById('stroke-canvas-container');
    container.innerHTML = '';
}

function closeStrokeModalIfBackground(e) {
    if (e.target.id === 'stroke-modal-overlay') closeStrokeModal();
}

// ─── Stroke Order: All Words in Summary ──────────────────────────────────────

let strokeAllQueue = [];
let strokeAllIndex = 0;
let strokeAllActive = false;

function strokeOrderAllSummary() {
    // Build a flat queue of every Chinese character across the summary rows.
    strokeAllQueue = [];
    (tableVocabList || []).forEach(v => {
        const word = v.word || '';
        const pinyin = v.pinyin || '';
        [...word].filter(c => /[一-鿿]/.test(c)).forEach(ch => strokeAllQueue.push({ ch, word, pinyin }));
    });
    if (!strokeAllQueue.length) return;

    strokeAllIndex = 0;
    strokeAllActive = true;
    document.getElementById('stroke-char-tabs').style.display = 'none';
    document.getElementById('stroke-modal-overlay').classList.add('open');
    renderStrokeAllChar();
}

function renderStrokeAllChar() {
    if (!strokeAllActive) return;
    const item = strokeAllQueue[strokeAllIndex];
    if (!item) { strokeAllActive = false; return; }

    // Keep the single-char controls (Animate/Reset) pointing at the current character.
    strokeChars = [item.ch];
    strokeCharIndex = 0;

    document.getElementById('stroke-modal-word').textContent = item.word;
    document.getElementById('stroke-modal-pinyin').textContent =
        `${item.pinyin ? item.pinyin + ' · ' : ''}${strokeAllIndex + 1}/${strokeAllQueue.length}`;

    const container = document.getElementById('stroke-canvas-container');
    container.innerHTML = '';

    if (!window.HanziWriter) {
        container.innerHTML = '<div class="vocab-empty">Stroke order is temporarily unavailable.</div>';
        strokeAllActive = false;
        return;
    }

    const target = document.createElement('div');
    target.id = 'stroke-svg-target';
    container.appendChild(target);

    const size = Math.min(280, window.innerWidth - 80);
    strokeWriter = HanziWriter.create('stroke-svg-target', item.ch, {
        width: size,
        height: size,
        padding: 16,
        strokeColor: '#e2e8f0',
        radicalColor: '#738a72',
        outlineColor: 'rgba(255,255,255,0.08)',
        drawingColor: '#576856',
        drawingWidth: 4,
        showOutline: true,
        showCharacter: false,
        delayBetweenStrokes: 300,
    });

    strokeWriter.animateCharacter({
        onComplete: () => {
            if (!strokeAllActive) return;
            setTimeout(() => {
                if (!strokeAllActive) return;
                strokeAllIndex++;
                if (strokeAllIndex < strokeAllQueue.length) renderStrokeAllChar();
                else strokeAllActive = false;
            }, 600);
        }
    });
}

function stopStrokeOrderAllSummary() {
    strokeAllActive = false;
    strokeAllQueue = [];
    strokeAllIndex = 0;
}
