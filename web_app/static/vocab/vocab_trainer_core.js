// Vocab trainer activity engine — shared by the solo batch trainer and the
// Learn Together room. Owns activity building and the typing / listening-match /
// reading-match rendering; the host page supplies the container and callbacks so
// it can record answers, place the primary action button, track progress and
// react to finish however it needs.
//
// Public API:
//   VocabTrainer.start({
//       container,                       // element to render activities into
//       words,                           // normalized word rows
//       onAnswer(row, type, answer, isCorrect, responseMs),
//       onProgress({ index, total, groupIndex, totalGroups }),
//       mountAction(button),             // place the Check/Continue button
//       onActivityAdvance(),             // called before moving to the next activity
//       onFinish(),                      // called after the last activity
//   })
(function () {
    const GROUP_SIZE = 5;                 // words per group

    // Each group runs typing -> listening match -> reading match.
    const ACTIVITY_TYPES = ['typing', 'listen', 'reading'];

    // Matching config per activity. `db` is the vocab_records mode; the left column is the
    // scored anchor (one record per word), the right column is what gets paired to it.
    const MATCH_CONFIG = {
        listen:  { db: 'listen',  instruction: 'instruction_match_listen',  leftKind: 'audio', rightKind: 'meaning' },
        reading: { db: 'meaning', instruction: 'instruction_match_reading', leftKind: 'word',  rightKind: 'meaning' },
    };

    // Keyboard shortcuts (opt-in via cfg.keyboardShortcuts): left/source cards are
    // picked with 1-5, by their position in the column.
    const LEFT_KEYS = ['1', '2', '3', '4', '5'];

    let cfg = null;                       // active start() config
    let activities = [];                  // flat list of { groupIndex, type, words }
    let currentActivityIndex = 0;
    let activityStartTime = 0;            // for per-answer response time
    let trainerAudio = null;
    let matchKeyHandler = null;           // active match-board keydown listener, if any

    function start(config) {
        cfg = config;
        activities = buildActivities(config.words || []);
        currentActivityIndex = 0;
        renderActivity();
    }

    // ── Activity building ───────────────────────────────────────────────────────
    function buildGroups(rows) {
        const groups = [];
        for (let i = 0; i < rows.length; i += GROUP_SIZE) {
            groups.push(rows.slice(i, i + GROUP_SIZE));
        }
        // Avoid a lone trailing word: fold a size-1 remainder into the previous group.
        if (groups.length > 1 && groups[groups.length - 1].length === 1) {
            groups[groups.length - 2].push(groups.pop()[0]);
        }
        return groups;
    }

    // Build the flat activity list. Each activity type gets its own independent random
    // grouping of the words, and the types are interleaved round by round, so the words
    // paired together differ between typing, listening, and reading (e.g. typing shows
    // A/C while listening shows B/D). Every word still appears once per type, so all
    // words complete all three activities.
    function buildActivities(rows) {
        const groupsByType = ACTIVITY_TYPES.map(type => ({
            type,
            groups: buildGroups(shuffle(rows.slice()))
        }));
        const roundCount = Math.max(...groupsByType.map(g => g.groups.length));

        const list = [];
        for (let round = 0; round < roundCount; round++) {
            groupsByType.forEach(({ type, groups }) => {
                const groupWords = groups[round];
                if (groupWords) list.push({ groupIndex: round, type, words: groupWords });
            });
        }
        return list;
    }

    // ── Flow ────────────────────────────────────────────────────────────────────
    function renderActivity() {
        // Tear down the previous board's keyboard shortcuts before leaving it.
        if (matchKeyHandler) {
            document.removeEventListener('keydown', matchKeyHandler);
            matchKeyHandler = null;
        }
        if (currentActivityIndex >= activities.length) {
            if (cfg.onFinish) cfg.onFinish();
            return;
        }
        const activity = activities[currentActivityIndex];
        reportProgress(activity);

        const area = cfg.container;
        area.innerHTML = '';
        activityStartTime = Date.now();

        if (activity.type === 'typing') {
            renderTypingActivity(area, activity);
        } else if (activity.type === 'listen' || activity.type === 'reading') {
            renderMatchActivity(area, activity);
        }
    }

    function advanceActivity() {
        if (cfg.onActivityAdvance) cfg.onActivityAdvance();
        currentActivityIndex++;
        renderActivity();
    }

    // Competition (auto-advance) has no Check/Continue button, so a single Skip lets the
    // learner bail on the items they don't know. Like the lesson trainer's old skip, the
    // first click reveals every unsolved answer (scored as incorrect) and the button turns
    // into Next — so the learner can read the answers before the board moves on.
    function mountAutoAdvanceSkip(revealUnsolved) {
        if (!cfg.autoAdvance || !cfg.mountAction) return;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn primary bt-primary-action';
        btn.innerText = t('vocab_trainer.skip');
        let revealed = false;
        btn.addEventListener('click', () => {
            if (!revealed) {
                revealed = true;
                revealUnsolved();
                btn.innerText = t('lesson.next');
            } else {
                advanceActivity();
            }
        });
        cfg.mountAction(btn);
    }

    function reportProgress(activity) {
        if (!cfg.onProgress) return;
        const totalGroups = activities.length ? activities[activities.length - 1].groupIndex + 1 : 1;
        cfg.onProgress({
            index: currentActivityIndex,
            total: activities.length,
            groupIndex: activity.groupIndex,
            totalGroups,
        });
    }

    // responseMs is the per-item elapsed time; wrongAttempts is the number of failed
    // tries before this item was completed (matching modes only).
    function record(row, type, userAnswer, isCorrect, responseMs, wrongAttempts = 0) {
        if (cfg.onAnswer) cfg.onAnswer(row, type, userAnswer, isCorrect, responseMs, wrongAttempts);
    }

    // ── Typing activity ─────────────────────────────────────────────────────────
    // Prompt shows the word; the learner types the Chinese word. One-shot: the value
    // at check time is the recorded answer.
    function renderTypingActivity(area, activity) {
        const wrap = document.createElement('div');
        wrap.className = 'bt-typing';

        const instruction = document.createElement('div');
        instruction.className = 'instruction';
        instruction.innerText = t('vocab_trainer.instruction_type_recall');
        wrap.appendChild(instruction);

        const list = document.createElement('div');
        list.className = 'bt-type-list';

        activity.words.forEach((row, idx) => {
            const fontSize = '30px';
            const item = document.createElement('div');
            item.className = 'bt-type-row';
            item.innerHTML = `
                <div class="bt-type-prompt">
                    <span class="bt-hanzi" style="font-size: ${fontSize};">${escapeHtml(row.word || '')}</span>
                </div>
                <input type="text" class="bt-type-input" lang="zh-CN" autocomplete="off"
                       inputmode="text"
                       data-index="${idx}"
                       style="font-size: ${fontSize}; background: #ffffff;">
                <div class="bt-type-result" aria-live="polite"></div>
            `;
            list.appendChild(item);
        });
        wrap.appendChild(list);

        // Auto-advance mode (competition) has no Check button: each word finalises as
        // soon as it is typed correctly, and the group advances once all are done.
        let checkBtn = null;
        if (!cfg.autoAdvance) {
            checkBtn = document.createElement('button');
            checkBtn.className = 'btn primary bt-primary-action';
            checkBtn.id = 'bt-check-btn';
            checkBtn.innerText = t('vocab_trainer.check');
            checkBtn.addEventListener('click', () => checkTypingGroup(activity, wrap, checkBtn));
        }

        area.appendChild(wrap);
        if (checkBtn && cfg.mountAction) cfg.mountAction(checkBtn);

        // Auto-advance (competition) locks each word in as it is solved; a shared counter
        // advances the group once every word is either typed correctly or skipped.
        let autoSolved = 0;
        function autoComplete() {
            autoSolved++;
            if (autoSolved === activity.words.length) setTimeout(advanceActivity, 350);
        }

        // Enter on the last input triggers the group check (manual mode only).
        const inputs = wrap.querySelectorAll('.bt-type-input');
        inputs.forEach((input, idx) => {
            const row = activity.words[idx];
            const rowEl = input.closest('.bt-type-row');
            const result = rowEl.querySelector('.bt-type-result');
            // Answers must be typed — block paste and drag-drop into the field.
            input.addEventListener('paste', (e) => e.preventDefault());
            input.addEventListener('drop', (e) => e.preventDefault());
            // When the typed value matches: reveal pinyin + meaning and play the audio once.
            input.addEventListener('input', () => {
                if (input.disabled) return;
                if (input.value.trim() === (row.word || '')) {
                    if (input.dataset.autoplayed !== '1') {
                        input.dataset.autoplayed = '1';
                        // Stamp when this word was first completed, for per-word timing.
                        input.dataset.completedAt = String(Date.now());
                        rowEl.classList.add('correct');
                        if (result) result.innerHTML = typingResultHtml(row, true);
                        playWordAudio(row.audio_key);
                        if (cfg.autoAdvance) {
                            // Lock the word in and score it; advance once the group is done.
                            input.disabled = true;
                            record(row, 'typing', input.value.trim(), true,
                                Number(input.dataset.completedAt) - activityStartTime, 0);
                            autoComplete();
                        }
                    }
                } else {
                    input.dataset.autoplayed = '';
                    input.dataset.completedAt = '';
                    // Edited away from the answer before checking — hide the live reveal again.
                    if (rowEl.classList.contains('correct')) {
                        rowEl.classList.remove('correct');
                        if (result) result.innerHTML = '';
                    }
                }
            });
            input.addEventListener('keydown', (e) => {
                if (e.key !== 'Enter') return;
                e.preventDefault();
                e.stopPropagation();   // don't let the global Enter handler also advance
                if (idx < inputs.length - 1) inputs[idx + 1].focus();
                else if (!cfg.autoAdvance) checkTypingGroup(activity, wrap, checkBtn);
            });
        });

        // Skip: reveal every word still unsolved (scored as incorrect, no points) so the
        // learner can read the answers, then Next advances the group.
        mountAutoAdvanceSkip(() => {
            inputs.forEach((input, idx) => {
                if (input.disabled) return;
                const row = activity.words[idx];
                const rowEl = input.closest('.bt-type-row');
                const result = rowEl.querySelector('.bt-type-result');
                input.disabled = true;
                rowEl.classList.remove('correct');
                rowEl.classList.add('incorrect');
                if (result) result.innerHTML = typingResultHtml(row, false);
                record(row, 'typing', input.value.trim(), false,
                    Date.now() - activityStartTime, 0);
            });
        });

        if (inputs[0]) inputs[0].focus();
    }

    function typingResultHtml(row, ok) {
        const cls = ok ? 'bt-ok' : 'bt-bad';
        const icon = ok ? 'fa-check' : 'fa-xmark';
        const meaning = row.meaning_vn || row.meaning_en || '';
        return `<span class="${cls}"><i class="fa-solid ${icon}"></i> ${escapeHtml(row.pinyin)} - ${escapeHtml(meaning)}</span>`;
    }

    function checkTypingGroup(activity, wrap, checkBtn) {
        if (checkBtn.dataset.done === '1') { advanceActivity(); return; }

        const rows = wrap.querySelectorAll('.bt-type-row');
        rows.forEach((rowEl, idx) => {
            const row = activity.words[idx];
            const input = rowEl.querySelector('.bt-type-input');
            const result = rowEl.querySelector('.bt-type-result');
            const answer = input.value.trim();
            const isCorrect = answer === row.word;

            input.disabled = true;
            rowEl.classList.remove('correct', 'incorrect');
            rowEl.classList.add(isCorrect ? 'correct' : 'incorrect');
            result.innerHTML = typingResultHtml(row, isCorrect);

            // Time from the word being shown to when it was first typed correctly
            // (or to check time if never correct). Typing carries no error penalty.
            const completedAt = Number(input.dataset.completedAt) || Date.now();
            record(row, 'typing', answer, isCorrect, completedAt - activityStartTime, 0);
        });

        checkBtn.dataset.done = '1';
        checkBtn.innerText = t('lesson.continue');
    }

    // ── Matching activities (listening / reading) ───────────────────────────────
    // Two columns of the same group's words. The left column is the scored anchor: the
    // first pairing attempt for each left item is what gets recorded (one-shot). Wrong
    // pairs flash and reset; the board must be fully matched to continue.
    function renderMatchActivity(area, activity) {
        const matchCfg = MATCH_CONFIG[activity.type];
        const wrap = document.createElement('div');
        wrap.className = 'bt-match';

        const instruction = document.createElement('div');
        instruction.className = 'instruction';
        instruction.innerText = t(`vocab_trainer.${matchCfg.instruction}`);
        wrap.appendChild(instruction);

        const board = document.createElement('div');
        // Both matching activities lay the two sides out as rows (word/audio row + meaning row).
        board.className = 'bt-match-board bt-match-board-rows';

        const leftCol = document.createElement('div');
        leftCol.className = 'bt-match-col';
        const rightCol = document.createElement('div');
        rightCol.className = 'bt-match-col';

        const total = activity.words.length;
        let solved = 0;
        const selected = { left: null, right: null };
        // Per left (anchor) word: when it was first selected, and how many mismatches
        // it took before being solved. Time + penalties are scored per pair on solve.
        const firstSelectedAt = {};
        const wrongAttempts = {};

        activity.words.forEach((row, i) => {
            leftCol.appendChild(makeMatchItem(row, 'left', matchCfg.leftKind, i));
        });
        shuffle(activity.words.slice()).forEach((row, i) => {
            rightCol.appendChild(makeMatchItem(row, 'right', matchCfg.rightKind, i));
        });

        board.appendChild(leftCol);
        board.appendChild(rightCol);
        wrap.appendChild(board);

        // Keyboard shortcuts: 1-5 select a source card, y-u-i-o-p a match card (by
        // column position). Only wired when enabled and while this board is on screen.
        if (cfg.keyboardShortcuts) {
            matchKeyHandler = (e) => {
                const target = e.target;
                if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return;
                const key = (e.key || '').toLowerCase();
                let column = null;
                let idx = LEFT_KEYS.indexOf(key);
                if (idx >= 0) column = leftCol;
                
                if (!column) return;
                const item = column.children[idx];
                if (item && !item.classList.contains('solved')) {
                    e.preventDefault();
                    select(item);
                }
            };
            document.addEventListener('keydown', matchKeyHandler);
        }

        // Auto-advance mode (competition) has no Continue button: the board advances on
        // its own the moment every pair is solved.
        let continueBtn = null;
        if (!cfg.autoAdvance) {
            continueBtn = document.createElement('button');
            continueBtn.className = 'btn primary bt-primary-action';
            continueBtn.innerText = t('lesson.continue');
            continueBtn.disabled = true;
            continueBtn.addEventListener('click', advanceActivity);
        }

        area.appendChild(wrap);
        if (continueBtn && cfg.mountAction) cfg.mountAction(continueBtn);

        // Skip: reveal the correct pairing for every unsolved item (scored as incorrect)
        // so the learner can see the answers, then Next advances the board.
        mountAutoAdvanceSkip(() => {
            if (selected.left) selected.left.classList.remove('selected');
            if (selected.right) selected.right.classList.remove('selected');
            selected.left = null;
            selected.right = null;
            const rightByWord = {};
            rightCol.querySelectorAll('.bt-match-item').forEach(el => {
                rightByWord[el.dataset.word] = el;
            });
            leftCol.querySelectorAll('.bt-match-item').forEach(leftItem => {
                if (leftItem.classList.contains('solved')) return;
                const word = leftItem.dataset.word;
                const row = wordByKey(activity.words, word);
                const startedAt = firstSelectedAt[word] || activityStartTime;
                record(row, matchCfg.db, '', false, Date.now() - startedAt, wrongAttempts[word] || 0);
                [leftItem, rightByWord[word]].forEach(el => {
                    if (!el) return;
                    el.classList.remove('selected', 'wrong');
                    el.classList.add('solved');
                });
            });
        });

        function select(item) {
            if (item.classList.contains('solved')) return;
            const side = item.dataset.side;
            if (side === 'left' && matchCfg.leftKind === 'audio') playWordAudio(item.dataset.audioKey);
            // Start this pair's clock the first time its source (left) card is picked.
            if (side === 'left' && !firstSelectedAt[item.dataset.word]) {
                firstSelectedAt[item.dataset.word] = Date.now();
            }

            if (selected[side] === item) {                 // toggle off
                item.classList.remove('selected');
                selected[side] = null;
                return;
            }
            if (selected[side]) selected[side].classList.remove('selected');
            selected[side] = item;
            item.classList.add('selected');

            if (selected.left && selected.right) evaluate();
        }

        function evaluate() {
            const leftItem = selected.left;
            const rightItem = selected.right;
            const leftWord = leftItem.dataset.word;
            const correct = leftWord === rightItem.dataset.word;
            const row = wordByKey(activity.words, leftWord);

            if (correct) {
                // Record once, on solve: elapsed since the source card was first picked,
                // plus the mismatches it took to get here (drives the error penalty).
                const startedAt = firstSelectedAt[leftWord] || activityStartTime;
                record(row, matchCfg.db, rightItem.dataset.answer || '', true,
                    Date.now() - startedAt, wrongAttempts[leftWord] || 0);
                [leftItem, rightItem].forEach(el => {
                    el.classList.remove('selected');
                    el.classList.add('solved');
                });
                selected.left = null;
                selected.right = null;
                solved++;
                if (solved === total) {
                    if (cfg.autoAdvance) setTimeout(advanceActivity, 500);
                    else continueBtn.disabled = false;
                }
            } else {
                wrongAttempts[leftWord] = (wrongAttempts[leftWord] || 0) + 1;
                [leftItem, rightItem].forEach(el => el.classList.add('wrong'));
                const a = leftItem, b = rightItem;
                selected.left = null;
                selected.right = null;
                setTimeout(() => {
                    [a, b].forEach(el => el.classList.remove('wrong', 'selected'));
                }, 700);
            }
        }

        function makeMatchItem(row, side, kind, index) {
            const item = document.createElement('button');
            item.className = 'bt-match-item';
            item.dataset.side = side;
            item.dataset.word = row.word;
            if (kind === 'audio') {
                item.classList.add('bt-match-audio');
                item.dataset.audioKey = row.audio_key || '';
                item.dataset.answer = row.word;
                item.innerHTML = '<i class="fa-solid fa-volume-high" aria-hidden="true"></i>';
                item.setAttribute('aria-label', t('lesson.play_audio'));
            } else if (kind === 'word') {
                item.dataset.answer = row.word;
                item.innerText = row.word;
                item.style.fontSize = '30px';
            } else { // meaning
                const meaning = row.meaning_vn || row.meaning_en || '';
                item.dataset.answer = meaning;
                item.innerText = meaning;
            }
            // Show the shortcut key badge when keyboard play is enabled. The item gets
            // extra inline padding so the badge sits in a gutter, never over the content.
            const keyChar = side === 'left' ? LEFT_KEYS[index] : RIGHT_KEYS[index];
            if (cfg.keyboardShortcuts && keyChar) {
                item.classList.add('bt-has-key');
                const hint = document.createElement('span');
                hint.className = 'bt-key-hint';
                hint.textContent = keyChar.toUpperCase();
                item.appendChild(hint);
            }
            item.addEventListener('click', () => select(item));
            return item;
        }
    }

    // ── Helpers ─────────────────────────────────────────────────────────────────
    function wordByKey(rows, word) {
        return rows.find(r => r.word === word) || { word };
    }

    function playWordAudio(audioKey) {
        if (!audioKey) return;
        try {
            if (!trainerAudio) trainerAudio = new Audio();
            trainerAudio.src = `/audio/${audioKey}.mp3`;
            trainerAudio.currentTime = 0;
            trainerAudio.play().catch(() => {});
        } catch (e) { /* ignore playback errors */ }
    }

    function shuffle(arr) {
        for (let i = arr.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        return arr;
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    window.VocabTrainer = { start };
})();
