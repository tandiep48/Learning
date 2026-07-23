// Lesson translation page: show each sentence's meaning (in the UI language) with an
// input for the learner to type the Chinese, plus a per-row reveal of the answer.

function getParam(name) {
    return new URLSearchParams(window.location.search).get(name);
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function meaningFor(row) {
    // CSV column is `vn`; UI language code for Vietnamese is `vi`.
    const useVi = (window.currentLang || 'en') === 'vi';
    const primary = useVi ? row.vn : row.en;
    return primary || row.en || row.vn || '';
}

function goBackToLearning() {
    // Return to this lesson's part list. /learning?passage_id=<id>&show_parts=true
    // deep-links into the part picker; it only needs level + lesson, so any part
    // index works (H<level>_<lesson>_1).
    const hskLevel = getParam('hsk_level');
    const lesson = getParam('lesson');
    const digits = String(hskLevel || '').replace(/\D/g, '');
    const lessonNum = String(lesson || '').replace(/\D/g, '');

    if (digits && lessonNum) {
        const passageId = `H${digits}_${lessonNum}_1`;
        window.location.href = `/learning?passage_id=${encodeURIComponent(passageId)}&show_parts=true`;
        return;
    }
    window.location.href = '/learning';
}

function renderRows(rows) {
    const list = document.getElementById('translation-list');
    list.innerHTML = '';

    rows.forEach((row, index) => {
        const item = document.createElement('div');
        item.className = 'translation-item';
        item.innerHTML = `
            <div class="translation-item-index">${index + 1}</div>
            <div class="translation-item-body">
                <div class="translation-meaning">${escapeHtml(meaningFor(row))}</div>
                <input type="text" class="translation-input" placeholder="${escapeHtml(t('translation.input_placeholder'))}"
                       autocomplete="off" autocapitalize="off" spellcheck="false">
                <div class="translation-answer" hidden>${escapeHtml(row.cn || '')}</div>
                <button type="button" class="translation-reveal-btn">${escapeHtml(t('translation.reveal'))}</button>
            </div>
        `;

        const answerEl = item.querySelector('.translation-answer');
        const revealBtn = item.querySelector('.translation-reveal-btn');
        revealBtn.addEventListener('click', () => {
            const showing = !answerEl.hidden;
            answerEl.hidden = showing;
            revealBtn.textContent = showing ? t('translation.reveal') : t('translation.hide');
        });

        list.appendChild(item);
    });
}

async function loadTranslations() {
    const hskLevel = getParam('hsk_level');
    const lesson = getParam('lesson');

    const loadingEl = document.getElementById('translation-loading');
    const emptyEl = document.getElementById('translation-empty');
    const subtitleEl = document.getElementById('translation-subtitle');

    if (subtitleEl && hskLevel && lesson) {
        subtitleEl.textContent = `${hskLevel} — ${t('translation.lesson_label')} ${lesson}`;
    }

    try {
        const res = await fetch(`/api/translation/lesson?hsk_level=${encodeURIComponent(hskLevel)}&lesson=${encodeURIComponent(lesson)}`);
        const data = await res.json();
        loadingEl.hidden = true;

        const rows = data.translations || [];
        if (!rows.length) {
            emptyEl.hidden = false;
            return;
        }
        renderRows(rows);
    } catch (e) {
        console.error(e);
        loadingEl.innerHTML = `<p style="color:var(--danger);">${t('translation.failed_load')}</p>`;
    }
}

document.addEventListener('DOMContentLoaded', loadTranslations);
