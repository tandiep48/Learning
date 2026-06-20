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
let allRowsHidden = false;
let hiddenRows = new Set();

let searchMode = false;
let searchDebounceTimer = null;

document.addEventListener('DOMContentLoaded', () => {
    initTableTrainer();
});

function initTableTrainer() {
    const pageSizeEl = document.getElementById('filter-page-size');
    if (pageSizeEl) pageSize = Number(pageSizeEl.value) || 20;
    setTableMode('standard');
    updateSelectionUI();
}

function setTableMode(mode) {
    tableMode = mode;
    currentPage = 1;
    currentRows = [];
    currentPassageId = null;
    groupedPassages = {};

    document.getElementById('mode-standard-btn')?.classList.toggle('active', mode === 'standard');
    document.getElementById('mode-free-btn')?.classList.toggle('active', mode === 'free');
    document.getElementById('mode-unsure-btn')?.classList.toggle('active', mode === 'unsure');
    document.getElementById('mode-unlearn-btn')?.classList.toggle('active', mode === 'unlearn');
    document.querySelectorAll('.hsk-filter').forEach(el => {
        el.style.display = isHistoryMode() ? 'none' : '';
    });
    document.querySelectorAll('.standard-filter').forEach(el => {
        el.style.display = mode === 'standard' ? '' : 'none';
    });

    resetSelect('filter-hsk', 'Select HSK');
    resetSelect('filter-lesson', 'Select lesson', true);
    resetSelect('filter-part', 'Select part', true);
    if (isHistoryMode()) {
        loadVocabTable();
    } else {
        clearTable('Choose filters to load vocabulary.');
    }
}

function isHistoryMode() {
    return tableMode === 'unsure' || tableMode === 'unlearn';
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

async function loadVocabTable() {
    const hskLevel = document.getElementById('filter-hsk').value;
    const lesson = document.getElementById('filter-lesson').value;
    const part = document.getElementById('filter-part').value;

    if (!isHistoryMode() && (!hskLevel || (tableMode === 'standard' && (!lesson || !part)))) {
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
    table.classList.toggle('all-vocab-hidden', allRowsHidden);
    table.innerHTML = `
        <thead>
            <tr>
                <th class="vocab-select-col">
                    <input type="checkbox" id="select-page-checkbox" onchange="togglePageSelection(this.checked)" title="Select visible rows">
                </th>
                <th class="vocab-tools-col">
                    <button class="vocab-header-icon-btn" onclick="event.stopPropagation(); playAllTableAudio()" title="Play all visible" aria-label="Play all visible">
                        <i class="fa-solid fa-play play-icon" aria-hidden="true"></i>
                    </button>
                    <button class="vocab-header-icon-btn" onclick="event.stopPropagation(); shuffleVisibleRows()" title="Shuffle visible" aria-label="Shuffle visible">
                        <i class="fa-solid fa-shuffle" aria-hidden="true"></i>
                    </button>
                    <button class="vocab-header-icon-btn" id="toggle-all-vocab-btn" onclick="event.stopPropagation(); toggleAllVocabVisibility()" title="Hide or show all rows" aria-label="Hide or show all rows">
                        <i class="fa-solid ${allRowsHidden ? 'fa-eye' : 'fa-eye-slash'}" aria-hidden="true"></i>
                    </button>
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
        tr.classList.toggle('row-vocab-hidden', hiddenRows.has(word));
        const checked = selectedWords.has(word) ? 'checked' : '';
        const audioCell = row.audio_key
            ? `<button class="vocab-audio-btn" onclick="playTableAudio('${escapeAttr(row.audio_key)}')" title="Play audio" aria-label="Play audio"><i class="fa-solid fa-play play-icon" aria-hidden="true"></i></button>`
            : '<span class="vocab-no-audio">-</span>';
        const pinyin = escapeAttr(row.pinyin || '');
        const writeBtn = `<button class="vocab-stroke-row-btn" onclick="openVocabStrokeModal(${escapeJsArg(word)}, '${pinyin}')" title="Write character" aria-label="Write character">&#9999;</button>`;
        tr.innerHTML = `
            <td class="vocab-select-col">
                <input type="checkbox" class="vocab-row-checkbox" ${checked} onchange="toggleWordSelection(${index}, this.checked)">
            </td>
            <td class="vocab-tools-cell">${audioCell}${writeBtn}</td>
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
    if (checked) selectedWords.set(word, normalizeSelectedRow(row));
    else selectedWords.delete(word);
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
    document.getElementById('selection-count').textContent = `${count} selected`;
    document.getElementById('btn-start-selected').disabled = count === 0;
    document.getElementById('btn-flashcards').disabled = count === 0;
}

function clearSelection() {
    selectedWords.clear();
    if (currentRows.length) renderVocabTable(currentRows);
    updateSelectionUI();
}

function getSelectedWordRows() {
    return Array.from(selectedWords.values());
}

function startSelectedTraining() {
    const selected = getSelectedWordRows();
    if (!selected.length) {
        alert('Select at least one word first.');
        return;
    }
    sessionStorage.setItem('selectedVocabTrainerWords', JSON.stringify(selected.map(row => row.word)));
    window.location.href = '/vocab-training';
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
    document.getElementById(tableId)?.classList.toggle(`hide-${colType}`);
}

function toggleAllVocabVisibility() {
    allRowsHidden = !allRowsHidden;
    if (allRowsHidden) {
        currentRows.forEach(row => hiddenRows.add(row.word || row.cn || ''));
    } else {
        currentRows.forEach(row => hiddenRows.delete(row.word || row.cn || ''));
    }
    refreshVisibilityControls();
}

function refreshVisibilityControls() {
    const table = document.getElementById('trainer-vocab-table');
    table?.classList.toggle('all-vocab-hidden', allRowsHidden);

    const headerIcon = document.querySelector('#toggle-all-vocab-btn .fa-solid');
    if (headerIcon) {
        headerIcon.classList.toggle('fa-eye', allRowsHidden);
        headerIcon.classList.toggle('fa-eye-slash', !allRowsHidden);
    }

    // Apply/remove hidden class on all rows based on global toggle
    currentRows.forEach((item, index) => {
        const row = document.getElementById(`trainer-vocab-tr-${index}`);
        row?.classList.toggle('row-vocab-hidden', allRowsHidden);
    });
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

function escapeJsArg(value) {
    return JSON.stringify(String(value ?? '')).replace(/"/g, '&quot;');
}

// ─── Vocab Table Stroke Order Modal ──────────────────────────────────────────

let vocabStrokeWriter = null;
let vocabStrokeChars = [];
let vocabStrokeCharIndex = 0;
let vocabStrokeQuizMode = false;

function openVocabStrokeModal(word, pinyin) {
    if (!word) return;

    // Split word into individual Chinese characters
    vocabStrokeChars = [...word].filter(c => /[\u4e00-\u9fff]/.test(c));
    if (vocabStrokeChars.length === 0) {
        alert('No Chinese characters found for this word.');
        return;
    }

    vocabStrokeCharIndex = 0;
    vocabStrokeQuizMode = false;

    // Populate header
    document.getElementById('vocab-stroke-modal-word').textContent = word;
    document.getElementById('vocab-stroke-modal-pinyin').textContent = pinyin || '';

    // Build character tabs
    const tabsEl = document.getElementById('vocab-stroke-char-tabs');
    if (vocabStrokeChars.length <= 1) {
        tabsEl.style.display = 'none';
    } else {
        tabsEl.style.display = 'flex';
        tabsEl.innerHTML = vocabStrokeChars.map((ch, i) =>
            `<button class="stroke-tab ${i === 0 ? 'active' : ''}" onclick="switchVocabStrokeChar(${i})">${ch}</button>`
        ).join('');
    }

    // Show modal
    document.getElementById('vocab-stroke-modal-overlay').classList.add('open');

    // Render first character
    renderVocabStrokeChar(vocabStrokeCharIndex);
}

function switchVocabStrokeChar(index) {
    vocabStrokeCharIndex = index;
    vocabStrokeQuizMode = false;

    document.querySelectorAll('#vocab-stroke-char-tabs .stroke-tab').forEach((t, i) => {
        t.classList.toggle('active', i === index);
    });

    renderVocabStrokeChar(index);
}

function renderVocabStrokeChar(index) {
    const container = document.getElementById('vocab-stroke-canvas-container');
    container.innerHTML = '';
    vocabStrokeWriter = null;

    const char = vocabStrokeChars[index];
    const size = Math.min(280, window.innerWidth - 80);

    const target = document.createElement('div');
    target.id = 'vocab-stroke-svg-target';
    container.appendChild(target);

    vocabStrokeWriter = HanziWriter.create('vocab-stroke-svg-target', char, {
        width: size,
        height: size,
        padding: 16,
        strokeColor: '#1a1a1a',
        radicalColor: '#007a61',
        outlineColor: 'rgba(0,0,0,0.08)',
        drawingColor: '#007a61',
        drawingWidth: 4,
        showOutline: true,
        showCharacter: false,
        delayBetweenStrokes: 300,
    });

    // Auto-animate on open
    vocabStrokeWriter.animateCharacter();
}

function vocabStrokeAnimate() {
    if (!vocabStrokeWriter) return;
    vocabStrokeQuizMode = false;
    vocabStrokeWriter.animateCharacter();
}

function vocabStrokeQuiz() {
    if (!vocabStrokeWriter) return;
    vocabStrokeQuizMode = true;
    vocabStrokeWriter.quiz({
        onMistake(strokeData) { console.log('Mistake on stroke', strokeData.strokeNum); },
        onCorrectStroke(strokeData) { console.log('Correct stroke', strokeData.strokeNum); },
        onComplete(summaryData) { console.log('Quiz complete! Mistakes:', summaryData.totalMistakes); }
    });
}

function vocabStrokeReset() {
    if (vocabStrokeCharIndex !== undefined) {
        renderVocabStrokeChar(vocabStrokeCharIndex);
    }
}

function closeVocabStrokeModal() {
    document.getElementById('vocab-stroke-modal-overlay').classList.remove('open');
    vocabStrokeWriter = null;
    const container = document.getElementById('vocab-stroke-canvas-container');
    container.innerHTML = '';
}

function closeVocabStrokeModalIfBackground(e) {
    if (e.target.id === 'vocab-stroke-modal-overlay') closeVocabStrokeModal();
}

// ─── Vocabulary Search ────────────────────────────────────────────────────────

function handleSearchInput() {
    const input = document.getElementById('vocab-search-input');
    const clearBtn = document.getElementById('vocab-search-clear');
    const query = input.value.trim();

    clearBtn.style.display = query ? 'flex' : 'none';

    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        if (query.length > 0) {
            searchMode = true;
            currentPage = 1;
            runVocabSearch(query);
        } else {
            exitSearchMode();
        }
    }, 300);
}

async function runVocabSearch(query) {
    setTableState('Searching…');
    const params = new URLSearchParams({
        q: query,
        page: String(currentPage),
        page_size: String(pageSize)
    });
    try {
        const res = await fetch(`/api/vocab/search?${params.toString()}`);
        const data = await res.json();
        if (!res.ok || data.error) {
            clearTable(data.error || 'Search failed.');
            return;
        }
        currentRows = data.rows || [];
        currentPage = data.page || 1;
        totalPages = data.total_pages || 1;
        renderVocabTable(currentRows);
        renderPagination(data.total || 0);
        if (!currentRows.length) clearTable(`No results for "${query}".`);
    } catch (e) {
        console.error(e);
        clearTable('Search failed.');
    }
}

async function changePage(delta) {
    const nextPage = currentPage + delta;
    if (nextPage < 1 || nextPage > totalPages) return;
    currentPage = nextPage;
    if (searchMode) {
        const query = document.getElementById('vocab-search-input')?.value.trim() || '';
        if (query) { await runVocabSearch(query); return; }
    }
    await loadVocabTable();
}

function clearSearch() {
    const input = document.getElementById('vocab-search-input');
    if (input) input.value = '';
    document.getElementById('vocab-search-clear').style.display = 'none';
    exitSearchMode();
}

function exitSearchMode() {
    searchMode = false;
    currentPage = 1;
    clearTable('Choose filters to load vocabulary.');
}

