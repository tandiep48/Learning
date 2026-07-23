// Lesson translation page: show each sentence's meaning (in the UI language) with an
// input for the learner to type the Chinese, plus a per-row reveal of the answer.
// Mirrors the grammar page: reached with a passage_id, driven by the shared picker
// and universal sidebar. Content is lesson-wide (all H<level>_<lesson>_* sentences).

let currentPassageId = null;
let isLessonPartFlow = false;

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const autoPassage = params.get('passage_id');
    isLessonPartFlow = params.get('flow') === 'lesson-part';

    Picker.init((passage) => {
        loadTranslation(passage.passage_id);
    }, 'Translation', !autoPassage);

    const backLink = document.getElementById('picker-back-link');
    if (backLink) {
        backLink.href = '/learning';
        backLink.innerHTML = '&larr; Back to Learning';
    }

    if (autoPassage) {
        loadTranslation(autoPassage);
    }
});

function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

function goBackToPartSelection() {
    if (currentPassageId) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(currentPassageId)}&show_parts=true`;
    } else {
        window.location.href = '/learning';
    }
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

// Derive HSK level + lesson from a passage_id like H1_2_1 -> { hskLevel: 'HSK1', lesson: '2' }.
function lessonKeyFrom(passageId) {
    const parts = String(passageId || '').split('_');
    const digits = (parts[0] || '').replace(/\D/g, '');
    const lesson = parts.length >= 2 ? (parts[1] || '').replace(/\D/g, '') : '';
    return { hskLevel: digits ? `HSK${digits}` : '', lesson };
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

async function loadTranslation(passageId) {
    currentPassageId = passageId;
    switchScreen('screen-loading');

    if (window.buildBreadcrumb) buildBreadcrumb('translation-breadcrumb', passageId);

    const { hskLevel, lesson } = lessonKeyFrom(passageId);
    const emptyEl = document.getElementById('translation-empty');
    emptyEl.hidden = true;

    try {
        const res = await fetch(`/api/translation/lesson?hsk_level=${encodeURIComponent(hskLevel)}&lesson=${encodeURIComponent(lesson)}`);
        const data = await res.json();

        const rows = data.translations || [];
        if (!rows.length) {
            document.getElementById('translation-list').innerHTML = '';
            emptyEl.hidden = false;
        } else {
            renderRows(rows);
        }
        switchScreen('screen-translation');
    } catch (e) {
        console.error(e);
        document.getElementById('translation-list').innerHTML =
            `<p style="color:var(--danger); padding:20px;">${t('translation.failed_load')}</p>`;
        switchScreen('screen-translation');
    }
}
