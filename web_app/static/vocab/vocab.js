let currentMode = "1";
let sessionData = null;
let currentTaskIndex = 0;
let missedTasks = [];
let taskStartTime = 0;
let selectedHskLevel = null;

let tableMode = "standard";
let currentPage = 1;
let pageSize = 20;
let totalPages = 1;
let currentRows = [];
let currentPassageId = null;
let groupedPassages = {};
let selectedWords = new Map();
let tableAudio = null;
let isPlayingTableAudio = false;

document.addEventListener('DOMContentLoaded', () => {
    initTableTrainer();

    const trainerWords = readSelectedTrainerWords();
    if (trainerWords.length) {
        startSession('7', { words: trainerWords });
        return;
    }

    const params = new URLSearchParams(window.location.search);
    if (params.get('mode') === '6' && params.get('passage_id')) {
        const passageId = params.get('passage_id');
        history.replaceState(null, '', '/vocab');
        startSession('6', { passage_id: passageId });
    }
});

function readSelectedTrainerWords() {
    const raw = sessionStorage.getItem('selectedVocabTrainerWords');
    if (!raw) return [];
    sessionStorage.removeItem('selectedVocabTrainerWords');
    try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
    } catch (e) {
        return [];
    }
}

function initTableTrainer() {
    const pageSizeEl = document.getElementById('filter-page-size');
    if (pageSizeEl) pageSize = Number(pageSizeEl.value) || 20;
    setTableMode('standard');
    updateSelectionUI();
}

function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    if (screenId) {
        document.getElementById(screenId).classList.add('active');
    }
}

function goHome() {
    closeQuitModal();
    switchScreen('screen-menu');
    sessionData = null;
    currentTaskIndex = 0;
    missedTasks = [];
    selectedHskLevel = null;
}

function setTableMode(mode) {
    tableMode = mode;
    currentPage = 1;
    currentRows = [];
    currentPassageId = null;
    groupedPassages = {};

    document.getElementById('mode-standard-btn')?.classList.toggle('active', mode === 'standard');
    document.getElementById('mode-free-btn')?.classList.toggle('active', mode === 'free');
    document.querySelectorAll('.standard-filter').forEach(el => {
        el.style.display = mode === 'standard' ? '' : 'none';
    });

    resetSelect('filter-hsk', 'Select HSK');
    resetSelect('filter-lesson', 'Select lesson', true);
    resetSelect('filter-part', 'Select part', true);
    clearTable('Choose filters to load vocabulary.');
}

function resetSelect(id, label, disabled = false) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = `<option value="">${label}</option>`;
    if (id === 'filter-hsk') {
        for (let i = 1; i <= 6; i++) {
            const option = document.createElement('option');
            option.value = `HSK${i}`;
            option.textContent = `HSK ${i}`;
            el.appendChild(option);
        }
    }
    el.value = '';
    el.disabled = disabled;
}

async function handleHskChange() {
    currentPage = 1;
    currentPassageId = null;
    resetSelect('filter-lesson', 'Select lesson', true);
    resetSelect('filter-part', 'Select part', true);

    const hskLevel = document.getElementById('filter-hsk').value;
    if (!hskLevel) {
        clearTable('Choose filters to load vocabulary.');
        return;
    }

    if (tableMode === 'free') {
        await loadVocabTable();
        return;
    }

    await loadStandardLessons(hskLevel);
}

async function loadStandardLessons(hskLevel) {
    setTableState('Loading lessons...');
    try {
        const res = await fetch(`/api/lesson/passages?hsk_level=${encodeURIComponent(hskLevel)}`);
        const data = await res.json();
        groupedPassages = {};

        (data.passages || []).forEach(passage => {
            const parts = String(passage.passage_id || '').split('_');
            const lesson = parts.length >= 2 ? parts[1] : 'Other';
            const part = parts.length >= 3 ? parts[2] : passage.passage_id;
            if (!groupedPassages[lesson]) groupedPassages[lesson] = [];
            groupedPassages[lesson].push({ ...passage, lesson, part });
        });

        const lessonSelect = document.getElementById('filter-lesson');
        resetSelect('filter-lesson', 'Select lesson');
        Object.keys(groupedPassages).sort(numericSort).forEach(lesson => {
            const option = document.createElement('option');
            option.value = lesson;
            option.textContent = lesson === 'Other' ? 'Other' : `Lesson ${lesson}`;
            lessonSelect.appendChild(option);
        });
        lessonSelect.disabled = Object.keys(groupedPassages).length === 0;
        clearTable(Object.keys(groupedPassages).length ? 'Choose a lesson and part.' : 'No lessons found.');
    } catch (e) {
        console.error(e);
        clearTable('Failed to load lessons.');
    }
}

function numericSort(a, b) {
    if (a === 'Other') return 1;
    if (b === 'Other') return -1;
    return Number(a) - Number(b);
}

function handleLessonChange() {
    currentPage = 1;
    currentPassageId = null;
    const lesson = document.getElementById('filter-lesson').value;
    const partSelect = document.getElementById('filter-part');
    resetSelect('filter-part', 'Select part');

    if (!lesson || !groupedPassages[lesson]) {
        partSelect.disabled = true;
        clearTable('Choose a lesson and part.');
        return;
    }

    groupedPassages[lesson].sort((a, b) => Number(a.part) - Number(b.part)).forEach(passage => {
        const option = document.createElement('option');
        option.value = passage.part;
        option.textContent = `Part ${passage.part}`;
        option.dataset.passageId = passage.passage_id;
        partSelect.appendChild(option);
    });
    partSelect.disabled = false;
    clearTable('Choose a part.');
}

async function handlePartChange() {
    currentPage = 1;
    await loadVocabTable();
}

function changePageSize() {
    pageSize = Number(document.getElementById('filter-page-size').value) || 20;
    currentPage = 1;
    loadVocabTable();
}

async function changePage(delta) {
    const nextPage = currentPage + delta;
    if (nextPage < 1 || nextPage > totalPages) return;
    currentPage = nextPage;
    await loadVocabTable();
}

async function loadVocabTable() {
    const hskLevel = document.getElementById('filter-hsk').value;
    const lesson = document.getElementById('filter-lesson').value;
    const part = document.getElementById('filter-part').value;

    if (!hskLevel || (tableMode === 'standard' && (!lesson || !part))) {
        clearTable(tableMode === 'standard' ? 'Choose HSK, lesson, and part.' : 'Choose HSK to load vocabulary.');
        return;
    }

    setTableState('Loading vocabulary...');
    const params = new URLSearchParams({
        mode: tableMode,
        hsk_level: hskLevel,
        page: String(currentPage),
        page_size: String(pageSize)
    });
    if (tableMode === 'standard') {
        params.set('lesson', lesson);
        params.set('part', part);
    }

    try {
        const res = await fetch(`/api/vocab/table?${params.toString()}`);
        const data = await res.json();
        if (!res.ok || data.error) {
            clearTable(data.error || 'Failed to load vocabulary.');
            return;
        }

        currentRows = data.rows || [];
        currentPassageId = data.passage_id || null;
        currentPage = data.page || 1;
        totalPages = data.total_pages || 1;
        renderVocabTable(currentRows);
        renderPagination(data.total || 0);
    } catch (e) {
        console.error(e);
        clearTable('Failed to load vocabulary.');
    }
}

function setTableState(message) {
    const state = document.getElementById('vocab-table-state');
    const wrap = document.getElementById('vocab-table-wrap');
    const pagination = document.getElementById('vocab-pagination');
    if (state) {
        state.textContent = message;
        state.style.display = 'block';
    }
    if (wrap) {
        wrap.style.display = 'none';
        wrap.innerHTML = '';
    }
    if (pagination) pagination.style.display = 'none';
}

function clearTable(message) {
    currentRows = [];
    setTableState(message);
}

function renderVocabTable(rows) {
    const state = document.getElementById('vocab-table-state');
    const wrap = document.getElementById('vocab-table-wrap');
    if (!rows.length) {
        clearTable('No vocabulary found.');
        return;
    }

    const table = document.createElement('table');
    table.className = 'vocab-table';
    table.id = 'trainer-vocab-table';
    table.innerHTML = `
        <thead>
            <tr>
                <th class="vocab-select-col">
                    <input type="checkbox" id="select-page-checkbox" onchange="togglePageSelection(this.checked)" title="Select visible rows">
                </th>
                <th style="width: 86px;">
                    <button class="vocab-header-icon-btn" onclick="event.stopPropagation(); playAllTableAudio()" title="Play all visible">Play</button>
                    <button class="vocab-header-icon-btn" onclick="event.stopPropagation(); shuffleVisibleRows()" title="Shuffle visible">Mix</button>
                </th>
                <th onclick="toggleVocabColumn('cn', 'trainer-vocab-table')">Character</th>
                <th onclick="toggleVocabColumn('py', 'trainer-vocab-table')">Pinyin</th>
                <th onclick="toggleVocabColumn('vn', 'trainer-vocab-table')">Meaning (VN)</th>
            </tr>
        </thead>
        <tbody></tbody>
    `;

    const tbody = table.querySelector('tbody');
    rows.forEach((row, index) => {
        const word = row.word || row.cn || '';
        const tr = document.createElement('tr');
        tr.id = `trainer-vocab-tr-${index}`;
        const checked = selectedWords.has(word) ? 'checked' : '';
        const audioCell = row.audio_key
            ? `<button class="vocab-audio-btn" onclick="playTableAudio('${escapeAttr(row.audio_key)}')" title="Play audio">Audio</button>`
            : '<span class="vocab-no-audio">-</span>';
        tr.innerHTML = `
            <td class="vocab-select-col">
                <input type="checkbox" class="vocab-row-checkbox" ${checked} onchange="toggleWordSelection(${index}, this.checked)">
            </td>
            <td>${audioCell}</td>
            <td class="vocab-cn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${escapeHtml(word)}</td>
            <td class="vocab-pinyin clickable-cell" onclick="this.classList.toggle('hidden-cell')">${escapeHtml(row.pinyin || '')}</td>
            <td class="vocab-meaning-vn clickable-cell" onclick="this.classList.toggle('hidden-cell')">${escapeHtml(row.meaning_vn || row.meaning_en || '')}</td>
        `;
        tbody.appendChild(tr);
    });

    wrap.innerHTML = '';
    wrap.appendChild(table);
    state.style.display = 'none';
    wrap.style.display = 'block';
    updatePageCheckbox();
    updateSelectionUI();
}

function renderPagination(total) {
    const pagination = document.getElementById('vocab-pagination');
    const status = document.getElementById('page-status');
    const prev = document.getElementById('page-prev-btn');
    const next = document.getElementById('page-next-btn');
    pagination.style.display = total > 0 ? 'flex' : 'none';
    status.textContent = `Page ${currentPage} / ${totalPages} (${total} words)`;
    prev.disabled = currentPage <= 1;
    next.disabled = currentPage >= totalPages;
}

function toggleWordSelection(index, checked) {
    const row = currentRows[index];
    if (!row) return;
    const word = row.word || row.cn;
    if (checked) {
        selectedWords.set(word, normalizeSelectedRow(row));
    } else {
        selectedWords.delete(word);
    }
    updatePageCheckbox();
    updateSelectionUI();
}

function togglePageSelection(checked) {
    currentRows.forEach(row => {
        const word = row.word || row.cn;
        if (checked) selectedWords.set(word, normalizeSelectedRow(row));
        else selectedWords.delete(word);
    });
    renderVocabTable(currentRows);
}

function normalizeSelectedRow(row) {
    const word = row.word || row.cn || '';
    return {
        word,
        cn: word,
        pinyin: row.pinyin || '',
        meaning_vn: row.meaning_vn || '',
        meaning_en: row.meaning_en || '',
        audio_key: row.audio_key || '',
        level: row.level || row.hsk_level || ''
    };
}

function updatePageCheckbox() {
    const checkbox = document.getElementById('select-page-checkbox');
    if (!checkbox) return;
    checkbox.checked = currentRows.length > 0 && currentRows.every(row => selectedWords.has(row.word || row.cn));
}

function updateSelectionUI() {
    const count = selectedWords.size;
    const countEl = document.getElementById('selection-count');
    if (countEl) countEl.textContent = `${count} selected`;
    const startBtn = document.getElementById('btn-start-selected');
    const flashBtn = document.getElementById('btn-flashcards');
    if (startBtn) startBtn.disabled = count === 0;
    if (flashBtn) flashBtn.disabled = count === 0;
}

function clearSelection() {
    selectedWords.clear();
    if (currentRows.length) renderVocabTable(currentRows);
    updateSelectionUI();
}

function getSelectedWordRows() {
    return Array.from(selectedWords.values());
}

async function startSelectedTraining() {
    const selected = getSelectedWordRows();
    if (!selected.length) {
        alert('Select at least one word first.');
        return;
    }
    await startSession('7', { words: selected.map(row => row.word) });
}

function openSelectedFlashcards() {
    const selected = getSelectedWordRows();
    if (!selected.length) {
        alert('Select at least one word first.');
        return;
    }
    sessionStorage.setItem('selectedVocabFlashcards', JSON.stringify(selected));
    window.location.href = '/vocab-learning?source=selection';
}

function toggleVocabColumn(colType, tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    table.classList.toggle(`hide-${colType}`);
}

function shuffleVisibleRows() {
    for (let i = currentRows.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [currentRows[i], currentRows[j]] = [currentRows[j], currentRows[i]];
    }
    renderVocabTable(currentRows);
}

function playTableAudio(audioKey) {
    if (!audioKey) return;
    if (tableAudio) tableAudio.pause();
    tableAudio = new Audio(`/audio/${audioKey}.mp3`);
    tableAudio.play().catch(e => console.warn('Audio playback failed:', e));
}

async function playAllTableAudio() {
    if (isPlayingTableAudio) {
        isPlayingTableAudio = false;
        if (tableAudio) tableAudio.pause();
        return;
    }
    isPlayingTableAudio = true;
    const playable = currentRows.map((row, index) => ({ ...row, index })).filter(row => row.audio_key);
    for (const row of playable) {
        if (!isPlayingTableAudio) break;
        document.querySelectorAll('#trainer-vocab-table tr').forEach(tr => tr.classList.remove('playing-highlight'));
        document.getElementById(`trainer-vocab-tr-${row.index}`)?.classList.add('playing-highlight');
        await new Promise(resolve => {
            if (tableAudio) tableAudio.pause();
            tableAudio = new Audio(`/audio/${row.audio_key}.mp3`);
            tableAudio.onended = resolve;
            tableAudio.onerror = resolve;
            tableAudio.play().catch(resolve);
        });
        await new Promise(resolve => setTimeout(resolve, 400));
    }
    document.querySelectorAll('#trainer-vocab-table tr').forEach(tr => tr.classList.remove('playing-highlight'));
    isPlayingTableAudio = false;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, '&#096;');
}

function openStandardMode() {
    setTableMode('standard');
    switchScreen('screen-menu');
}

async function showSetup(mode) {
    currentMode = mode;
    const titles = {
        "2": "Unlearned Words Setup",
        "3": "Unsure Words Setup",
        "4": "Hard Semantic Setup",
        "5": "Hard Stroke Setup"
    };
    document.getElementById('other-setup-title').innerText = titles[mode];
    switchScreen('screen-loading');

    try {
        const response = await fetch('/api/vocab/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode })
        });
        const data = await response.json();

        if (data.error) {
            alert(data.error);
            goHome();
            return;
        }

        const words = data.words || [];
        document.getElementById('preview-count').innerText = `Found ${words.length} words in your history.`;

        const listEl = document.getElementById('preview-list');
        listEl.innerHTML = '';
        words.forEach(w => {
            const li = document.createElement('li');
            li.innerHTML = `<strong>${escapeHtml(w.word)}</strong> | ${escapeHtml(w.pinyin)} <br> <span style="color:var(--text-muted)">${escapeHtml(w.meaning_vn)}</span>`;
            listEl.appendChild(li);
        });

        if (words.length === 0) {
            listEl.innerHTML = '<li>No words found.</li>';
            document.getElementById('btn-start-other').disabled = true;
        } else {
            document.getElementById('btn-start-other').disabled = false;
        }

        switchScreen('screen-setup-other');
    } catch (e) {
        console.error(e);
        alert('Failed to fetch preview.');
        goHome();
    }
}

async function startSession(mode, extraParams = {}) {
    sessionData = null;
    currentTaskIndex = 0;
    missedTasks = [];
    const limitInput = document.getElementById('input-limit');
    if (limitInput) limitInput.value = '';

    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    document.getElementById('screen-loading').classList.add('active');

    let bodyData = { mode: mode };
    if (mode === "6") {
        bodyData.passage_id = extraParams.passage_id;
    } else if (mode === "7") {
        bodyData.words = extraParams.words || [];
    } else {
        bodyData.limit = limitInput ? limitInput.value : '';
    }

    try {
        const response = await fetch('/api/vocab/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bodyData)
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || 'Failed to start session.');
            goHome();
            return;
        }

        sessionData = data;
        currentTaskIndex = 0;
        missedTasks = [];
        loadTask();
    } catch (e) {
        alert('Error connecting to server.');
        goHome();
    }
}

function loadTask() {
    if (currentTaskIndex >= sessionData.tasks.length) {
        finishRound();
        return;
    }

    switchScreen('screen-training');

    const task = sessionData.tasks[currentTaskIndex];
    const total = sessionData.tasks.length;

    document.getElementById('progress-fill').style.width = `${(currentTaskIndex / total) * 100}%`;
    document.getElementById('task-counter').innerText = `Task ${currentTaskIndex + 1}/${total}`;

    document.getElementById('word-display').style.display = 'none';
    document.getElementById('audio-controls').style.display = 'none';
    document.getElementById('mc-area').style.display = 'none';
    document.getElementById('typing-area').style.display = 'none';
    document.getElementById('typing-input').value = '';

    const mcFeedback = document.getElementById('mc-feedback');
    if (mcFeedback) { mcFeedback.style.display = 'none'; mcFeedback.innerHTML = ''; }

    const typingFeedback = document.getElementById('typing-feedback');
    if (typingFeedback) { typingFeedback.style.display = 'none'; typingFeedback.innerHTML = ''; }

    const instructionEl = document.getElementById('task-instruction');
    const audioEl = document.getElementById('audio-player');

    if (task.audio_key) {
        audioEl.src = `/audio/${task.audio_key}.mp3`;
    } else {
        audioEl.removeAttribute('src');
    }

    taskStartTime = Date.now();

    if (task.type === "listen") {
        instructionEl.innerText = 'Listen to the audio and choose the correct meaning:';
        document.getElementById('audio-controls').style.display = 'block';
        if (task.audio_key) audioEl.play().catch(e => console.warn('Audio playback failed:', e));
        setupMultipleChoice(task);
    } else if (task.type === "typing") {
        instructionEl.innerText = 'Type the following word:';
        document.getElementById('word-display').innerText = task.word;
        document.getElementById('word-display').style.display = 'block';
        document.getElementById('typing-area').style.display = 'flex';
        document.getElementById('typing-input').focus();
    } else if (task.type === "meaning") {
        instructionEl.innerText = 'What is the meaning of this word?';
        document.getElementById('word-display').innerText = task.word;
        document.getElementById('word-display').style.display = 'block';
        setupMultipleChoice(task);
    }
}

function setupMultipleChoice(task) {
    const mcArea = document.getElementById('mc-area');
    mcArea.innerHTML = '';
    mcArea.style.display = 'grid';

    task.options.forEach((opt, idx) => {
        const btn = document.createElement('button');
        btn.className = 'btn';
        btn.dataset.optionIndex = idx;
        btn.innerHTML = `<span class="mc-btn-inner"><span class="key-hint">${idx + 1}</span>${escapeHtml(opt)}</span>`;
        btn.addEventListener('click', () => submitMC(opt, task, btn));
        mcArea.appendChild(btn);
    });
}

function playCurrentAudio() {
    const audioEl = document.getElementById('audio-player');
    if (audioEl.src) {
        audioEl.play().catch(e => console.warn('Audio playback failed:', e));
    }
}

function submitTyping() {
    const input = document.getElementById('typing-input').value.trim();
    if (!input) return;

    const task = sessionData.tasks[currentTaskIndex];
    const btn = document.getElementById('typing-submit-btn');
    checkAnswer(task, input, task.word, btn);
}

function submitMC(selected, task, btnElement) {
    checkAnswer(task, selected, task.meaning_vn, btnElement);
}

async function checkAnswer(task, userAnswer, correctAnswer, element) {
    const responseTime = Date.now() - taskStartTime;
    const isCorrect = (userAnswer === correctAnswer);

    if (element) {
        element.style.transition = 'background-color 0.3s, color 0.3s';
        element.style.backgroundColor = isCorrect ? 'var(--success)' : 'var(--danger)';
        element.style.color = 'white';
        element.style.borderColor = isCorrect ? 'var(--success)' : 'var(--danger)';
    }

    if (task.type === "typing") {
        const fb = document.getElementById('typing-feedback');
        if (fb) {
            let html = `<span style="color:var(--primary); font-weight:bold;">${escapeHtml(task.pinyin)}</span><br><span style="color:var(--text-muted)">${escapeHtml(task.meaning_vn)}</span>`;
            if (!isCorrect) {
                html += `<br><span style="color:var(--danger); font-size:16px;">Correct Answer: ${escapeHtml(task.word)}</span>`;
            }
            fb.innerHTML = html;
            fb.style.display = 'block';
        }
    } else {
        const fb = document.getElementById('mc-feedback');
        if (fb) {
            let html = `<span style="color:var(--primary); font-weight:bold;">${escapeHtml(task.pinyin)}</span><br><span style="color:var(--text-muted)">${escapeHtml(task.meaning_vn)}</span>`;
            if (task.type === "listen") {
                html = `<span style="color:white; font-size:24px; font-weight:bold;">${escapeHtml(task.word)}</span><br>` + html;
            }
            fb.innerHTML = html;
            fb.style.display = 'block';
        }
    }

    if (!isCorrect) {
        missedTasks.push(task);
        if (task.options) {
            const mcBtns = document.querySelectorAll('#mc-area .btn');
            mcBtns.forEach(btn => {
                const textContent = btn.querySelector('.mc-btn-inner')
                    ? btn.querySelector('.mc-btn-inner').textContent.slice(1).trim()
                    : btn.innerText.slice(1).trim();
                if (textContent === correctAnswer) {
                    btn.style.backgroundColor = 'var(--success)';
                    btn.style.color = 'white';
                    btn.style.borderColor = 'var(--success)';
                }
            });
        }
    }

    if (task.audio_key) {
        const audioEl = document.getElementById('audio-player');
        if (audioEl.src) audioEl.play().catch(e => console.warn('Audio playback failed:', e));
    }

    const allBtns = document.querySelectorAll('#screen-training .btn');
    allBtns.forEach(b => b.disabled = true);
    const typingInput = document.getElementById('typing-input');
    if (typingInput) typingInput.disabled = true;

    const gameInfo = { pinyin: task.pinyin, meaning_en: task.meaning_en };
    if (task.options) gameInfo.options = task.options;

    fetch('/api/vocab/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionData.session_id,
            type: task.type,
            word: task.word,
            round_num: sessionData.is_retry ? 2 : 1,
            user_answer: userAnswer,
            is_correct: isCorrect,
            response_time_ms: responseTime,
            game_info: gameInfo
        })
    }).catch(e => console.error('DB Log failed', e));

    setTimeout(() => {
        allBtns.forEach(b => b.disabled = false);
        if (typingInput) typingInput.disabled = false;

        if (element) {
            element.style.backgroundColor = '';
            element.style.color = '';
            element.style.borderColor = '';
        }
        if (!isCorrect && task.options) {
            document.querySelectorAll('#mc-area .btn').forEach(btn => {
                btn.style.backgroundColor = '';
                btn.style.color = '';
                btn.style.borderColor = '';
            });
        }

        nextTask();
    }, 3000);
}

function nextTask() {
    currentTaskIndex++;
    loadTask();
}

function finishRound() {
    switchScreen('screen-complete');

    if (missedTasks.length > 0) {
        document.getElementById('recap-area').style.display = 'block';
        document.getElementById('perfect-area').style.display = 'none';

        const list = document.getElementById('recap-list');
        list.innerHTML = '';

        const uniqueMissed = [...new Set(missedTasks.map(t => t.word))];
        uniqueMissed.forEach(wordStr => {
            const t = missedTasks.find(x => x.word === wordStr);
            const li = document.createElement('li');
            li.innerHTML = `<strong>${escapeHtml(t.word)}</strong> | ${escapeHtml(t.pinyin)} <br> <span style="color:var(--text-muted)">${escapeHtml(t.meaning_vn)}</span>`;
            list.appendChild(li);
        });
    } else {
        document.getElementById('recap-area').style.display = 'none';
        document.getElementById('perfect-area').style.display = 'flex';
    }
}

function retryMissed() {
    for (let i = missedTasks.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [missedTasks[i], missedTasks[j]] = [missedTasks[j], missedTasks[i]];
    }

    sessionData.tasks = [...missedTasks];
    sessionData.is_retry = true;
    currentTaskIndex = 0;
    missedTasks = [];
    loadTask();
}

function confirmQuit() {
    document.getElementById('quit-modal-overlay').classList.add('open');
}

function closeQuitModal() {
    document.getElementById('quit-modal-overlay').classList.remove('open');
}

function closeQuitModalIfBackground(event) {
    if (event.target === document.getElementById('quit-modal-overlay')) {
        closeQuitModal();
    }
}

document.addEventListener('keydown', function (e) {
    const trainingActive = document.getElementById('screen-training').classList.contains('active');
    if (!trainingActive) return;

    if (e.key === 'Enter') {
        if (document.getElementById('typing-area').style.display !== 'none') {
            const typingInput = document.getElementById('typing-input');
            if (!typingInput.disabled) submitTyping();
        }
        return;
    }

    const keyMap = { '1': 0, '2': 1, '3': 2, '4': 3 };
    if (e.key in keyMap) {
        const mcArea = document.getElementById('mc-area');
        if (mcArea.style.display === 'none') return;

        const btns = mcArea.querySelectorAll('.btn');
        const idx = keyMap[e.key];
        if (idx < btns.length && !btns[idx].disabled) btns[idx].click();
    }
});
