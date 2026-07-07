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
let hiddenCells = new Set();
let hiddenColumns = new Set();
let revealedColumnCells = new Set();
let activeTableAudioButton = null;
let activeAudioRevealRow = null;

let searchMode = false;
let searchDebounceTimer = null;

document.addEventListener('DOMContentLoaded', () => {
    initTableTrainer();
});

function initTableTrainer() {
    const pageSizeEl = document.getElementById('filter-page-size');
    if (pageSizeEl) pageSize = Number(pageSizeEl.value) || 20;
    const params = new URLSearchParams(window.location.search);
    const requestedMode = params.get('mode');
    const allowedModes = new Set(['standard', 'free', 'unsure', 'unlearn', 'recent']);
    setTableMode(allowedModes.has(requestedMode) ? requestedMode : 'standard');
    updateSelectionUI();
}

function setTableMode(mode) {
    tableMode = mode;
    currentPage = 1;
    currentRows = [];
    currentPassageId = null;
    groupedPassages = {};

    // Sync dropdown
    const modeSelect = document.getElementById('mode-select');
    if (modeSelect && modeSelect.value !== mode) modeSelect.value = mode;

    document.querySelectorAll('.hsk-filter').forEach(el => {
        el.style.display = isHistoryMode() ? 'none' : '';
    });
    document.querySelectorAll('.standard-filter').forEach(el => {
        el.style.display = mode === 'standard' ? '' : 'none';
    });

    resetSelect('filter-hsk', t('vocab.select_hsk'));
    resetSelect('filter-lesson', t('vocab.select_lesson_option'), true);
    resetSelect('filter-part', t('vocab.select_part_option'), true);
    if (isHistoryMode()) {
        loadVocabTable();
    } else {
        clearTable(t('vocab.state_choose_filters'));
    }
}

function isHistoryMode() {
    return tableMode === 'unsure' || tableMode === 'unlearn' || tableMode === 'recent';
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
    resetSelect('filter-lesson', t('vocab.select_lesson_option'), true);
    resetSelect('filter-part', t('vocab.select_part_option'), true);

    const hskLevel = document.getElementById('filter-hsk').value;
    if (!hskLevel) {
        clearTable(t('vocab.state_choose_filters'));
        return;
    }

    if (tableMode === 'free') {
        await loadVocabTable();
        return;
    }

    await loadStandardLessons(hskLevel);
}

async function loadStandardLessons(hskLevel) {
    setTableState(t('picker.loading_lessons'));
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
        resetSelect('filter-lesson', t('vocab.select_lesson_option'));
        Object.keys(groupedPassages).sort(numericSort).forEach(lesson => {
            const option = document.createElement('option');
            option.value = lesson;
            option.textContent = lesson === 'Other' ? t('vocab.other_label') : `${t('picker.lesson_prefix')} ${lesson}`;
            lessonSelect.appendChild(option);
        });
        lessonSelect.disabled = Object.keys(groupedPassages).length === 0;
        clearTable(Object.keys(groupedPassages).length ? t('vocab.choose_lesson_and_part') : t('vocab.no_lessons_found'));
    } catch (e) {
        console.error(e);
        clearTable(t('picker.failed_load_lessons'));
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
    resetSelect('filter-part', t('vocab.select_part_option'));

    if (!lesson || !groupedPassages[lesson]) {
        partSelect.disabled = true;
        clearTable(t('vocab.choose_lesson_and_part'));
        return;
    }

    groupedPassages[lesson].sort((a, b) => Number(a.part) - Number(b.part)).forEach(passage => {
        const option = document.createElement('option');
        option.value = passage.part;
        option.textContent = `${t('picker.part_prefix')} ${passage.part}`;
        option.dataset.passageId = passage.passage_id;
        partSelect.appendChild(option);
    });
    partSelect.disabled = false;
    clearTable(t('vocab.choose_a_part'));
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
        clearTable(tableMode === 'standard' ? t('vocab.choose_hsk_lesson_part') : t('vocab.choose_hsk_only'));
        return;
    }

    setTableState(t('dashboard.loading_vocabulary'));
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
        const url = tableMode === 'recent'
            ? `/api/user/learned-vocab?page=${encodeURIComponent(currentPage)}&page_size=${encodeURIComponent(pageSize)}`
            : `/api/vocab/table?${params.toString()}`;
        const res = await fetch(url);
        const data = await res.json();
        if (!res.ok || data.error) {
            clearTable(data.error || t('reading.failed_load_vocabulary'));
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
        clearTable(t('reading.failed_load_vocabulary'));
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
        clearTable(t('vocab.no_vocab_found'));
        return;
    }

    const table = document.createElement('table');
    table.className = 'vocab-table';
    table.id = 'trainer-vocab-table';
    syncAllRowsHiddenState();
    ['cn', 'py', 'vn'].forEach(col => table.classList.toggle(`hide-${col}`, hiddenColumns.has(col)));
    table.innerHTML = `
        <thead>
            <tr>
                <th class="vocab-no-col">
                    <button class="vocab-header-icon-btn" onclick="event.stopPropagation(); shuffleVisibleRows()" title="${t('vocab.shuffle_visible_aria')}" aria-label="${t('vocab.shuffle_visible_aria')}">
                        <i class="fa-solid fa-shuffle" aria-hidden="true"></i>
                    </button>
                    <span class="vocab-no-label">${t('vocab.no_column')}</span>
                </th>
                <th class="vocab-select-col">
                    <input type="checkbox" id="select-page-checkbox" onchange="togglePageSelection(this.checked)" title="${t('vocab.select_visible_rows_aria')}">
                </th>
                <th class="vocab-tools-col">
                    <button class="vocab-header-icon-btn" id="table-play-all-btn" onclick="event.stopPropagation(); playAllTableAudio()" title="${t('vocab.play_all_visible_aria')}" aria-label="${t('vocab.play_all_visible_aria')}">
                        <i class="fa-solid fa-play play-icon" aria-hidden="true"></i>
                    </button>
                    <button class="vocab-header-icon-btn" id="table-stroke-all-btn" onclick="event.stopPropagation(); strokeOrderAll()" title="${t('vocab.stroke_all_aria')}" aria-label="${t('vocab.stroke_all_aria')}">
                        <i class="fa-solid fa-paintbrush" aria-hidden="true"></i>
                    </button>
                </th>
                <th>${renderColumnHeader('cn', t('dashboard.table_character'), 'trainer-vocab-table')}</th>
                <th>${renderColumnHeader('py', t('dashboard.table_pinyin'), 'trainer-vocab-table')}</th>
                <th>${renderColumnHeader('vn', t('dashboard.table_meaning_vn'), 'trainer-vocab-table')}</th>
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
            ? `<button class="vocab-audio-btn" onclick="playTableAudio('${escapeAttr(row.audio_key)}', ${escapeJsArg(word)}, this)" title="${t('lesson.play_audio')}" aria-label="${t('lesson.play_audio')}"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>`
            : '<span class="vocab-no-audio">-</span>';
        const pinyin = escapeAttr(row.pinyin || '');
        const writeBtn = /[\u4e00-\u9fff]/.test(word)
            ? `<button class="vocab-stroke-row-btn" onclick="openVocabStrokeModal(${escapeJsArg(word)}, '${pinyin}')" title="${t('vocab.write_character_aria')}" aria-label="${t('vocab.write_character_aria')}"><i class="fa-solid fa-paintbrush" aria-hidden="true"></i></button>`
            : '';
        tr.innerHTML = `
            <td class="vocab-no-cell">${index + 1}</td>
            <td class="vocab-select-col">
                <input type="checkbox" class="vocab-row-checkbox" ${checked} onchange="toggleWordSelection(${index}, this.checked)">
            </td>
            <td class="vocab-tools-cell">${writeBtn}${audioCell}</td>
            <td class="vocab-cn clickable-cell ${getVocabCellClasses(word, 'cn')}" onclick="toggleVocabCell(this, 'cn', ${escapeJsArg(word)}, 'trainer-vocab-table')">${escapeHtml(word)}</td>
            <td class="vocab-pinyin clickable-cell ${getVocabCellClasses(word, 'py')}" onclick="toggleVocabCell(this, 'py', ${escapeJsArg(word)}, 'trainer-vocab-table')">${escapeHtml(row.pinyin || '')}</td>
            <td class="vocab-meaning-vn clickable-cell ${getVocabCellClasses(word, 'vn')}" onclick="toggleVocabCell(this, 'vn', ${escapeJsArg(word)}, 'trainer-vocab-table')">${escapeHtml(row.meaning_vn || row.meaning_en || '')}</td>
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
    status.textContent = t('vocab.page_status_with_count', { current: currentPage, total: totalPages, count: total });
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

function startSelectedTraining() {
    const selected = getSelectedWordRows();
    if (!selected.length) {
        alert(t('vocab.select_at_least_one'));
        return;
    }
    sessionStorage.setItem('selectedVocabTrainerWords', JSON.stringify(selected.map(row => row.word)));
    window.location.href = '/vocab-training';
}

function openSelectedFlashcards() {
    const selected = getSelectedWordRows();
    if (!selected.length) {
        alert(t('vocab.select_at_least_one'));
        return;
    }
    sessionStorage.setItem('selectedVocabFlashcards', JSON.stringify(selected));
    window.location.href = '/vocab-learning?source=selection';
}

function renderColumnHeader(colType, label, tableId) {
    const isHidden = hiddenColumns.has(colType);
    return `
        <span class="vocab-column-header-label">${escapeHtml(label)}</span>
        <button type="button" class="vocab-column-toggle" data-col="${colType}" onclick="event.stopPropagation(); toggleVocabColumn('${colType}', '${tableId}')" title="${isHidden ? t('vocab.show') : t('vocab.hide')} ${escapeAttr(label)}" aria-label="${isHidden ? t('vocab.show') : t('vocab.hide')} ${escapeAttr(label)}">
            <i class="fa-solid ${isHidden ? 'fa-eye' : 'fa-eye-slash'}" aria-hidden="true"></i>
        </button>
    `;
}

function toggleVocabColumn(colType, tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    currentRows.forEach(row => revealedColumnCells.delete(getVocabCellKey(row.word || row.cn || '', colType)));
    if (hiddenColumns.has(colType)) hiddenColumns.delete(colType);
    else {
        hiddenColumns.add(colType);
        currentRows.forEach(row => hiddenCells.delete(getVocabCellKey(row.word || row.cn || '', colType)));
    }
    table.classList.toggle(`hide-${colType}`, hiddenColumns.has(colType));
    updateColumnToggleIcon(colType);
    refreshVocabCellVisibility();
}

function toggleVocabCell(cell, colType, word, tableId) {
    const table = document.getElementById(tableId);
    const key = getVocabCellKey(word, colType);
    if (table?.classList.contains(`hide-${colType}`)) {
        const shouldReveal = !revealedColumnCells.has(key);
        if (shouldReveal) revealedColumnCells.add(key);
        else revealedColumnCells.delete(key);
        cell.classList.toggle('column-cell-revealed', shouldReveal);
        return;
    }
    const shouldHide = !hiddenCells.has(key);
    if (shouldHide) hiddenCells.add(key);
    else hiddenCells.delete(key);
    cell.classList.toggle('hidden-cell', shouldHide);
}

function updateColumnToggleIcon(colType) {
    const button = document.querySelector(`.vocab-column-toggle[data-col="${colType}"]`);
    if (!button) return;
    const icon = button.querySelector('.fa-solid');
    const isHidden = hiddenColumns.has(colType);
    icon?.classList.toggle('fa-eye', isHidden);
    icon?.classList.toggle('fa-eye-slash', !isHidden);
    button.title = `${isHidden ? t('vocab.show') : t('vocab.hide')} ${t('vocab.column_label')}`;
    button.setAttribute('aria-label', button.title);
}

function getVocabCellKey(word, colType) {
    return `${word || ''}::${colType}`;
}

function getVocabCellClasses(word, colType) {
    const key = getVocabCellKey(word, colType);
    return [
        hiddenCells.has(key) ? 'hidden-cell' : '',
        revealedColumnCells.has(key) ? 'column-cell-revealed' : ''
    ].filter(Boolean).join(' ');
}

function refreshVocabCellVisibility() {
    const table = document.getElementById('trainer-vocab-table');
    if (!table) return;
    currentRows.forEach((row, index) => {
        const word = row.word || row.cn || '';
        const tr = document.getElementById(`trainer-vocab-tr-${index}`);
        if (!tr) return;
        [
            ['cn', '.vocab-cn'],
            ['py', '.vocab-pinyin'],
            ['vn', '.vocab-meaning-vn']
        ].forEach(([colType, selector]) => {
            const cell = tr.querySelector(selector);
            const key = getVocabCellKey(word, colType);
            cell?.classList.toggle('hidden-cell', hiddenCells.has(key));
            cell?.classList.toggle('column-cell-revealed', hiddenColumns.has(colType) && revealedColumnCells.has(key));
        });
    });
}

function toggleAllVocabVisibility() {
    syncAllRowsHiddenState();
    const shouldHide = !allRowsHidden;
    if (shouldHide) {
        currentRows.forEach(row => hiddenRows.add(row.word || row.cn || ''));
    } else {
        currentRows.forEach(row => hiddenRows.delete(row.word || row.cn || ''));
    }
    refreshVisibilityControls();
}

function refreshVisibilityControls() {
    syncAllRowsHiddenState();
    currentRows.forEach((item, index) => {
        const row = document.getElementById(`trainer-vocab-tr-${index}`);
        row?.classList.toggle('row-vocab-hidden', hiddenRows.has(item.word || item.cn || ''));
    });
}

function syncAllRowsHiddenState() {
    allRowsHidden = currentRows.length > 0 && currentRows.every(row => hiddenRows.has(row.word || row.cn || ''));
}

function revealRowForAudio(rowIndex) {
    restoreAudioReveal();
    const row = document.getElementById(`trainer-vocab-tr-${rowIndex}`);
    if (!row) return;
    row.classList.add('audio-revealed');
    activeAudioRevealRow = row;
}

function restoreAudioReveal() {
    activeAudioRevealRow?.classList.remove('audio-revealed');
    activeAudioRevealRow = null;
}

function shuffleVisibleRows() {
    if (tableAudio) tableAudio.pause();
    isPlayingTableAudio = false;
    resetTableAudioButtons();
    for (let i = currentRows.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [currentRows[i], currentRows[j]] = [currentRows[j], currentRows[i]];
    }
    renderVocabTable(currentRows);
}

function setAudioButtonPlaying(button, playing) {
    const icon = button?.querySelector('.fa-solid');
    if (!icon) return;
    // Row buttons show a speaker icon at rest; the header "play all" button shows a play icon.
    const isRowButton = button.classList.contains('vocab-audio-btn');
    const restIcon = isRowButton ? 'fa-volume-high' : 'fa-play';
    icon.classList.toggle(restIcon, !playing);
    icon.classList.toggle('fa-pause', playing);
    icon.classList.toggle('play-icon', !playing && !isRowButton);
}

function resetTableAudioButtons() {
    if (activeTableAudioButton) setAudioButtonPlaying(activeTableAudioButton, false);
    activeTableAudioButton = null;
    setAudioButtonPlaying(document.getElementById('table-play-all-btn'), false);
    restoreAudioReveal();
}

function playTableAudio(audioKey, word = '', button = null) {
    if (!audioKey) return;
    if (tableAudio) tableAudio.pause();
    resetTableAudioButtons();
    const rowIndex = currentRows.findIndex(row => (row.word || row.cn || '') === word);
    if (rowIndex !== -1) revealRowForAudio(rowIndex);
    tableAudio = new Audio(`/audio/${audioKey}.mp3`);
    activeTableAudioButton = button;
    setAudioButtonPlaying(activeTableAudioButton, true);
    tableAudio.onended = resetTableAudioButtons;
    tableAudio.onerror = resetTableAudioButtons;
    tableAudio.play().catch(e => {
        resetTableAudioButtons();
        console.warn('Audio playback failed:', e);
    });
}

async function playAllTableAudio() {
    if (isPlayingTableAudio) {
        isPlayingTableAudio = false;
        if (tableAudio) tableAudio.pause();
        resetTableAudioButtons();
        return;
    }
    isPlayingTableAudio = true;
    resetTableAudioButtons();
    setAudioButtonPlaying(document.getElementById('table-play-all-btn'), true);
    const playable = currentRows.map((row, index) => ({ ...row, index })).filter(row => row.audio_key);
    for (const row of playable) {
        if (!isPlayingTableAudio) break;
        document.querySelectorAll('#trainer-vocab-table tr').forEach(tr => tr.classList.remove('playing-highlight'));
        document.getElementById(`trainer-vocab-tr-${row.index}`)?.classList.add('playing-highlight');
        revealRowForAudio(row.index);
        await new Promise(resolve => {
            if (tableAudio) tableAudio.pause();
            tableAudio = new Audio(`/audio/${row.audio_key}.mp3`);
            tableAudio.onended = resolve;
            tableAudio.onerror = resolve;
            tableAudio.play().catch(resolve);
        });
        restoreAudioReveal();
        await new Promise(resolve => setTimeout(resolve, 400));
    }
    document.querySelectorAll('#trainer-vocab-table tr').forEach(tr => tr.classList.remove('playing-highlight'));
    isPlayingTableAudio = false;
    resetTableAudioButtons();
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
    stopStrokeOrderAll();

    // Split word into individual Chinese characters
    vocabStrokeChars = [...word].filter(c => /[\u4e00-\u9fff]/.test(c));
    if (vocabStrokeChars.length === 0) {
        alert(t('vocab.no_chars_found'));
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
    stopStrokeOrderAll();
    document.getElementById('vocab-stroke-modal-overlay').classList.remove('open');
    vocabStrokeWriter = null;
    const container = document.getElementById('vocab-stroke-canvas-container');
    container.innerHTML = '';
}

function closeVocabStrokeModalIfBackground(e) {
    if (e.target.id === 'vocab-stroke-modal-overlay') closeVocabStrokeModal();
}

// ─── Stroke Order: All Words on Current Page ─────────────────────────────────

let strokeAllQueue = [];
let strokeAllIndex = 0;
let strokeAllActive = false;

function strokeOrderAll() {
    // Build a flat queue of every Chinese character across the current page's rows.
    strokeAllQueue = [];
    currentRows.forEach(row => {
        const word = row.word || row.cn || '';
        const pinyin = row.pinyin || '';
        [...word].filter(c => /[一-鿿]/.test(c)).forEach(ch => strokeAllQueue.push({ ch, word, pinyin }));
    });
    if (!strokeAllQueue.length) {
        alert(t('vocab.no_chars_found'));
        return;
    }
    strokeAllIndex = 0;
    strokeAllActive = true;
    document.getElementById('vocab-stroke-char-tabs').style.display = 'none';
    document.getElementById('vocab-stroke-modal-overlay').classList.add('open');
    renderStrokeAllChar();
}

function renderStrokeAllChar() {
    if (!strokeAllActive) return;
    const item = strokeAllQueue[strokeAllIndex];
    if (!item) { strokeAllActive = false; return; }

    // Keep the single-char controls (Animate/Reset) pointing at the current character.
    vocabStrokeChars = [item.ch];
    vocabStrokeCharIndex = 0;

    document.getElementById('vocab-stroke-modal-word').textContent = item.word;
    document.getElementById('vocab-stroke-modal-pinyin').textContent =
        `${item.pinyin ? item.pinyin + ' · ' : ''}${strokeAllIndex + 1}/${strokeAllQueue.length}`;

    const container = document.getElementById('vocab-stroke-canvas-container');
    container.innerHTML = '';
    const target = document.createElement('div');
    target.id = 'vocab-stroke-svg-target';
    container.appendChild(target);

    const size = Math.min(280, window.innerWidth - 80);
    vocabStrokeWriter = HanziWriter.create('vocab-stroke-svg-target', item.ch, {
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

    vocabStrokeWriter.animateCharacter({
        onComplete: () => {
            if (!strokeAllActive) return;
            setTimeout(() => {
                if (!strokeAllActive) return;
                strokeAllIndex++;
                if (strokeAllIndex < strokeAllQueue.length) renderStrokeAllChar();
                else strokeAllActive = false;
            }, 600);
        }
    });
}

function stopStrokeOrderAll() {
    strokeAllActive = false;
    strokeAllQueue = [];
    strokeAllIndex = 0;
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
    setTableState(t('vocab.searching'));
    const params = new URLSearchParams({
        q: query,
        page: String(currentPage),
        page_size: String(pageSize)
    });
    try {
        const res = await fetch(`/api/vocab/search?${params.toString()}`);
        const data = await res.json();
        if (!res.ok || data.error) {
            clearTable(data.error || t('vocab.search_failed'));
            return;
        }
        currentRows = data.rows || [];
        currentPage = data.page || 1;
        totalPages = data.total_pages || 1;
        renderVocabTable(currentRows);
        renderPagination(data.total || 0);
        if (!currentRows.length) clearTable(t('vocab.no_results_for', { query }));
    } catch (e) {
        console.error(e);
        clearTable(t('vocab.search_failed'));
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
    clearTable(t('vocab.state_choose_filters'));
}

