// Vocab review page — one combined, priority-ordered list (unsure + unlearned) from
// /api/vocab/review. The learner selects all or some, then starts the batch trainer.

const PAGE_SIZE = 100;

const selectedWords = new Map();   // word -> row
let loadedRows = [];               // rows rendered so far
let page = 1;
let totalPages = 1;
let reviewAudio = null;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('review-select-all-cb')?.addEventListener('change', (e) => toggleSelectAll(e.target.checked));
    document.getElementById('review-load-more')?.addEventListener('click', loadMore);
    loadReview();
});

async function loadReview() {
    setState(t('vocab_review.loading'));
    let data;
    try {
        data = await fetchPage(1);
    } catch (e) {
        setState(t('vocab_review.load_failed'));
        return;
    }
    page = 1;
    totalPages = data.total_pages || 1;
    appendRows(data.rows || []);

    document.getElementById('review-state').style.display = 'none';
    document.getElementById('review-sections').style.display = '';
    updateUI();
}

function fetchPage(pageNum) {
    return fetch(`/api/vocab/review?page=${pageNum}&page_size=${PAGE_SIZE}`).then(r => {
        if (!r.ok) throw new Error('load failed');
        return r.json();
    });
}

async function loadMore() {
    if (page >= totalPages) return;
    const btn = document.getElementById('review-load-more');
    if (btn) btn.disabled = true;
    try {
        const data = await fetchPage(page + 1);
        page += 1;
        totalPages = data.total_pages || totalPages;
        appendRows(data.rows || []);
    } catch (e) {
        /* leave the button for a retry */
    }
    if (btn) btn.disabled = false;
    updateUI();
}

// ── Rendering ────────────────────────────────────────────────────────────────

function appendRows(rows) {
    const list = document.getElementById('review-list');
    rows.forEach(row => {
        if (!row || !row.word) return;
        loadedRows.push(row);
        list.appendChild(buildRow(row));
    });
    const emptyEl = document.getElementById('review-empty');
    if (emptyEl) emptyEl.style.display = loadedRows.length ? 'none' : 'block';
}

function buildRow(row) {
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
    cb.addEventListener('change', () => setSelected(row, cb.checked));

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

function setSelected(row, isSelected) {
    if (isSelected) selectedWords.set(row.word, row);
    else selectedWords.delete(row.word);
    updateUI();
}

function toggleSelectAll(checked) {
    loadedRows.forEach(row => {
        if (checked) selectedWords.set(row.word, row);
        else selectedWords.delete(row.word);
    });
    document.querySelectorAll('#review-list .review-item-cb').forEach(cb => { cb.checked = checked; });
    updateUI();
}

function updateUI() {
    const countEl = document.getElementById('review-count');
    if (countEl) countEl.textContent = loadedRows.length;

    const selectAll = document.getElementById('review-select-all-cb');
    if (selectAll) {
        const selectedCount = loadedRows.filter(r => selectedWords.has(r.word)).length;
        selectAll.checked = loadedRows.length > 0 && selectedCount === loadedRows.length;
        selectAll.indeterminate = selectedCount > 0 && selectedCount < loadedRows.length;
        selectAll.disabled = loadedRows.length === 0;
    }

    const loadMoreBtn = document.getElementById('review-load-more');
    if (loadMoreBtn) loadMoreBtn.style.display = page < totalPages ? '' : 'none';

    const startBtn = document.getElementById('review-start-btn');
    if (startBtn) {
        const count = selectedWords.size;
        startBtn.textContent = t('vocab_review.start_training', { count });
        startBtn.disabled = count === 0;
    }
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

function setState(message) {
    const el = document.getElementById('review-state');
    if (el) {
        el.style.display = '';
        el.textContent = message;
    }
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
