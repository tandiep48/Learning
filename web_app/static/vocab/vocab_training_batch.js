// Batch vocab trainer — words are worked in small groups, one activity at a time.
// Phase 1: word loading, per-group rounds, and the Typing activity.
// (Listening/Reading matching activities are added in Phase 2.)

const GROUP_SIZE = 5;          // words per group
const FEEDBACK_MS = 1200;      // pause on the success popup handoff

let words = [];                // normalized rows for the whole selection
let activities = [];           // flat list of {groupIndex, type, words}
let currentActivityIndex = 0;
let sessionId = 0;

// Entry-source state, used to send the learner back where they came from.
let isLessonPartFlow = false;
let currentTrainingPassageId = null;   // lesson-part passage deep-link (mode 6)
let lessonWideTrainingMeta = null;     // lesson-wide picker payload (passage_ids)
let numberTrainerReturnPassageId = null;
let isRetry = false;
let missedWords = [];          // rows answered wrong (deduped on finish)
let retryPool = [];            // unique missed rows offered for a round-2 retry
let pendingRecords = [];       // buffered answers, flushed per activity in one request
let totalAnswers = 0;          // number of recorded answers this session
let correctAnswers = 0;

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    isLessonPartFlow = params.get('flow') === 'lesson-part';
    hideBaseControls();

    // Word-list flows: vocabulary-page selection, lesson-part selection, number part.
    const trainerWords = readSelectedTrainerWords();
    if (trainerWords.length) {
        resolveAndStart({ words: trainerWords });
        return;
    }

    // Lesson-wide picker: a set of passage_ids to union.
    const lessonWide = readLessonWideVocabTrainer();
    if (lessonWide?.passage_ids?.length) {
        lessonWideTrainingMeta = lessonWide;
        resolveAndStart({ passage_ids: lessonWide.passage_ids });
        return;
    }

    // Lesson-part passage deep-link (mode 6).
    if (params.get('mode') === '6' && params.get('passage_id')) {
        currentTrainingPassageId = params.get('passage_id');
        resolveAndStart({ passage_id: currentTrainingPassageId });
        return;
    }

    window.location.href = '/vocab';
});

// ── Entry data ────────────────────────────────────────────────────────────────

function readSelectedTrainerWords() {
    const raw = sessionStorage.getItem('selectedVocabTrainerWords');
    if (!raw) return [];
    sessionStorage.removeItem('selectedVocabTrainerWords');
    numberTrainerReturnPassageId = sessionStorage.getItem('numberTrainerReturnPassageId');
    sessionStorage.removeItem('numberTrainerReturnPassageId');
    try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
    } catch (e) {
        return [];
    }
}

function readLessonWideVocabTrainer() {
    const raw = sessionStorage.getItem('lessonWideVocabTrainer');
    if (!raw) return null;
    sessionStorage.removeItem('lessonWideVocabTrainer');
    try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed?.passage_ids) ? parsed : null;
    } catch (e) {
        return null;
    }
}

async function resolveAndStart(payload) {
    switchScreen('screen-loading');
    try {
        const response = await fetch('/api/vocab/words', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        words = Array.isArray(data.words) ? data.words.filter(w => w && w.word) : [];
    } catch (e) {
        words = [];
    }

    if (!words.length) {
        alert(t('lesson.failed_start_session'));
        goHome();
        return;
    }

    startSession();
}

// ── Session / group / activity setup ───────────────────────────────────────────

function buildGroups(rows) {
    const groups = [];
    for (let i = 0; i < rows.length; i += GROUP_SIZE) {
        groups.push(rows.slice(i, i + GROUP_SIZE));
    }
    // Avoid a lone trailing word: fold a size-1 remainder into the previous group.
    if (groups.length > 1 && groups[groups.length - 1].length === 1) {
        groups[groups.length - 2].push(groups.pop()[0]);
    }
    return groups;
}

// Each group runs typing -> listening match -> reading match.
const ACTIVITY_TYPES = ['typing', 'listen', 'reading'];

// Matching config per activity. `db` is the vocab_records mode; the left column is the
// scored anchor (one record per word), the right column is what gets paired to it.
const MATCH_CONFIG = {
    listen:  { db: 'listen',  instruction: 'instruction_match_listen',  leftKind: 'audio', rightKind: 'meaning' },
    reading: { db: 'meaning', instruction: 'instruction_match_reading', leftKind: 'word',  rightKind: 'meaning' },
};

let trainerAudio = null;

function buildActivities(groups) {
    const list = [];
    groups.forEach((groupWords, groupIndex) => {
        ACTIVITY_TYPES.forEach(type => {
            list.push({ groupIndex, type, words: groupWords });
        });
    });
    return list;
}

function startSession() {
    sessionId = Date.now();
    isRetry = false;
    missedWords = [];
    pendingRecords = [];
    totalAnswers = 0;
    correctAnswers = 0;
    activities = buildActivities(buildGroups(words));
    currentActivityIndex = 0;
    renderActivity();
}

function renderActivity() {
    if (currentActivityIndex >= activities.length) {
        finishSession();
        return;
    }
    switchScreen('screen-training');
    const activity = activities[currentActivityIndex];
    updateProgress(activity);

    const area = document.getElementById('activity-area');
    area.innerHTML = '';

    if (activity.type === 'typing') {
        renderTypingActivity(area, activity);
    } else if (activity.type === 'listen' || activity.type === 'reading') {
        renderMatchActivity(area, activity);
    }
}

function updateProgress(activity) {
    const totalGroups = activities.length ? activities[activities.length - 1].groupIndex + 1 : 1;
    const fill = document.getElementById('progress-fill');
    if (fill) fill.style.width = `${(currentActivityIndex / activities.length) * 100}%`;

    const counter = document.getElementById('task-counter');
    if (counter) {
        counter.innerText = t('vocab_trainer.group_counter', {
            current: activity.groupIndex + 1,
            total: totalGroups
        });
    }
    // const subtitle = document.getElementById('trainer-subtitle');
    // if (subtitle) subtitle.innerText = t(`vocab_trainer.activity_${activity.type}`);
}

// ── Typing activity ─────────────────────────────────────────────────────────────
// Prompt shows pinyin + meaning; the learner types the Chinese word. One-shot: the
// value at check time is the recorded answer.

function renderTypingActivity(area, activity) {
    const wrap = document.createElement('div');
    wrap.className = 'bt-typing';

    const instruction = document.createElement('div');
    instruction.className = 'instruction';
    instruction.innerText = t('vocab_trainer.instruction_type_recall');
    wrap.appendChild(instruction);

    const list = document.createElement('div');
    list.className = 'bt-type-list';

    activity.words.forEach((row, idx) => {
        const fontSize = window.HanText ? (window.HanText.fontSizeForLevel(row.level) || '24px') : '24px';
        const item = document.createElement('div');
        item.className = 'bt-type-row';
        item.innerHTML = `
            <div class="bt-type-prompt">
                <span class="bt-hanzi" style="font-size: ${fontSize}; font-weight: bold;">${escapeHtml(row.word || '')}</span>
                <div class="bt-type-result" aria-live="polite"></div>
            </div>
            <input type="text" class="bt-type-input" lang="zh-CN" autocomplete="off"
                   inputmode="text" placeholder="${escapeHtml(t('vocab_trainer.type_word_placeholder'))}"
                   data-index="${idx}"
                   style="font-size: ${fontSize}; background: #ffffff;">
        `;
        list.appendChild(item);
    });
    wrap.appendChild(list);

    const actions = document.createElement('div');
    actions.className = 'bt-actions';
    const checkBtn = document.createElement('button');
    checkBtn.className = 'btn primary bt-primary-action';
    checkBtn.id = 'bt-check-btn';
    checkBtn.innerText = t('vocab_trainer.check');
    checkBtn.addEventListener('click', () => checkTypingGroup(activity, wrap, checkBtn));
    actions.appendChild(checkBtn);
    wrap.appendChild(actions);

    area.appendChild(wrap);

    // Enter on the last input triggers the group check.
    const inputs = wrap.querySelectorAll('.bt-type-input');
    inputs.forEach((input, idx) => {
        input.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            e.stopPropagation();   // don't let the global Enter handler also advance
            if (idx < inputs.length - 1) inputs[idx + 1].focus();
            else checkTypingGroup(activity, wrap, checkBtn);
        });
    });
    if (inputs[0]) inputs[0].focus();
}

function checkTypingGroup(activity, wrap, checkBtn) {
    if (checkBtn.dataset.done === '1') { advanceActivity(); return; }

    const rows = wrap.querySelectorAll('.bt-type-row');
    rows.forEach((rowEl, idx) => {
        const row = activity.words[idx];
        const input = rowEl.querySelector('.bt-type-input');
        const result = rowEl.querySelector('.bt-type-result');
        const answer = input.value.trim();
        const isCorrect = answer === row.word;

        input.disabled = true;
        rowEl.classList.add(isCorrect ? 'correct' : 'incorrect');
        result.innerHTML = isCorrect
            ? `<span class="bt-ok"><i class="fa-solid fa-check"></i> ${escapeHtml(row.pinyin)} - ${escapeHtml(row.meaning_vn || row.meaning_en || '')}</span>`
            : `<span class="bt-bad"><i class="fa-solid fa-xmark"></i> ${escapeHtml(row.pinyin)} - ${escapeHtml(row.meaning_vn || row.meaning_en || '')}</span>`;

        recordAnswer(row, 'typing', answer, isCorrect);
    });

    checkBtn.dataset.done = '1';
    checkBtn.innerText = t('lesson.continue');
}

// ── Matching activities (listening / reading) ───────────────────────────────────
// Two columns of the same group's words. The left column is the scored anchor: the
// first pairing attempt for each left item is what gets recorded (one-shot). Wrong
// pairs flash and reset; the board must be fully matched to continue.

function renderMatchActivity(area, activity) {
    const cfg = MATCH_CONFIG[activity.type];
    const wrap = document.createElement('div');
    wrap.className = 'bt-match';

    const instruction = document.createElement('div');
    instruction.className = 'instruction';
    instruction.innerText = t(`vocab_trainer.${cfg.instruction}`);
    wrap.appendChild(instruction);

    const board = document.createElement('div');
    board.className = 'bt-match-board';

    const leftCol = document.createElement('div');
    leftCol.className = 'bt-match-col';
    const rightCol = document.createElement('div');
    rightCol.className = 'bt-match-col';

    const total = activity.words.length;
    const recorded = new Set();
    let solved = 0;
    const selected = { left: null, right: null };

    activity.words.forEach(row => {
        leftCol.appendChild(makeMatchItem(row, 'left', cfg.leftKind));
    });
    shuffle(activity.words.slice()).forEach(row => {
        rightCol.appendChild(makeMatchItem(row, 'right', cfg.rightKind));
    });

    board.appendChild(leftCol);
    board.appendChild(rightCol);
    wrap.appendChild(board);

    const actions = document.createElement('div');
    actions.className = 'bt-actions';
    const continueBtn = document.createElement('button');
    continueBtn.className = 'btn primary bt-primary-action';
    continueBtn.innerText = t('lesson.continue');
    continueBtn.disabled = true;
    continueBtn.addEventListener('click', advanceActivity);
    actions.appendChild(continueBtn);
    wrap.appendChild(actions);

    area.appendChild(wrap);

    function select(item) {
        if (item.classList.contains('solved')) return;
        const side = item.dataset.side;
        if (side === 'left' && cfg.leftKind === 'audio') playWordAudio(item.dataset.audioKey);

        if (selected[side] === item) {                 // toggle off
            item.classList.remove('selected');
            selected[side] = null;
            return;
        }
        if (selected[side]) selected[side].classList.remove('selected');
        selected[side] = item;
        item.classList.add('selected');

        if (selected.left && selected.right) evaluate();
    }

    function evaluate() {
        const leftItem = selected.left;
        const rightItem = selected.right;
        const leftWord = leftItem.dataset.word;
        const correct = leftWord === rightItem.dataset.word;
        const row = wordByKey(activity.words, leftWord);

        if (!recorded.has(leftWord)) {
            recorded.add(leftWord);
            recordAnswer(row, cfg.db, rightItem.dataset.answer || '', correct);
        }

        if (correct) {
            [leftItem, rightItem].forEach(el => {
                el.classList.remove('selected');
                el.classList.add('solved');
            });
            selected.left = null;
            selected.right = null;
            solved++;
            if (solved === total) continueBtn.disabled = false;
        } else {
            [leftItem, rightItem].forEach(el => el.classList.add('wrong'));
            const a = leftItem, b = rightItem;
            selected.left = null;
            selected.right = null;
            setTimeout(() => {
                [a, b].forEach(el => el.classList.remove('wrong', 'selected'));
            }, 700);
        }
    }

    function makeMatchItem(row, side, kind) {
        const item = document.createElement('button');
        item.className = 'bt-match-item';
        item.dataset.side = side;
        item.dataset.word = row.word;
        if (kind === 'audio') {
            item.classList.add('bt-match-audio');
            item.dataset.audioKey = row.audio_key || '';
            item.dataset.answer = row.word;
            item.innerHTML = '<i class="fa-solid fa-volume-high" aria-hidden="true"></i>';
            item.setAttribute('aria-label', t('lesson.play_audio'));
        } else if (kind === 'word') {
            item.dataset.answer = row.word;
            item.innerText = row.word;
        } else { // meaning
            const meaning = row.meaning_vn || row.meaning_en || '';
            item.dataset.answer = meaning;
            item.innerText = meaning;
        }
        item.addEventListener('click', () => select(item));
        return item;
    }
}

function wordByKey(rows, word) {
    return rows.find(r => r.word === word) || { word };
}

function playWordAudio(audioKey) {
    if (!audioKey) return;
    try {
        if (!trainerAudio) trainerAudio = new Audio();
        trainerAudio.src = `/audio/${audioKey}.mp3`;
        trainerAudio.currentTime = 0;
        trainerAudio.play().catch(() => {});
    } catch (e) { /* ignore playback errors */ }
}

function shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
}

// ── Recording ───────────────────────────────────────────────────────────────────

function recordAnswer(row, type, userAnswer, isCorrect) {
    totalAnswers++;
    if (isCorrect) correctAnswers++;
    else missedWords.push(row);

    pendingRecords.push({
        type: type,
        word: row.word,
        round_num: isRetry ? 2 : 1,
        user_answer: userAnswer,
        is_correct: isCorrect,
        response_time_ms: 0,
        game_info: { pinyin: row.pinyin, meaning_en: row.meaning_en }
    });
}

// Send the buffered answers for the just-completed activity in a single request.
function flushRecords() {
    if (!pendingRecords.length) return;
    const batch = pendingRecords;
    pendingRecords = [];
    fetch('/api/vocab/submit-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, records: batch })
    }).catch(e => console.error('DB batch log failed', e));
}

// ── Flow control ────────────────────────────────────────────────────────────────

function advanceActivity() {
    flushRecords();
    currentActivityIndex++;
    renderActivity();
}

function finishSession() {
    flushRecords();
    const fill = document.getElementById('progress-fill');
    if (fill) fill.style.width = '100%';

    SuccessPopup.show({
        total: totalAnswers,
        correct: correctAnswers,
        continueLabel: t('lesson.view_results'),
        onContinue: showCompleteScreen,
        onHome: goHome,
    });
}

function showCompleteScreen() {
    switchScreen('screen-complete');
    const tableBody = document.getElementById('recap-table-body');
    const emptyState = document.getElementById('perfect-area');
    const missedTitle = document.getElementById('training-complete-title');
    const retryBtn = document.getElementById('btn-retry');
    const startLessonBtn = document.getElementById('btn-start-lesson');
    if (startLessonBtn) {
        startLessonBtn.style.display = (isLessonPartFlow && currentTrainingPassageId) ? 'inline-flex' : 'none';
    }
    if (tableBody) tableBody.innerHTML = '';

    const uniqueMissed = [];
    const seen = new Set();
    missedWords.forEach(row => {
        if (seen.has(row.word)) return;
        seen.add(row.word);
        uniqueMissed.push(row);
    });
    retryPool = uniqueMissed;

    if (uniqueMissed.length) {
        if (missedTitle) missedTitle.style.display = 'block';
        if (emptyState) emptyState.style.display = 'none';
        if (retryBtn) retryBtn.style.display = 'inline-flex';
        uniqueMissed.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="complete-word">${escapeHtml(row.word)}</td>
                <td>${escapeHtml(row.pinyin || '')}</td>
                <td>${escapeHtml(row.meaning_vn || row.meaning_en || '')}</td>
            `;
            tableBody.appendChild(tr);
        });
    } else {
        if (missedTitle) missedTitle.style.display = 'none';
        if (emptyState) emptyState.style.display = 'block';
        if (retryBtn) retryBtn.style.display = 'none';
    }
}

function startLearnLesson() {
    if (!currentTrainingPassageId) return;
    const params = new URLSearchParams({
        passage_id: currentTrainingPassageId,
        flow: 'lesson-part',
        mode: 'lesson-learner'
    });
    window.location.href = `/reading?${params.toString()}`;
}

// Re-run the full activity flow (typing -> listen -> reading) for just the missed words,
// recorded as round 2 so mastery (round-1 only) is unaffected.
function retryMissed() {
    if (!retryPool.length) return;
    isRetry = true;
    missedWords = [];
    pendingRecords = [];
    totalAnswers = 0;
    correctAnswers = 0;
    activities = buildActivities(buildGroups(retryPool));
    currentActivityIndex = 0;
    renderActivity();
}

// ── Shared trainer_base helpers ─────────────────────────────────────────────────

function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    if (screenId) document.getElementById(screenId)?.classList.add('active');
}

function hideBaseControls() {
    // trainer_base ships a skip button wired to the sequential flow; the batch flow
    // advances via each activity's own Check/Continue button instead.
    const skipBtn = document.getElementById('btn-skip-task');
    if (skipBtn) skipBtn.style.display = 'none';
}

function goHome() {
    closeQuitModal();
    if (numberTrainerReturnPassageId) {
        window.location.href = `/reading?passage_id=${encodeURIComponent(numberTrainerReturnPassageId)}&mode=lesson-learner&flow=lesson-part`;
        return;
    }
    if (lessonWideTrainingMeta?.passage_ids?.length) {
        window.location.href = lessonWidePickerUrl(lessonWideTrainingMeta);
        return;
    }
    if (currentTrainingPassageId) {
        window.location.href = `/vocab-learning?passage_id=${encodeURIComponent(currentTrainingPassageId)}&flow=lesson-part`;
        return;
    }
    window.location.href = '/vocab';
}

function lessonWidePickerUrl(meta) {
    const passageId = meta?.passage_ids?.[0] || '';
    return passageId
        ? `/learning?passage_id=${encodeURIComponent(passageId)}&show_parts=true`
        : '/learning';
}

function confirmQuit() {
    document.getElementById('quit-modal-overlay')?.classList.add('open');
}

function closeQuitModal() {
    document.getElementById('quit-modal-overlay')?.classList.remove('open');
}

function closeQuitModalIfBackground(event) {
    if (event.target === document.getElementById('quit-modal-overlay')) closeQuitModal();
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Enter advances the current activity via its Check/Continue button. Typing inputs manage
// their own Enter (navigate fields / check), so we only act when focus is outside an input.
document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    if (!document.getElementById('screen-training')?.classList.contains('active')) return;
    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;
    const action = document.querySelector('#activity-area .bt-primary-action:not([disabled])');
    if (action) { e.preventDefault(); action.click(); }
});
