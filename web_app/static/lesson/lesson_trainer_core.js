// Lesson trainer activity engine for the "Learn Together" lesson mode. Runs a shared,
// pre-generated list of lesson tasks (listening / meaning / typing / reorder) inside a
// host-supplied container, auto-advancing competition-style. The host page provides the
// container and callbacks so it can record answers, place the Skip/Next button, track
// progress and react to finish.
//
// Public API:
//   LessonTrainer.start({
//       container,                       // element to render tasks into
//       tasks,                           // lesson task rows (from the server session)
//       onAnswer(task, isCorrect, responseMs),
//       onProgress({ index, total }),
//       mountAction(button),             // place the Skip/Next button
//       onFinish(),                      // called after the last task
//   })
(function () {
    let cfg = null;
    let tasks = [];
    let currentIndex = 0;
    let taskStartTime = 0;
    let answered = false;
    let trainerAudio = null;
    let keyHandler = null;            // active number-key listener for MC boards

    function start(config) {
        cfg = config;
        tasks = Array.isArray(config.tasks) ? config.tasks : [];
        currentIndex = 0;
        renderTask();
    }

    // ── Flow ──────────────────────────────────────────────────────────────────
    function renderTask() {
        detachKeyHandler();
        if (currentIndex >= tasks.length) {
            if (cfg.onFinish) cfg.onFinish();
            return;
        }
        const task = tasks[currentIndex];
        reportProgress();

        const area = cfg.container;
        area.innerHTML = '';
        answered = false;
        taskStartTime = Date.now();

        if (task.type === 'listening' || task.type === 'meaning') {
            renderChoice(area, task);
        } else if (task.type === 'typing') {
            renderTyping(area, task);
        } else if (task.type === 'reorder') {
            renderReorder(area, task);
        }
        applyHanText(area, task);
    }

    function advance() {
        detachKeyHandler();
        currentIndex++;
        renderTask();
    }

    function reportProgress() {
        if (cfg.onProgress) cfg.onProgress({ index: currentIndex, total: tasks.length });
    }

    function itemKey(task) {
        return `${task.passage_id || ''}:${task.line_id != null ? task.line_id : ''}`;
    }

    // Record the task's outcome once. responseMs is time from the task being shown.
    function record(task, isCorrect) {
        if (cfg.onAnswer) cfg.onAnswer(task, isCorrect, Date.now() - taskStartTime);
    }

    // Shared settle: record, reveal the answer, then either auto-advance (correct) or
    // turn the action button into Next so the learner can study a wrong/skipped answer.
    function settle(task, isCorrect, reveal) {
        if (answered) return;
        answered = true;
        detachKeyHandler();
        record(task, isCorrect);
        reveal(isCorrect);
        if (isCorrect) {
            if (task.type === 'typing' || task.type === 'reorder') {
                playAudioToEnd(task).then(advance);
            } else {
                setTimeout(advance, 800);
            }
        } else {
            setAction(t('lesson.next'), advance);
        }
    }

    // The single primary action button (Skip before answering; Next after). Rebuilt each
    // time so the host's mountAction can drop the previous one.
    function setAction(label, handler) {
        if (!cfg.mountAction) return;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn primary bt-primary-action';
        btn.innerText = label;
        btn.addEventListener('click', handler);
        cfg.mountAction(btn);
    }

    function mountSkip(task, reveal) {
        setAction(t('trainer.skip'), () => settle(task, false, reveal));
    }

    // ── Multiple choice (listening / meaning) ─────────────────────────────────
    function renderChoice(area, task) {
        const wrap = document.createElement('div');
        wrap.className = 'lt-task lt-choice';

        const isListening = task.type === 'listening';
        const instruction = document.createElement('div');
        instruction.className = 'instruction';
        const icon = isListening ? 'fa-headphones-simple' : 'fa-book-open';
        const text = isListening ? t('lesson.instruction_listen') : t('lesson.instruction_meaning');
        instruction.innerHTML = `<i class="fa-solid ${icon}" aria-hidden="true"></i><span>${escapeHtml(text)}</span>`;
        wrap.appendChild(instruction);

        if (isListening) {
            const audioBtn = document.createElement('button');
            audioBtn.type = 'button';
            audioBtn.className = 'lt-audio-btn';
            audioBtn.innerHTML = '<i class="fa-solid fa-volume-high" aria-hidden="true"></i>';
            audioBtn.setAttribute('aria-label', t('lesson.play_audio'));
            audioBtn.addEventListener('click', () => playAudio(task));
            wrap.appendChild(audioBtn);
        } else {
            const word = document.createElement('div');
            word.className = 'lt-word';
            word.innerText = task.content || '';
            wrap.appendChild(word);
        }

        const grid = document.createElement('div');
        grid.className = 'lt-mc-area';
        const options = task.options || [];
        options.forEach((opt, idx) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn lt-mc-btn';
            btn.innerHTML = `<span class="mc-btn-inner"><span class="key-hint">${idx + 1}</span>${escapeHtml(opt)}</span>`;
            btn.addEventListener('click', () => {
                if (answered) return;
                const isCorrect = answersMatch(opt, task.correct_answer);
                btn.classList.add(isCorrect ? 'lt-correct' : 'lt-wrong');
                settle(task, isCorrect, () => revealChoice(grid, task));
            });
            grid.appendChild(btn);
        });
        wrap.appendChild(grid);
        area.appendChild(wrap);

        mountSkip(task, () => revealChoice(grid, task));

        // Number keys 1-4 pick an option, matching the solo lesson trainer.
        keyHandler = (e) => {
            const tag = e.target && e.target.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA') return;
            const n = parseInt(e.key, 10);
            if (!n || n > grid.children.length) return;
            e.preventDefault();
            grid.children[n - 1].click();
        };
        document.addEventListener('keydown', keyHandler);

        if (isListening) playAudio(task);
    }

    function revealChoice(grid, task) {
        grid.querySelectorAll('.lt-mc-btn').forEach(btn => {
            const label = btn.querySelector('.mc-btn-inner');
            const value = label ? label.textContent.slice(1).trim() : btn.innerText.trim();
            if (answersMatch(value, task.correct_answer)) btn.classList.add('lt-correct');
            btn.disabled = true;
        });
    }

    // ── Typing ────────────────────────────────────────────────────────────────
    function renderTyping(area, task) {
        const wrap = document.createElement('div');
        wrap.className = 'lt-task lt-typing';

        const instruction = document.createElement('div');
        instruction.className = 'instruction';
        instruction.innerHTML = `<i class="fa-solid fa-keyboard" aria-hidden="true"></i><span>${escapeHtml(t('lesson.instruction_typing'))}</span>`;
        wrap.appendChild(instruction);

        const targetText = window.HanziSettings?.convertText?.(task.content || '') ?? (task.content || '');
        const target = document.createElement('div');
        target.className = 'lt-typing-target';
        target.setAttribute('data-han-skip', '');
        for (const ch of [...targetText]) {
            const span = document.createElement('span');
            span.className = 'typing-char';
            span.textContent = ch;
            target.appendChild(span);
        }
        wrap.appendChild(target);

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'lt-typing-input';
        input.lang = 'zh-CN';
        input.autocomplete = 'off';
        input.setAttribute('inputmode', 'text');
        input.addEventListener('paste', (e) => e.preventDefault());
        input.addEventListener('drop', (e) => e.preventDefault());
        input.addEventListener('input', () => {
            if (answered) return;
            highlightTyping(target, targetText, input.value);
            if (input.value.trim() === (task.correct_answer || '')) {
                settle(task, true, () => revealTyping(task, input, wrap));
            }
        });
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); }
        });
        wrap.appendChild(input);

        const pinyin = document.createElement('div');
        pinyin.className = 'lt-typing-pinyin';
        wrap.appendChild(pinyin);

        area.appendChild(wrap);
        mountSkip(task, () => revealTyping(task, input, wrap));
        input.focus();
    }

    function highlightTyping(target, targetText, value) {
        const targetChars = [...targetText];
        const typed = [...value];
        const spans = target.children;
        for (let i = 0; i < spans.length; i++) {
            spans[i].classList.remove('char-correct', 'char-wrong');
            if (i < typed.length && /[一-鿿]/.test(typed[i])) {
                spans[i].classList.add(typed[i] === targetChars[i] ? 'char-correct' : 'char-wrong');
            }
        }
    }

    function revealTyping(task, input, wrap) {
        input.disabled = true;
        if (task.pinyin) {
            const el = wrap.querySelector('.lt-typing-pinyin');
            if (el) { el.textContent = task.pinyin; el.style.display = 'block'; }
        }
    }

    // ── Reorder ───────────────────────────────────────────────────────────────
    // Click a source chip to append it to the answer row (building the order), click a
    // placed chip to send it back. Auto-submits once the answer row matches.
    function renderReorder(area, task) {
        const wrap = document.createElement('div');
        wrap.className = 'lt-task lt-reorder';

        const instruction = document.createElement('div');
        instruction.className = 'instruction';
        instruction.innerHTML = `<i class="fa-solid fa-arrows-up-down-left-right" aria-hidden="true"></i><span>${escapeHtml(t('lesson.instruction_reorder'))}</span>`;
        wrap.appendChild(instruction);

        const targetRow = document.createElement('div');
        targetRow.className = 'chip-container lt-reorder-target';
        const sourceRow = document.createElement('div');
        sourceRow.className = 'chip-container lt-reorder-source';

        const feedback = document.createElement('div');
        feedback.className = 'lt-reorder-feedback';

        const syncAndCheck = () => {
            if (answered) return;
            const order = [...targetRow.children].map(c => c.dataset.token);
            if (reorderMatches(order, task.tokens)) {
                settle(task, true, () => revealReorder(task, feedback));
            }
        };

        (task.shuffled_tokens || []).forEach(token => {
            const chip = document.createElement('div');
            chip.className = 'chip lesson-reorder-chip';
            chip.innerText = token;
            chip.dataset.token = token;
            chip.addEventListener('click', () => {
                if (answered) return;
                if (chip.parentElement === sourceRow) targetRow.appendChild(chip);
                else sourceRow.appendChild(chip);
                syncAndCheck();
            });
            sourceRow.appendChild(chip);
        });

        wrap.appendChild(targetRow);
        wrap.appendChild(sourceRow);
        wrap.appendChild(feedback);
        area.appendChild(wrap);

        mountSkip(task, () => revealReorder(task, feedback));
    }

    function revealReorder(task, feedback) {
        feedback.innerHTML =
            `<span class="lt-reorder-label">${escapeHtml(t('lesson.correct_answer_label'))}</span>` +
            `<span class="lt-reorder-answer">${escapeHtml(task.correct_answer || '')}</span>`;
        feedback.style.display = 'block';
    }

    // ── Audio ─────────────────────────────────────────────────────────────────
    function audioSrc(task) {
        if (!task.audio_key) return null;
        if (task.book_code) return `/lesson_audio/${task.book_code}/${task.audio_key}.mp3`;
        let hsk = task.hsk_level || 'HSK1';
        if (!String(hsk).startsWith('HSK')) hsk = 'HSK' + String(hsk).replace('H', '');
        return `/lesson_audio/${hsk}/${task.audio_key}.mp3`;
    }

    function playAudio(task) {
        const src = audioSrc(task);
        if (!src) return;
        try {
            if (!trainerAudio) trainerAudio = new Audio();
            trainerAudio.src = src;
            trainerAudio.currentTime = 0;
            trainerAudio.play().catch(() => {});
        } catch (e) { /* ignore playback errors */ }
    }

    // Play the task audio and resolve when it ends (bounded), so typing/reorder answers
    // let the audio finish before advancing. Resolves quickly when there is no audio.
    function playAudioToEnd(task) {
        const src = audioSrc(task);
        if (!src) return new Promise(resolve => setTimeout(resolve, 500));
        return new Promise(resolve => {
            let done = false;
            const finish = () => { if (!done) { done = true; resolve(); } };
            try {
                if (!trainerAudio) trainerAudio = new Audio();
                trainerAudio.src = src;
                trainerAudio.onended = finish;
                trainerAudio.onerror = finish;
                trainerAudio.currentTime = 0;
                trainerAudio.play().catch(finish);
            } catch (e) { finish(); }
            setTimeout(finish, 6000);
        });
    }

    // ── Helpers ───────────────────────────────────────────────────────────────
    function detachKeyHandler() {
        if (keyHandler) {
            document.removeEventListener('keydown', keyHandler);
            keyHandler = null;
        }
    }

    function applyHanText(area, task) {
        if (window.HanText && area) window.HanText.apply(area, task?.hsk_level);
    }

    // Mirror of the lesson trainer's answer normalization so matches agree with the server.
    const ANSWER_PUNCT_MAP = {
        '、': ',', '。': '.', '｡': '.', '【': '[', '】': ']', '《': '<', '》': '>',
        '「': '"', '」': '"', '『': '"', '』': '"', '“': '"', '”': '"', '‘': "'", '’': "'",
        '～': '~', '—': '-', '–': '-', '‧': '', '·': '', '・': ''
    };

    function normalizeAnswer(value) {
        if (value == null) return '';
        return String(value)
            .normalize('NFKC')
            .replace(/[、。｡【】《》「」『』“”‘’～—–‧·・]/g, ch => ANSWER_PUNCT_MAP[ch] ?? ch)
            .replace(/[\s​‌‍﻿]/g, '');
    }

    function answersMatch(a, b) {
        return normalizeAnswer(a) === normalizeAnswer(b);
    }

    function reorderMatches(userTokens, correctTokens) {
        if (!Array.isArray(userTokens) || !Array.isArray(correctTokens)) return false;
        if (userTokens.length !== correctTokens.length) return false;
        return correctTokens.every((token, i) => normalizeAnswer(userTokens[i]) === normalizeAnswer(token));
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    window.LessonTrainer = { start };
})();
