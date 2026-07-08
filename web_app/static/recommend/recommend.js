let allRecommendations = [];
let currentLevelTab = 'all';
let currentSkillTab = 'all';
let currentCategoryTab = 'all';
let currentStatusTab = 'Not start';

const PAGE_SIZE = 10;
let currentPage = 1;
let recommendSelection;

async function fetchRecommendations() {
    const container = document.getElementById('rec-container');

    try {
        const res = await fetch('/api/practice/recommend');
        const data = await res.json();

        if (!res.ok) {
            showError(container, data.error || t('recommend.failed_load'));
            return;
        }

        allRecommendations = data.recommendations || [];

        if (allRecommendations.length === 0) {
            try {
                const histRes = await fetch('/api/vocab/has_history');
                const histData = await histRes.json();
                if (!histData.has_history) {
                    showNewUser(container);
                    return;
                }
            } catch (_) {
                // Continue to the regular empty state.
            }
        }

        renderRecommendations();
    } catch (e) {
        showError(container, t('recommend.connect_failed'));
    }
}

function renderRecommendations() {
    const container = document.getElementById('rec-container');
    const pagBar = document.getElementById('pagination-bar');

    const filtered = allRecommendations.filter(r => {
        const matchLevel = currentLevelTab === 'all' || r.level == currentLevelTab;
        const matchSkill = currentSkillTab === 'all' || r.skill === currentSkillTab;
        const matchCategory = currentCategoryTab === 'all' || r.category === currentCategoryTab;
        const status = r.status || 'Not start';
        const matchStatus = currentStatusTab === 'all' || status === currentStatusTab;
        return matchLevel && matchSkill && matchCategory && matchStatus;
    });

    if (filtered.length === 0) {
        showEmpty(container);
        pagBar.style.display = 'none';
        return;
    }

    const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const start = (currentPage - 1) * PAGE_SIZE;
    const pageRecs = filtered.slice(start, start + PAGE_SIZE);

    container.innerHTML = '';

    const countEl = document.createElement('p');
    countEl.className = 'results-count';
    countEl.innerHTML = t('recommend.groups_found', { count: `<strong>${filtered.length}</strong>` });
    container.appendChild(countEl);

    const grid = document.createElement('div');
    grid.className = 'rec-grid';
    pageRecs.forEach(rec => grid.appendChild(recommendSelection.buildCard(rec)));
    container.appendChild(grid);

    renderPagination(totalPages, filtered.length);
    updateMultiSelectUI();
}

function renderPagination(totalPages, totalItems) {
    const bar = document.getElementById('pagination-bar');

    if (totalPages <= 1) {
        bar.style.display = 'none';
        return;
    }

    bar.style.display = 'flex';
    bar.innerHTML = '';

    const prev = document.createElement('button');
    prev.className = 'page-btn' + (currentPage === 1 ? ' disabled' : '');
    prev.disabled = currentPage === 1;
    prev.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
    prev.addEventListener('click', () => {
        currentPage--;
        renderRecommendations();
        window.scrollTo(0, 0);
    });
    bar.appendChild(prev);

    getPageNumbers(currentPage, totalPages).forEach(page => {
        if (page === '...') {
            const dot = document.createElement('span');
            dot.className = 'page-ellipsis';
            dot.textContent = '...';
            bar.appendChild(dot);
            return;
        }

        const btn = document.createElement('button');
        btn.className = 'page-btn' + (page === currentPage ? ' active' : '');
        btn.textContent = page;
        btn.addEventListener('click', () => {
            currentPage = page;
            renderRecommendations();
            window.scrollTo(0, 0);
        });
        bar.appendChild(btn);
    });

    const next = document.createElement('button');
    next.className = 'page-btn' + (currentPage === totalPages ? ' disabled' : '');
    next.disabled = currentPage === totalPages;
    next.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
    next.addEventListener('click', () => {
        currentPage++;
        renderRecommendations();
        window.scrollTo(0, 0);
    });
    bar.appendChild(next);

    const info = document.createElement('span');
    info.className = 'page-info';
    const start = (currentPage - 1) * PAGE_SIZE + 1;
    const end = Math.min(currentPage * PAGE_SIZE, totalItems);
    info.textContent = `${start}-${end} of ${totalItems}`;
    bar.appendChild(info);
}

function getPageNumbers(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    if (current <= 4) return [1, 2, 3, 4, 5, '...', total];
    if (current >= total - 3) return [1, '...', total - 4, total - 3, total - 2, total - 1, total];
    return [1, '...', current - 1, current, current + 1, '...', total];
}

function updateMultiSelectUI() {
    const bar = document.getElementById('multi-select-bar');
    const countEl = document.getElementById('multi-select-count');
    const count = recommendSelection.getSelectedCount();
    if (count > 0) {
        bar.classList.remove('hidden');
        document.body.classList.add('has-multi-select');
        countEl.textContent = t('recommend.items_selected', { count });
    } else {
        bar.classList.add('hidden');
        document.body.classList.remove('has-multi-select');
    }
}

function startMultiRecommend() {
    recommendSelection.startSelected('recommend');
}

function showNewUser(container) {
    document.getElementById('pagination-bar').style.display = 'none';
    container.innerHTML = `
        <div class="state-box new-user-box">
            <div class="state-icon"><i class="fa-solid fa-seedling" aria-hidden="true"></i></div>
            <div class="state-title">Welcome! You're just getting started.</div>
            <div class="state-sub">
                You haven't practiced any vocabulary yet.<br>
                Recommended lessons unlock automatically as you learn words - start with the <strong>Vocabulary Trainer</strong>!
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
            <div class="state-sub">${RecommendCards.escapeHtml(msg)}</div>
        </div>
    `;
}

function startFromRecommend(url) {
    sessionStorage.setItem('practice_referrer', 'recommend');
    window.location.href = url;
}

function onFilterChange() {
    currentLevelTab = document.getElementById('filter-level').value;
    currentSkillTab = document.getElementById('filter-skill').value;
    currentCategoryTab = document.getElementById('filter-category').value;
    currentStatusTab = document.getElementById('filter-status').value;
    currentPage = 1;
    if (allRecommendations.length > 0) renderRecommendations();
}

document.getElementById('filter-level').addEventListener('change', onFilterChange);
document.getElementById('filter-skill').addEventListener('change', onFilterChange);
document.getElementById('filter-category').addEventListener('change', onFilterChange);
document.getElementById('filter-status').addEventListener('change', onFilterChange);

recommendSelection = RecommendCards.createSelection({ onChange: updateMultiSelectUI });
document.getElementById('filter-status').value = currentStatusTab;
fetchRecommendations();
