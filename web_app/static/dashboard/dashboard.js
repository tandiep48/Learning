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

        renderTimeChart();
        renderWordsChart();
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

let wordsChartInstance = null;
let timeChartInstance = null;

function formatChartDate(iso) {
    const parts = String(iso || '').split('-').map(Number);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    if (parts.length !== 3 || !months[parts[1] - 1]) return String(iso || '');
    return `${months[parts[1] - 1]} ${parts[2]}`;
}

// "Words Mastered (Last 3 Days)" bar chart. Pulls per-day learned-word counts and
// renders with Chart.js; shows an empty state when there is no recent activity.
async function renderWordsChart() {
    const canvas = document.getElementById('wordsChart');
    const emptyEl = document.getElementById('wordsChartEmpty');
    if (!canvas || typeof Chart === 'undefined') return;

    let days = [];
    try {
        const res = await fetch('/api/user/learned-words-last-3-days');
        if (res.ok) {
            const data = await res.json();
            days = data.days || [];
        }
    } catch (e) {
        console.warn('Could not load learned-words chart data', e);
    }

    if (!days.length) {
        canvas.style.display = 'none';
        if (emptyEl) emptyEl.style.display = 'block';
        if (wordsChartInstance) { wordsChartInstance.destroy(); wordsChartInstance = null; }
        return;
    }

    canvas.style.display = '';
    if (emptyEl) emptyEl.style.display = 'none';

    const labels = days.map(d => formatChartDate(d.date));
    const counts = days.map(d => d.count);

    if (wordsChartInstance) wordsChartInstance.destroy();
    wordsChartInstance = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: t('dashboard.words_mastered'),
                data: counts,
                backgroundColor: '#007a61',
                borderRadius: 6,
                barPercentage: 0.5,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { backgroundColor: '#111827', padding: 12, cornerRadius: 8 },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0 },
                    grid: { color: '#f3f4f6' },
                    border: { display: false },
                },
                x: {
                    grid: { display: false },
                    border: { display: false },
                },
            },
        },
    });
}

// "Time Learned (Last 3 Days)" bar chart — hours studied per day.
async function renderTimeChart() {
    const canvas = document.getElementById('timeChart');
    const emptyEl = document.getElementById('timeChartEmpty');
    if (!canvas || typeof Chart === 'undefined') return;

    let days = [];
    try {
        const res = await fetch('/api/user/time-learned-last-3-days');
        if (res.ok) {
            const data = await res.json();
            days = data.days || [];
        }
    } catch (e) {
        console.warn('Could not load time-learned chart data', e);
    }

    if (!days.length) {
        canvas.style.display = 'none';
        if (emptyEl) emptyEl.style.display = 'block';
        if (timeChartInstance) { timeChartInstance.destroy(); timeChartInstance = null; }
        return;
    }

    canvas.style.display = '';
    if (emptyEl) emptyEl.style.display = 'none';

    const labels = days.map(d => formatChartDate(d.date));
    const minutes = days.map(d => d.minutes);

    if (timeChartInstance) timeChartInstance.destroy();
    timeChartInstance = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: t('dashboard.minutes_label'),
                data: minutes,
                backgroundColor: '#007a61',
                borderRadius: 6,
                barPercentage: 0.5,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#111827',
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: { label: ctx => `${ctx.parsed.y}m` },
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#f3f4f6' },
                    border: { display: false },
                    ticks: { precision: 0, callback: value => `${value}m` },
                },
                x: {
                    grid: { display: false },
                    border: { display: false },
                },
            },
        },
    });
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
