// Lesson translation page: a flashcard drill. Each card shows one sentence's meaning
// (in the UI language) with an input to type the Chinese and a reveal for the answer,
// navigated one at a time like the "Learn these words" flow. Reached with a passage_id,
// driven by the shared picker and universal sidebar. Content is lesson-wide (all
// H<level>_<lesson>_* sentences).

let currentPassageId = null;
let isLessonPartFlow = false;

let translationRows = [];   // all sentences for the lesson
let cardIndex = 0;          // which card is showing

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

    // Highlight the input once the typed Chinese matches the current answer.
    const input = document.getElementById('translation-card-input');
    if (input) {
        input.addEventListener('input', () => {
            const row = translationRows[cardIndex];
            const match = row && input.value.trim() === (row.cn || '').trim();
            input.classList.toggle('success-highlight', !!match);
        });
    }

    // Arrow keys flip between cards, but not while the learner is typing.
    document.addEventListener('keydown', (e) => {
        if (document.getElementById('translation-card-view').hidden) return;
        if (document.activeElement === input) return;
        if (e.key === 'ArrowLeft') prevCard();
        if (e.key === 'ArrowRight') nextCard();
    });

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

// ── Flashcards ──────────────────────────────────────────────────

function renderCards(rows) {
    translationRows = rows;
    cardIndex = 0;
    document.getElementById('translation-empty').hidden = true;
    document.getElementById('translation-card-view').hidden = false;
    renderCard();
}

function renderCard() {
    const row = translationRows[cardIndex];
    if (!row) return;
    const total = translationRows.length;

    document.getElementById('translation-counter').textContent = `${cardIndex + 1} / ${total}`;
    document.getElementById('translation-progress-fill').style.width = `${((cardIndex + 1) / total) * 100}%`;

    document.getElementById('translation-card-meaning').textContent = meaningFor(row);

    const input = document.getElementById('translation-card-input');
    input.value = '';
    input.classList.remove('success-highlight');

    const answer = document.getElementById('translation-card-answer');
    answer.textContent = row.cn || '';
    answer.hidden = true;
    document.getElementById('translation-reveal-btn').textContent = t('translation.reveal');

    document.getElementById('translation-prev').disabled = cardIndex === 0;
    document.getElementById('translation-next').disabled = cardIndex === total - 1;

    input.focus();
}

function toggleAnswer() {
    const answer = document.getElementById('translation-card-answer');
    const showing = !answer.hidden;
    answer.hidden = showing;
    document.getElementById('translation-reveal-btn').textContent =
        showing ? t('translation.reveal') : t('translation.hide');
}

function prevCard() {
    if (cardIndex > 0) {
        cardIndex--;
        renderCard();
    }
}

function nextCard() {
    if (cardIndex < translationRows.length - 1) {
        cardIndex++;
        renderCard();
    }
}

function shuffleCards() {
    if (translationRows.length <= 1) return;
    for (let i = translationRows.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [translationRows[i], translationRows[j]] = [translationRows[j], translationRows[i]];
    }
    cardIndex = 0;
    renderCard();
}

async function loadTranslation(passageId) {
    currentPassageId = passageId;
    switchScreen('screen-loading');

    if (window.buildBreadcrumb) buildBreadcrumb('translation-breadcrumb', passageId);

    const { hskLevel, lesson } = lessonKeyFrom(passageId);
    const emptyEl = document.getElementById('translation-empty');
    emptyEl.hidden = true;
    document.getElementById('translation-card-view').hidden = true;

    try {
        const res = await fetch(`/api/translation/lesson?hsk_level=${encodeURIComponent(hskLevel)}&lesson=${encodeURIComponent(lesson)}`);
        const data = await res.json();

        const rows = data.translations || [];
        if (!rows.length) {
            emptyEl.querySelector('p').textContent = t('translation.empty');
            emptyEl.hidden = false;
        } else {
            renderCards(rows);
        }
        switchScreen('screen-translation');
    } catch (e) {
        console.error(e);
        emptyEl.querySelector('p').textContent = t('translation.failed_load');
        emptyEl.hidden = false;
        switchScreen('screen-translation');
    }
}
