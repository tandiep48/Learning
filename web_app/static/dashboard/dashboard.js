document.addEventListener('DOMContentLoaded', () => {
    loadHomeDashboard();
});

async function loadHomeDashboard() {
    setDashboardState('Loading your lesson dashboard...', true);
    try {
        // Fetch lesson data and global stats in parallel
        const [lessonRes, statsRes] = await Promise.all([
            fetch(`/api/user/dashboard-current-lesson?page=1&page_size=5`),
            fetch(`/api/user/global-stats`)
        ]);

        const lessonContentType = lessonRes.headers.get('content-type') || '';
        if (!lessonContentType.includes('application/json')) {
            showSignedOutState();
            return;
        }

        const lessonData = await lessonRes.json();
        if (!lessonRes.ok) throw new Error(lessonData.error || 'Failed to load dashboard.');
        if (!lessonData.has_recent) {
            showNoRecentState();
            return;
        }

        // Render lesson content
        renderHomeDashboard(lessonData);

        // Render global stats (non-blocking — silently ignore errors)
        if (statsRes.ok) {
            const statsData = await statsRes.json();
            renderGlobalStats(statsData);
        }

    } catch (err) {
        setDashboardState(err.message || 'Failed to load dashboard.', false);
    }
}

function renderHomeDashboard(data) {
    document.getElementById('dashboard-state').style.display = 'none';
    document.getElementById('dashboard-content').style.display = '';

    const lesson = data.lesson || {};
    document.getElementById('home-lesson-title').textContent = `${lesson.hsk_level || 'HSK'} - Lesson ${lesson.lesson || ''}`;
    document.getElementById('home-lesson-subtitle').textContent = `Current part: Part ${lesson.part || '-'} - ${lesson.passage_ids?.length || 1} part${lesson.passage_ids?.length === 1 ? '' : 's'} in this lesson`;
    document.getElementById('home-continue-link').href = `/learning?passage_id=${encodeURIComponent(lesson.passage_id || '')}`;

    renderVocab(data.vocab || {});
}

function renderVocab(vocab) {
    const rows = vocab.rows || [];
    const count = document.getElementById('home-vocab-count');
    const state = document.getElementById('home-vocab-state');
    const wrap = document.getElementById('home-vocab-table-wrap');
    const viewAllRow = document.getElementById('home-vocab-view-all');

    count.textContent = `${vocab.total || 0} word${vocab.total === 1 ? '' : 's'}`;

    if (!rows.length) {
        state.textContent = 'No vocabulary found for this lesson.';
        state.style.display = 'block';
        wrap.style.display = 'none';
        if (viewAllRow) viewAllRow.style.display = 'none';
        return;
    }

    const table = document.createElement('table');
    table.className = 'vocab-table home-vocab-table';
    table.innerHTML = `
        <thead>
            <tr>
                <th>Character</th>
                <th>Pinyin</th>
                <th>Meaning (VN)</th>
            </tr>
        </thead>
        <tbody>
            ${rows.map(row => `
                <tr>
                    <td class="vocab-cn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${escapeHtml(row.word || row.cn || '')}</td>
                    <td class="vocab-pinyin clickable-cell" onclick="this.classList.toggle('hidden-cell')">${escapeHtml(row.pinyin || '')}</td>
                    <td class="vocab-meaning-vn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${escapeHtml(row.meaning_vn || row.meaning_en || '')}</td>
                </tr>
            `).join('')}
        </tbody>
    `;

    wrap.innerHTML = '';
    wrap.appendChild(table);
    wrap.style.display = 'block';
    state.style.display = 'none';
    if (viewAllRow) viewAllRow.style.display = 'block';
}

function renderGlobalStats(data) {
    const buckets = data.buckets || {};

    // Hero totals
    const totalTimeEl = document.getElementById('stat-total-time');
    const totalWordsEl = document.getElementById('stat-total-words');
    if (totalTimeEl) totalTimeEl.textContent = data.total_time_label || '0s';
    if (totalWordsEl) totalWordsEl.textContent = (data.total_words || 0).toLocaleString();

    // Bucket cards
    setBucketCard('exercise', buckets.exercise);
    setBucketCard('exam', buckets.exam);
    setBucketCard('lesson', buckets.lesson_trainer);
    setBucketCard('vocab', buckets.vocab_trainer);
}

function setBucketCard(key, bucket) {
    const q = document.getElementById(`stat-${key}-q`);
    const t = document.getElementById(`stat-${key}-t`);
    if (!bucket) return;
    if (q) q.textContent = (bucket.questions || 0).toLocaleString();
    if (t) t.textContent = bucket.time_label || '0s';
}

function setDashboardState(message, loading) {
    const state = document.getElementById('dashboard-state');
    const content = document.getElementById('dashboard-content');
    content.style.display = 'none';
    state.style.display = 'grid';
    state.innerHTML = `${loading ? '<div class="loader"></div>' : ''}<p>${escapeHtml(message)}</p>`;
}

function showNoRecentState() {
    document.getElementById('dashboard-content').style.display = 'none';
    document.getElementById('dashboard-state').style.display = 'grid';
    document.getElementById('dashboard-state').innerHTML = `
        <div class="dashboard-empty-state">
            <span class="dashboard-kicker">Current Lesson</span>
            <h1>Choose a lesson to begin</h1>
            <p>Your Home dashboard will appear after you select a learning lesson.</p>
            <a class="btn primary dashboard-action-link" href="/learning">Open Learning</a>
        </div>
    `;
}

function showSignedOutState() {
    document.getElementById('dashboard-content').style.display = 'none';
    document.getElementById('dashboard-state').style.display = 'grid';
    document.getElementById('dashboard-state').innerHTML = `
        <div class="dashboard-empty-state">
            <span class="dashboard-kicker">Learning Dashboard</span>
            <h1>Sign in to continue</h1>
            <p>Your current lesson, vocabulary, exercises, and progress are saved to your account.</p>
            <a class="btn primary dashboard-action-link" href="/login">Login</a>
        </div>
    `;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
