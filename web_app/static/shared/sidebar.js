// static/shared/sidebar.js
let sidebarPassageId = null;
let currentDomain = null; // 'lesson', 'vocab', 'grammar', 'translation'
var NUMBER_PART_ID = window.NUMBER_PART_ID || 'H1_5_99';
window.NUMBER_PART_ID = NUMBER_PART_ID;

const SIDEBAR_HSK_MAP = {
    'H1': 'HSK1', 'H2': 'HSK2', 'H3': 'HSK3',
    'H4': 'HSK4', 'H5': 'HSK5', 'H6': 'HSK6', 'H79': 'HSK7-9'
};

function isNumberPart(passageId) {
    return String(passageId || '') === NUMBER_PART_ID;
}

function isBookPassageId(passageId) {
    // Book passages are "<book_code>_<lesson>_<part>" (e.g. AML_1_1); the prefix
    // is a book code, not an "H<level>" HSK level.
    const prefix = String(passageId || '').split('_')[0];
    return !!prefix && !/^H\d+$/i.test(prefix);
}

function sidebarEscapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', () => {
    // Determine current domain from URL
    const path = window.location.pathname;
    if (path.includes('reading')) currentDomain = 'lesson';
    else if (path.includes('vocab-learning')) currentDomain = 'vocab';
    else if (path.includes('grammar')) currentDomain = 'grammar';
    else if (path.includes('translation')) currentDomain = 'translation';

    // Extract passage ID from URL
    const params = new URLSearchParams(window.location.search);
    sidebarPassageId = params.get('passage_id');

    initAccordion();
    highlightCurrentDomain();

    if (sidebarPassageId) {
        populateSidebarHeader(sidebarPassageId);
        loadSidebarParts(sidebarPassageId);
    }
});

// ── Accordion ──────────────────────────────────────────────────────────────
function initAccordion() {
    document.querySelectorAll('.accordion-header').forEach(header => {
        header.addEventListener('click', () => {
            openAccordionItem(header.closest('.accordion-item'));
        });
    });

    // Open the section matching the current domain (parts by default).
    let targetId = 'acc-parts';
    if (currentDomain === 'grammar') targetId = 'acc-grammar';
    else if (currentDomain === 'translation') targetId = 'acc-translation';
    const body = document.getElementById(targetId);
    if (body) openAccordionItem(body.closest('.accordion-item'));
}

function openAccordionItem(item) {
    if (!item) return;
    document.querySelectorAll('.accordion-item').forEach(it => {
        const body = it.querySelector('.accordion-body');
        const arrow = it.querySelector('.acc-arrow');
        const isTarget = it === item;
        it.classList.toggle('active', isTarget);
        if (body) body.style.display = isTarget ? 'block' : 'none';
        if (arrow) {
            arrow.classList.toggle('ph-caret-up', isTarget);
            arrow.classList.toggle('ph-caret-down', !isTarget);
        }
    });
}

function highlightCurrentDomain() {
    if (!currentDomain) return;
    const btn = document.getElementById(`sidebar-nav-${currentDomain}`);
    if (btn) btn.classList.add('active');
}

// ── Toggle / navigation ─────────────────────────────────────────────────────
function toggleSidebar() {
    const sidebar = document.getElementById('universal-sidebar');
    const layout = document.getElementById('page-layout');
    if (!sidebar || !layout) return;

    if (sidebar.classList.contains('collapsed')) {
        sidebar.classList.remove('collapsed');
        layout.classList.add('sidebar-open');
    } else {
        sidebar.classList.add('collapsed');
        layout.classList.remove('sidebar-open');
    }
}

function goBackToPartPicker() {
    if (sidebarPassageId) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(sidebarPassageId)}&show_parts=true`;
    } else {
        window.location.href = '/learning';
    }
}

function navigateToDomain(domain) {
    if (!sidebarPassageId) return;
    let url = '';
    if (domain === 'lesson') {
        url = `/reading?passage_id=${encodeURIComponent(sidebarPassageId)}&mode=lesson-learner&flow=lesson-part`;
    } else if (domain === 'vocab') {
        url = `/vocab-learning?passage_id=${encodeURIComponent(sidebarPassageId)}&flow=lesson-part`;
    } else if (domain === 'grammar') {
        url = `/grammar?passage_id=${encodeURIComponent(sidebarPassageId)}&flow=lesson-part`;
    } else if (domain === 'translation') {
        url = `/translation?passage_id=${encodeURIComponent(sidebarPassageId)}&flow=lesson-part`;
    }
    window.location.href = url;
}

function navigateToPart(newPassageId) {
    sidebarPassageId = newPassageId;
    // Word/Lesson Summary are content tabs now, so a part opens in its Word/Lesson
    // view; keep the current one if we're already in it, else default to Word Summary.
    const domain = (currentDomain === 'vocab' || currentDomain === 'lesson') ? currentDomain : 'vocab';
    navigateToDomain(domain);
}

// ── Header + parts ──────────────────────────────────────────────────────────
function populateSidebarHeader(passageId) {
    const parts = passageId.split('_');
    const hskLevel = SIDEBAR_HSK_MAP[parts[0]] || parts[0];
    const lessonNum = parts.length >= 2 ? parts[1] : '';
    const badge = document.getElementById('sidebar-hsk-badge');
    const title = document.getElementById('sidebar-lesson-title');
    if (badge) badge.textContent = hskLevel;
    if (title) title.textContent = lessonNum ? `${t('picker.lesson_prefix')} ${lessonNum}` : t('sidebar.navigation');
}

async function loadPartsProgress(hskLevel) {
    try {
        const res = await fetch(`/api/lesson/picker-progress?hsk_level=${encodeURIComponent(hskLevel)}`);
        if (!res.ok) return null;
        return await res.json();
    } catch (_) {
        return null;
    }
}

async function loadSidebarParts(passageId) {
    const partsContainer = document.getElementById('sidebar-parts-list');
    if (!partsContainer) return;

    const partsStr = passageId.split('_');
    if (partsStr.length < 2) {
        partsContainer.innerHTML = '<div class="sidebar-loader">Invalid passage ID</div>';
        return;
    }

    if (isBookPassageId(passageId)) {
        return loadSidebarBookParts(partsContainer, passageId);
    }

    const hskLevelCode = partsStr[0]; // e.g. H1
    const lessonNum = partsStr[1];
    const hskLevel = SIDEBAR_HSK_MAP[hskLevelCode] || hskLevelCode;

    try {
        const [data, progress] = await Promise.all([
            fetch(`/api/lesson/passages?hsk_level=${hskLevel}`).then(r => r.json()),
            loadPartsProgress(hskLevel),
        ]);

        let lessonPassages = data.passages.filter(p => {
            const pParts = p.passage_id.split('_');
            return pParts.length >= 2 && pParts[1] === lessonNum;
        });

        // Hardcode exception for H1_1
        if (hskLevel === 'HSK1' && lessonNum === '1') {
            lessonPassages = lessonPassages.filter(p => !p.passage_id.startsWith('H1_1_'));
            lessonPassages.push({ passage_id: 'H1_1_1', title: t('sidebar.pinyin_title') });
        }
        if (hskLevel === 'HSK1' && lessonNum === '5' && !lessonPassages.some(p => p.passage_id === NUMBER_PART_ID)) {
            lessonPassages.push({ passage_id: NUMBER_PART_ID, title: t('picker.number_part') });
        }

        // Sort passages by part number
        lessonPassages.sort((a, b) => {
            if (isNumberPart(a.passage_id)) return -1;
            if (isNumberPart(b.passage_id)) return 1;
            const aPart = parseInt(a.passage_id.split('_')[2]) || 0;
            const bPart = parseInt(b.passage_id.split('_')[2]) || 0;
            return aPart - bPart;
        });

        if (lessonPassages.length === 0) {
            partsContainer.innerHTML = `<div class="sidebar-loader">${t('sidebar.no_parts_found')}</div>`;
            return;
        }

        partsContainer.innerHTML = lessonPassages
            .map(p => renderPartStep(p, passageId, progress))
            .join('');

    } catch (e) {
        console.error('Sidebar parts load failed', e);
        partsContainer.innerHTML = `<div class="sidebar-loader">${t('sidebar.failed_load_parts')}</div>`;
    }
}

async function loadSidebarBookParts(partsContainer, passageId) {
    const pStr = passageId.split('_');
    const bookCode = pStr[0];
    const lessonNum = pStr[1];
    try {
        const res = await fetch(`/api/lesson/book/${encodeURIComponent(bookCode)}`);
        const data = await res.json();
        const lesson = (data.lessons || []).find(l => String(l.lesson) === String(lessonNum));
        const parts = (lesson?.parts || [])
            .slice()
            .sort((a, b) => (parseInt(a.part) || 0) - (parseInt(b.part) || 0));

        if (!parts.length) {
            partsContainer.innerHTML = `<div class="sidebar-loader">${t('sidebar.no_parts_found')}</div>`;
            return;
        }

        // Book parts show no mini-stats — pass null progress so renderPartStep
        // renders just the part label.
        partsContainer.innerHTML = parts
            .map(p => renderPartStep(p, passageId, null))
            .join('');
    } catch (e) {
        console.error('Sidebar book parts load failed', e);
        partsContainer.innerHTML = `<div class="sidebar-loader">${t('sidebar.failed_load_parts')}</div>`;
    }
}

function renderPartStep(p, activePassageId, progress) {
    const pParts = p.passage_id.split('_');
    const partNum = pParts.length > 2 ? pParts[2] : '1';
    const isActive = p.passage_id === activePassageId;
    const number = isNumberPart(p.passage_id);
    const label = p.title || (number ? t('picker.number_part') : `${t('picker.part_prefix')} ${partNum}`);
    const iconContent = number ? '#' : partNum;

    const stat = progress?.parts?.[p.passage_id];
    const statsHtml = stat ? renderMiniStats(stat) : '';

    return `<button class="sidebar-step ${isActive ? 'active' : ''}" onclick="navigateToPart('${p.passage_id}')">
        <div class="step-icon">${sidebarEscapeHtml(iconContent)}</div>
        <div class="step-info">
            <span class="step-label">${sidebarEscapeHtml(label)}</span>
            ${statsHtml}
        </div>
    </button>`;
}

function sidebarPct(done, total) {
    if (!total || total <= 0) return 0;
    return Math.max(0, Math.min(100, Math.round(((Number(done) || 0) / total) * 100)));
}

function renderMiniStats(stat) {
    const wordsPct = sidebarPct(stat.learned_words, stat.total_words);
    const lessonPct = Math.max(0, Math.min(100, Math.round(Number(stat.progress_pct) || 0)));
    const wordsFull = (stat.total_words || 0) > 0 && wordsPct >= 100;
    const lessonFull = lessonPct >= 100;

    return `<div class="sidebar-part-stats">
        <div class="mini-stat">
            <span class="label">${t('picker.words_label')}</span>
            <div class="mini-progress-bg"><div class="mini-progress-fill ${wordsFull ? 'success' : ''}" style="width:${wordsPct}%;"></div></div>
            <span class="value ${wordsFull ? 'success-text' : ''}">${Number(stat.learned_words) || 0}/${Number(stat.total_words) || 0}</span>
        </div>
        <div class="mini-stat">
            <span class="label">${t('picker.lesson_progress_label')}</span>
            <div class="mini-progress-bg"><div class="mini-progress-fill ${lessonFull ? 'success' : ''}" style="width:${lessonPct}%;"></div></div>
            <span class="value ${lessonFull ? 'success-text' : ''}">${lessonPct}%</span>
        </div>
    </div>`;
}
