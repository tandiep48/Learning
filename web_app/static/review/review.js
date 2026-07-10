// Review page: browse past practice/exam sessions and inspect each answered
// question read-only (prompt + options + the user's answer vs the correct one).

const GCS = 'https://storage.googleapis.com/chinese-learning-audio-assets';

function audioSrc(key, level, category) {
    const cat = category || 'practice';
    return `${GCS}/question_bank/${cat}/${cat}-${level}/${key}.mp3`;
}

function imageUrl(level, filename, category) {
    const cat = category || 'practice';
    let file = String(filename).trim();
    if (!file.toLowerCase().match(/\.(jpg|jpeg|png|gif|webp)$/)) {
        file += '.jpg';
    }
    return `${GCS}/images/${cat}/${level}/${file}`;
}

function isImageFilename(val) {
    if (typeof val !== 'string') return false;
    const v = val.trim();
    return /\.(jpg|jpeg|png|gif|webp)$/i.test(v) || /^\d+\.\d+[a-zA-Z]*$/.test(v);
}

// Split a stored answer/user_answer string into a set of comparable tokens.
function answerTokens(raw) {
    if (raw === null || raw === undefined) return new Set();
    return new Set(
        String(raw)
            .split(/[,、\s]+/)
            .map(s => s.trim())
            .filter(Boolean)
    );
}

function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d)) return '';
    return d.toLocaleString(window.currentLang === 'vi' ? 'vi-VN' : 'en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
}

// ── Session list ────────────────────────────────────────────────

function todayStr() {
    const d = new Date();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${d.getFullYear()}-${mm}-${dd}`;
}

const filters = { level: 'all', category: 'all', sort: 'recent', date: todayStr(), page: 1 };
let hasMore = false;

async function loadSessions() {
    const list = document.getElementById('session-list');
    const pager = document.getElementById('review-pagination');
    list.innerHTML = `
        <div class="state-box">
            <div class="loading-dots"><span></span><span></span><span></span></div>
        </div>`;
    pager.classList.add('hidden');

    const qs = new URLSearchParams({
        level: filters.level,
        category: filters.category,
        sort: filters.sort,
        page: filters.page,
    });
    if (filters.date) qs.set('date', filters.date);
    try {
        const res = await fetch(`/api/practice/history?${qs.toString()}`);
        const data = await res.json();
        if (!res.ok) {
            list.innerHTML = stateBox(data.error || t('review.failed_load'));
            return;
        }
        const sessions = data.sessions || [];
        hasMore = !!data.has_more;
        if (sessions.length === 0) {
            const emptyMsg = filters.page > 1 ? t('review.no_more') : t('review.empty_sub');
            const emptyTitle = filters.page > 1 ? '' : t('review.empty_title');
            list.innerHTML = `
                <div class="state-box">
                    <i class="fa-regular fa-folder-open state-icon" aria-hidden="true"></i>
                    ${emptyTitle ? `<div class="state-title">${emptyTitle}</div>` : ''}
                    <div class="state-sub">${emptyMsg}</div>
                </div>`;
        } else {
            list.innerHTML = sessions.map(sessionCard).join('');
        }
        renderPagination();
    } catch (e) {
        list.innerHTML = stateBox(t('review.connect_failed'));
    }
}

function renderPagination() {
    const pager = document.getElementById('review-pagination');
    // Only show the pager when there's somewhere to go.
    if (filters.page <= 1 && !hasMore) {
        pager.classList.add('hidden');
        return;
    }
    pager.classList.remove('hidden');
    document.getElementById('page-prev').disabled = filters.page <= 1;
    document.getElementById('page-next').disabled = !hasMore;
    document.getElementById('page-indicator').textContent =
        t('review.page_indicator', { page: filters.page });
}

function changePage(delta) {
    const next = filters.page + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
    filters.page = next;
    loadSessions();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function onFilterChange() {
    filters.level = document.getElementById('filter-level').value;
    filters.category = document.getElementById('filter-category').value;
    filters.sort = document.getElementById('filter-sort').value;
    filters.date = document.getElementById('filter-date').value;
    filters.page = 1;
    loadSessions();
}

function clearDateFilter() {
    filters.date = '';
    document.getElementById('filter-date').value = '';
    filters.page = 1;
    loadSessions();
}

function sessionCard(s) {
    const levels = (s.levels || []).map(l => `HSK ${l}`).join(', ');
    const lessons = (s.lessons || []).join(', ');
    const cats = (s.categories || []).map(c =>
        c === 'exam' ? t('dashboard.exam') : t('dashboard.exercise')
    );
    const catLabel = [...new Set(cats)].join(', ');
    const pct = s.score_pct;
    const scoreClass = pct >= 80 ? 'good' : pct >= 50 ? 'mid' : 'low';

    return `
        <button type="button" class="session-card" onclick="openSession(${s.session_id})">
            <div class="session-card-main">
                <div class="session-card-title">${levels}${lessons ? ` · ${t('picker.lesson_prefix')} ${lessons}` : ''}</div>
                <div class="session-card-meta">
                    <span class="session-cat">${catLabel}</span>
                    <span class="session-date">${fmtDate(s.ended_at)}</span>
                    <span>${t('review.questions', { count: s.total })}</span>
                </div>
            </div>
            <div class="session-score ${scoreClass}">
                <span class="session-score-pct">${pct}%</span>
                <span class="session-score-sub">${t('review.session_summary', { correct: s.correct, total: s.total })}</span>
            </div>
        </button>`;
}

// ── Session detail ──────────────────────────────────────────────

async function openSession(sessionId) {
    const detail = document.getElementById('session-detail');
    detail.innerHTML = stateBox(t('review.loading'));
    showSessionDetail();
    try {
        const res = await fetch(`/api/practice/history/${sessionId}`);
        const data = await res.json();
        if (!res.ok) {
            detail.innerHTML = stateBox(data.error || t('review.failed_load'));
            return;
        }
        renderDetail(data);
    } catch (e) {
        detail.innerHTML = stateBox(t('review.connect_failed'));
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderDetail(data) {
    const detail = document.getElementById('session-detail');
    const header = `
        <div class="detail-summary">
            <span class="detail-score">${data.score_pct}%</span>
            <span>${t('review.session_summary', { correct: data.correct, total: data.total })}</span>
        </div>`;
    const cards = (data.questions || []).map((q, i) => questionCard(q, i + 1)).join('');
    detail.innerHTML = header + `<div class="q-review-list">${cards}</div>`;
}

function questionCard(q, index) {
    const correct = !!q.is_correct;
    const badge = correct
        ? `<span class="q-badge correct"><i class="fa-solid fa-check"></i> ${t('review.correct_badge')}</span>`
        : `<span class="q-badge incorrect"><i class="fa-solid fa-xmark"></i> ${t('review.incorrect_badge')}</span>`;

    const parts = [];

    // Audio
    if (Array.isArray(q.audio_key) && q.audio_key.length) {
        q.audio_key.forEach(key => {
            parts.push(audioButton(key, q.level, q.category));
        });
    }

    // Image (explicit image column, or the question field being a filename)
    const imgFile = q.image || (isImageFilename(q.question) ? q.question : null);
    if (imgFile) {
        parts.push(`<img class="q-image" src="${imageUrl(q.level, imgFile, q.category)}" alt="">`);
    }

    // Passage / content
    if (q.content) {
        parts.push(`<div class="q-content">${escapeHtml(q.content)}</div>`);
    }

    // Question prompt (text only, not when it's an image filename)
    if (q.question && !isImageFilename(q.question)) {
        parts.push(`<div class="q-prompt">${escapeHtml(q.question)}</div>`);
    }

    // Options
    const opts = q.options || {};
    const correctSet = answerTokens(q.answer);
    const userSet = answerTokens(q.user_answer);
    const optEntries = Object.entries(opts);
    if (optEntries.length) {
        const optHtml = optEntries.map(([key, val]) => optionRow(key, val, q, correctSet, userSet)).join('');
        parts.push(`<div class="q-options">${optHtml}</div>`);
    }

    // Answer summary (always shown as an unambiguous fallback)
    const userText = (q.user_answer === null || q.user_answer === undefined || q.user_answer === '')
        ? `<em>${t('review.no_answer')}</em>`
        : escapeHtml(String(q.user_answer));
    const summary = `
        <div class="q-answers">
            <div class="q-answer-line ${correct ? 'ok' : 'bad'}">
                <span class="q-answer-label">${t('review.your_answer')}</span>
                <span>${userText}</span>
            </div>
            <div class="q-answer-line ok">
                <span class="q-answer-label">${t('review.correct_answer')}</span>
                <span>${q.answer ? escapeHtml(String(q.answer)) : '—'}</span>
            </div>
        </div>`;

    const missing = (!optEntries.length && !q.content && !q.question && !imgFile)
        ? `<div class="q-missing">${t('review.detail_missing')}</div>`
        : '';

    return `
        <div class="q-review-card ${correct ? 'is-correct' : 'is-incorrect'}">
            <div class="q-review-head">
                <span class="q-num">${t('review.question_label', { n: index })}</span>
                ${badge}
            </div>
            ${missing}
            ${parts.join('')}
            ${summary}
        </div>`;
}

function optionRow(key, val, q, correctSet, userSet) {
    const isCorrect = correctSet.has(key);
    const isUser = userSet.has(key);
    let cls = 'q-option';
    if (isCorrect) cls += ' opt-correct';
    if (isUser && !isCorrect) cls += ' opt-user-wrong';
    if (isUser && isCorrect) cls += ' opt-user-correct';

    let body;
    if (val === true || val === 'True') {
        body = t('practice.true_label') || 'True';
    } else if (val === false || val === 'False') {
        body = t('practice.false_label') || 'False';
    } else if (isImageFilename(String(val))) {
        body = `<img class="q-option-img" src="${imageUrl(q.level, String(val), q.category)}" alt="">`;
    } else {
        body = escapeHtml(String(val));
    }

    const marks = [];
    if (isUser) marks.push(`<i class="fa-solid fa-user q-mark" title="${t('review.your_answer')}"></i>`);
    if (isCorrect) marks.push(`<i class="fa-solid fa-check q-mark" title="${t('review.correct_answer')}"></i>`);

    return `
        <div class="${cls}">
            <span class="q-option-key">${escapeHtml(key)}</span>
            <span class="q-option-val">${body}</span>
            <span class="q-option-marks">${marks.join('')}</span>
        </div>`;
}

// Lightweight play/pause audio button (no scrubber needed for review).
let reviewAudioId = 0;
function audioButton(key, level, category) {
    const id = `rev-audio-${reviewAudioId++}`;
    const src = audioSrc(key, level, category);
    return `
        <div class="q-audio">
            <button type="button" class="q-audio-btn" onclick="toggleAudio('${id}', this)">
                <i class="fa-solid fa-play"></i>
            </button>
            <audio id="${id}" src="${src}" preload="none"
                   onended="resetAudioBtn('${id}')"></audio>
        </div>`;
}

function toggleAudio(id, btn) {
    const el = document.getElementById(id);
    if (!el) return;
    document.querySelectorAll('audio').forEach(a => {
        if (a !== el) { a.pause(); a.currentTime = 0; }
    });
    document.querySelectorAll('.q-audio-btn i').forEach(i => {
        if (i !== btn.querySelector('i')) i.className = 'fa-solid fa-play';
    });
    if (el.paused) {
        el.play();
        btn.querySelector('i').className = 'fa-solid fa-pause';
    } else {
        el.pause();
        btn.querySelector('i').className = 'fa-solid fa-play';
    }
}

function resetAudioBtn(id) {
    const el = document.getElementById(id);
    const btn = el && el.parentElement.querySelector('.q-audio-btn i');
    if (btn) btn.className = 'fa-solid fa-play';
}

// ── View switching + helpers ────────────────────────────────────

function showSessionList() {
    document.getElementById('session-detail-view').classList.add('hidden');
    document.getElementById('session-list-view').classList.remove('hidden');
}

function showSessionDetail() {
    document.getElementById('session-list-view').classList.add('hidden');
    document.getElementById('session-detail-view').classList.remove('hidden');
}

function stateBox(msg) {
    return `<div class="state-box"><div class="state-title">${msg}</div></div>`;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => {
    ['filter-level', 'filter-category', 'filter-sort', 'filter-date'].forEach(id => {
        document.getElementById(id).addEventListener('change', onFilterChange);
    });
    document.getElementById('filter-date').value = filters.date;   // default: today
    document.getElementById('filter-date-clear').addEventListener('click', clearDateFilter);
    loadSessions();
});
