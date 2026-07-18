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
let currentNumberPracticeRows = [];
const LESSON_SPEAKING_MAX_MS = 15000;
var NUMBER_PART_ID = window.NUMBER_PART_ID || 'H1_5_99';
window.NUMBER_PART_ID = NUMBER_PART_ID;
const NUMBER_DIGITS = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九'];
const NUMBER_PINYIN_DIGITS = ['', 'yi', 'er', 'san', 'si', 'wu', 'liu', 'qi', 'ba', 'jiu'];

// ── Init ─────────────────────────────────────────────
window.onload = async () => {
    const params = new URLSearchParams(window.location.search);
    const autoPassage = params.get('passage_id');
    isLessonPartFlow = params.get('flow') === 'lesson-part';
    isLessonLearnerMode = isLessonPartFlow && params.get('mode') === 'lesson-learner';

    Picker.init((passage) => {
        loadPassage(passage.passage_id);
    }, isLessonLearnerMode ? t('reading.lesson_learning_title') : t('reading.reading_lesson_title'), !autoPassage);

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
    if (passage_id === NUMBER_PART_ID) {
        currentPassage = {
            passage_id: NUMBER_PART_ID,
            hsk_level: 'HSK1',
            title: 'Number',
            lines: []
        };
        renderNumberLessonSummary();
        switchScreen('screen-lesson-summary');
        return;
    }
    try {
        const res = await fetch(`/api/lesson/passage/${passage_id}`);
        const data = await res.json();
        if (!res.ok) { alert(data.error || t('reading.failed_load_passage')); goHome(); return; }
        currentPassage = data.passage;
        if (isLessonLearnerMode) {
            renderLessonSummary();
            switchScreen('screen-lesson-summary');
        } else {
            renderPassage();
            switchScreen('screen-reading');
        }
    } catch (e) {
        alert(t('lesson.error_connecting'));
        goHome();
    }
}

function renderPassage() {
    stopAutoPlay();
    if (window.buildBreadcrumb) window.buildBreadcrumb('reading-breadcrumb', currentPassage.passage_id);

    const contentDiv = document.getElementById('reading-content');
    contentDiv.innerHTML = '';

    currentPassage.lines.forEach(line => {
        const lineDiv = document.createElement('div');
        lineDiv.className = 'reading-line';

        let audioHTML = '';
        if (line.audio_key) {
            const hskLevel = currentPassage.hsk_level || 'H1';
            const src = `/lesson_audio/${hskLevel}/${line.audio_key}.mp3`;
            audioHTML = `<button class="audio-btn" onclick="playAudio('${src}')" title="${t('reading.play_audio')}" aria-label="${t('reading.play_audio')}"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>`;
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
    stopAutoPlay();
    if (currentAudio) currentAudio.pause();
    currentAudio = new Audio(src);
    currentAudio.play().catch(e => console.warn("Audio failed", e));
}

// ── Auto-play: run every line's audio in sequence ─────
let lineAutoPlayActive = false;
let lineAutoPlayItems = [];
let lineAutoPlayIndex = 0;

function collectLineAudioItems() {
    if (!currentPassage?.lines) return [];
    const hskLevel = currentPassage.hsk_level || 'H1';
    const lineDivs = document.querySelectorAll('#reading-content .reading-line');
    const items = [];
    currentPassage.lines.forEach((line, i) => {
        if (line.audio_key) {
            items.push({ src: `/lesson_audio/${hskLevel}/${line.audio_key}.mp3`, el: lineDivs[i] || null });
        }
    });
    return items;
}

function toggleAutoPlay() {
    if (lineAutoPlayActive) {
        stopAutoPlay();
        return;
    }
    const items = collectLineAudioItems();
    if (!items.length) return;
    lineAutoPlayItems = items;
    lineAutoPlayIndex = 0;
    lineAutoPlayActive = true;
    setAutoPlayBtn(true);
    playNextAutoPlay();
}

function playNextAutoPlay() {
    if (!lineAutoPlayActive) return;
    if (lineAutoPlayIndex >= lineAutoPlayItems.length) {
        stopAutoPlay();
        return;
    }
    const item = lineAutoPlayItems[lineAutoPlayIndex];
    if (currentAudio) currentAudio.pause();
    highlightAutoPlayLine(item.el);
    currentAudio = new Audio(item.src);
    const advance = () => {
        if (!lineAutoPlayActive) return;
        lineAutoPlayIndex++;
        playNextAutoPlay();
    };
    currentAudio.onended = advance;
    currentAudio.onerror = advance;
    currentAudio.play().catch(e => {
        console.warn("Auto-play audio failed", e);
        advance();
    });
}

function stopAutoPlay() {
    if (!lineAutoPlayActive) return;
    lineAutoPlayActive = false;
    if (currentAudio) {
        currentAudio.onended = null;
        currentAudio.onerror = null;
        currentAudio.pause();
    }
    setAutoPlayBtn(false);
    highlightAutoPlayLine(null);
}

function highlightAutoPlayLine(el) {
    document.querySelectorAll('#reading-content .reading-line.reading-line-active')
        .forEach(line => line.classList.remove('reading-line-active'));
    if (el) el.classList.add('reading-line-active');
}

function setAutoPlayBtn(playing) {
    const btn = document.getElementById('auto-play-btn');
    if (!btn) return;
    const icon = btn.querySelector('i');
    const label = btn.querySelector('span');
    if (icon) icon.className = playing ? 'fa-solid fa-stop' : 'fa-solid fa-play';
    if (label) label.textContent = playing ? t('reading.stop_auto_play') : t('reading.auto_play');
    btn.classList.toggle('primary', playing);
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
        btn.innerText = pinyinVisible ? t('reading.hide_pinyin') : t('reading.show_pinyin');
        btn.classList.toggle('primary', pinyinVisible);
    }
}

function updateMeaningBtnText() {
    const btn = document.getElementById('toggle-meaning-btn');
    if (btn) {
        btn.innerText = meaningVisible ? t('reading.hide_meaning') : t('reading.show_meaning');
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
    body.innerHTML = `<div class="vocab-loading">${t('dashboard.loading_vocabulary')}</div>`;

    try {
        const res = await fetch(`/api/lesson/vocab/${currentPassage.passage_id}`);
        const data = await res.json();
        vocabLoaded = true;
        currentVocabList = data.vocab || [];
        renderVocabTable(currentVocabList);
    } catch (e) {
        body.innerHTML = `<div class="vocab-empty">${t('reading.failed_load_vocabulary')}</div>`;
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
        body.innerHTML = `<div class="vocab-empty">${t('reading.no_vocab_linked')}</div>`;
        return;
    }

    const table = document.createElement('table');
    table.className = 'vocab-table vocab-canonical-table';
    table.innerHTML = `
        <thead>
            <tr>
                <th class="vocab-tools-col">
                    <button type="button" class="vocab-header-icon-btn" onclick="playAllVocabAudio()"
                        title="${t('reading.play_all_vocab_audio')}" aria-label="${t('reading.play_all_vocab_audio')}">
                        <i class="fa-solid fa-play" aria-hidden="true"></i>
                    </button>
                    <button type="button" class="vocab-header-icon-btn" onclick="shuffleVocab()"
                        title="${t('reading.shuffle_vocab_audio')}" aria-label="${t('reading.shuffle_vocab_audio')}">
                        <i class="fa-solid fa-shuffle" aria-hidden="true"></i>
                    </button>
                </th>
                <th onclick="toggleVocabColumn('cn')">${t('dashboard.table_character').toUpperCase()}</th>
                <th onclick="toggleVocabColumn('py')">${t('dashboard.table_pinyin').toUpperCase()}</th>
                <th onclick="toggleVocabColumn('vn')">${t('dashboard.table_meaning_vn').toUpperCase()}</th>
            </tr>
        </thead>
        <tbody id="vocab-tbody"></tbody>`;

    const tbody = table.querySelector('#vocab-tbody');

    vocab.forEach((w, index) => {
        const tr = document.createElement('tr');
        tr.id = `reading-vocab-tr-${index}`;
        const audioCell = w.audio_key
            ? `<button type="button" class="vocab-audio-btn" onclick="playVocabAudio('${escapeAttr(w.audio_key)}')" title="${t('reading.play_word_audio')}" aria-label="${escapeAttr(t('reading.play_audio_for', { word: w.word || w.cn || 'word' }))}"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>`
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
            alert(t('reading.no_vocab_linked'));
            return;
        }

        sessionStorage.setItem('selectedVocabFlashcards', JSON.stringify(selectedRows));
        window.location.href = '/vocab-learning?source=reading';
    } catch (e) {
        alert(t('reading.failed_open_flashcards'));
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
    stopLessonSummaryAutoPlay();
    document.querySelector('.lesson-summary-actions')?.removeAttribute('hidden');
    const actionFooter = document.querySelector('.lesson-summary-actions');
    if (actionFooter) {
        actionFooter.style.display = '';
        const learnButton = ensureLessonSummaryLearnButton(actionFooter);
        const learnLabel = learnButton?.querySelector('span');
        const trainLabel = actionFooter.querySelector('.vl-train-btn:not(.vl-learn-btn) span');
        if (learnButton) learnButton.style.display = '';
        if (learnLabel) learnLabel.textContent = t('reading.learn_this_lesson');
        if (trainLabel) trainLabel.textContent = t('reading.train_this_lesson');
    }
    const preview = document.getElementById('lesson-learner-preview');
    
    if (window.buildBreadcrumb) window.buildBreadcrumb('lesson-learner-breadcrumb', currentPassage?.passage_id);

    if (!preview) return;

    const lines = getLessonLines();
    if (!lines.length) {
        preview.innerHTML = `<div class="lesson-learner-empty">${t('reading.no_lines_found')}</div>`;
        return;
    }

    prefetchTokens(lines);
    preview.innerHTML = lines.map((line, index) => {
        const audioSrc = getLessonAudioSrc(line);
        const lineLabel = escapeAttr(t('reading.play_passage_line', { n: index + 1 }));
        const audioBtn = audioSrc
            ? `<button type="button" class="lesson-passage-audio-btn" onclick="playPassageLineAudio(${index})" title="${lineLabel}" aria-label="${lineLabel}"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>`
            : `<span class="lesson-passage-audio-btn lesson-passage-audio-empty" title="${t('reading.no_audio_available')}"></span>`;
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
    applyLessonLearnerHanText(preview);
}

function numberHanzi(value) {
    const n = Number(value);
    if (n === 0) return '零';
    if (n === 10) return '十';
    if (n < 10) return NUMBER_DIGITS[n];
    const tens = Math.floor(n / 10);
    const ones = n % 10;
    if (tens === 1) return ones ? `十${NUMBER_DIGITS[ones]}` : '十';
    return `${NUMBER_DIGITS[tens]}十${ones ? NUMBER_DIGITS[ones] : ''}`;
}

function numberPinyin(value) {
    const n = Number(value);
    if (n === 0) return 'ling';
    if (n === 10) return 'shi';
    if (n < 10) return NUMBER_PINYIN_DIGITS[n];
    const tens = Math.floor(n / 10);
    const ones = n % 10;
    if (tens === 1) return ones ? `shi${NUMBER_PINYIN_DIGITS[ones]}` : 'shi';
    return `${NUMBER_PINYIN_DIGITS[tens]}shi${ones ? NUMBER_PINYIN_DIGITS[ones] : ''}`;
}

function numberAudioKey(value) {
    const n = Number(value);
    const fixed = {
        0: 'ling_69',
        1: 'yi_59',
        2: 'er_60',
        3: 'san_61',
        4: 'si_62',
        5: 'wu_63',
        6: 'liu_64',
        7: 'qi_65',
        8: 'ba_66',
        9: 'jiu_67',
        10: 'shi_68'
    };
    if (fixed[n]) return fixed[n];
    return `${numberPinyin(n)}_${17601 + n}`;
}

function renderNumberLessonSummary() {
    const preview = document.getElementById('lesson-learner-preview');
    if (window.buildBreadcrumb) window.buildBreadcrumb('lesson-learner-breadcrumb', NUMBER_PART_ID);
    const actionFooter = document.querySelector('.lesson-summary-actions');
    if (actionFooter) {
        actionFooter.style.display = '';
        const learnButton = actionFooter.querySelector('.vl-learn-btn');
        const trainLabel = actionFooter.querySelector('.vl-train-btn:not(.vl-learn-btn) span');
        if (learnButton) learnButton.remove();
        if (trainLabel) trainLabel.textContent = t('reading.train_these_numbers');
    }
    if (!preview) return;

    currentNumberPracticeRows = buildNumberPracticeRows();

    const headers = [10, 20, 30, 40, 50, 60, 70, 80, 90];
    let html = `
        <div class="number-summary-wrap">
            <table class="number-summary-table">
                <thead>
                    <tr>
                        <th class="number-corner"></th>
                        ${headers.map(n => renderNumberCell(n, true)).join('')}
                    </tr>
                </thead>
                <tbody>
    `;

    for (let ones = 1; ones <= 9; ones += 1) {
        html += `<tr>${renderNumberCell(ones, true)}`;
        headers.forEach(tens => {
            html += renderNumberCell(tens + ones, false);
        });
        html += '</tr>';
    }

    html += `
                </tbody>
            </table>
        </div>
    `;
    preview.innerHTML = html;
    updateLessonSummaryToggleText();
    applyLessonLearnerHanText(preview);
}

function ensureLessonSummaryLearnButton(actionFooter) {
    let learnButton = actionFooter.querySelector('.vl-learn-btn');
    if (learnButton) return learnButton;

    learnButton = document.createElement('button');
    learnButton.className = 'vl-train-btn vl-learn-btn';
    learnButton.setAttribute('onclick', 'startLessonCards()');
    learnButton.innerHTML = `
        <i class="fa-solid fa-graduation-cap" aria-hidden="true"></i>
        <span>Learn This Lesson</span>
    `;
    actionFooter.prepend(learnButton);
    return learnButton;
}

function buildNumberPracticeRows() {
    const fixed = [44, 14, 41];
    const pool = Array.from({ length: 100 }, (_, index) => index)
        .filter(value => !fixed.includes(value));
    for (let i = pool.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    return [...fixed, ...pool.slice(0, 7)]
        .map(value => ({
            word: numberHanzi(value),
            cn: numberHanzi(value),
            pinyin: numberPinyin(value),
            meaning_vn: String(value),
            meaning_en: String(value),
            audio_key: numberAudioKey(value),
            level: 'HSK1'
        }));
}

function renderNumberCell(value, isHeader) {
    const tag = isHeader ? 'th' : 'td';
    const word = numberHanzi(value);
    const pinyin = numberPinyin(value);
    const audioKey = numberAudioKey(value);
    return `
        <${tag} class="number-summary-cell">
            <button type="button" class="number-cell-button" onclick="playNumberCellAudio('${audioKey}', this)" title="Play ${word}" aria-label="Play ${word}">
                <span class="hanzi-text number-cell-hanzi">${word}</span>
                <span class="pinyin-text lesson-summary-pinyin ${lessonSummaryPinyinVisible ? 'show' : ''}">${pinyin}</span>
                <span class="meaning-text lesson-summary-meaning ${lessonSummaryMeaningVisible ? 'show' : ''}">${value}</span>
            </button>
        </${tag}>`;
}

function playNumberCellAudio(audioKey, button) {
    document.querySelectorAll('.number-cell-button').forEach(el => el.classList.remove('playing-highlight'));
    button?.classList.add('playing-highlight');
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.onended = null;
        currentAudio.onerror = null;
    }
    currentAudio = new Audio(`/audio/${audioKey}.mp3`);
    currentAudio.onended = () => button?.classList.remove('playing-highlight');
    currentAudio.onerror = () => button?.classList.remove('playing-highlight');
    currentAudio.play().catch(e => {
        button?.classList.remove('playing-highlight');
        console.warn("Audio failed", e);
    });
}

function applyLessonLearnerHanText(container) {
    const target = container || document.getElementById('screen-lesson-summary');
    if (window.HanText && target) {
        window.HanText.apply(target, currentPassage?.hsk_level);
    }
}

// ── Lesson summary auto-play: run every line's audio in sequence ─────
let summaryAutoPlayActive = false;
let summaryAutoPlayItems = [];
let summaryAutoPlayPos = 0;

function toggleLessonSummaryAutoPlay() {
    if (summaryAutoPlayActive) {
        stopLessonSummaryAutoPlay();
        return;
    }
    const lines = getLessonLines();
    summaryAutoPlayItems = [];
    lines.forEach((line, i) => { if (getLessonAudioSrc(line)) summaryAutoPlayItems.push(i); });
    if (!summaryAutoPlayItems.length) return;
    summaryAutoPlayPos = 0;
    summaryAutoPlayActive = true;
    setSummaryAutoPlayBtn(true);
    playNextSummaryAutoPlay();
}

function playNextSummaryAutoPlay() {
    if (!summaryAutoPlayActive) return;
    if (summaryAutoPlayPos >= summaryAutoPlayItems.length) {
        stopLessonSummaryAutoPlay();
        return;
    }
    const index = summaryAutoPlayItems[summaryAutoPlayPos];
    const src = getLessonAudioSrc(getLessonLines()[index]);
    document.querySelectorAll('.lesson-preview-line').forEach(el => el.classList.remove('playing-highlight'));
    const lineEl = document.getElementById(`lesson-preview-line-${index}`);
    if (lineEl) lineEl.classList.add('playing-highlight');
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.onended = null;
        currentAudio.onerror = null;
    }
    currentAudio = new Audio(src);
    const advance = () => {
        if (lineEl) lineEl.classList.remove('playing-highlight');
        if (!summaryAutoPlayActive) return;
        summaryAutoPlayPos++;
        playNextSummaryAutoPlay();
    };
    currentAudio.onended = advance;
    currentAudio.onerror = advance;
    currentAudio.play().catch(e => {
        console.warn("Auto-play audio failed", e);
        advance();
    });
}

function stopLessonSummaryAutoPlay() {
    if (!summaryAutoPlayActive) return;
    summaryAutoPlayActive = false;
    if (currentAudio) {
        currentAudio.onended = null;
        currentAudio.onerror = null;
        currentAudio.pause();
    }
    document.querySelectorAll('.lesson-preview-line').forEach(el => el.classList.remove('playing-highlight'));
    setSummaryAutoPlayBtn(false);
}

function setSummaryAutoPlayBtn(playing) {
    const btn = document.getElementById('lesson-summary-auto-play-btn');
    if (!btn) return;
    const icon = btn.querySelector('i');
    const label = btn.querySelector('span');
    if (icon) icon.className = playing ? 'fa-solid fa-stop' : 'fa-solid fa-play';
    if (label) label.textContent = playing ? t('reading.stop_auto_play') : t('reading.auto_play');
    btn.classList.toggle('primary', playing);
}

function playPassageLineAudio(index) {
    stopLessonSummaryAutoPlay();
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
    stopLessonSummaryAutoPlay();
    resetLessonSpeakingPractice(true);
    if (currentPassage?.passage_id === NUMBER_PART_ID) {
        renderNumberLessonSummary();
        switchScreen('screen-lesson-summary');
        return;
    }
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
        pinyinBtn.textContent = lessonSummaryPinyinVisible ? t('reading.hide_pinyin') : t('reading.show_pinyin');
        pinyinBtn.classList.toggle('primary', lessonSummaryPinyinVisible);
    }
    if (meaningBtn) {
        meaningBtn.textContent = lessonSummaryMeaningVisible ? t('reading.hide_meaning') : t('reading.show_meaning');
        meaningBtn.classList.toggle('primary', lessonSummaryMeaningVisible);
    }
}

// ── Lesson Cards ──────────────────────────────────────
function startLessonCards() {
    if (currentPassage?.passage_id === NUMBER_PART_ID) {
        startNumberFlashcards();
        return;
    }
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
    nextBtn.textContent = currentLessonLineIndex === lines.length - 1 ? t('grammar.finish') : t('reading.next');
    applyLessonLearnerHanText(document.getElementById('screen-lesson-card'));
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
        showLessonSpeakingMessage(t('vocab_trainer.no_audio_support'), true);
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
        showLessonSpeakingMessage(t('reading.recording_sentence_status'));
        lessonSpeakingTimer = setTimeout(stopLessonSpeakingRecording, LESSON_SPEAKING_MAX_MS);
    } catch (error) {
        console.error(error);
        resetLessonSpeakingPractice(false);
        showLessonSpeakingMessage(t('reading.mic_blocked'), true);
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
        showLessonSpeakingMessage(t('reading.scoring_pronunciation'));
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
        showLessonSpeakingMessage(t('vocab_trainer.no_audio_recorded'), true);
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
            showLessonSpeakingMessage(data.error || t('reading.score_failed_sentence'), true);
            return;
        }
        renderLessonSpeakingResult(data);
    } catch (error) {
        console.error(error);
        if (attemptId !== lessonSpeakingAttemptId) return;
        setLessonSpeakingButtonState('idle');
        showLessonSpeakingMessage(t('reading.scorer_connect_failed'), true);
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
    if (label) label.textContent = state === 'recording' ? t('vocab_trainer.stop') : state === 'scoring' ? t('vocab_trainer.scoring') : t('vocab_trainer.speak');
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

function goToLessonTrainer() {
    if (!currentPassage?.passage_id) return;
    if (currentPassage.passage_id === NUMBER_PART_ID) {
        startNumberTrainer();
        return;
    }
    const params = new URLSearchParams({ passage_id: currentPassage.passage_id });
    if (isLessonPartFlow) params.set('flow', 'lesson-part');
    window.location.href = `/lesson?${params.toString()}`;
}

function ensureNumberPracticeRows() {
    if (!currentNumberPracticeRows.length) {
        currentNumberPracticeRows = buildNumberPracticeRows();
    }
    return currentNumberPracticeRows;
}

function startNumberFlashcards() {
    sessionStorage.setItem('selectedVocabFlashcards', JSON.stringify(ensureNumberPracticeRows()));
    window.location.href = '/vocab-learning?source=number';
}

function startNumberTrainer() {
    sessionStorage.setItem('selectedVocabTrainerWords', JSON.stringify(ensureNumberPracticeRows().map(row => row.word)));
    sessionStorage.setItem('numberTrainerReturnPassageId', NUMBER_PART_ID);
    window.location.href = '/vocab-training-batch';
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
