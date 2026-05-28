// ─── State ───────────────────────────────────────────────────────────────────

let words = [];          // full vocab list for this lesson
let currentIndex = 0;
let lessonMeta = null;   // { lesson, start_idx, end_idx, hsk_level }
const hskLevel = window.hskLevel; // injected by Flask template

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadLessons();
});

// ─── Lesson Picker ────────────────────────────────────────────────────────────

async function loadLessons() {
    const listEl = document.getElementById('vl-lesson-list');
    const subtitleEl = document.getElementById('vl-level-subtitle');

    try {
        const res = await fetch(`/api/vocab/lessons/${hskLevel}`);
        const data = await res.json();

        if (!res.ok || data.error) {
            listEl.innerHTML = `<p style="color:var(--danger); text-align:center;">Error: ${data.error || 'Failed to load lessons.'}</p>`;
            return;
        }

        const lessons = data.lessons || [];
        if (subtitleEl) subtitleEl.textContent = `${lessons.length} lesson${lessons.length !== 1 ? 's' : ''} available`;

        listEl.innerHTML = '';
        lessons.forEach(lesson => {
            const card = document.createElement('div');
            card.className = 'vl-lesson-card';
            const preview = lesson.preview && lesson.preview.length > 0
                ? lesson.preview.join('  ·  ')
                : '';
            card.innerHTML = `
                <div>
                    <div class="vl-lesson-title">Lesson ${lesson.lesson}</div>
                    <div class="vl-lesson-preview">${preview}</div>
                </div>
                <div class="vl-lesson-badge">${lesson.word_count} words</div>
            `;
            card.addEventListener('click', () => startLesson(lesson));
            listEl.appendChild(card);
        });

    } catch (e) {
        listEl.innerHTML = `<p style="color:var(--danger); text-align:center;">Failed to connect to server.</p>`;
    }
}

// ─── Word Fetching ────────────────────────────────────────────────────────────

async function startLesson(lesson) {
    lessonMeta = { ...lesson, hsk_level: hskLevel };

    // Show loading
    document.getElementById('screen-picker').style.display = 'none';
    const loadingEl = document.getElementById('screen-loading');
    loadingEl.style.display = 'block';

    try {
        // Use the vocab/start API to get the full word list for this lesson
        const res = await fetch('/api/vocab/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: '1',
                hsk_level: hskLevel,
                start_idx: lesson.start_idx,
                end_idx: lesson.end_idx
            })
        });
        const data = await res.json();

        if (!res.ok || data.error) {
            alert(data.error || 'Failed to load words.');
            backToLessons();
            return;
        }

        // Deduplicate tasks → one entry per unique word
        const seen = new Set();
        words = [];
        for (const task of (data.tasks || [])) {
            if (!seen.has(task.word)) {
                seen.add(task.word);
                words.push(task);
            }
        }

        if (words.length === 0) {
            alert('No words found for this lesson.');
            backToLessons();
            return;
        }

        currentIndex = 0;
        loadingEl.style.display = 'none';
        document.getElementById('screen-learning').style.display = 'block';
        renderWord();

    } catch (e) {
        alert('Error connecting to server.');
        backToLessons();
    }
}

// ─── Word Rendering ───────────────────────────────────────────────────────────

function renderWord() {
    const word = words[currentIndex];
    const total = words.length;

    // Progress
    document.getElementById('vl-counter').textContent = `${currentIndex + 1} / ${total}`;
    document.getElementById('vl-progress-fill').style.width = `${((currentIndex + 1) / total) * 100}%`;

    // Content
    document.getElementById('vl-hanzi').textContent = word.word;
    document.getElementById('vl-pinyin').textContent = word.pinyin || '';
    document.getElementById('vl-meaning').textContent = word.meaning_vn || word.meaning_en || '';

    // Navigation buttons
    document.getElementById('btn-prev').disabled = currentIndex === 0;
    document.getElementById('btn-next').disabled = currentIndex === total - 1;

    // Audio
    const audio = document.getElementById('vl-audio');
    if (word.audio_key) {
        audio.src = `/audio/${word.audio_key}.mp3`;
        audio.play().catch(() => {});
        setAudioPlaying(true);
        audio.onended = () => setAudioPlaying(false);
    } else {
        audio.removeAttribute('src');
        setAudioPlaying(false);
    }
}

function setAudioPlaying(playing) {
    const btn = document.getElementById('btn-audio');
    if (playing) {
        btn.classList.add('playing');
        btn.innerHTML = '🔊 Playing…';
    } else {
        btn.classList.remove('playing');
        btn.innerHTML = '🔊 Play Audio';
    }
}

// ─── Controls ─────────────────────────────────────────────────────────────────

function playAudio() {
    const audio = document.getElementById('vl-audio');
    if (audio.src) {
        audio.currentTime = 0;
        audio.play().catch(() => {});
        setAudioPlaying(true);
        audio.onended = () => setAudioPlaying(false);
    }
}

function prevWord() {
    if (currentIndex > 0) {
        currentIndex--;
        renderWord();
    }
}

function nextWord() {
    if (currentIndex < words.length - 1) {
        currentIndex++;
        renderWord();
    }
}

function backToLessons() {
    words = [];
    currentIndex = 0;
    lessonMeta = null;
    document.getElementById('screen-loading').style.display = 'none';
    document.getElementById('screen-learning').style.display = 'none';
    document.getElementById('screen-picker').style.display = 'block';

    const audio = document.getElementById('vl-audio');
    audio.pause();
    audio.removeAttribute('src');
}

function goToTrainer() {
    if (!lessonMeta) return;
    // Deep-link to vocab trainer with URL params so it auto-starts
    const params = new URLSearchParams({
        mode: '1',
        hsk_level: lessonMeta.hsk_level,
        start_idx: lessonMeta.start_idx,
        end_idx: lessonMeta.end_idx
    });
    window.location.href = `/vocab?${params.toString()}`;
}

// ─── Keyboard Shortcuts ───────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
    if (document.getElementById('screen-learning').style.display === 'none') return;
    if (e.key === 'ArrowLeft')  prevWord();
    if (e.key === 'ArrowRight') nextWord();
    if (e.key === ' ')          { e.preventDefault(); playAudio(); }
});
