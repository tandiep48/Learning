let homeVocabPage = 1;
const homeVocabPageSize = 12;

document.addEventListener('DOMContentLoaded', () => {
    loadHomeDashboard();
    document.getElementById('home-vocab-prev')?.addEventListener('click', () => {
        if (homeVocabPage > 1) loadHomeDashboard(homeVocabPage - 1);
    });
    document.getElementById('home-vocab-next')?.addEventListener('click', () => {
        loadHomeDashboard(homeVocabPage + 1);
    });
});

async function loadHomeDashboard(page = 1) {
    setDashboardState('Loading your lesson dashboard...', true);
    try {
        const params = new URLSearchParams({
            page: String(page),
            page_size: String(homeVocabPageSize)
        });
        const res = await fetch(`/api/user/dashboard-current-lesson?${params.toString()}`);
        const contentType = res.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            showSignedOutState();
            return;
        }

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to load dashboard.');
        if (!data.has_recent) {
            showNoRecentState();
            return;
        }

        renderHomeDashboard(data);
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
    renderProgress(data.progress || {});
}

function renderVocab(vocab) {
    const rows = vocab.rows || [];
    const count = document.getElementById('home-vocab-count');
    const state = document.getElementById('home-vocab-state');
    const wrap = document.getElementById('home-vocab-table-wrap');
    const pagination = document.getElementById('home-vocab-pagination');
    const status = document.getElementById('home-vocab-page-status');
    const prev = document.getElementById('home-vocab-prev');
    const next = document.getElementById('home-vocab-next');

    homeVocabPage = vocab.page || 1;
    count.textContent = `${vocab.total || 0} word${vocab.total === 1 ? '' : 's'}`;

    if (!rows.length) {
        state.textContent = 'No vocabulary found for this lesson.';
        state.style.display = 'block';
        wrap.style.display = 'none';
        pagination.style.display = 'none';
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

    const totalPages = vocab.total_pages || 1;
    pagination.style.display = totalPages > 1 ? 'flex' : 'none';
    status.textContent = `Page ${homeVocabPage} / ${totalPages}`;
    prev.disabled = homeVocabPage <= 1;
    next.disabled = homeVocabPage >= totalPages;
}

function renderActivities(activities) {
    const practice = activities.filter(item => item.category === 'practice');
    const exam = activities.filter(item => item.category === 'exam');
    renderActivityList('home-practice-list', practice, 'No exercise groups for this lesson.');
    renderActivityList('home-exam-list', exam, 'No exam groups for this lesson.');
}

function renderActivityList(id, items, emptyText) {
    const list = document.getElementById(id);
    if (!list) return;
    if (!items.length) {
        list.innerHTML = `<div class="dashboard-empty compact">${escapeHtml(emptyText)}</div>`;
        return;
    }

    list.innerHTML = items.map(item => `
        <a class="activity-card" href="${escapeAttr(item.start_url || '#')}">
            <div>
                <span class="activity-badge ${item.category === 'exam' ? 'exam' : 'practice'}">${escapeHtml(item.category === 'exam' ? 'Exam' : 'Exercise')}</span>
                <strong>${escapeHtml(progressLabel(item.progress))}</strong>
            </div>
            <span>${escapeHtml(capitalize(item.skill || 'Practice'))} - ${item.question_count || 0} question${item.question_count === 1 ? '' : 's'}</span>
        </a>
    `).join('');
}

function renderProgress(progress) {
    const total = document.getElementById('home-progress-total');
    const list = document.getElementById('home-progress-list');
    const modes = progress.modes || [];
    total.textContent = `${progress.attempts || 0} attempt${progress.attempts === 1 ? '' : 's'} - ${progress.accuracy_pct || 0}% - ${progress.time_label || '0s'}`;

    if (!modes.length) {
        list.innerHTML = `
            <div class="dashboard-empty progress-empty">
                <span>No lesson trainer activity yet.</span>
                <a class="btn primary dashboard-action-link" href="${escapeAttr(document.getElementById('home-continue-link').href)}">Continue Lesson</a>
            </div>
        `;
        return;
    }

    list.innerHTML = modes.map(item => `
        <div class="progress-card">
            <span>${escapeHtml(capitalize(item.mode))}</span>
            <strong>${item.accuracy_pct || 0}%</strong>
            <small>${item.correct || 0}/${item.attempts || 0} correct - ${escapeHtml(item.time_label || '0s')}</small>
        </div>
    `).join('');
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

function progressLabel(progress) {
    if (!progress) return 'Questions';
    const text = String(progress);
    if (text.includes('-')) return `Questions ${text}`;
    return `Question ${text}`;
}

function capitalize(value) {
    const text = String(value || '');
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeAttr(value) {
    return escapeHtml(value);
}
