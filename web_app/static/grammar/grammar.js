let currentPassageId = null;
let isLessonPartFlow = false;

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const autoPassage = params.get('passage_id');
    isLessonPartFlow = params.get('flow') === 'lesson-part';

    Picker.init((passage) => {
        loadGrammar(passage.passage_id);
    }, 'Grammar', !autoPassage);

    const backLink = document.getElementById('picker-back-link');
    if (backLink) {

        backLink.href = '/learning';
        backLink.innerHTML = '&larr; Back to Learning';
    }

    if (autoPassage) {
        loadGrammar(autoPassage);
    }
});

function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

function goHome() {
    if (currentPassageId) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(currentPassageId)}&show_parts=true`;
    } else {
        window.location.href = '/learning';
    }
}

function goBackToPartSelection() {
    if (currentPassageId) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(currentPassageId)}&show_parts=true`;
    } else {
        window.location.href = '/learning';
    }
}

async function loadGrammar(passageId) {
    currentPassageId = passageId;
    const learningLink = document.getElementById('grammar-learning-link');
    if (learningLink) {
        learningLink.href = `/learning?passage_id=${encodeURIComponent(passageId)}`;
        learningLink.textContent = isLessonPartFlow ? t('grammar.finish') : t('nav.learning');
    }
    switchScreen('screen-loading');

    try {
        const res = await fetch(`/api/lesson/grammar/${encodeURIComponent(passageId)}`);
        const data = await res.json();
        // Build clickable breadcrumb
        if (window.buildBreadcrumb) buildBreadcrumb('grammar-breadcrumb', passageId);

        if (data.grammar && data.grammar.length > 0) {
            const sections = splitGrammarByType1(data.grammar);
            renderGrammar(sections, document.getElementById('grammar-body'));
        } else {
            document.getElementById('grammar-body').innerHTML =
                `<div style="padding:20px;text-align:center;color:#666;">${t('grammar.no_rules')}</div>`;
        }

        switchScreen('screen-grammar');
    } catch (e) {
        document.getElementById('grammar-body').innerHTML =
            `<div style="color:red;padding:20px;">${t('grammar.error_loading')}</div>`;
        switchScreen('screen-grammar');
    }
}

// Split the flat, id-ordered grammar list into sections, starting a new section at
// each type=1 row (e.g. [1,2,4,2,2,1,4,3,2] -> [[1,2,4,2,2],[1,4,3,2]]).
function splitGrammarByType1(grammarList) {
    const sections = [];
    let current = null;
    grammarList.forEach(g => {
        if (g.type === 1 || current === null) {
            current = [];
            sections.push(current);
        }
        current.push(g);
    });
    return sections;
}

function renderGrammar(sections, container) {
    let html = '<div class="grammar-content">';
    sections.forEach(section => {
        html += '<div class="grammar-section">';
        section.forEach(g => { html += renderGrammarItem(g); });
        html += '</div>';
    });
    html += '</div>';
    container.innerHTML = html;
}

function renderGrammarItem(g) {
    if (g.type === 1) {
        return `<h3 class="grammar-title">${escapeHtml(g.vietnamese_content || '')}</h3>`;
    }
    if (g.type === 2) {
        return `<p class="grammar-desc">${escapeHtml(g.vietnamese_content || '')}</p>`;
    }
    if (g.type === 3) {
        const parts = (g.vietnamese_content || '').split('~');
        return `<div class="grammar-example">
            <div class="ex-cn">${escapeHtml((parts[0] || '').trim())}</div>
            <div class="ex-vn">${escapeHtml((parts[1] || '').trim())}</div>
        </div>`;
    }
    if (g.type === 4) {
        if (g.vn_context && Array.isArray(g.vn_context) && g.vn_context.length > 0) {
            return renderGrammarTable(g.vn_context);
        }
        return `<div class="grammar-table-ref">${escapeHtml(g.vietnamese_content || '')}</div>`;
    }
    if (g.type === 5) {
        // Example dialogue: "A：...？ ~ translation" -> Chinese line + translation.
        const parts = (g.vietnamese_content || '').split('~');
        return `<div class="grammar-dialogue">
            <div class="dlg-cn">${escapeHtml((parts[0] || '').trim())}</div>
            <div class="dlg-vn">${escapeHtml((parts[1] || '').trim())}</div>
        </div>`;
    }
    return '';
}

function renderGrammarTable(rows) {
    let tableHtml = '<div class="grammar-table-container"><table class="grammar-table"><thead><tr>';
    const headers = Object.keys(rows[0] || {});
    headers.forEach(h => {
        tableHtml += `<th>${escapeHtml(h)}</th>`;
    });
    tableHtml += '</tr></thead><tbody>';
    rows.forEach(row => {
        tableHtml += '<tr>';
        headers.forEach(h => {
            tableHtml += `<td>${escapeHtml(row[h] || '')}</td>`;
        });
        tableHtml += '</tr>';
    });
    tableHtml += '</tbody></table></div>';
    return tableHtml;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
