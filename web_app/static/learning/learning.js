let selectedPassage = null;
let selectedLessonNum = null;
let recentPassageId = null;

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const autoPassageId = params.get('passage_id');
    const showParts = params.get('show_parts') === 'true';

    Picker.init((passage) => {
        selectedPassage = passage;
        const parts = String(passage.passage_id || '').split('_');
        selectedLessonNum = parts.length >= 2 ? parts[1] : null;
        // Start immediately — skip the intermediate action screen
        saveRecentLearning();
        const passageId = encodeURIComponent(passage.passage_id);
        
        if (passage.passage_id === 'H1_1_1') {
            window.location.href = '/lesson/basic-pinyin';
            return;
        } else if (passage.passage_id === 'H1_1_2') {
            window.location.href = '/lesson/advanced-pinyin';
            return;
        }
        
        window.location.href = `/vocab-learning?passage_id=${passageId}&flow=lesson-part`;
    }, 'Learning', !autoPassageId);

    const backLink = document.getElementById('picker-back-link');
    if (backLink) {
        backLink.href = '/';
        backLink.innerHTML = '&larr; Back to Dashboard';
    }

    if (autoPassageId) {
        if (showParts) {
            openSelectedPassageForParts(autoPassageId);
        } else {
            openSelectedPassage(autoPassageId);
        }
    } else {
        loadRecentLearning();
    }
});

async function openSelectedPassageForParts(passageId) {
    const parts = String(passageId || '').split('_');
    selectedLessonNum = parts.length >= 2 ? parts[1] : null;
    const hskLevel = normalizeHskLevel(parts[0]);
    selectedPassage = {
        passage_id: passageId,
        hsk_level: hskLevel
    };

    if (hskLevel) {
        await Picker.showLessonPicker(hskLevel);
    }
    if (selectedLessonNum) {
        Picker.showPartPicker(selectedLessonNum);
    }
}

async function openSelectedPassage(passageId) {
    const parts = String(passageId || '').split('_');
    selectedLessonNum = parts.length >= 2 ? parts[1] : null;
    const hskLevel = normalizeHskLevel(parts[0]);
    selectedPassage = {
        passage_id: passageId,
        hsk_level: hskLevel
    };

    if (hskLevel) {
        await Picker.showLessonPicker(hskLevel);
    }
    if (selectedLessonNum) {
        Picker.showPartPicker(selectedLessonNum);
    }
}

function normalizeHskLevel(value) {
    const text = String(value || '');
    const compactMatch = text.match(/^H(\d)$/i);
    if (compactMatch) return `HSK${compactMatch[1]}`;
    return text || null;
}

async function loadRecentLearning() {
    try {
        const res = await fetch('/api/user/recent-learning');
        const data = await res.json();
        if (!res.ok || !data.recent?.passage_id) return;
        recentPassageId = data.recent.passage_id;
        showRecentPanel(recentPassageId);
    } catch (e) {
        console.warn('Could not load recent learning', e);
    }
}

function showRecentPanel(passageId) {
    const panel = document.getElementById('learning-recent-panel');
    const context = document.getElementById('learning-recent-context');
    if (!panel || !context) return;
    context.textContent = formatPassageContext(passageId);
    panel.style.display = 'flex';
}

function continueRecentLesson() {
    if (!recentPassageId) return;
    if (recentPassageId === 'H1_1_1') {
        window.location.href = '/lesson/basic-pinyin';
        return;
    } else if (recentPassageId === 'H1_1_2') {
        window.location.href = '/lesson/advanced-pinyin';
        return;
    }
    window.location.href = `/vocab-learning?passage_id=${encodeURIComponent(recentPassageId)}&flow=lesson-part`;
}

function formatPassageContext(passageId) {
    if (passageId === 'H1_5_99') return 'HSK1 - Lesson 5 - Number';
    const parts = String(passageId || '').split('_');
    const hsk = normalizeHskLevel(parts[0]) || parts[0] || 'HSK';
    const lesson = parts.length >= 2 ? `Lesson ${parts[1]}` : 'Lesson';
    const part = parts.length >= 3 ? `Part ${parts[2]}` : passageId;
    return `${hsk} - ${lesson} - ${part}`;
}

async function saveRecentLearning() {
    if (!selectedPassage?.passage_id) return;
    try {
        await fetch('/api/user/recent-learning', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ passage_id: selectedPassage.passage_id })
        });
    } catch (e) {
        console.warn('Could not save recent learning', e);
    }
}
