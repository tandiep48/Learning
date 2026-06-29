// static/shared/sidebar.js
let sidebarPassageId = null;
let currentDomain = null; // 'lesson', 'vocab', 'grammar'

document.addEventListener('DOMContentLoaded', () => {
    // Determine current domain from URL
    const path = window.location.pathname;
    if (path.includes('reading')) currentDomain = 'lesson';
    else if (path.includes('vocab-learning')) currentDomain = 'vocab';
    else if (path.includes('grammar')) currentDomain = 'grammar';

    // Highlight current domain button
    if (currentDomain) {
        const btn = document.getElementById(`sidebar-nav-${currentDomain}`);
        if (btn) btn.classList.add('active');
    }

    // Extract passage ID from URL
    const params = new URLSearchParams(window.location.search);
    sidebarPassageId = params.get('passage_id');

    if (sidebarPassageId) {
        loadSidebarParts(sidebarPassageId);
    }
});

function toggleSidebar() {
    const sidebar = document.getElementById('universal-sidebar');
    const layout  = document.getElementById('page-layout');
    if (!sidebar || !layout) return;

    if (sidebar.classList.contains('collapsed')) {
        // Open
        sidebar.classList.remove('collapsed');
        layout.classList.add('sidebar-open');
    } else {
        // Close
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
    }
    window.location.href = url;
}

function navigateToPart(newPassageId) {
    sidebarPassageId = newPassageId;
    navigateToDomain(currentDomain || 'lesson');
}

async function loadSidebarParts(passageId) {
    const partsContainer = document.getElementById('sidebar-parts-list');
    if (!partsContainer) return;

    const partsStr = passageId.split('_');
    if (partsStr.length < 2) {
        partsContainer.innerHTML = '<div class="sidebar-loader">Invalid passage ID</div>';
        return;
    }

    const hskLevelCode = partsStr[0]; // e.g. H1
    const lessonNum    = partsStr[1];

    const hskMap = {
        'H1': 'HSK1', 'H2': 'HSK2', 'H3': 'HSK3',
        'H4': 'HSK4', 'H5': 'HSK5', 'H6': 'HSK6', 'H79': 'HSK7-9'
    };
    const hskLevel = hskMap[hskLevelCode] || hskLevelCode;

    try {
        const res  = await fetch(`/api/lesson/passages?hsk_level=${hskLevel}`);
        const data = await res.json();

        let lessonPassages = data.passages.filter(p => {
            const pParts = p.passage_id.split('_');
            return pParts.length >= 2 && pParts[1] === lessonNum;
        });

        // Hardcode exception for H1_1
        if (hskLevel === 'HSK1' && lessonNum === '1') {
            lessonPassages = lessonPassages.filter(p => !p.passage_id.startsWith('H1_1_'));
            lessonPassages.push({ passage_id: 'H1_1_1', title: 'Pinyin' });
        }

        // Sort passages by part number
        lessonPassages.sort((a, b) => {
            const aPart = parseInt(a.passage_id.split('_')[2]) || 0;
            const bPart = parseInt(b.passage_id.split('_')[2]) || 0;
            return aPart - bPart;
        });

        if (lessonPassages.length === 0) {
            partsContainer.innerHTML = '<div class="sidebar-loader">No parts found.</div>';
            return;
        }

        partsContainer.innerHTML = lessonPassages.map(p => {
            const pParts  = p.passage_id.split('_');
            const partNum = pParts.length > 2 ? pParts[2] : '1';
            const isActive = p.passage_id === passageId;
            const title    = p.title || `Part ${partNum}`;
            return `<button class="sidebar-part-btn ${isActive ? 'active' : ''}" onclick="navigateToPart('${p.passage_id}')">${title}</button>`;
        }).join('');

    } catch (e) {
        console.error('Sidebar parts load failed', e);
        partsContainer.innerHTML = '<div class="sidebar-loader">Failed to load parts.</div>';
    }
}
