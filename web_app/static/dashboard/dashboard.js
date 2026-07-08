document.addEventListener('DOMContentLoaded', () => {
    dashboardRecommendationSelection = RecommendCards.createSelection({
        onChange: updateDashboardRecommendationActions,
    });
    document.getElementById('dashboard-start-selected')?.addEventListener('click', () => {
        dashboardRecommendationSelection.startSelected('dashboard');
    });
    loadHomeDashboard();
});

let dashboardRecommendationSelection;

async function loadHomeDashboard() {
    setDashboardState(t('dashboard.loading'), true);
    try {
        const [lessonRes, statsRes, recommendRes] = await Promise.all([
            fetch('/api/user/dashboard-current-lesson?page=1&page_size=5'),
            fetch('/api/user/global-stats'),
            fetch('/api/practice/recommend?limit=4&status=Not%20start'),
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

        renderHomeDashboard(lessonData);
        renderDashboardRecommendations(recommendRes);

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

async function renderDashboardRecommendations(response) {
    const state = document.getElementById('dashboard-recommend-state');
    const grid = document.getElementById('dashboard-recommend-grid');

    try {
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || t('dashboard.recommend_error'));
        }

        const data = await response.json();
        const recommendations = (data.recommendations || []).slice(0, 4);

        grid.innerHTML = '';
        if (!recommendations.length) {
            state.textContent = t('dashboard.recommend_empty');
            state.style.display = 'block';
            grid.style.display = 'none';
            updateDashboardRecommendationActions();
            return;
        }

        recommendations.forEach(rec => {
            grid.appendChild(dashboardRecommendationSelection.buildCard(rec));
        });
        state.style.display = 'none';
        grid.style.display = 'grid';
        updateDashboardRecommendationActions();
    } catch (err) {
        state.textContent = err.message || t('dashboard.recommend_error');
        state.style.display = 'block';
        grid.style.display = 'none';
        updateDashboardRecommendationActions();
    }
}

function updateDashboardRecommendationActions() {
    const actions = document.getElementById('dashboard-recommend-actions');
    const selected = document.getElementById('dashboard-recommend-selected');
    const count = dashboardRecommendationSelection?.getSelectedCount() || 0;
    if (selected) selected.textContent = t('recommend.items_selected', { count });
    if (actions) actions.classList.toggle('is-visible', count > 0);
}

function renderGlobalStats(data) {
    const buckets = data.buckets || {};

    const totalTimeEl = document.getElementById('stat-total-time');
    const totalWordsEl = document.getElementById('stat-total-words');
    if (totalTimeEl) totalTimeEl.textContent = data.total_time_label || '0s';
    if (totalWordsEl) totalWordsEl.textContent = (data.total_words || 0).toLocaleString();

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
