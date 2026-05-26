async function fetchRecommendations() {
    const container = document.getElementById('rec-container');

    try {
        const res = await fetch('/api/practice/recommend');
        const data = await res.json();

        if (!res.ok) {
            showError(container, data.error || 'Failed to load recommendations.');
            return;
        }

        const recs = data.recommendations || [];
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

    } catch (e) {
        showError(container, 'Could not connect to the server.');
    }
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
            <a href="${startUrl}" class="btn-start-practice">
                &#9654; Start
            </a>
        </div>
    `;

    return card;
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

fetchRecommendations();
