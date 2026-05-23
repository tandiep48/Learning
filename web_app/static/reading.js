let currentPassage = null;
let pinyinVisible  = false;
let meaningVisible = false;
let currentAudio   = null;
let vocabLoaded    = false;   // cache: don't re-fetch each open

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
        renderVocabTable(data.vocab || []);
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
                <th></th>
                <th>Character</th>
                <th>Pinyin</th>
                <th>Meaning (VN)</th>
                <th>Meaning (EN)</th>
                <th>Level</th>
            </tr>
        </thead>
        <tbody id="vocab-tbody"></tbody>`;

    const tbody = table.querySelector('#vocab-tbody');

    vocab.forEach(w => {
        const tr = document.createElement('tr');
        const audioCell = w.audio_key
            ? `<button class="vocab-audio-btn" onclick="playVocabAudio('${w.audio_key}')" title="Play">🔊</button>`
            : '';
        tr.innerHTML = `
            <td>${audioCell}</td>
            <td><span class="vocab-cn">${w.cn}</span></td>
            <td><span class="vocab-pinyin">${w.pinyin}</span></td>
            <td><span class="vocab-meaning">${w.meaning_vn}</span></td>
            <td><span class="vocab-meaning">${w.meaning_en}</span></td>
            <td><span class="vocab-level">${w.hsk_level}</span></td>`;
        tbody.appendChild(tr);
    });

    body.innerHTML = '';
    body.appendChild(table);
}

function playVocabAudio(audioKey) {
    const src = `/audio/${audioKey}.mp3`;
    playAudio(src);
}

// ── Start Lesson Practice ─────────────────────────────────────
function startLessonPractice() {
    if (!currentPassage) return;
    const hskLevel  = currentPassage.hsk_level || 'H1';
    const passageId = encodeURIComponent(currentPassage.passage_id);
    // Navigate to the lesson page for this HSK level, auto-starting this passage
    window.location.href = `/lesson/${hskLevel}?passage_id=${passageId}`;
}
