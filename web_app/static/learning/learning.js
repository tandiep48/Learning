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
        if (isBookPassageId(autoPassageId)) {
            // Book passages are "<book_code>_<lesson>_<part>" (e.g. AML_1_1), not HSK
            // levels — route to the book's part list instead of the HSK picker.
            openBookForPassage(autoPassageId);
        } else if (showParts) {
            openSelectedPassageForParts(autoPassageId);
        } else {
            openSelectedPassage(autoPassageId);
        }
    } else {
        loadRecentLearning();
    }
});

function isBookPassageId(passageId) {
    const prefix = String(passageId || '').split('_')[0];
    return !!prefix && !/^H\d+$/i.test(prefix);
}

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
    if (passageId === 'H1_5_99') return `HSK1 - ${t('picker.lesson_prefix')} 5 - ${t('picker.number_part')}`;
    const parts = String(passageId || '').split('_');
    const hsk = normalizeHskLevel(parts[0]) || parts[0] || 'HSK';
    const lesson = parts.length >= 2 ? `${t('picker.lesson_prefix')} ${parts[1]}` : t('picker.lesson_prefix');
    const part = parts.length >= 3 ? `${t('picker.part_prefix')} ${parts[2]}` : passageId;
    return `${hsk} - ${lesson} - ${part}`;
}

// ─── Books tab ──────────────────────────────────────────────────────────────
let booksLoadPromise = null;   // cached grid load so it runs once and can be awaited
let currentBook = null;        // { book_code, lessons: [...] }

function switchLearningTab(tab) {
    const isBooks = tab === 'books';
    document.getElementById('tab-hsk').hidden = isBooks;
    document.getElementById('tab-books').hidden = !isBooks;
    document.getElementById('learning-tab-hsk').classList.toggle('active', !isBooks);
    document.getElementById('learning-tab-books').classList.toggle('active', isBooks);
    if (isBooks) {
        ensureBooksLoaded();
    }
}

// Load the cover grid at most once. Returns the same promise so callers (tab
// switch and the deep-link path) can await a populated grid before overlaying
// the lesson/part screens.
function ensureBooksLoaded() {
    if (!booksLoadPromise) {
        booksLoadPromise = loadBooks();
    }
    return booksLoadPromise;
}

async function loadBooks() {
    const grid = document.getElementById('books-grid');
    try {
        const res = await fetch('/api/lesson/books');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'load failed');
        const books = data.books || [];
        if (books.length === 0) {
            grid.innerHTML = `<p style="color:var(--text-muted); text-align:center;">${t('books.no_books_found')}</p>`;
            return;
        }
        grid.innerHTML = '';
        books.forEach(book => {
            const card = document.createElement('div');
            card.className = 'book-card';
            const lessons = t('books.lessons_count', { count: book.lesson_count });
            let parts = t('books.parts_count', { count: book.part_count });
            if (book.done_count > 0) parts += ` · ${book.done_count}/${book.part_count}`;
            card.innerHTML = `
                <div class="book-card-img-wrap">
                    <img class="book-card-img" src="${escapeHtml(book.cover_url)}" alt="${escapeHtml(book.book_code)}" loading="lazy">
                </div>
                <div class="book-card-body">
                    <div class="book-card-title">${escapeHtml(book.name || book.book_code)}</div>
                    <div class="book-card-count">${escapeHtml(lessons)}</div>
                    <div class="book-card-count">${escapeHtml(parts)}</div>
                </div>`;
            card.addEventListener('click', () => openBook(book.book_code));
            grid.appendChild(card);
        });
    } catch (e) {
        console.warn('Could not load books', e);
        grid.innerHTML = `<p style="color:var(--danger); text-align:center;">${t('books.failed_load_books')}</p>`;
        booksLoadPromise = null;   // allow a retry on the next tab switch
    }
}

async function openBookForPassage(passageId) {
    const parts = String(passageId || '').split('_');
    const bookCode = parts[0];
    const lessonNum = parts.length >= 2 ? parts[1] : null;
    switchLearningTab('books');
    // Populate the cover grid first so backing out from the part list shows it.
    await ensureBooksLoaded();
    await openBook(bookCode);
    if (lessonNum && currentBook?.lessons) {
        const lesson = currentBook.lessons.find(l => String(l.lesson) === String(lessonNum));
        if (lesson) openBookLesson(lesson);
    }
}

async function openBook(code) {
    const list = document.getElementById('books-lesson-list');
    document.getElementById('books-lessons-title').textContent = code;
    document.getElementById('books-lessons-cover').src = `/lesson-cover/${encodeURIComponent(code)}`;
    list.innerHTML = `<p style="color:var(--text-muted); text-align:center;">${t('books.loading_lessons')}</p>`;
    showBookScreen('lessons');
    try {
        const res = await fetch(`/api/lesson/book/${encodeURIComponent(code)}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'load failed');
        currentBook = data;
        document.getElementById('books-lessons-title').textContent = data.book_name || code;
        renderBookLessons();
    } catch (e) {
        console.warn('Could not load book', e);
        list.innerHTML = `<p style="color:var(--danger); text-align:center;">${t('books.failed_load_lessons')}</p>`;
    }
}

function renderBookLessons() {
    const list = document.getElementById('books-lesson-list');
    const lessons = currentBook?.lessons || [];
    document.getElementById('books-lessons-sub').textContent =
        t('books.lessons_count', { count: lessons.length });
    list.innerHTML = '';
    lessons.forEach(lesson => {
        const card = document.createElement('div');
        card.className = 'lesson-card';
        const label = `${t('picker.lesson_prefix')} ${lesson.lesson}`;
        // Show the lesson title when present, with "Lesson N" as the sub-label.
        const title = lesson.title || label;
        const sub = lesson.title ? label : '';
        let count = t('books.parts_count', { count: lesson.part_count });
        if (lesson.done_count > 0) count += ` · ${lesson.done_count}/${lesson.part_count}`;
        card.innerHTML = `
            <div class="lesson-card-body">
                <div class="lesson-card-title">${escapeHtml(title)}</div>
                ${sub ? `<div class="lesson-card-sub">${escapeHtml(sub)}</div>` : ''}
                <div class="lesson-card-count">${escapeHtml(count)}</div>
            </div>`;
        card.addEventListener('click', () => openBookLesson(lesson));
        list.appendChild(card);
    });
}

function openBookLesson(lesson) {
    const bookLabel = currentBook.book_name || currentBook.book_code;
    const lessonLabel = lesson.title || `${t('picker.lesson_prefix')} ${lesson.lesson}`;
    document.getElementById('books-parts-title').textContent = `${bookLabel} · ${lessonLabel}`;
    const list = document.getElementById('books-part-list');
    list.innerHTML = '';
    (lesson.parts || []).forEach(part => {
        const btn = document.createElement('div');
        btn.className = 'part-list-item';
        const partName = `${t('picker.part_prefix')} ${part.part}`;
        const done = part.completed
            ? `<span class="book-part-done">✓ ${escapeHtml(t('books.completed'))}</span>`
            : '';
        btn.innerHTML = `<div class="part-list-title">${escapeHtml(partName)} ${done}</div>`;
        btn.addEventListener('click', () => {
            // Open the reading/lesson summary (sentence view) first, like HSK parts.
            window.location.href =
                `/reading?passage_id=${encodeURIComponent(part.passage_id)}&mode=lesson-learner&flow=lesson-part`;
        });
        list.appendChild(btn);
    });
    showBookScreen('parts');
}

function showBookScreen(name) {
    document.getElementById('books-screen-grid').hidden = name !== 'grid';
    document.getElementById('books-screen-lessons').hidden = name !== 'lessons';
    document.getElementById('books-screen-parts').hidden = name !== 'parts';
}

function showBooksGrid() { showBookScreen('grid'); }
function showBookLessons() { showBookScreen('lessons'); }

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
    ));
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
