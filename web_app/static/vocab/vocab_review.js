// Vocab review page — lists the user's Unlearned and Unsure words, lets them select
// all or some, then hands the selection to the batch vocab trainer.

const REVIEW_MODES = ['unlearn', 'unsure'];
const PAGE_SIZE = 100;

const selectedWords = new Map();   // word -> row (shared across both sections)
const sectionState = {};           // mode -> { page, totalPages, rows: [] }
let reviewAudio = null;

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.review-select-all-cb').forEach(cb => {
        cb.addEventListener('change', () => toggleSelectAll(cb.dataset.mode, cb.checked));
    });
    document.querySelectorAll('.review-load-more').forEach(btn => {
        btn.addEventListener('click', () => loadMore(btn.dataset.mode));
    });
    loadSections();
});

async function loadSections() {
    setState(t('vocab_review.loading'), true);
    try {
        const results = await Promise.all(REVIEW_MODES.map(mode => fetchPage(mode, 1)));
        REVIEW_MODES.forEach((mode, i) => {
            const data = results[i];
            sectionState[mode] = { page: 1, totalPages: data.total_pages || 1, rows: [] };
            appendRows(mode, data.rows || []);
        });
    } catch (e) {
        setState(t('vocab_review.load_failed'), false);
        return;
    }

    document.getElementById('review-state').style.display = 'none';
    document.getElementById('review-sections').style.display = '';
    updateStartButton();
}

function fetchPage(mode, page) {
    const url = `/api/vocab/table?mode=${encodeURIComponent(mode)}&page=${page}&page_size=${PAGE_SIZE}`;
    return fetch(url).then(r => {
        if (!r.ok) throw new Error('load failed');
        return r.json();
    });
}

async function loadMore(mode) {
    const state = sectionState[mode];
    if (!state || state.page >= state.totalPages) return;
    const btn = document.querySelector(`.review-load-more[data-mode="${mode}"]`);
    if (btn) btn.disabled = true;
    try {
        const data = await fetchPage(mode, state.page + 1);
        state.page += 1;
        state.totalPages = data.total_pages || state.totalPages;
        appendRows(mode, data.rows || []);
    } catch (e) {
        /* leave the button for a retry */
    }
    if (btn) btn.disabled = false;
}

// ── Rendering ────────────────────────────────────────────────────────────────

function appendRows(mode, rows) {
    const state = sectionState[mode];
    const list = document.querySelector(`.review-list[data-mode="${mode}"]`);
    const emptyEl = document.querySelector(`.review-empty[data-mode="${mode}"]`);

    rows.forEach(row => {
        if (!row || !row.word) return;
        state.rows.push(row);
        list.appendChild(buildRow(mode, row));
    });

    if (emptyEl) emptyEl.style.display = state.rows.length ? 'none' : 'block';
    updateSectionUI(mode);
}

function buildRow(mode, row) {
    const item = document.createElement('label');
    item.className = 'review-item';
    item.dataset.word = row.word;

    const meaning = row.meaning_vn || row.meaning_en || '';
    const audioBtn = row.audio_key
        ? `<button type="button" class="review-audio-btn" data-audio="${escapeAttr(row.audio_key)}" title="${escapeAttr(t('lesson.play_audio'))}" aria-label="${escapeAttr(t('lesson.play_audio'))}"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>`
        : '';

    item.innerHTML = `
        <input type="checkbox" class="review-item-cb" ${selectedWords.has(row.word) ? 'checked' : ''}>
        <span class="review-item-word">${escapeHtml(row.word)}</span>
        <span class="review-item-pinyin">${escapeHtml(row.pinyin || '')}</span>
        <span class="review-item-meaning">${escapeHtml(meaning)}</span>
        ${audioBtn}
    `;

    const cb = item.querySelector('.review-item-cb');
    cb.addEventListener('change', () => setSelected(row, cb.checked, mode));

    const audio = item.querySelector('.review-audio-btn');
    if (audio) {
        audio.addEventListener('click', (e) => {
            e.preventDefault();
            playAudio(audio.dataset.audio);
        });
    }
    return item;
}

// ── Selection ────────────────────────────────────────────────────────────────

function setSelected(row, isSelected, mode) {
    if (isSelected) selectedWords.set(row.word, row);
    else selectedWords.delete(row.word);
    updateSectionUI(mode);
    updateStartButton();
}

function toggleSelectAll(mode, checked) {
    const state = sectionState[mode];
    if (!state) return;
    state.rows.forEach(row => {
        if (checked) selectedWords.set(row.word, row);
        else selectedWords.delete(row.word);
    });
    // Reflect on the visible checkboxes for this section.
    document.querySelectorAll(`.review-list[data-mode="${mode}"] .review-item-cb`).forEach(cb => {
        cb.checked = checked;
    });
    updateSectionUI(mode);
    updateStartButton();
}

function updateSectionUI(mode) {
    const state = sectionState[mode];
    if (!state) return;
    const countEl = document.querySelector(`.review-section-count[data-mode="${mode}"]`);
    if (countEl) countEl.textContent = state.rows.length;

    const selectAll = document.querySelector(`.review-select-all-cb[data-mode="${mode}"]`);
    if (selectAll) {
        const selectedInSection = state.rows.filter(r => selectedWords.has(r.word)).length;
        selectAll.checked = state.rows.length > 0 && selectedInSection === state.rows.length;
        selectAll.indeterminate = selectedInSection > 0 && selectedInSection < state.rows.length;
        selectAll.disabled = state.rows.length === 0;
    }

    const loadMoreBtn = document.querySelector(`.review-load-more[data-mode="${mode}"]`);
    if (loadMoreBtn) loadMoreBtn.style.display = state.page < state.totalPages ? '' : 'none';
}

function updateStartButton() {
    const btn = document.getElementById('review-start-btn');
    if (!btn) return;
    const count = selectedWords.size;
    btn.textContent = t('vocab_review.start_training', { count });
    btn.disabled = count === 0;
}

function startReviewTraining() {
    if (!selectedWords.size) return;
    sessionStorage.setItem('selectedVocabTrainerWords', JSON.stringify([...selectedWords.keys()]));
    window.location.href = '/vocab-training-batch';
}

// ── Audio ────────────────────────────────────────────────────────────────────

function playAudio(audioKey) {
    if (!audioKey) return;
    try {
        if (reviewAudio) reviewAudio.pause();
        reviewAudio = new Audio(`/audio/${audioKey}.mp3`);
        reviewAudio.play().catch(() => {});
    } catch (e) { /* ignore playback errors */ }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function setState(message, loading) {
    const el = document.getElementById('review-state');
    if (!el) return;
    el.style.display = '';
    el.textContent = message;
    el.classList.toggle('is-loading', !!loading);
    document.getElementById('review-sections').style.display = 'none';
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
    return escapeHtml(value);
}
