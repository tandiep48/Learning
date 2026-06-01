let currentPassage = null;
let pinyinVisible  = false;
let meaningVisible = false;
let currentAudio   = null;
let vocabLoaded    = false;   // cache: don't re-fetch each open
let currentVocabList = [];
let isPlayingAll = false;

// ── Init ─────────────────────────────────────────────────────
window.onload = async () => {
    try {
        const hskLevel = window.hskLevel || "";
        const url = hskLevel
            ? `/api/lesson/passages?hsk_level=${hskLevel}`
            : `/api/lesson/passages`;
        const res  = await fetch(url);
        const data = await res.json();
        const container = document.getElementById('passage-container');
        container.innerHTML = '';

        const backDiv = document.createElement('div');
        backDiv.innerHTML = `<a href="/reading" style="display:inline-block;margin-bottom:20px;color:#3b82f6;text-decoration:none;">← Back to Levels</a>`;
        container.appendChild(backDiv);

        const section = document.createElement('div');
        section.className = 'passage-section';

        const header = document.createElement('h3');
        header.innerText = hskLevel || "All Passages";
        section.appendChild(header);

        const grid = document.createElement('div');
        grid.className = 'dashboard-container';
        grid.style.marginTop = '10px';

        data.passages.forEach(p => {
            const btn = document.createElement('div');
            btn.className = 'dash-card';
            btn.style.padding = '15px';
            btn.innerHTML = `<div class="dash-title" style="font-size:18px;">${p.passage_id}</div>
                             <div class="dash-desc">${p.line_count} sentences</div>`;
            btn.onclick = () => loadPassage(p.passage_id);
            grid.appendChild(btn);
        });

        section.appendChild(grid);
        container.appendChild(section);
    } catch (e) {
        document.getElementById('passage-container').innerHTML = '<p>Error loading passages.</p>';
    }
};

// ── Screen helpers ────────────────────────────────────────────
function switchScreen(id) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    if (currentAudio) currentAudio.pause();
}

function goHome() {
    switchScreen('screen-menu');
    currentPassage = null;
    vocabLoaded    = false;
}

// ── Load & render passage ─────────────────────────────────────
async function loadPassage(passage_id) {
    switchScreen('screen-loading');
    vocabLoaded = false;
    try {
        const res  = await fetch(`/api/lesson/passage/${passage_id}`);
        const data = await res.json();
        if (!res.ok) { alert(data.error || "Failed to load passage."); goHome(); return; }
        currentPassage = data.passage;
        renderPassage();
        switchScreen('screen-reading');
    } catch(e) {
        alert("Error connecting to server.");
        goHome();
    }
}

function renderPassage() {
    document.getElementById('reading-title').innerText = currentPassage.passage_id;

    const contentDiv = document.getElementById('reading-content');
    contentDiv.innerHTML = '';

    currentPassage.lines.forEach(line => {
        const lineDiv = document.createElement('div');
        lineDiv.className = 'reading-line';

        let audioHTML = '';
        if (line.audio_key) {
            const hskLevel = currentPassage.hsk_level || 'H1';
            const src = `/lesson_audio/${hskLevel}/${line.audio_key}.mp3`;
            audioHTML = `<button class="audio-btn" onclick="playAudio('${src}')" title="Play Audio">🔊</button>`;
        }

        const pinyinClass  = pinyinVisible  ? 'pinyin-text show'  : 'pinyin-text';
        const meaningClass = meaningVisible ? 'meaning-text show' : 'meaning-text';

        const textHTML = `
            <div class="reading-text">
                <div class="hanzi-text">${line.content}</div>
                <div class="${pinyinClass}">${line.pinyin || ''}</div>
                <div class="${meaningClass}">${line.translations.vi || line.translations.en || ''}</div>
            </div>`;

        lineDiv.innerHTML = textHTML + audioHTML;
        contentDiv.appendChild(lineDiv);
    });

    updatePinyinBtnText();
    updateMeaningBtnText();
}

// ── Audio ─────────────────────────────────────────────────────
function playAudio(src) {
    if (currentAudio) currentAudio.pause();
    currentAudio = new Audio(src);
    currentAudio.play().catch(e => console.warn("Audio failed", e));
}

// ── Pinyin / Meaning toggles ──────────────────────────────────
function togglePinyin() {
    pinyinVisible = !pinyinVisible;
    document.querySelectorAll('.pinyin-text').forEach(el =>
        el.classList.toggle('show', pinyinVisible));
    updatePinyinBtnText();
}

function toggleMeaning() {
    meaningVisible = !meaningVisible;
    document.querySelectorAll('.meaning-text').forEach(el =>
        el.classList.toggle('show', meaningVisible));
    updateMeaningBtnText();
}

function updatePinyinBtnText() {
    const btn = document.getElementById('toggle-pinyin-btn');
    btn.innerText = pinyinVisible ? "Hide Pinyin" : "Show Pinyin";
    btn.classList.toggle('primary', pinyinVisible);
}

function updateMeaningBtnText() {
    const btn = document.getElementById('toggle-meaning-btn');
    btn.innerText = meaningVisible ? "Hide Meaning" : "Show Meaning";
    btn.classList.toggle('primary', meaningVisible);
}

// ── Passage search (menu screen) ──────────────────────────────
function filterPassages() {
    const q = document.getElementById('search-input').value.toLowerCase();
    document.querySelectorAll('.passage-section').forEach(sec => {
        let any = false;
        sec.querySelectorAll('.dash-card').forEach(card => {
            const match = card.querySelector('.dash-title').innerText.toLowerCase().includes(q);
            card.style.display = match ? 'flex' : 'none';
            if (match) any = true;
        });
        sec.style.display = any ? 'block' : 'none';
    });
}

// ── Vocab Panel ───────────────────────────────────────────────
async function openVocabPanel() {
    if (!currentPassage) return;
    const overlay = document.getElementById('vocab-panel-overlay');
    overlay.classList.add('open');

    // Update title
    document.getElementById('vocab-panel-title').textContent =
        `Vocab – ${currentPassage.passage_id}`;

    if (vocabLoaded) return;  // already fetched for this passage

    const body = document.getElementById('vocab-panel-body');
    body.innerHTML = '<div class="vocab-loading">Loading vocabulary…</div>';

    try {
        const res  = await fetch(`/api/lesson/vocab/${currentPassage.passage_id}`);
        const data = await res.json();
        vocabLoaded = true;
        currentVocabList = data.vocab || [];
        renderVocabTable(currentVocabList);
    } catch (e) {
        body.innerHTML = '<div class="vocab-empty">Failed to load vocabulary.</div>';
    }
}

function closeVocabPanel() {
    document.getElementById('vocab-panel-overlay').classList.remove('open');
}

function closeVocabIfBackground(e) {
    if (e.target.id === 'vocab-panel-overlay') closeVocabPanel();
}

function renderVocabTable(vocab) {
    const body = document.getElementById('vocab-panel-body');

    if (!vocab.length) {
        body.innerHTML = '<div class="vocab-empty">No vocabulary linked to this passage.</div>';
        return;
    }

    const table = document.createElement('table');
    table.className = 'vocab-table';
    table.innerHTML = `
        <thead>
            <tr>
                <th style="width: 80px;">
                    <button class="vocab-header-icon-btn" onclick="playAllVocabAudio()" title="Play All">▶</button>
                    <button class="vocab-header-icon-btn" onclick="shuffleVocab()" title="Shuffle">🔀</button>
                </th>
                <th onclick="toggleVocabColumn('cn')">CHARACTER</th>
                <th onclick="toggleVocabColumn('py')">PINYIN</th>
                <th onclick="toggleVocabColumn('vn')">MEANING (VN)</th>
            </tr>
        </thead>
        <tbody id="vocab-tbody"></tbody>`;

    const tbody = table.querySelector('#vocab-tbody');

    vocab.forEach((w, index) => {
        const tr = document.createElement('tr');
        tr.id = `reading-vocab-tr-${index}`;
        const audioCell = w.audio_key
            ? `<button class="vocab-audio-btn" onclick="playVocabAudio('${w.audio_key}')" title="Play">🔊</button>`
            : '<span style="color:#666">-</span>';
        tr.innerHTML = `
            <td>${audioCell}</td>
            <td class="vocab-cn">${w.cn}</td>
            <td class="vocab-pinyin">${w.pinyin}</td>
            <td class="vocab-meaning-vn">${w.meaning_vn}</td>`;
        tbody.appendChild(tr);
    });

    body.innerHTML = '';
    body.appendChild(table);
}

function playVocabAudio(audioKey) {
    const src = `/audio/${audioKey}.mp3`;
    playAudio(src);
}

function toggleVocabColumn(col) {
    const table = document.querySelector('.vocab-table');
    if (table) {
        table.classList.toggle(`hide-${col}`);
    }
}

function shuffleVocab() {
    currentVocabList.sort(() => Math.random() - 0.5);
    const oldTable = document.querySelector('.vocab-table');
    const hiddenClasses = Array.from(oldTable?.classList || []).filter(c => c.startsWith('hide-'));
    
    renderVocabTable(currentVocabList);
    
    const newTable = document.querySelector('.vocab-table');
    if (newTable) hiddenClasses.forEach(c => newTable.classList.add(c));
}

async function playAllVocabAudio() {
    if (isPlayingAll) {
        isPlayingAll = false;
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
        return;
    }
    isPlayingAll = true;
    for (let i = 0; i < currentVocabList.length; i++) {
        let w = currentVocabList[i];
        if (!isPlayingAll) break;
        if (w.audio_key) {
            // Clear all highlights
            document.querySelectorAll('.vocab-table tr').forEach(tr => tr.classList.remove('playing-highlight'));
            
            // Highlight current
            const tr = document.getElementById(`reading-vocab-tr-${i}`);
            if (tr) {
                tr.classList.add('playing-highlight');
                tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

            await new Promise(resolve => {
                const src = `/audio/${w.audio_key}.mp3`;
                if (currentAudio) currentAudio.pause();
                currentAudio = new Audio(src);
                currentAudio.onended = resolve;
                currentAudio.onerror = resolve;
                currentAudio.play().catch(resolve);
            });
            if (!isPlayingAll) break;
            await new Promise(resolve => setTimeout(resolve, 600));
        }
    }
    document.querySelectorAll('.vocab-table tr').forEach(tr => tr.classList.remove('playing-highlight'));
    isPlayingAll = false;
}

// ── Start Lesson Practice ─────────────────────────────────────
function startLessonPractice() {
    if (!currentPassage) return;
    const hskLevel  = currentPassage.hsk_level || 'H1';
}

// ── Audio ─────────────────────────────────────────────────────
function playAudio(src) {
    if (currentAudio) currentAudio.pause();
    currentAudio = new Audio(src);
    currentAudio.play().catch(e => console.warn("Audio failed", e));
}

// ── Pinyin / Meaning toggles ──────────────────────────────────
function togglePinyin() {
    pinyinVisible = !pinyinVisible;
    document.querySelectorAll('.pinyin-text').forEach(el =>
        el.classList.toggle('show', pinyinVisible));
    updatePinyinBtnText();
}

function toggleMeaning() {
    meaningVisible = !meaningVisible;
    document.querySelectorAll('.meaning-text').forEach(el =>
        el.classList.toggle('show', meaningVisible));
    updateMeaningBtnText();
}

function updatePinyinBtnText() {
    const btn = document.getElementById('toggle-pinyin-btn');
    btn.innerText = pinyinVisible ? "Hide Pinyin" : "Show Pinyin";
    btn.classList.toggle('primary', pinyinVisible);
}

function updateMeaningBtnText() {
    const btn = document.getElementById('toggle-meaning-btn');
    btn.innerText = meaningVisible ? "Hide Meaning" : "Show Meaning";
    btn.classList.toggle('primary', meaningVisible);
}

// ── Passage search (menu screen) ──────────────────────────────
function filterPassages() {
    const q = document.getElementById('search-input').value.toLowerCase();
    document.querySelectorAll('.passage-section').forEach(sec => {
        let any = false;
        sec.querySelectorAll('.dash-card').forEach(card => {
            const match = card.querySelector('.dash-title').innerText.toLowerCase().includes(q);
            card.style.display = match ? 'flex' : 'none';
            if (match) any = true;
        });
        sec.style.display = any ? 'block' : 'none';
    });
}

// ── Vocab Panel ───────────────────────────────────────────────
async function openVocabPanel() {
    if (!currentPassage) return;
    const overlay = document.getElementById('vocab-panel-overlay');
    overlay.classList.add('open');

    // Update title
    document.getElementById('vocab-panel-title').textContent =
        `Vocab – ${currentPassage.passage_id}`;

    if (vocabLoaded) return;  // already fetched for this passage

    const body = document.getElementById('vocab-panel-body');
    body.innerHTML = '<div class="vocab-loading">Loading vocabulary…</div>';

    try {
        const res  = await fetch(`/api/lesson/vocab/${currentPassage.passage_id}`);
        const data = await res.json();
        vocabLoaded = true;
        currentVocabList = data.vocab || [];
        renderVocabTable(currentVocabList);
    } catch (e) {
        body.innerHTML = '<div class="vocab-empty">Failed to load vocabulary.</div>';
    }
}

function closeVocabPanel() {
    document.getElementById('vocab-panel-overlay').classList.remove('open');
}

function closeVocabIfBackground(e) {
    if (e.target.id === 'vocab-panel-overlay') closeVocabPanel();
}

function renderVocabTable(vocab) {
    const body = document.getElementById('vocab-panel-body');

    if (!vocab.length) {
        body.innerHTML = '<div class="vocab-empty">No vocabulary linked to this passage.</div>';
        return;
    }

    const table = document.createElement('table');
    table.className = 'vocab-table';
    table.innerHTML = `
        <thead>
            <tr>
                <th style="width: 80px;">
                    <button class="vocab-header-icon-btn" onclick="playAllVocabAudio()" title="Play All">▶</button>
                    <button class="vocab-header-icon-btn" onclick="shuffleVocab()" title="Shuffle">🔀</button>
                </th>
                <th onclick="toggleVocabColumn('cn')">CHARACTER</th>
                <th onclick="toggleVocabColumn('py')">PINYIN</th>
                <th onclick="toggleVocabColumn('vn')">MEANING (VN)</th>
            </tr>
        </thead>
        <tbody id="vocab-tbody"></tbody>`;

    const tbody = table.querySelector('#vocab-tbody');

    vocab.forEach((w, index) => {
        const tr = document.createElement('tr');
        tr.id = `reading-vocab-tr-${index}`;
        const audioCell = w.audio_key
            ? `<button class="vocab-audio-btn" onclick="playVocabAudio('${w.audio_key}')" title="Play">🔊</button>`
            : '<span style="color:#666">-</span>';
        tr.innerHTML = `
            <td>${audioCell}</td>
            <td class="vocab-cn">${w.cn}</td>
            <td class="vocab-pinyin">${w.pinyin}</td>
            <td class="vocab-meaning-vn">${w.meaning_vn}</td>`;
        tbody.appendChild(tr);
    });

    body.innerHTML = '';
    body.appendChild(table);
}

function playVocabAudio(audioKey) {
    const src = `/audio/${audioKey}.mp3`;
    playAudio(src);
}

function toggleVocabColumn(col) {
    const table = document.querySelector('.vocab-table');
    if (table) {
        table.classList.toggle(`hide-${col}`);
    }
}

function shuffleVocab() {
    currentVocabList.sort(() => Math.random() - 0.5);
    const oldTable = document.querySelector('.vocab-table');
    const hiddenClasses = Array.from(oldTable?.classList || []).filter(c => c.startsWith('hide-'));
    
    renderVocabTable(currentVocabList);
    
    const newTable = document.querySelector('.vocab-table');
    if (newTable) hiddenClasses.forEach(c => newTable.classList.add(c));
}

async function playAllVocabAudio() {
    if (isPlayingAll) {
        isPlayingAll = false;
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
        return;
    }
    isPlayingAll = true;
    for (let i = 0; i < currentVocabList.length; i++) {
        let w = currentVocabList[i];
        if (!isPlayingAll) break;
        if (w.audio_key) {
            // Clear all highlights
            document.querySelectorAll('.vocab-table tr').forEach(tr => tr.classList.remove('playing-highlight'));
            
            // Highlight current
            const tr = document.getElementById(`reading-vocab-tr-${i}`);
            if (tr) {
                tr.classList.add('playing-highlight');
                tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

            await new Promise(resolve => {
                const src = `/audio/${w.audio_key}.mp3`;
                if (currentAudio) currentAudio.pause();
                currentAudio = new Audio(src);
                currentAudio.onended = resolve;
                currentAudio.onerror = resolve;
                currentAudio.play().catch(resolve);
            });
            if (!isPlayingAll) break;
            await new Promise(resolve => setTimeout(resolve, 600));
        }
    }
    document.querySelectorAll('.vocab-table tr').forEach(tr => tr.classList.remove('playing-highlight'));
    isPlayingAll = false;
}

// ── Start Lesson Practice ─────────────────────────────────────
function startLessonPractice() {
    if (!currentPassage) return;
    const hskLevel  = currentPassage.hsk_level || 'H1';
    const passageId = encodeURIComponent(currentPassage.passage_id);
    // Navigate to the lesson page for this HSK level, auto-starting this passage
    window.location.href = `/lesson/${hskLevel}?passage_id=${passageId}`;
}

// ── Grammar Panel ──

function openGrammarPanel() {
    document.getElementById('grammar-panel-overlay').classList.add('open');
    if (currentPassage && currentPassage.passage_id) {
        fetchGrammar(currentPassage.passage_id);
    }
}

function closeGrammarPanel() {
    document.getElementById('grammar-panel-overlay').classList.remove('open');
}

function closeGrammarIfBackground(e) {
    if (e.target.id === 'grammar-panel-overlay') {
        closeGrammarPanel();
    }
}

async function fetchGrammar(passageId) {
    const tbody = document.getElementById('grammar-panel-body');
    tbody.innerHTML = '<div class="vocab-loading">Loading grammar...</div>';
    try {
        const res = await fetch(`/api/lesson/grammar/${passageId}`);
        const data = await res.json();
        if (data.grammar && data.grammar.length > 0) {
            const sortedGrammar = groupAndSortGrammar(data.grammar);
            renderGrammar(sortedGrammar, tbody);
        } else {
            tbody.innerHTML = '<div style="padding:20px;text-align:center;color:#666;">No grammar rules for this passage.</div>';
        }
    } catch(e) {
        tbody.innerHTML = '<div style="color:red;padding:20px;">Error loading grammar.</div>';
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
            const aHasExample = (a.vietnamese_content || '').includes('Ví dụ:');
            const bHasExample = (b.vietnamese_content || '').includes('Ví dụ:');
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
            html += `<h3 class="grammar-title">${g.vietnamese_content}</h3>`;
        } else if (g.type === 2) {
            html += `<p class="grammar-desc">${g.vietnamese_content}</p>`;
        } else if (g.type === 3) {
            const parts = (g.vietnamese_content || '').split('~');
            const cn = parts[0] ? parts[0].trim() : '';
            const vn = parts[1] ? parts[1].trim() : '';
            html += `<div class="grammar-example">
                <div class="ex-cn">${cn}</div>
                <div class="ex-vn">${vn}</div>
            </div>`;
        } else if (g.type === 4) {
            if (g.vn_context && Array.isArray(g.vn_context) && g.vn_context.length > 0) {
                let tableHtml = '<div class="grammar-table-container"><table class="grammar-table"><thead><tr>';
                const headers = Object.keys(g.vn_context[0]);
                headers.forEach(h => {
                    tableHtml += `<th>${h}</th>`;
                });
                tableHtml += '</tr></thead><tbody>';
                g.vn_context.forEach(row => {
                    tableHtml += '<tr>';
                    headers.forEach(h => {
                        tableHtml += `<td>${row[h] || ''}</td>`;
                    });
                    tableHtml += '</tr>';
                });
                tableHtml += '</tbody></table></div>';
                html += tableHtml;
            } else {
                html += `<div class="grammar-table-ref">${g.vietnamese_content}</div>`;
            }
        }
    });
    html += '</div>';
    container.innerHTML = html;
}
