document.addEventListener('DOMContentLoaded', () => {
    loadHomeDashboard();
});

let dashboardVocabBuckets = {};
let dashboardVocabOrder = ['unsure', 'unlearn', 'recent'];
let dashboardVocabIndex = 0;

async function loadHomeDashboard() {
    setDashboardState(t('dashboard.loading'), true);
    try {
        // Fetch lesson data and global stats in parallel
        const [lessonRes, statsRes, vocabRes] = await Promise.all([
            fetch(`/api/user/dashboard-current-lesson?page=1&page_size=5`),
            fetch(`/api/user/global-stats`),
            fetch(`/api/user/dashboard-vocab-buckets`)
        ]);

        const lessonContentType = lessonRes.headers.get('content-type') || '';
        if (!lessonContentType.includes('application/json')) {
            showSignedOutState();
            return;
        }

        const lessonData = await lessonRes.json();
        if (!lessonRes.ok) throw new Error(lessonData.error || t('dashboard.load_failed'));
        if (!lessonData.has_recent) {
            showNoRecentState();
            return;
        }

        // Render lesson content
        renderHomeDashboard(lessonData);
        if (vocabRes.ok) {
            const vocabData = await vocabRes.json();
            renderDashboardVocabBuckets(vocabData);
        } else {
            renderVocab(lessonData.vocab || {});
        }

        // Render global stats (non-blocking — silently ignore errors)
        if (statsRes.ok) {
            const statsData = await statsRes.json();
            renderGlobalStats(statsData);
        }

    } catch (err) {
        setDashboardState(err.message || t('dashboard.load_failed'), false);
    }
}

function renderHomeDashboard(data) {
    document.getElementById('dashboard-state').style.display = 'none';
    document.getElementById('dashboard-content').style.display = '';

    const lesson = data.lesson || {};
    document.getElementById('home-lesson-title').textContent = `${lesson.hsk_level || 'HSK'} - Lesson ${lesson.lesson || ''}`;
    document.getElementById('home-lesson-subtitle').textContent = t('dashboard.current_part', {
        part: lesson.part || '-',
        count: lesson.passage_ids?.length || 1,
    });
    document.getElementById('home-continue-link').href = `/learning?passage_id=${encodeURIComponent(lesson.passage_id || '')}`;
}

function renderDashboardVocabBuckets(data) {
    dashboardVocabBuckets = data.buckets || {};
    dashboardVocabOrder = (data.order || dashboardVocabOrder).filter(key => dashboardVocabBuckets[key]);
    dashboardVocabIndex = 0;
    renderActiveDashboardVocab();
}

function showDashboardVocabBucket(delta) {
    if (!dashboardVocabOrder.length) return;
    dashboardVocabIndex = (dashboardVocabIndex + delta + dashboardVocabOrder.length) % dashboardVocabOrder.length;
    renderActiveDashboardVocab();
}

function renderActiveDashboardVocab() {
    const key = dashboardVocabOrder[dashboardVocabIndex];
    renderVocab(dashboardVocabBuckets[key] || {});
}

function renderVocab(vocab) {
    const rows = vocab.rows || [];
    const title = document.getElementById('home-vocab-title');
    const count = document.getElementById('home-vocab-count');
    const state = document.getElementById('home-vocab-state');
    const wrap = document.getElementById('home-vocab-table-wrap');
    const viewAllRow = document.getElementById('home-vocab-view-all');
    const viewAllLink = document.getElementById('home-vocab-view-all-link');

    if (title) title.textContent = vocab.title || t('dashboard.vocabulary_kicker');
    count.textContent = t('dashboard.word_count', { count: vocab.total || 0 });
    if (viewAllLink) viewAllLink.href = `/vocab?mode=${encodeURIComponent(vocab.mode || 'standard')}`;

    if (!rows.length) {
        state.textContent = t('dashboard.no_x_found', { title: (vocab.title || t('dashboard.vocabulary_kicker')).toLowerCase() });
        state.style.display = 'block';
        wrap.style.display = 'none';
        if (viewAllRow) viewAllRow.style.display = 'block';
        return;
    }

    const table = document.createElement('table');
    table.className = 'vocab-table home-vocab-table';
    table.innerHTML = `
        <thead>
            <tr>
                <th>${t('dashboard.table_character')}</th>
                <th>${t('dashboard.table_pinyin')}</th>
                <th>${t('dashboard.table_meaning_vn')}</th>
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
            <span class="dashboard-kicker">${t('dashboard.current_lesson')}</span>
            <h1>${t('dashboard.no_lesson_title')}</h1>
            <p>${t('dashboard.no_lesson_body')}</p>
            <a class="btn primary dashboard-action-link" href="/learning">${t('dashboard.open_learning')}</a>
        </div>
    `;
}

function showSignedOutState() {
    document.getElementById('dashboard-content').style.display = 'none';
    document.getElementById('dashboard-state').style.display = 'grid';
    document.getElementById('dashboard-state').innerHTML = `
        <div class="dashboard-empty-state">
            <span class="dashboard-kicker">${t('nav.brand')}</span>
            <h1>${t('dashboard.signed_out_title')}</h1>
            <p>${t('dashboard.signed_out_body')}</p>
            <a class="btn primary dashboard-action-link" href="/login">${t('nav.login')}</a>
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
