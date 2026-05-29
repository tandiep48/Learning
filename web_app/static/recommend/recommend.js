let allRecommendations = [];
let currentLevelTab = 'all';
let currentSkillTab = 'all';
let currentCategoryTab = 'all';

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
        return matchLevel && matchSkill && matchCategory;
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

    // Animate coverage bars after paint
    requestAnimationFrame(() => {
        document.querySelectorAll('.coverage-bar-fill').forEach(bar => {
            bar.style.width = bar.dataset.pct + '%';
        });
    });
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

    // Preview: first non-null content line
    const previewQ = rec.questions && rec.questions.find(q => q.content);
    const previewText = previewQ ? previewQ.content.split('\n')[0] : '—';

    // Deep-link URL
    const startUrl = `/practice/${rec.level}/${rec.lesson}/${encodeURIComponent(rec.progress)}`;

    card.innerHTML = `
        <div class="rec-card-header">
            <span class="hsk-badge hsk-${rec.level}">HSK ${rec.level}</span>
            <span class="rec-card-title">Lesson ${rec.lesson}</span>
            <span class="rec-card-skill">${skillIcon} ${skillLabel}</span>
            <span class="category-badge ${categoryClass}">${categoryLabel}</span>
        </div>

        <div class="rec-progress-label">${progressLabel(rec.progress)} &nbsp;·&nbsp; ${qCount} question${qCount !== 1 ? 's' : ''}</div>

        <div class="coverage-section">
            <div class="coverage-label">
                <span>Vocabulary coverage</span>
                <span class="coverage-pct">${pct}%</span>
            </div>
            <div class="coverage-bar-track">
                <div class="coverage-bar-fill ${barClass}" data-pct="${pct}" style="width:0%"></div>
            </div>
        </div>

        <div class="rec-preview">
            <div class="preview-label">Preview</div>
            <div class="preview-text">${escapeHtml(previewText)}</div>
        </div>

        <div class="rec-card-footer">
            <span class="word-count">
                <strong>${rec.known_words}</strong> / ${rec.total_words} words mastered
            </span>
            <button class="btn-start-practice" onclick="startFromRecommend('${startUrl}')">
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
document.querySelectorAll('.tab-btn:not(.skill-btn):not(.category-btn)').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn:not(.skill-btn):not(.category-btn)').forEach(b => b.classList.remove('active'));
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

fetchRecommendations();
