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
        window.location.href = `/learning?passage_id=${encodeURIComponent(currentPassageId)}`;
        return;
    }
    currentPassageId = null;
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    Picker.showLevelPicker();
}

async function loadGrammar(passageId) {
    currentPassageId = passageId;
    const learningLink = document.getElementById('grammar-learning-link');
    if (learningLink) {
        learningLink.href = `/learning?passage_id=${encodeURIComponent(passageId)}`;
        learningLink.textContent = isLessonPartFlow ? 'Finish' : 'Learning';
    }
    switchScreen('screen-loading');

    try {
        const res = await fetch(`/api/lesson/grammar/${encodeURIComponent(passageId)}`);
        const data = await res.json();
        document.getElementById('grammar-title').textContent = `Grammar - ${passageId}`;

        if (data.grammar && data.grammar.length > 0) {
            const sortedGrammar = groupAndSortGrammar(data.grammar);
            renderGrammar(sortedGrammar, document.getElementById('grammar-body'));
        } else {
            document.getElementById('grammar-body').innerHTML =
                '<div style="padding:20px;text-align:center;color:#666;">No grammar rules for this passage.</div>';
        }

        switchScreen('screen-grammar');
    } catch (e) {
        document.getElementById('grammar-body').innerHTML =
            '<div style="color:red;padding:20px;">Error loading grammar.</div>';
        switchScreen('screen-grammar');
    }
}

function groupAndSortGrammar(grammarList) {
    const groups = {};
    grammarList.forEach(g => {
        if (!groups[g.grammar_id]) groups[g.grammar_id] = [];
        groups[g.grammar_id].push(g);
    });

    let sortedList = [];

    for (const id in groups) {
        const items = groups[id];
        const type1 = items.filter(g => g.type === 1);

        let type2 = items.filter(g => g.type === 2);
        type2.sort((a, b) => {
            const aHasExample = (a.vietnamese_content || '').includes('Vi du:') ||
                (a.vietnamese_content || '').includes('Ví dụ:');
            const bHasExample = (b.vietnamese_content || '').includes('Vi du:') ||
                (b.vietnamese_content || '').includes('Ví dụ:');
            if (aHasExample && !bHasExample) return 1;
            if (!aHasExample && bHasExample) return -1;
            return 0;
        });

        const type4 = items.filter(g => g.type === 4);
        const type3 = items.filter(g => g.type === 3);

        sortedList = sortedList.concat(type1, type2, type4, type3);
    }

    return sortedList;
}

function renderGrammar(grammarList, container) {
    let html = '<div class="grammar-content">';
    grammarList.forEach(g => {
        if (g.type === 1) {
            html += `<h3 class="grammar-title">${escapeHtml(g.vietnamese_content || '')}</h3>`;
        } else if (g.type === 2) {
            html += `<p class="grammar-desc">${escapeHtml(g.vietnamese_content || '')}</p>`;
        } else if (g.type === 3) {
            const parts = (g.vietnamese_content || '').split('~');
            const cn = parts[0] ? parts[0].trim() : '';
            const vn = parts[1] ? parts[1].trim() : '';
            html += `<div class="grammar-example">
                <div class="ex-cn">${escapeHtml(cn)}</div>
                <div class="ex-vn">${escapeHtml(vn)}</div>
            </div>`;
        } else if (g.type === 4) {
            if (g.vn_context && Array.isArray(g.vn_context) && g.vn_context.length > 0) {
                html += renderGrammarTable(g.vn_context);
            } else {
                html += `<div class="grammar-table-ref">${escapeHtml(g.vietnamese_content || '')}</div>`;
            }
        }
    });
    html += '</div>';
    container.innerHTML = html;
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
