let allRecommendations = [];
let currentLevelTab    = 'all';
let currentSkillTab    = 'all';
let currentCategoryTab = 'all';
let currentStatusTab   = 'all';
let selectedMultiItems = [];

const PAGE_SIZE = 10;
let currentPage = 1;

// ── Fetch ──────────────────────────────────────────────────────────────────
async function fetchRecommendations() {
    const container = document.getElementById('rec-container');

    try {
        const res  = await fetch('/api/practice/recommend');
        const data = await res.json();

        if (!res.ok) {
            showError(container, data.error || 'Failed to load recommendations.');
            return;
        }

        allRecommendations = data.recommendations || [];

        if (allRecommendations.length === 0) {
            try {
                const histRes  = await fetch('/api/vocab/has_history');
                const histData = await histRes.json();
                if (!histData.has_history) {
                    showNewUser(container);
                    return;
                }
            } catch (_) { /* fallthrough */ }
        }

        renderRecommendations();

    } catch (e) {
        showError(container, 'Could not connect to the server.');
    }
}

// ── Render ─────────────────────────────────────────────────────────────────
function renderRecommendations() {
    const container   = document.getElementById('rec-container');
    const pagBar      = document.getElementById('pagination-bar');

    // Apply filters
    const filtered = allRecommendations.filter(r => {
        const matchLevel    = currentLevelTab    === 'all' || r.level == currentLevelTab;
        const matchSkill    = currentSkillTab    === 'all' || r.skill === currentSkillTab;
        const matchCategory = currentCategoryTab === 'all' || r.category === currentCategoryTab;
        const matchStatus   = currentStatusTab   === 'all' || r.status === currentStatusTab;
        return matchLevel && matchSkill && matchCategory && matchStatus;
    });

    if (filtered.length === 0) {
        showEmpty(container);
        pagBar.style.display = 'none';
        return;
    }

    // Clamp page
    const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1)          currentPage = 1;

    const start = (currentPage - 1) * PAGE_SIZE;
    const pageRecs = filtered.slice(start, start + PAGE_SIZE);

    // Build DOM
    container.innerHTML = '';

    const countEl = document.createElement('p');
    countEl.className = 'results-count';
    countEl.innerHTML = `Found <strong>${filtered.length}</strong> question group${filtered.length > 1 ? 's' : ''} ready to practice.`;
    container.appendChild(countEl);

    const grid = document.createElement('div');
    grid.className = 'rec-grid';
    pageRecs.forEach(rec => grid.appendChild(buildCard(rec)));
    container.appendChild(grid);

    // Pagination bar
    renderPagination(totalPages, filtered.length);
    updateMultiSelectUI();
}

// ── Pagination ─────────────────────────────────────────────────────────────
function renderPagination(totalPages, totalItems) {
    const bar = document.getElementById('pagination-bar');

    if (totalPages <= 1) {
        bar.style.display = 'none';
        return;
    }

    bar.style.display = 'flex';
    bar.innerHTML = '';

    // Prev
    const prev = document.createElement('button');
    prev.className = 'page-btn' + (currentPage === 1 ? ' disabled' : '');
    prev.disabled  = currentPage === 1;
    prev.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
    prev.addEventListener('click', () => { currentPage--; renderRecommendations(); window.scrollTo(0, 0); });
    bar.appendChild(prev);

    // Page number buttons (show max 7 with ellipsis)
    const pages = getPageNumbers(currentPage, totalPages);
    pages.forEach(p => {
        if (p === '…') {
            const dot = document.createElement('span');
            dot.className = 'page-ellipsis';
            dot.textContent = '…';
            bar.appendChild(dot);
        } else {
            const btn = document.createElement('button');
            btn.className = 'page-btn' + (p === currentPage ? ' active' : '');
            btn.textContent = p;
            btn.addEventListener('click', () => { currentPage = p; renderRecommendations(); window.scrollTo(0, 0); });
            bar.appendChild(btn);
        }
    });

    // Next
    const next = document.createElement('button');
    next.className = 'page-btn' + (currentPage === totalPages ? ' disabled' : '');
    next.disabled  = currentPage === totalPages;
    next.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
    next.addEventListener('click', () => { currentPage++; renderRecommendations(); window.scrollTo(0, 0); });
    bar.appendChild(next);

    // Page info text
    const info = document.createElement('span');
    info.className = 'page-info';
    const start = (currentPage - 1) * PAGE_SIZE + 1;
    const end   = Math.min(currentPage * PAGE_SIZE, totalItems);
    info.textContent = `${start}–${end} of ${totalItems}`;
    bar.appendChild(info);
}

function getPageNumbers(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    if (current <= 4) return [1, 2, 3, 4, 5, '…', total];
    if (current >= total - 3) return [1, '…', total-4, total-3, total-2, total-1, total];
    return [1, '…', current-1, current, current+1, '…', total];
}

// ── Multi-select ───────────────────────────────────────────────────────────
function updateMultiSelectUI() {
    const bar     = document.getElementById('multi-select-bar');
    const countEl = document.getElementById('multi-select-count');
    if (selectedMultiItems.length > 0) {
        bar.classList.remove('hidden');
        countEl.textContent = `${selectedMultiItems.length} item${selectedMultiItems.length > 1 ? 's' : ''} selected`;
    } else {
        bar.classList.add('hidden');
    }
}

function toggleMultiSelect(checkbox, recJson) {
    const rec       = JSON.parse(decodeURIComponent(recJson));
    const isChecked = checkbox.checked;
    if (isChecked) {
        const exists = selectedMultiItems.some(i =>
            i.level === rec.level && i.lesson === rec.lesson &&
            i.progress === rec.progress && i.category === rec.category
        );
        if (!exists) {
            selectedMultiItems.push({
                level: rec.level, lesson: rec.lesson,
                progress: rec.progress, category: rec.category || 'practice'
            });
        }
    } else {
        selectedMultiItems = selectedMultiItems.filter(i =>
            !(i.level === rec.level && i.lesson === rec.lesson &&
              i.progress === rec.progress && i.category === (rec.category || 'practice'))
        );
    }
    updateMultiSelectUI();
}

function startMultiRecommend() {
    if (selectedMultiItems.length === 0) return;
    sessionStorage.setItem('multi_practice_queue', JSON.stringify(selectedMultiItems));
    sessionStorage.setItem('practice_referrer', 'recommend');
    window.location.href = '/practice/multi';
}

// ── Card builder ───────────────────────────────────────────────────────────
function progressLabel(progress) {
    if (!progress) return '—';
    if (progress.includes('-')) {
        const [a, b] = progress.split('-');
        return `Questions ${a}–${b}`;
    }
    return `Question ${progress}`;
}

function buildCard(rec) {
    const card = document.createElement('div');
    card.className = 'rec-card';

    const pct           = rec.coverage_pct;
    const barClass      = pct >= 90 ? 'high' : pct >= 75 ? 'medium' : '';
    const skillIcon     = rec.skill === 'listening'
        ? '<i class="fa-solid fa-headphones-simple" aria-hidden="true"></i>'
        : '<i class="fa-solid fa-book-open" aria-hidden="true"></i>';
    const skillLabel    = rec.skill ? rec.skill.charAt(0).toUpperCase() + rec.skill.slice(1) : '';
    const qCount        = rec.questions ? rec.questions.length : 0;
    const categoryLabel = rec.category === 'exam'
        ? '<i class="fa-solid fa-file-lines" aria-hidden="true"></i><span>Exam</span>'
        : '<i class="fa-solid fa-list-check" aria-hidden="true"></i><span>Practice</span>';
    const categoryClass = rec.category === 'exam' ? 'badge-exam' : 'badge-practice';
    const recentWords   = Array.isArray(rec.recent_matched_words) ? rec.recent_matched_words.slice(0, 6) : [];
    const focusHtml     = recentWords.length
        ? `<div class="rec-new-focus">New focus: ${recentWords.map(escapeHtml).join(', ')}</div>`
        : '';

    const startUrl = `/practice/${rec.level}/${rec.lesson}/${encodeURIComponent(rec.progress)}?category=${rec.category || 'practice'}`;
    const recJson  = encodeURIComponent(JSON.stringify({
        level: rec.level, lesson: rec.lesson, progress: rec.progress, category: rec.category
    }));
    const isSelected = selectedMultiItems.some(i =>
        i.level === rec.level && i.lesson === rec.lesson &&
        i.progress === rec.progress && i.category === (rec.category || 'practice')
    );

    card.innerHTML = `
        <div class="rec-card-header">
            <input type="checkbox" class="rec-card-checkbox" ${isSelected ? 'checked' : ''} onchange="toggleMultiSelect(this, '${recJson}')">
            <span class="hsk-badge hsk-${rec.level}">HSK ${rec.level}</span>
            <span class="rec-card-title">Lesson ${rec.lesson}</span>
        </div>
        <div class="rec-card-meta" style="display: flex; align-items: center; gap: 10px; margin-top: -6px;">
            <span class="rec-card-skill">${skillIcon} ${skillLabel}</span>
            <span class="category-badge ${categoryClass}" style="margin-left: 0;">${categoryLabel}</span>
            <span class="status-badge" style="font-size: 0.8em; margin-left: auto; color: var(--text-muted);">${rec.status || 'Not start'}</span>
        </div>

        <div class="rec-progress-label">${progressLabel(rec.progress)} &nbsp;·&nbsp; ${qCount} question${qCount !== 1 ? 's' : ''}</div>
        ${focusHtml}

        <div class="rec-card-footer">
            <button class="btn-start-practice" onclick="startFromRecommend('${startUrl}')" style="width: 100%; margin-top: 10px;">
                <i class="fa-solid fa-play" aria-hidden="true"></i><span>Start</span>
            </button>
        </div>
    `;

    return card;
}

// ── State views ────────────────────────────────────────────────────────────
function showNewUser(container) {
    document.getElementById('pagination-bar').style.display = 'none';
    container.innerHTML = `
        <div class="state-box new-user-box">
            <div class="state-icon"><i class="fa-solid fa-seedling" aria-hidden="true"></i></div>
            <div class="state-title">Welcome! You're just getting started.</div>
            <div class="state-sub">
                You haven't practiced any vocabulary yet.<br>
                Recommended lessons unlock automatically as you learn words — start with the <strong>Vocabulary Trainer</strong>!
            </div>
            <a href="/vocab" class="btn-start-practice" style="margin-top:20px; display:inline-block; padding: 12px 28px; font-size:1rem;">
                <i class="fa-solid fa-book-open" aria-hidden="true"></i><span>Go to Vocabulary Trainer</span>
            </a>
        </div>
    `;
}

function showEmpty(container) {
    container.innerHTML = `
        <div class="state-box">
            <div class="state-icon"><i class="fa-solid fa-graduation-cap" aria-hidden="true"></i></div>
            <div class="state-title">No recommendations yet</div>
            <div class="state-sub">Keep learning vocabulary to unlock recommended practice groups!</div>
        </div>
    `;
}

function showError(container, msg) {
    document.getElementById('pagination-bar').style.display = 'none';
    container.innerHTML = `
        <div class="state-box">
            <div class="state-icon"><i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i></div>
            <div class="state-title">Something went wrong</div>
            <div class="state-sub">${escapeHtml(msg)}</div>
        </div>
    `;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function startFromRecommend(url) {
    sessionStorage.setItem('practice_referrer', 'recommend');
    window.location.href = url;
}

// ── Dropdown filter wiring ─────────────────────────────────────────────────
function onFilterChange() {
    currentLevelTab    = document.getElementById('filter-level').value;
    currentSkillTab    = document.getElementById('filter-skill').value;
    currentCategoryTab = document.getElementById('filter-category').value;
    currentStatusTab   = document.getElementById('filter-status').value;
    currentPage = 1; // reset to first page on any filter change
    if (allRecommendations.length > 0) renderRecommendations();
}

document.getElementById('filter-level').addEventListener('change', onFilterChange);
document.getElementById('filter-skill').addEventListener('change', onFilterChange);
document.getElementById('filter-category').addEventListener('change', onFilterChange);
document.getElementById('filter-status').addEventListener('change', onFilterChange);

fetchRecommendations();
