let allRecommendations = [];
let currentLevelTab = 'all';
let currentSkillTab = 'all';
let currentCategoryTab = 'all';
let currentStatusTab = 'all';
let selectedMultiItems = [];

async function fetchRecommendations() {
    const container = document.getElementById('rec-container');

    try {
        const res = await fetch('/api/practice/recommend');
        const data = await res.json();

        if (!res.ok) {
            showError(container, data.error || 'Failed to load recommendations.');
            return;
        }

        allRecommendations = data.recommendations || [];

        // If no recommendations, check whether the user is brand-new
        if (allRecommendations.length === 0) {
            try {
                const histRes = await fetch('/api/vocab/has_history');
                const histData = await histRes.json();
                if (!histData.has_history) {
                    showNewUser(container);
                    return;
                }
            } catch (_) { /* fallthrough to normal empty state */ }
        }

        renderRecommendations();

    } catch (e) {
        showError(container, 'Could not connect to the server.');
    }
}

function renderRecommendations() {
    const container = document.getElementById('rec-container');
    
    // Filter by tab
    const recs = allRecommendations.filter(r => {
        const matchLevel    = currentLevelTab    === 'all' || r.level == currentLevelTab;
        const matchSkill    = currentSkillTab    === 'all' || r.skill === currentSkillTab;
        const matchCategory = currentCategoryTab === 'all' || r.category === currentCategoryTab;
        const matchStatus   = currentStatusTab   === 'all' || r.status === currentStatusTab;
        return matchLevel && matchSkill && matchCategory && matchStatus;
    });

    if (recs.length === 0) {
        showEmpty(container);
        return;
    }

    container.innerHTML = '';

    const countEl = document.createElement('p');
    countEl.className = 'results-count';
    countEl.innerHTML = `Found <strong>${recs.length}</strong> question group${recs.length > 1 ? 's' : ''} ready to practice.`;
    container.appendChild(countEl);

    const grid = document.createElement('div');
    grid.className = 'rec-grid';
    recs.forEach(rec => grid.appendChild(buildCard(rec)));
    container.appendChild(grid);

    // Removed coverage bar animation
    
    // Clear selections if they are no longer in the filtered list (optional, but good practice)
    updateMultiSelectUI();
}

function updateMultiSelectUI() {
    const bar = document.getElementById('multi-select-bar');
    const countEl = document.getElementById('multi-select-count');
    
    if (selectedMultiItems.length > 0) {
        bar.classList.remove('hidden');
        countEl.textContent = `${selectedMultiItems.length} item${selectedMultiItems.length > 1 ? 's' : ''} selected`;
    } else {
        bar.classList.add('hidden');
    }
}

function toggleMultiSelect(checkbox, recJson) {
    const rec = JSON.parse(decodeURIComponent(recJson));
    const isChecked = checkbox.checked;
    
    if (isChecked) {
        // Add if not already present
        const exists = selectedMultiItems.some(i => 
            i.level === rec.level && i.lesson === rec.lesson && 
            i.progress === rec.progress && i.category === rec.category
        );
        if (!exists) {
            selectedMultiItems.push({
                level: rec.level,
                lesson: rec.lesson,
                progress: rec.progress,
                category: rec.category || 'practice'
            });
        }
    } else {
        // Remove
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

    const pct = rec.coverage_pct;
    const barClass = pct >= 90 ? 'high' : pct >= 75 ? 'medium' : '';
    const skillIcon = rec.skill === 'listening' ? '🎧' : '📖';
    const skillLabel = rec.skill ? rec.skill.charAt(0).toUpperCase() + rec.skill.slice(1) : '';
    const qCount = rec.questions ? rec.questions.length : 0;
    const categoryLabel = rec.category === 'exam' ? '📝 Exam' : '📋 Practice';
    const categoryClass = rec.category === 'exam' ? 'badge-exam' : 'badge-practice';

    // Removed preview text

    // Deep-link URL
    const startUrl = `/practice/${rec.level}/${rec.lesson}/${encodeURIComponent(rec.progress)}?category=${rec.category || 'practice'}`;
    const recJson = encodeURIComponent(JSON.stringify({
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

        <div class="rec-card-footer">
            <button class="btn-start-practice" onclick="startFromRecommend('${startUrl}')" style="width: 100%; margin-top: 10px;">
                &#9654; Start
            </button>
        </div>
    `;

    return card;
}

function showNewUser(container) {
    container.innerHTML = `
        <div class="state-box new-user-box">
            <div class="state-icon">🌱</div>
            <div class="state-title">Welcome! You're just getting started.</div>
            <div class="state-sub">
                You haven't practiced any vocabulary yet.<br>
                Recommended lessons unlock automatically as you learn words — start with the <strong>Vocabulary Trainer</strong>!
            </div>
            <a href="/vocab" class="btn-start-practice" style="margin-top:20px; display:inline-block; padding: 12px 28px; font-size:1rem;">
                📖 Go to Vocabulary Trainer
            </a>
        </div>
    `;
}

function showEmpty(container) {
    container.innerHTML = `
        <div class="state-box">
            <div class="state-icon">&#127891;</div>
            <div class="state-title">No recommendations yet</div>
            <div class="state-sub">Keep learning vocabulary to unlock recommended practice groups!</div>
        </div>
    `;
}

function showError(container, msg) {
    container.innerHTML = `
        <div class="state-box">
            <div class="state-icon">&#9888;&#65039;</div>
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

// Navigate from recommend — sets referrer for context-aware Back button
function startFromRecommend(url) {
    sessionStorage.setItem('practice_referrer', 'recommend');
    window.location.href = url;
}

// Setup Tabs — Level
document.querySelectorAll('.tab-btn:not(.skill-btn):not(.category-btn):not(.status-btn)').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn:not(.skill-btn):not(.category-btn):not(.status-btn)').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentLevelTab = btn.dataset.level;
        if (allRecommendations.length > 0) renderRecommendations();
    });
});

// Setup Tabs — Skill
document.querySelectorAll('.skill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.skill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentSkillTab = btn.dataset.skill;
        if (allRecommendations.length > 0) renderRecommendations();
    });
});

// Setup Tabs — Category
document.querySelectorAll('.category-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentCategoryTab = btn.dataset.category;
        if (allRecommendations.length > 0) renderRecommendations();
    });
});

// Setup Tabs — Status
document.querySelectorAll('.status-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentStatusTab = btn.dataset.status;
        if (allRecommendations.length > 0) renderRecommendations();
    });
});

fetchRecommendations();
