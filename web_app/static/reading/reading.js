let currentPassage = null;
let pinyinVisible  = false;
let meaningVisible = false;
let currentAudio   = null;
let vocabLoaded    = false;   // cache: don't re-fetch each open
let currentVocabList = [];
let isPlayingAll = false;

// ── Init ─────────────────────────────────────────────────────
window.onload = async () => {
    const params = new URLSearchParams(window.location.search);
    const autoPassage = params.get('passage_id');

    Picker.init((passage) => {
        loadPassage(passage.passage_id);
    }, "Reading Lesson", !autoPassage);

    if (autoPassage) {
        await loadPassage(autoPassage);
    }
};

// ── Screen helpers ────────────────────────────────────────────
function switchScreen(id) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    if (currentAudio) currentAudio.pause();
}

function goHome() {
    if (currentPassage?.passage_id) {
        window.location.href = `/learning?passage_id=${encodeURIComponent(currentPassage.passage_id)}`;
        return;
    }
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    Picker.showLevelPicker();
    currentPassage = null;
    vocabLoaded    = false;
}

// ── Load & render passage ─────────────────────────────────────
async function loadPassage(passage_id) {
    switchScreen('screen-loading');
    vocabLoaded = false;
    currentVocabList = [];
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
            audioHTML = `<button class="audio-btn" onclick="playAudio('${src}')" title="Play Audio" aria-label="Play Audio"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>`;
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
                    <button class="vocab-header-icon-btn" onclick="playAllVocabAudio()" title="Play all" aria-label="Play all">
                        <i class="fa-solid fa-play play-icon" aria-hidden="true"></i>
                    </button>
                    <button class="vocab-header-icon-btn" onclick="shuffleVocab()" title="Shuffle" aria-label="Shuffle">
                        <i class="fa-solid fa-shuffle" aria-hidden="true"></i>
                    </button>
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
            ? `<button class="vocab-audio-btn" onclick="playVocabAudio('${w.audio_key}')" title="Play audio" aria-label="Play audio"><i class="fa-solid fa-play play-icon" aria-hidden="true"></i></button>`
            : '<span class="vocab-no-audio">-</span>';
        tr.innerHTML = `
            <td>${audioCell}</td>
            <td class="vocab-cn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${w.cn}</td>
            <td class="vocab-pinyin clickable-cell" onclick="this.classList.toggle('hidden-cell')">${w.pinyin}</td>
            <td class="vocab-meaning-vn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${w.meaning_vn}</td>`;
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
    const popSound = new Audio("data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
    popSound.play().catch(e => console.log('Sound error', e));

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
    openReadingFlashcards();
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
                    <button class="vocab-header-icon-btn" onclick="playAllVocabAudio()" title="Play all" aria-label="Play all">
                        <i class="fa-solid fa-play play-icon" aria-hidden="true"></i>
                    </button>
                    <button class="vocab-header-icon-btn" onclick="shuffleVocab()" title="Shuffle" aria-label="Shuffle">
                        <i class="fa-solid fa-shuffle" aria-hidden="true"></i>
                    </button>
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
            ? `<button class="vocab-audio-btn" onclick="playVocabAudio('${w.audio_key}')" title="Play audio" aria-label="Play audio"><i class="fa-solid fa-play play-icon" aria-hidden="true"></i></button>`
            : '<span class="vocab-no-audio">-</span>';
        tr.innerHTML = `
            <td>${audioCell}</td>
            <td class="vocab-cn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${w.cn}</td>
            <td class="vocab-pinyin clickable-cell" onclick="this.classList.toggle('hidden-cell')">${w.pinyin}</td>
            <td class="vocab-meaning-vn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${w.meaning_vn}</td>`;
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
    const popSound = new Audio("data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=");
    popSound.play().catch(e => console.log('Sound error', e));

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
    openReadingFlashcards();
}

async function openReadingFlashcards() {
    if (!currentPassage) return;

    try {
        let vocab = currentVocabList || [];
        if (!vocab.length) {
            const res = await fetch(`/api/lesson/vocab/${currentPassage.passage_id}`);
            const data = await res.json();
            vocab = data.vocab || [];
        }

        const selectedRows = vocab.map(w => ({
            word: w.word || w.cn || '',
            cn: w.word || w.cn || '',
            pinyin: w.pinyin || '',
            meaning_vn: w.meaning_vn || '',
            meaning_en: w.meaning_en || '',
            audio_key: w.audio_key || '',
            level: w.level || w.hsk_level || currentPassage.hsk_level || ''
        })).filter(w => w.word);

        if (!selectedRows.length) {
            alert('No vocabulary linked to this passage.');
            return;
        }

        sessionStorage.setItem('selectedVocabFlashcards', JSON.stringify(selectedRows));
        window.location.href = '/vocab-learning?source=reading';
    } catch (e) {
        alert('Failed to open flash cards.');
    }
}

