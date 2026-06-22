let selectedPassage = null;
let selectedLessonNum = null;
let recentPassageId = null;

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const autoPassageId = params.get('passage_id');

    Picker.init((passage) => {
        selectedPassage = passage;
        const parts = String(passage.passage_id || '').split('_');
        selectedLessonNum = parts.length >= 2 ? parts[1] : null;
        // Start immediately — skip the intermediate action screen
        saveRecentLearning();
        const passageId = encodeURIComponent(passage.passage_id);
        window.location.href = `/vocab-learning?passage_id=${passageId}&flow=lesson-part`;
    }, 'Learning', !autoPassageId);

    const backLink = document.getElementById('picker-back-link');
    if (backLink) {
        backLink.href = '/';
        backLink.innerHTML = '&larr; Back to Dashboard';
    }

    if (autoPassageId) {
        openSelectedPassage(autoPassageId);
    } else {
        loadRecentLearning();
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
    hydrateSelectedPassageFromPicker();
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
    document.getElementById('learning-recent-panel').style.display = 'none';
    document.getElementById('learning-action-screen').style.display = 'block';

    const parts = String(selectedPassage.passage_id || '').split('_');
    const hsk = selectedPassage.hsk_level || parts[0] || 'HSK';
    const lesson = parts.length >= 2 ? `Lesson ${parts[1]}` : 'Lesson';
    const part = parts.length >= 3 ? `Part ${parts[2]}` : selectedPassage.passage_id;
    document.getElementById('learning-context').textContent = `${hsk} - ${lesson} - ${part}`;
    updatePartNavButtons();
    syncLearningUrl();
    saveRecentLearning();
}

async function backToPartPicker() {
    document.getElementById('learning-action-screen').style.display = 'none';
    document.getElementById('learning-recent-panel').style.display = 'none';
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

function startGuidedLessonPart() {
    if (!selectedPassage || !selectedPassage.passage_id) return;
    saveRecentLearning();
    const passageId = encodeURIComponent(selectedPassage.passage_id);
    window.location.href = `/vocab-learning?passage_id=${passageId}&flow=lesson-part`;
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
    window.location.href = `/learning?passage_id=${encodeURIComponent(recentPassageId)}`;
}

function formatPassageContext(passageId) {
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

function hydrateSelectedPassageFromPicker() {
    const passageId = selectedPassage?.passage_id;
    if (!passageId || !selectedLessonNum) return;

    const matched = getCurrentLessonParts().find(p => p.passage_id === passageId);
    if (matched) {
        selectedPassage = {
            ...matched,
            hsk_level: matched.hsk_level || selectedPassage.hsk_level
        };
    }
}

function getCurrentLessonParts() {
    if (!selectedLessonNum || !Picker.groupedPassages) return [];
    return [...(Picker.groupedPassages[selectedLessonNum] || [])].sort(comparePassagePart);
}

function comparePassagePart(a, b) {
    return getPartNumber(a.passage_id) - getPartNumber(b.passage_id);
}

function getPartNumber(passageId) {
    const parts = String(passageId || '').split('_');
    const part = parts.length >= 3 ? Number(parts[2]) : Number.MAX_SAFE_INTEGER;
    return Number.isFinite(part) ? part : Number.MAX_SAFE_INTEGER;
}

function getCurrentPartIndex(parts) {
    return parts.findIndex(p => p.passage_id === selectedPassage?.passage_id);
}

function updatePartNavButtons() {
    const prevBtn = document.getElementById('btn-prev-part');
    const nextBtn = document.getElementById('btn-next-part');
    if (!prevBtn || !nextBtn) return;

    const parts = getCurrentLessonParts();
    const currentIndex = getCurrentPartIndex(parts);
    const canNavigate = currentIndex !== -1;

    prevBtn.disabled = !canNavigate || currentIndex <= 0;
    nextBtn.disabled = !canNavigate || currentIndex >= parts.length - 1;
}

function goToAdjacentPart(delta) {
    const parts = getCurrentLessonParts();
    const currentIndex = getCurrentPartIndex(parts);
    if (currentIndex === -1) return;

    const nextIndex = currentIndex + delta;
    if (nextIndex < 0 || nextIndex >= parts.length) return;

    selectedPassage = parts[nextIndex];
    const idParts = String(selectedPassage.passage_id || '').split('_');
    selectedLessonNum = idParts.length >= 2 ? idParts[1] : selectedLessonNum;
    showLearningActions();
}

function syncLearningUrl() {
    if (!selectedPassage?.passage_id) return;
    const nextUrl = `/learning?passage_id=${encodeURIComponent(selectedPassage.passage_id)}`;
    if (window.location.pathname + window.location.search !== nextUrl) {
        window.history.replaceState(null, '', nextUrl);
    }
}
