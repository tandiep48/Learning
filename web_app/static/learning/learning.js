let selectedPassage = null;
let selectedLessonNum = null;

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const autoPassageId = params.get('passage_id');

    Picker.init((passage) => {
        selectedPassage = passage;
        const parts = String(passage.passage_id || '').split('_');
        selectedLessonNum = parts.length >= 2 ? parts[1] : null;
        showLearningActions();
    }, 'Learning', !autoPassageId);

    const backLink = document.getElementById('picker-back-link');
    if (backLink) {
        backLink.href = '/';
        backLink.innerHTML = '&larr; Back to Dashboard';
    }

    if (autoPassageId) {
        openSelectedPassage(autoPassageId);
    }
});

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
    showLearningActions();
}

function normalizeHskLevel(value) {
    const text = String(value || '');
    const compactMatch = text.match(/^H(\d)$/i);
    if (compactMatch) return `HSK${compactMatch[1]}`;
    return text || null;
}

function showLearningActions() {
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    document.getElementById('learning-action-screen').style.display = 'block';

    const parts = String(selectedPassage.passage_id || '').split('_');
    const hsk = selectedPassage.hsk_level || parts[0] || 'HSK';
    const lesson = parts.length >= 2 ? `Lesson ${parts[1]}` : 'Lesson';
    const part = parts.length >= 3 ? `Part ${parts[2]}` : selectedPassage.passage_id;
    document.getElementById('learning-context').textContent = `${hsk} - ${lesson} - ${part}`;
}

async function backToPartPicker() {
    document.getElementById('learning-action-screen').style.display = 'none';
    if (selectedLessonNum && Object.keys(Picker.groupedPassages || {}).length === 0 && selectedPassage?.hsk_level) {
        await Picker.showLessonPicker(selectedPassage.hsk_level);
    }
    if (selectedLessonNum) {
        Picker.showPartPicker(selectedLessonNum);
    } else if (Picker.currentHskLevel) {
        Picker.showLessonPicker(Picker.currentHskLevel);
    } else {
        Picker.showLevelPicker();
    }
}

function openLearningAction(action) {
    if (!selectedPassage || !selectedPassage.passage_id) return;

    const passageId = encodeURIComponent(selectedPassage.passage_id);
    const routes = {
        'vocab-reading': `/vocab-learning?passage_id=${passageId}`,
        'vocab-trainer': `/vocab?mode=6&passage_id=${passageId}`,
        'lesson-reading': `/reading?passage_id=${passageId}`,
        'lesson-trainer': `/lesson?passage_id=${passageId}`,
        'grammar': `/grammar?passage_id=${passageId}`
    };

    if (routes[action]) {
        window.location.href = routes[action];
    }
}
