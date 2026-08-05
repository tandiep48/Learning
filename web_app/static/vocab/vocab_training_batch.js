// Batch vocab trainer page — words are worked in small groups, one activity at a
// time (typing -> listening match -> reading match). The activity engine lives in
// the shared vocab_trainer_core.js (VocabTrainer); this file handles page entry,
// word loading, answer recording to the DB, and the results/recap screen.

let words = [];                // normalized rows for the whole selection
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

// ── Session setup ───────────────────────────────────────────────────────────────

// Config handed to the shared activity engine: where to render, which words, and how
// this page records answers / tracks progress / finishes.
function trainerConfig(rows) {
    return {
        container: document.getElementById('activity-area'),
        words: rows,
        onAnswer: recordAnswer,
        onProgress: updateProgress,
        mountAction: mountBottomAction,
        onActivityAdvance: flushRecords,
        onFinish: finishSession,
    };
}

function startSession() {
    sessionId = Date.now();
    isRetry = false;
    missedWords = [];
    pendingRecords = [];
    totalAnswers = 0;
    correctAnswers = 0;
    switchScreen('screen-training');
    VocabTrainer.start(trainerConfig(words));
}

function updateProgress({ index, total, groupIndex, totalGroups }) {
    const fill = document.getElementById('progress-fill');
    if (fill) fill.style.width = `${(index / total) * 100}%`;

    const counter = document.getElementById('task-counter');
    if (counter) {
        counter.innerText = t('vocab_trainer.group_counter', {
            current: groupIndex + 1,
            total: totalGroups
        });
    }
    updateTrainerSubtitle();
}

// Show a "HSK · Lesson N · Part M" heading (lesson-part flow only) so the learner
// knows which part they are training.
function updateTrainerSubtitle() {
    const el = document.getElementById('trainer-subtitle');
    if (!el) return;
    if (!currentTrainingPassageId) { el.textContent = ''; return; }
    const parts = String(currentTrainingPassageId).split('_');
    const hskRaw = parts[0] || '';
    const hsk = hskRaw ? (hskRaw.startsWith('HSK') ? hskRaw : 'HSK' + hskRaw.replace(/^H/, '')) : '';
    const lessonLabel = parts[1] ? `${t('picker.lesson_prefix')} ${parts[1]}` : '';
    const partLabel = parts[2] ? `${t('picker.part_prefix')} ${parts[2]}` : '';
    el.textContent = [hsk, lessonLabel, partLabel].filter(Boolean).join(' · ');
}

// ── Recording ───────────────────────────────────────────────────────────────────

function recordAnswer(row, type, userAnswer, isCorrect, responseMs, wrongAttempts = 0) {
    // Matching now reports once on solve (always correct) with the mistake count; a word
    // that needed a retry counts as missed, so mastery / retry-missed behave as before.
    const clean = isCorrect && !wrongAttempts;
    totalAnswers++;
    if (clean) correctAnswers++;
    else missedWords.push(row);

    pendingRecords.push({
        type: type,
        word: row.word,
        round_num: isRetry ? 2 : 1,
        user_answer: userAnswer,
        is_correct: clean,
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

// ── Finish / recap ────────────────────────────────────────────────────────────────

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

// On finish, return to the vocab (word) summary the training was launched from.
function goToVocabSummary() {
    if (!currentTrainingPassageId) return;
    const params = new URLSearchParams({
        passage_id: currentTrainingPassageId,
        flow: 'lesson-part'
    });
    window.location.href = `/vocab-learning?${params.toString()}`;
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
    switchScreen('screen-training');
    VocabTrainer.start(trainerConfig(retryPool));
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

// Place an activity's primary action (Check / Continue) in the shared sticky bottom
// bar so the layout matches the lesson trainer, replacing the previous one.
function mountBottomAction(btn) {
    const bar = document.querySelector('.trainer-bottom-bar');
    if (!bar) return;
    bar.querySelectorAll('.bt-primary-action').forEach(el => el.remove());
    bar.appendChild(btn);
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
    const action = document.querySelector('.trainer-bottom-bar .bt-primary-action:not([disabled])');
    if (action) { e.preventDefault(); action.click(); }
});
