/* ============================================================
   PRACTICE MODULE – Frontend Logic  (v2)
   All type renderers, group navigation, audio, scoring.
   ============================================================ */

const NUM = window.practiceNumber;

let groups = [];
let currentGroupIndex = 0;
let score = 0;
let totalQuestions = 0;
let sessionAnswers = [];
let sessionCounter = 1;
let practiceSessionId = null;
let groupStartTime = 0;

// Per-group persistence for navigation (Prev/Next). Each entry:
// { card, userAnswers, chipOrder, blankState, activeBlank, checked, startTime }
// The rendered DOM node is cached so entered answers survive navigating away and back.
let groupSaved = [];

// Per-group state (reset each renderGroup)
let userAnswers = {};      // { blockId: selectedKey }
let chipOrder   = {};      // { blockId: [key, key, ...] } for type 4
let blankState  = {};      // { blockId: { blankIdx: optKey } }  for type 6
let activeBlank = {};      // { blockId: blankIdx|null }         for type 6

const audioEl = document.getElementById('audio-player');
let activeAudioControl = null;
let activeAudioSrc = '';

// ── Helpers ─────────────────────────────────────────────────

function stopAudio() {
    audioEl.pause();
    audioEl.removeAttribute('src');
    audioEl.onended = null;
    audioEl.onerror = null;
    audioEl.onpause = null;
    audioEl.onloadedmetadata = null;
    audioEl.ontimeupdate = null;
    activeAudioControl = null;
    activeAudioSrc = '';
    resetAllAudioControls();
}

function formatAudioTime(sec) {
    if (!Number.isFinite(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
}

function getScrubberEls(control) {
    return {
        range: control?.querySelector('.p-audio-progress'),
        elapsed: control?.querySelector('.p-audio-elapsed'),
        duration: control?.querySelector('.p-audio-duration'),
    };
}

function syncScrubberMeta(control) {
    const { range, duration } = getScrubberEls(control);
    const dur = Number.isFinite(audioEl.duration) ? audioEl.duration : 0;
    if (range) range.max = String(Math.max(1, Math.floor(dur)));
    if (duration) duration.textContent = formatAudioTime(dur);
}

function syncScrubberProgress(control) {
    if (!control || control.classList.contains('scrubbing')) return;
    const { range, elapsed } = getScrubberEls(control);
    const cur = Number.isFinite(audioEl.currentTime) ? audioEl.currentTime : 0;
    if (range) range.value = String(Math.floor(cur));
    if (elapsed) elapsed.textContent = formatAudioTime(cur);
}

function resetScrubber(control) {
    const { range, elapsed } = getScrubberEls(control);
    if (range) range.value = '0';
    if (elapsed) elapsed.textContent = formatAudioTime(0);
}

function audioSrc(key, level, category) {
    const cat = category || window.practiceCategory || 'practice';
    const lvl = level || NUM || 1;
    return `https://storage.googleapis.com/chinese-learning-audio-assets/question_bank/${cat}/${cat}-${lvl}/${key}.mp3`;
}

function resetAudioControl(control) {
    if (!control) return;
    const btn = control.querySelector('.p-audio-play-btn');
    const icon = btn?.querySelector('.fa-solid');
    control.classList.remove('playing');
    if (icon) {
        icon.classList.add('fa-play');
        icon.classList.remove('fa-stop');
    }
    if (btn) {
        btn.title = t('lesson.play_audio');
        btn.setAttribute('aria-label', t('lesson.play_audio'));
    }
    resetScrubber(control);
}

function setAudioControlPlaying(control) {
    const btn = control?.querySelector('.p-audio-play-btn');
    const icon = btn?.querySelector('.fa-solid');
    if (!control || !btn || !icon) return;
    control.classList.add('playing');
    icon.classList.remove('fa-play');
    icon.classList.add('fa-stop');
    btn.title = t('practice.stop_audio');
    btn.setAttribute('aria-label', t('practice.stop_audio'));
}

function resetAllAudioControls() {
    document.querySelectorAll('.p-audio-control').forEach(resetAudioControl);
}

function loadAudioForControl(control, src) {
    if (activeAudioControl && activeAudioControl !== control) {
        resetAudioControl(activeAudioControl);
    }
    activeAudioControl = control;
    activeAudioSrc = src;
    if (audioEl.src !== src) {
        audioEl.src = src;
    }
    audioEl.onended = () => {
        resetAudioControl(control);
        activeAudioControl = null;
        activeAudioSrc = '';
    };
    audioEl.onerror = audioEl.onended;
    audioEl.onpause = () => {
        if (activeAudioControl === control && audioEl.currentTime === 0) {
            resetAudioControl(control);
        }
    };
    audioEl.onloadedmetadata = () => syncScrubberMeta(control);
    audioEl.ontimeupdate = () => syncScrubberProgress(control);
    if (Number.isFinite(audioEl.duration) && audioEl.duration > 0) {
        syncScrubberMeta(control);
        syncScrubberProgress(control);
    }
}

function playAudio(key, control, level, category) {
    const src = audioSrc(key, level, category);
    const isSamePausedAudio = activeAudioControl === control && audioEl.paused && activeAudioSrc === src;
    // Toggling the button while it plays acts as "stop": halt and rewind to the start.
    if (activeAudioControl === control && !audioEl.paused) {
        audioEl.pause();
        audioEl.currentTime = 0;
        resetAudioControl(control);
        return;
    }

    if (activeAudioControl && activeAudioControl !== control) {
        audioEl.pause();
    }

    loadAudioForControl(control, src);
    if (!isSamePausedAudio) {
        audioEl.currentTime = 0;
    }
    audioEl.play().then(() => {
        setAudioControlPlaying(control);
    }).catch(() => {
        resetAudioControl(control);
    });
}

function seekAudio(key, control, level, category, deltaSeconds) {
    const src = audioSrc(key, level, category);
    if (activeAudioSrc !== src || activeAudioControl !== control) {
        if (activeAudioControl && activeAudioControl !== control) {
            audioEl.pause();
            resetAudioControl(activeAudioControl);
        }
        loadAudioForControl(control, src);
    }

    const current = Number.isFinite(audioEl.currentTime) ? audioEl.currentTime : 0;
    const duration = Number.isFinite(audioEl.duration) ? audioEl.duration : null;
    const next = current + deltaSeconds;
    audioEl.currentTime = duration === null
        ? Math.max(0, next)
        : Math.max(0, Math.min(duration, next));
    syncScrubberProgress(control);
}

// Absolute seek from the scrubber (seconds is the target position).
function seekAudioTo(key, control, level, category, seconds) {
    const src = audioSrc(key, level, category);
    if (activeAudioSrc !== src || activeAudioControl !== control) {
        if (activeAudioControl && activeAudioControl !== control) {
            audioEl.pause();
            resetAudioControl(activeAudioControl);
        }
        loadAudioForControl(control, src);
    }
    const duration = Number.isFinite(audioEl.duration) ? audioEl.duration : null;
    audioEl.currentTime = duration === null
        ? Math.max(0, seconds)
        : Math.max(0, Math.min(duration, seconds));
    syncScrubberProgress(control);
}

function showScreen(id) {
    document.querySelectorAll('.p-screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

function imageUrl(level, filename, category) {
    const cat = category || 'practice';
    let file = filename.trim();
    if (!file.toLowerCase().match(/\.(jpg|jpeg|png|gif|webp)$/)) {
        file += '.jpg';
    }
    return `https://storage.googleapis.com/chinese-learning-audio-assets/images/${cat}/${level}/${file}`;
}

// Detect any kind of blank: （ ）, （）, ( ), ()
// Also handles numbered blanks like （24）__________
function hasBlank(content) {
    if (!content) return false;
    return /[（(][\s\d]*[）)][\s_]*_*|[（(]\s*[）)]/.test(content);
}

// Replace ALL blanks in content with interactive/static spans
function replaceAllBlanks(content, fills, interactive, blockId) {
    let idx = 0;
    // Match: （N）___... style OR （ ）/ () style
    return content.replace(/[（(][\s\d]*[）)][\s_]*_+|[（(]\s*[）)]/g, () => {
        const i = idx++;
        const val = fills ? fills[i] : null;
        if (interactive) {
            const css = val ? 'blank-gap blank-filled' : 'blank-gap blank-empty';
            return `<span class="${css}" data-blank="${i}" data-block="${blockId}" onclick="clickBlankTarget(this)">${val || '　　'}</span>`;
        }
        return val
            ? `<span class="blank-gap filled">${val}</span>`
            : `<span class="blank-gap">　　</span>`;
    });
}

function isImageFilename(val) {
    if (typeof val !== 'string') return false;
    const v = val.trim();
    if (/\.(jpg|jpeg|png|gif|webp)$/i.test(v)) return true;
    if (/^\d+\.\d+[a-zA-Z]*$/.test(v)) return true;
    return false;
}

function makeAudioBtn(key, label, level, category) {
    const control = document.createElement('div');
    control.className = 'p-audio-control';

    const backBtn = document.createElement('button');
    backBtn.type = 'button';
    backBtn.className = 'p-audio-seek-btn';
    backBtn.title = t('practice.back_5_seconds');
    backBtn.setAttribute('aria-label', t('practice.back_5_seconds'));
    backBtn.innerHTML = '<i class="fa-solid fa-backward" aria-hidden="true"></i>';
    backBtn.onclick = () => seekAudio(key, control, level, category, -5);

    const playBtn = document.createElement('button');
    playBtn.type = 'button';
    playBtn.className = 'p-audio-btn p-audio-play-btn';
    playBtn.title = t('lesson.play_audio');
    const labelText = label || t('lesson.audio_fallback');
    playBtn.setAttribute('aria-label', t('practice.play_label', { label: labelText }));
    playBtn.innerHTML = '<i class="fa-solid fa-play" aria-hidden="true"></i>';
    playBtn.onclick = () => playAudio(key, control, level, category);

    const forwardBtn = document.createElement('button');
    forwardBtn.type = 'button';
    forwardBtn.className = 'p-audio-seek-btn';
    forwardBtn.title = t('practice.forward_5_seconds');
    forwardBtn.setAttribute('aria-label', t('practice.forward_5_seconds'));
    forwardBtn.innerHTML = '<i class="fa-solid fa-forward" aria-hidden="true"></i>';
    forwardBtn.onclick = () => seekAudio(key, control, level, category, 5);

    // Scrubber: elapsed time — draggable progress — total duration
    const scrubber = document.createElement('div');
    scrubber.className = 'p-audio-scrubber';

    const elapsed = document.createElement('span');
    elapsed.className = 'p-audio-time p-audio-elapsed';
    elapsed.textContent = '0:00';

    const range = document.createElement('input');
    range.type = 'range';
    range.className = 'p-audio-progress';
    range.min = '0';
    range.max = '1';
    range.step = '1';
    range.value = '0';
    range.setAttribute('aria-label', t('practice.seek_slider'));
    range.addEventListener('input', () => {
        control.classList.add('scrubbing');
        elapsed.textContent = formatAudioTime(Number(range.value));
    });
    range.addEventListener('change', () => {
        seekAudioTo(key, control, level, category, Number(range.value));
        control.classList.remove('scrubbing');
    });

    const duration = document.createElement('span');
    duration.className = 'p-audio-time p-audio-duration';
    duration.textContent = '0:00';

    scrubber.appendChild(elapsed);
    scrubber.appendChild(range);
    scrubber.appendChild(duration);

    control.appendChild(backBtn);
    control.appendChild(playBtn);
    control.appendChild(forwardBtn);
    control.appendChild(scrubber);
    return control;
}

// ── Init ────────────────────────────────────────────────────

async function init() {
    showScreen('screen-loading');

    // Context-aware Back button — read and clear referrer set by previous page
    const referrer = sessionStorage.getItem('practice_referrer');
    sessionStorage.removeItem('practice_referrer');
    const backBtn = document.querySelector('.p-back-btn');
    if (backBtn) {
        if (referrer === 'recommend') {
            backBtn.href = '/recommend';
            backBtn.title = t('practice_select.back_to_recommendations');
        } else if (referrer && referrer.startsWith('exam-')) {
            const lvl = referrer.split('-')[1];
            backBtn.href = `/practice/${lvl}?category=exam`;
            backBtn.title = t('practice.back_to_hsk_exam', { level: lvl });
        } else if (referrer && referrer.startsWith('practice-')) {
            const lvl = referrer.split('-')[1];
            backBtn.href = `/practice/${lvl}`;
            backBtn.title = t('practice.back_to_hsk_lessons', { level: lvl });
        } else {
            backBtn.href = '/practice';
            backBtn.title = t('practice.back_to_practice');
        }

        const resultBackBtn = document.getElementById('result-back-btn');
        if (resultBackBtn) {
            resultBackBtn.href = backBtn.href;
            resultBackBtn.textContent = '← ' + backBtn.title;
        }
    }

    try {
        let data;
        const progressFilter = window.progressFilter || '';

        if (window.multiMode) {
            // Multi-select mode
            const rawQueue = sessionStorage.getItem('multi_practice_queue');
            if (!rawQueue) {
                alert(t('practice.no_items_selected'));
                window.location.href = '/recommend';
                return;
            }
            const items = JSON.parse(rawQueue);
            const res = await fetch('/api/practice/multi', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items })
            });
            if (!res.ok) throw new Error();
            data = await res.json();
        } else if (progressFilter) {
            // Deep-link mode: fetch only this specific progress group
            const catParam = window.practiceCategory ? `?category=${window.practiceCategory}` : '';
            const res = await fetch(`/api/practice/${NUM}/${window.lessonId}/${encodeURIComponent(progressFilter)}${catParam}`);
            if (!res.ok) throw new Error();
            const groupData = await res.json();
            // Wrap single progress group into the expected {groups:[]} shape
            data = {
                groups: [{
                    progress: groupData.progress,
                    questions: groupData.questions,
                }]
            };
        } else {
            // Normal mode: fetch the full lesson
            const catParam = window.practiceCategory ? `?category=${encodeURIComponent(window.practiceCategory)}` : '';
            const res = await fetch(`/api/practice/${NUM}/${window.lessonId}${catParam}`);
            if (!res.ok) throw new Error();
            data = await res.json();
        }

        groups = data.groups;
        totalQuestions = groups.reduce((s, g) => s + g.questions.length, 0);
        currentGroupIndex = 0;
        score = 0;
        sessionAnswers = [];
        groupSaved = groups.map(() => null);
        practiceSessionId = sessionCounter++;
        renderGroup();
        showScreen('screen-practice');
    } catch (e) {
        alert(t('practice.load_failed'));
    }
}

// ── Group Rendering ──────────────────────────────────────────

function renderGroup() {
    stopAudio();
    const idx = currentGroupIndex;
    const group = groups[idx];

    // Progress reflects how many groups have been checked, not raw position.
    const checkedCount = groups.filter((_, i) => groupSaved[i]?.checked).length;
    const pct = Math.round((checkedCount / groups.length) * 100);
    document.getElementById('progress-fill').style.width = pct + '%';
    document.getElementById('group-counter').textContent = `${idx + 1} / ${groups.length}`;
    document.getElementById('score-val').textContent = score;

    // Skill tag
    const skill = group.questions[0]?.skill || 'listening';
    const skillTag = document.getElementById('skill-tag');
    skillTag.innerHTML = skill === 'listening'
        ? `<i class="fa-solid fa-headphones-simple" aria-hidden="true"></i><span>${t('recommend.listening')}</span>`
        : `<i class="fa-solid fa-book-open" aria-hidden="true"></i><span>${t('recommend.reading')}</span>`;
    skillTag.className = `p-skill-tag ${skill}`;

    const host = document.getElementById('question-card');
    host.innerHTML = '';

    let entry = groupSaved[idx];
    if (entry && entry.card) {
        // Reuse the cached DOM so previously entered answers (and any reveal) persist.
        userAnswers = entry.userAnswers;
        chipOrder   = entry.chipOrder;
        blankState  = entry.blankState;
        activeBlank = entry.activeBlank;
        groupStartTime = entry.startTime;
        host.appendChild(entry.card);
    } else {
        userAnswers = {};
        chipOrder   = {};
        blankState  = {};
        activeBlank = {};
        const card = document.createElement('div');
        card.className = 'p-group-card';
        buildGroupContent(card, group);
        applyQuestionNumbers(card, group);
        entry = {
            card,
            userAnswers, chipOrder, blankState, activeBlank,
            checked: false,
            startTime: Date.now(),
        };
        groupSaved[idx] = entry;
        groupStartTime = entry.startTime;
        host.appendChild(card);
    }

    updateNav();
    applyPracticeHanText(group);
}

// Renders the question content for a group into `card`.
function buildGroupContent(card, group) {
    const skill = group.questions[0]?.skill || 'listening';
    const type  = group.questions[0]?.type;
    const isListening = skill === 'listening';

    if (type === 2) {
        renderType2Group(card, group);
    } else if (type === 5 && isListening && group.questions.length > 1) {
        renderType5ListeningGroup(card, group);
    } else if (type === 5 && !isListening && group.questions.length > 1) {
        const q0 = group.questions[0];
        const optVals = Object.values(q0.options || {});
        const isImgGroup = optVals.every(v => isImageFilename(String(v)));
        if (!isImgGroup) {
            renderType5ReadingMatchGroup(card, group);
        } else {
            renderType5ReadingImageGroup(card, group);
        }
    } else if (type === 6) {
        renderType6Group(card, group);
    } else {
        if (group.questions.length > 1) {
            const hdr = document.createElement('div');
            hdr.className = 'p-group-header';
            hdr.textContent = t('practice.questions_group', { progress: group.progress });
            card.appendChild(hdr);
        }
        group.questions.forEach((q, idx) => card.appendChild(renderQuestion(q, idx)));
    }
}

// Number each sub-question when a group holds more than one.
// Group layouts that already number their rows (type 5 audio/sentence rows) are skipped.
function applyQuestionNumbers(card, group) {
    if (group.questions.length <= 1) return;
    const blocks = card.querySelectorAll('.p-question-block');
    blocks.forEach((block, i) => {
        if (block.querySelector('.p-qnum')) return;
        const badge = document.createElement('span');
        badge.className = 'p-qnum';
        badge.textContent = t('practice.question_number', { n: i + 1 });
        block.insertBefore(badge, block.firstChild);
    });
}

// ── Navigation state helpers ─────────────────────────────────────
function firstUncheckedBefore(idx) {
    for (let i = idx - 1; i >= 0; i--) if (!groupSaved[i]?.checked) return i;
    return -1;
}
function firstUncheckedAfter(idx) {
    for (let i = idx + 1; i < groups.length; i++) if (!groupSaved[i]?.checked) return i;
    return -1;
}
function allGroupsChecked() {
    return groups.every((_, i) => groupSaved[i]?.checked);
}
function setNavBtn(id, visible) {
    const el = document.getElementById(id);
    if (el) el.style.display = visible ? '' : 'none';
}

function updateNav() {
    const idx = currentGroupIndex;
    const checked = !!groupSaved[idx]?.checked;
    const everyChecked = allGroupsChecked();

    setNavBtn('btn-prev', firstUncheckedBefore(idx) !== -1);
    setNavBtn('btn-skip', !checked);
    setNavBtn('btn-check', !checked);
    setNavBtn('btn-finish', everyChecked);
    setNavBtn('btn-next', !everyChecked && firstUncheckedAfter(idx) !== -1);

    const checkBtn = document.getElementById('btn-check');
    if (checkBtn && !checked) checkBtn.textContent = t('practice.check');
    if (!checked) updateCheckButton();

    const checkedCount = groups.filter((_, i) => groupSaved[i]?.checked).length;
    document.getElementById('progress-fill').style.width =
        Math.round((checkedCount / groups.length) * 100) + '%';
}

function goPrevGroup() {
    const i = firstUncheckedBefore(currentGroupIndex);
    if (i !== -1) { currentGroupIndex = i; renderGroup(); }
}
function goNextGroup() {
    const i = firstUncheckedAfter(currentGroupIndex);
    if (i !== -1) { currentGroupIndex = i; renderGroup(); }
}

// Reveal-then-skip: discard partial answers so the group is marked incorrect,
// reveal the correct answers, lock it, then let the user move on.
function skipGroup() {
    const entry = groupSaved[currentGroupIndex];
    if (!entry || entry.checked) return;
    userAnswers = {};
    entry.userAnswers = userAnswers;
    checkAnswers();
}

function applyPracticeHanText(group = groups[currentGroupIndex]) {
    const card = document.getElementById('question-card');
    const level = group?.questions?.[0]?.level || NUM;
    if (window.HanText && card) {
        window.HanText.apply(card, level);
    }
}

// ── TYPE 2: Shared paragraph (listening=audio only) + sub-questions ─────

function renderType2Group(card, group) {
    const isListening = group.questions[0]?.skill === 'listening';
    const passage = group.questions.find(q => q.content);

    if (isListening) {
        // Only show audio for the passage – no text
        if (passage?.audio_key?.length) {
            card.appendChild(makeAudioBtn(passage.audio_key[0], t('practice.play_passage'), passage.level, passage.category));
        }
    } else {
        // Reading: show content
        if (passage?.content) {
            const el = document.createElement('div');
            el.className = 'p-paragraph';
            el.textContent = passage.content;
            card.appendChild(el);
        }
    }

    // Sub-questions
    group.questions.forEach((q, idx) => {
        const block = document.createElement('div');
        const blockId = `q-${idx}`;
        block.className = 'p-question-block';
        block.id = blockId;

        if (isListening) {
            // Don't show question text; only show per-question audio for follow-up
            const keyIdx = idx === 0 && q.audio_key?.length === 2 ? 1 : 0;
            if (q.audio_key?.length) {
                block.appendChild(makeAudioBtn(q.audio_key[keyIdx], t('recommend.question_single', { n: idx + 1 }), q.level, q.category));
            }
        } else {
            // Reading: show question text
            if (q.question) {
                const qEl = document.createElement('div');
                qEl.className = 'p-question-text';
                qEl.textContent = q.question;
                block.appendChild(qEl);
            }
        }

        block.appendChild(makeMCOptions(q.options, blockId));

        const fb = makeFeedback(blockId);
        block.appendChild(fb);
        card.appendChild(block);
    });
}

// ── TYPE 5 LISTENING GROUP: shared images + per-question audio rows ─────

function renderType5ListeningGroup(card, group) {
    const q0 = group.questions[0];
    const opts = q0.options;
    const allImgOpts = Object.values(opts).every(v => isImageFilename(String(v)));

    if (allImgOpts) {
        // Image row at top (shared)
        const imgRow = document.createElement('div');
        imgRow.className = 't5l-images-row';
        Object.entries(opts).forEach(([key, filename]) => {
            const col = document.createElement('div');
            col.className = 't5l-img-col';
            const img = document.createElement('img');
            img.src = imageUrl(q0.level, filename, q0.category);
            img.alt = key;
            img.className = 't5l-img';
            const lbl = document.createElement('div');
            lbl.className = 't5l-img-label';
            lbl.textContent = key;
            col.appendChild(img);
            col.appendChild(lbl);
            imgRow.appendChild(col);
        });
        card.appendChild(imgRow);

        const instr = document.createElement('p');
        instr.className = 't5l-instruction';
        instr.textContent = t('practice.choose_image_for_audio');
        card.appendChild(instr);
    }

    // Track which keys are selected across all rows
    // Each question gets its own audio row with a key picker
    const optKeys = Object.keys(opts);
    const rowsContainer = document.createElement('div');
    rowsContainer.className = 't5l-rows';
    rowsContainer.id = 't5l-rows-container';

    group.questions.forEach((q, idx) => {
        const blockId = `q-${idx}`;
        const row = document.createElement('div');
        row.className = 't5l-audio-row';
        row.id = `row-${blockId}`;

        // Audio button
        const audioPart = document.createElement('div');
        audioPart.className = 't5l-audio-part';
        const rowNumber = document.createElement('span');
        rowNumber.className = 't5l-row-number';
        rowNumber.textContent = idx + 1;
        audioPart.appendChild(rowNumber);
        if (q.audio_key?.length) {
            const btn = makeAudioBtn(q.audio_key[0], t('practice.audio_numbered', { n: idx + 1 }), q.level, q.category);
            audioPart.appendChild(btn);
        }

        // Option selector – small letter buttons
        const optPart = document.createElement('div');
        optPart.className = 't5l-opt-part';

        optKeys.forEach(key => {
            const btn = document.createElement('button');
            btn.className = 't5l-key-btn';
            btn.dataset.key = key;
            btn.dataset.block = blockId;
            btn.textContent = key;
            btn.onclick = () => selectT5LKey(blockId, key, rowsContainer, group);
            optPart.appendChild(btn);
        });

        row.appendChild(audioPart);
        row.appendChild(optPart);
        rowsContainer.appendChild(row);
    });

    card.appendChild(rowsContainer);

    // Single shared feedback at bottom
    card.appendChild(makeFeedback('t5l-group'));
}

// ── TYPE 5 READING MATCH GROUP: text options once + sentence rows ───────

function renderType5ReadingMatchGroup(card, group) {
    const q0 = group.questions[0];
    const opts = q0.options;
    const optKeys = Object.keys(opts);

    // 1. Text options list at top
    const optBox = document.createElement('div');
    optBox.className = 't5r-options-box';

    Object.entries(opts).forEach(([key, text]) => {
        const row = document.createElement('div');
        row.className = 't5r-opt-row';
        const kSpan = document.createElement('span');
        kSpan.className = 't5r-opt-key';
        kSpan.textContent = key + '.';
        const tSpan = document.createElement('span');
        tSpan.className = 't5r-opt-text';
        tSpan.textContent = String(text);
        row.appendChild(kSpan);
        row.appendChild(tSpan);
        optBox.appendChild(row);
    });
    card.appendChild(optBox);

    // 2. Instruction + shared key buttons (shown once)
    const instr = document.createElement('p');
    instr.className = 't5l-instruction';
    instr.textContent = t('practice.choose_answer_per_sentence');
    card.appendChild(instr);

    // 3. Sentence rows – each question is one row
    const rowsContainer = document.createElement('div');
    rowsContainer.className = 't5l-rows';
    rowsContainer.id = 't5r-rows-container';

    group.questions.forEach((q, idx) => {
        const blockId = `q-${idx}`;
        const row = document.createElement('div');
        row.className = 't5l-audio-row';
        row.id = `row-${blockId}`;

        // Sentence text on left
        const sentPart = document.createElement('div');
        sentPart.className = 't5r-sentence-part';
        const sentEl = document.createElement('span');
        sentEl.className = 't5r-sentence';
        sentEl.innerHTML = replaceAllBlanks(q.content || '', null, false, blockId);
        sentPart.appendChild(sentEl);

        // Letter selector on right (circular buttons)
        const optPart = document.createElement('div');
        optPart.className = 't5l-opt-part';
        optKeys.forEach(key => {
            const btn = document.createElement('button');
            btn.className = 't5l-key-btn';
            btn.dataset.key = key;
            btn.dataset.block = blockId;
            btn.textContent = key;
            btn.onclick = () => selectT5LKey(blockId, key, rowsContainer, group);
            optPart.appendChild(btn);
        });

        row.appendChild(sentPart);
        row.appendChild(optPart);
        rowsContainer.appendChild(row);
    });

    card.appendChild(rowsContainer);
    card.appendChild(makeFeedback('t5r-group'));
}

// Type 5 reading image group: shared images once + per-sentence key buttons.
function renderType5ReadingImageGroup(card, group) {
    const q0 = group.questions[0];
    const opts = q0.options || {};
    const optKeys = Object.keys(opts);

    const imgRow = document.createElement('div');
    imgRow.className = 't5l-images-row t5ri-images-row';
    Object.entries(opts).forEach(([key, filename]) => {
        const col = document.createElement('div');
        col.className = 't5l-img-col t5ri-img-col';

        const img = document.createElement('img');
        img.src = imageUrl(q0.level, filename, q0.category);
        img.alt = key;
        img.className = 't5l-img t5ri-img';

        const lbl = document.createElement('div');
        lbl.className = 't5l-img-label t5ri-img-label';
        lbl.textContent = key;

        col.appendChild(img);
        col.appendChild(lbl);
        imgRow.appendChild(col);
    });
    card.appendChild(imgRow);

    const instr = document.createElement('p');
    instr.className = 't5l-instruction';
    instr.textContent = t('practice.choose_image_per_sentence');
    card.appendChild(instr);

    const rowsContainer = document.createElement('div');
    rowsContainer.className = 't5l-rows';
    rowsContainer.id = 't5ri-rows-container';

    group.questions.forEach((q, idx) => {
        const blockId = `q-${idx}`;
        const row = document.createElement('div');
        row.className = 't5l-audio-row t5ri-sentence-row';
        row.id = `row-${blockId}`;

        const sentPart = document.createElement('div');
        sentPart.className = 't5r-sentence-part';
        const sentEl = document.createElement('span');
        sentEl.className = 't5r-sentence';
        sentEl.textContent = q.content || '';
        sentPart.appendChild(sentEl);

        const optPart = document.createElement('div');
        optPart.className = 't5l-opt-part';
        optKeys.forEach(key => {
            const btn = document.createElement('button');
            btn.className = 't5l-key-btn';
            btn.dataset.key = key;
            btn.dataset.block = blockId;
            btn.textContent = key;
            btn.onclick = () => selectT5LKey(blockId, key, rowsContainer, group);
            optPart.appendChild(btn);
        });

        row.appendChild(sentPart);
        row.appendChild(optPart);
        rowsContainer.appendChild(row);
    });

    card.appendChild(rowsContainer);
    card.appendChild(makeFeedback('t5ri-group'));
}

function selectT5LKey(blockId, key, container, group) {
    // Allow only one key per row; a key can only be used by one row
    const oldKey = userAnswers[blockId];

    // Deselect previous in this row
    container.querySelectorAll(`[data-block="${blockId}"].t5l-key-btn`).forEach(b => b.classList.remove('selected'));

    // Toggle: if same key clicked, deselect
    if (oldKey === key) {
        delete userAnswers[blockId];
    } else {
        userAnswers[blockId] = key;
        container.querySelector(`[data-block="${blockId}"][data-key="${key}"]`)?.classList.add('selected');
    }

    // Refresh disabled state across all rows based on usage
    const usedKeys = new Set(Object.values(userAnswers));
    container.querySelectorAll('.t5l-key-btn').forEach(btn => {
        const bKey   = btn.dataset.key;
        const bBlock = btn.dataset.block;
        const isSelected = userAnswers[bBlock] === bKey;
        const usedElsewhere = usedKeys.has(bKey) && !isSelected;
        btn.disabled = usedElsewhere;
        btn.classList.toggle('used-elsewhere', usedElsewhere);
    });

    updateCheckButton();
}

// ── TYPE 6: Numbered blanks + shared options ─────────────────

function renderType6Group(card, group) {
    const isListening = group.questions[0]?.skill === 'listening';
    const passage = group.questions.find(q => q.content);

    if (isListening && passage?.audio_key?.length) {
        card.appendChild(makeAudioBtn(passage.audio_key[0], t('practice.play_passage'), passage.level, passage.category));
    }

    // Collect all option keys – they're shared across all blanks in the group
    const sharedOpts = group.questions.reduce((acc, q) => {
        Object.assign(acc, q.options);
        return acc;
    }, {});

    // Each question in group gets a paragraph block with an interactive blank
    group.questions.forEach((q, idx) => {
        const blockId = `q-${idx}`;
        blankState[blockId]  = {};
        activeBlank[blockId] = null;

        const block = document.createElement('div');
        block.className = 'p-question-block';
        block.id = blockId;

        if (!isListening && q.content) {
            const paraEl = document.createElement('div');
            paraEl.className = 'p-paragraph';
            paraEl.id = `para-${blockId}`;
            paraEl.innerHTML = replaceAllBlanks(q.content, null, true, blockId);
            block.appendChild(paraEl);
        }

        block.appendChild(makeFeedback(blockId));
        card.appendChild(block);
    });

    // Shared options shown ONCE at the bottom
    const sharedOptsEl = document.createElement('div');
    sharedOptsEl.className = 't6-shared-options';
    sharedOptsEl.id = 't6-options';

    const label = document.createElement('div');
    label.className = 'p-group-header';
    label.textContent = t('practice.choose_from_options');
    sharedOptsEl.appendChild(label);

    const optsWrap = document.createElement('div');
    optsWrap.className = 'mc-options';
    optsWrap.id = 't6-opts-wrap';

    Object.entries(sharedOpts).forEach(([key, text]) => {
        const btn = document.createElement('button');
        btn.className = 'mc-option';
        btn.id = `t6opt-${key}`;
        btn.dataset.key = key;

        const keySpan = document.createElement('span');
        keySpan.className = 'opt-key';
        keySpan.textContent = key;

        const textSpan = document.createElement('span');
        textSpan.textContent = String(text);

        btn.appendChild(keySpan);
        btn.appendChild(textSpan);
        btn.onclick = () => assignT6Option(key);
        optsWrap.appendChild(btn);
    });

    sharedOptsEl.appendChild(optsWrap);
    card.appendChild(sharedOptsEl);
}

function clickBlankTarget(el) {
    const blockId   = el.dataset.block;
    const blankIdx  = parseInt(el.dataset.blank);

    // Clear all blank highlights
    document.querySelectorAll('.blank-gap').forEach(b => b.classList.remove('blank-active'));
    el.classList.add('blank-active');
    activeBlank[blockId] = blankIdx;
}

function assignT6Option(key) {
    // Find which blank+block is currently active
    let targetBlock = null;
    let targetBlankIdx = null;
    for (const blockId of Object.keys(blankState)) {
        if (activeBlank[blockId] !== null && activeBlank[blockId] !== undefined) {
            targetBlock = blockId;
            targetBlankIdx = activeBlank[blockId];
            break;
        }
    }
    if (targetBlock === null) return; // no blank selected

    const q = groups[currentGroupIndex].questions.find((_, i) => `q-${i}` === targetBlock);
    if (!q) return;

    // Return old option to pool if this blank was filled
    const oldKey = blankState[targetBlock][targetBlankIdx];
    if (oldKey) {
        const oldBtn = document.getElementById(`t6opt-${oldKey}`);
        if (oldBtn) {
            oldBtn.disabled = false;
            oldBtn.classList.remove('selected');
        }
    }

    // Assign
    blankState[targetBlock][targetBlankIdx] = key;
    userAnswers[targetBlock] = Object.values(blankState[targetBlock]).join('');
    activeBlank[targetBlock] = null;

    // Disable this option button
    const optBtn = document.getElementById(`t6opt-${key}`);
    if (optBtn) {
        optBtn.disabled = true;
        optBtn.classList.add('selected');
    }

    // Clear blank highlight
    document.querySelectorAll('.blank-gap').forEach(b => b.classList.remove('blank-active'));

    // Re-render paragraph with fills
    const fills = Object.keys(blankState[targetBlock])
        .sort((a, b) => a - b)
        .map(i => blankState[targetBlock][i] || null);

    const paraEl = document.getElementById(`para-${targetBlock}`);
    if (paraEl) {
        paraEl.innerHTML = replaceAllBlanks(q.content, fills, true, targetBlock);
    }

    updateCheckButton();
}

// ── Individual Question Renderer ────────────────────────────

function renderQuestion(q, idx) {
    const block = document.createElement('div');
    const blockId = `q-${idx}`;
    block.className = 'p-question-block';
    block.id = blockId;

    const skill = q.skill || 'listening';
    const type  = q.type;
    const optEntries = Object.entries(q.options || {});
    const allImgOpts = optEntries.every(([, v]) => isImageFilename(String(v)));

    if (type === 1) {
        renderType1(block, q, blockId, skill);
    } else if (type === 3) {
        if (allImgOpts) {
            renderType5Images(block, q, blockId, skill);
        } else {
            renderType3(block, q, blockId, skill);
        }
    } else if (type === 4) {
        renderType4(block, q, blockId);
    } else if (type === 5) {
        if (allImgOpts) {
            renderType5Images(block, q, blockId, skill);
        } else if (hasBlank(q.content)) {
            renderType5Blank(block, q, blockId, skill);
        } else {
            renderType5Match(block, q, blockId, skill);
        }
    } else if (type === 6) {
        // Single type 6 question (standalone or in group)
        if (q.content) {
            blankState[blockId]  = {};
            activeBlank[blockId] = null;
            const paraEl = document.createElement('div');
            paraEl.className = 'p-paragraph';
            paraEl.id = `para-${blockId}`;
            paraEl.innerHTML = replaceAllBlanks(q.content, null, true, blockId);
            block.appendChild(paraEl);
        }
        block.appendChild(makeMCOptions(q.options, blockId));
    }

    block.appendChild(makeFeedback(blockId));
    return block;
}

// ── Type 1: True / False ─────────────────────────────────────

function renderType1(block, q, blockId, skill) {
    if (skill === 'listening' && q.audio_key?.length) {
        block.appendChild(makeAudioBtn(q.audio_key[0], null, q.level, q.category));
    }

    // Image
    const imgFile = q.image || (isImageFilename(q.question) ? q.question : null);
    if (imgFile) {
        const img = document.createElement('img');
        img.className = 'p-image';
        img.src = imageUrl(q.level, imgFile, q.category);
        block.appendChild(img);
    }

    // Question text (reading only, if it's a real question and not a filename)
    if (skill === 'reading' && q.question && !isImageFilename(q.question)) {
        const qEl = document.createElement('div');
        qEl.className = 'p-question-text p-centered';
        qEl.textContent = q.question;
        block.appendChild(qEl);
    }

    // True/False buttons
    const tfWrap = document.createElement('div');
    tfWrap.className = 'tf-buttons';

    Object.entries(q.options || {}).forEach(([key, val]) => {
        const btn = document.createElement('button');
        btn.className = 'tf-btn';
        btn.dataset.key = key;
        btn.dataset.block = blockId;
        const label = (val === true || val === 'True') ? t('practice.true_label') : (val === false || val === 'False') ? t('practice.false_label') : `${key}: ${val}`;
        btn.textContent = label;
        btn.onclick = () => {
            tfWrap.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            userAnswers[blockId] = key;
            updateCheckButton();
        };
        tfWrap.appendChild(btn);
    });
    block.appendChild(tfWrap);
}

// ── Type 3 ────────────────────────────────────────────────────

function renderType3(block, q, blockId, skill) {
    if (skill === 'listening') {
        if (q.audio_key?.length) block.appendChild(makeAudioBtn(q.audio_key[0], null, q.level, q.category));
    } else {
        // Reading: show content and question
        if (q.content) {
            const para = document.createElement('div');
            para.className = 'p-paragraph';
            para.textContent = q.content;
            block.appendChild(para);
        }
        if (q.question) {
            const qEl = document.createElement('div');
            qEl.className = 'p-question-text p-centered';
            qEl.textContent = q.question;
            block.appendChild(qEl);
        }
    }
    block.appendChild(makeMCOptions(q.options, blockId));
}

// ── Type 4: Sentence Reorder ──────────────────────────────────

function renderType4(block, q, blockId) {
    chipOrder[blockId] = [];
    const opts = q.options;

    const area = document.createElement('div');
    area.className = 'reorder-area';

    const ansLabel = document.createElement('div');
    ansLabel.className = 'reorder-label';
    ansLabel.textContent = t('practice.your_order');
    area.appendChild(ansLabel);

    const ansZone = document.createElement('div');
    ansZone.className = 'chip-answer';
    ansZone.id = `ans-zone-${blockId}`;
    area.appendChild(ansZone);

    const poolLabel = document.createElement('div');
    poolLabel.className = 'reorder-label';
    poolLabel.textContent = t('practice.sentences_click_add');
    area.appendChild(poolLabel);

    const poolZone = document.createElement('div');
    poolZone.className = 'chip-pool';
    poolZone.id = `pool-zone-${blockId}`;

    // Shuffle but keep original key labels visible
    const shuffledKeys = Object.keys(opts).sort(() => Math.random() - 0.5);
    shuffledKeys.forEach(key => {
        const chip = document.createElement('div');
        chip.className = 'chip';
        chip.dataset.key = key;
        chip.innerHTML = `<span class="chip-key">${key}</span> ${opts[key]}`;
        chip.onclick = () => toggleChip(chip, key, blockId, poolZone, ansZone);
        poolZone.appendChild(chip);
    });
    area.appendChild(poolZone);
    block.appendChild(area);
}

function toggleChip(chip, key, blockId, poolZone, ansZone) {
    if (chip.classList.contains('in-answer')) {
        chip.classList.remove('in-answer');
        chipOrder[blockId] = chipOrder[blockId].filter(k => k !== key);
        poolZone.appendChild(chip);
    } else {
        chip.classList.add('in-answer');
        chipOrder[blockId].push(key);
        ansZone.appendChild(chip);
    }
    userAnswers[blockId] = chipOrder[blockId].join('');
    updateCheckButton();
}

// ── Type 5 (image options) ────────────────────────────────────

function renderType5Images(block, q, blockId, skill) {
    if (skill === 'listening' && q.audio_key?.length) block.appendChild(makeAudioBtn(q.audio_key[0], null, q.level, q.category));
    if (skill === 'reading' && q.content) {
        const para = document.createElement('div');
        para.className = 'p-paragraph p-centered';
        para.textContent = q.content;
        block.appendChild(para);
    }
    const grid = document.createElement('div');
    grid.className = 'img-options-grid';
    if (skill === 'listening') grid.classList.add('listening-img-options-grid');
    Object.entries(q.options).forEach(([key, filename]) => {
        const cell = document.createElement('div');
        cell.className = 'img-option';
        cell.dataset.key = key;
        cell.dataset.block = blockId;
        const lbl = document.createElement('div');
        lbl.className = 'img-label';
        lbl.textContent = key;
        const img = document.createElement('img');
        img.src = imageUrl(q.level, filename, q.category);
        img.alt = key;
        cell.appendChild(img);
        cell.appendChild(lbl);
        cell.onclick = () => {
            grid.querySelectorAll('.img-option').forEach(c => c.classList.remove('selected'));
            cell.classList.add('selected');
            userAnswers[blockId] = key;
            updateCheckButton();
        };
        grid.appendChild(cell);
    });
    block.appendChild(grid);
}

// ── Type 5 (fill-in-blank) ────────────────────────────────────

function renderType5Blank(block, q, blockId, skill) {
    if (skill === 'listening' && q.audio_key?.length) block.appendChild(makeAudioBtn(q.audio_key[0], null, q.level, q.category));

    const contentEl = document.createElement('div');
    contentEl.className = 'p-paragraph p-centered';
    contentEl.id = `blank-para-${blockId}`;
    contentEl.innerHTML = replaceAllBlanks(q.content, null, false, blockId);
    block.appendChild(contentEl);

    const mc = makeMCOptions(q.options, blockId, (key, text) => {
        document.getElementById(`blank-para-${blockId}`).innerHTML =
            replaceAllBlanks(q.content, [text], false, blockId);
    });
    block.appendChild(mc);
}

// ── Type 5 (text match) ───────────────────────────────────────

function renderType5Match(block, q, blockId, skill) {
    if (skill === 'listening' && q.audio_key?.length) block.appendChild(makeAudioBtn(q.audio_key[0], null, q.level, q.category));
    if (q.content) {
        const para = document.createElement('div');
        para.className = 'p-paragraph p-centered';
        para.textContent = q.content;
        block.appendChild(para);
    }
    block.appendChild(makeMCOptions(q.options, blockId));
}

// ── Shared UI Builders ────────────────────────────────────────

function makeMCOptions(options, blockId, onSelect) {
    const wrap = document.createElement('div');
    wrap.className = 'mc-options';
    Object.entries(options || {}).forEach(([key, text]) => {
        const btn = document.createElement('button');
        btn.className = 'mc-option';
        btn.dataset.key = key;
        btn.dataset.block = blockId;
        const kSpan = document.createElement('span');
        kSpan.className = 'opt-key';
        kSpan.textContent = key;
        const tSpan = document.createElement('span');
        tSpan.textContent = String(text);
        btn.appendChild(kSpan);
        btn.appendChild(tSpan);
        btn.onclick = () => {
            wrap.querySelectorAll('.mc-option').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            userAnswers[blockId] = key;
            if (onSelect) onSelect(key, String(text));
            updateCheckButton();
        };
        wrap.appendChild(btn);
    });
    return wrap;
}

function makeFeedback(id) {
    const el = document.createElement('div');
    el.className = 'p-feedback';
    el.id = `feedback-${id}`;
    return el;
}

// ── Answer Checking ────────────────────────────────────────────

function updateCheckButton() {
    const group = groups[currentGroupIndex];
    const type  = group.questions[0]?.type;
    const isType6Group = type === 6 && group.questions.length > 1;

    const needed = group.questions.length;
    const answered = Object.keys(userAnswers).length;
    document.getElementById('btn-check').disabled = answered < needed;
}

function checkAnswers() {
    const entry = groupSaved[currentGroupIndex];
    if (entry && entry.checked) return;   // score each group only once
    const group = groups[currentGroupIndex];
    const type  = group.questions[0]?.type;
    let groupCorrect = 0;

    group.questions.forEach((q, idx) => {
        const blockId = `q-${idx}`;
        const chosen  = (userAnswers[blockId] || '').toString().trim().toUpperCase();
        const correct = String(q.answer).trim().toUpperCase();
        const isCorrect = chosen === correct;
        const block   = document.getElementById(blockId);
        const fb      = document.getElementById(`feedback-${blockId}`);

        if (isCorrect) {
            groupCorrect++;
            if (block) block.classList.add('correct');
            if (fb) { fb.className = 'p-feedback correct'; fb.textContent = t('practice.correct_exclaim'); }
        } else {
            if (block) block.classList.add('wrong');
            if (fb)    { fb.className = 'p-feedback wrong'; fb.textContent = t('practice.correct_answer_colon', { answer: correct }); }
        }

        highlightAnswer(block, q, blockId, chosen, correct, isCorrect);
    });

    // For type 5 listening group OR reading match group
    const isT5LGroup = type === 5 && group.questions[0]?.skill === 'listening' && group.questions.length > 1;
    const q0opts = group.questions[0]?.options || {};
    const isT5RGroup = type === 5 && group.questions[0]?.skill !== 'listening' && group.questions.length > 1
        && !Object.values(q0opts).every(v => isImageFilename(String(v)));
    const isT5RIGroup = type === 5 && group.questions[0]?.skill !== 'listening' && group.questions.length > 1
        && Object.values(q0opts).every(v => isImageFilename(String(v)));

    if (isT5LGroup) {
        const fb = document.getElementById('feedback-t5l-group');
        if (fb) {
            fb.className = groupCorrect === group.questions.length ? 'p-feedback correct' : 'p-feedback wrong';
            fb.textContent = t('practice.score_correct', { correct: groupCorrect, total: group.questions.length });
        }
    } else if (isT5RGroup) {
        const fb = document.getElementById('feedback-t5r-group');
        if (fb) {
            fb.className = groupCorrect === group.questions.length ? 'p-feedback correct' : 'p-feedback wrong';
            fb.textContent = t('practice.score_correct', { correct: groupCorrect, total: group.questions.length });
        }
    } else if (isT5RIGroup) {
        const fb = document.getElementById('feedback-t5ri-group');
        if (fb) {
            fb.className = groupCorrect === group.questions.length ? 'p-feedback correct' : 'p-feedback wrong';
            fb.textContent = t('practice.score_correct', { correct: groupCorrect, total: group.questions.length });
        }
    }

    // Save to sessionAnswers
    const responseTimeMs = Math.max(0, Date.now() - groupStartTime);
    const perQuestionTimeMs = Math.round(responseTimeMs / Math.max(1, group.questions.length));
    group.questions.forEach((q, idx) => {
        const blockId = `q-${idx}`;
        const chosen  = (userAnswers[blockId] || '').toString().trim().toUpperCase();
        const correct = String(q.answer).trim().toUpperCase();
        const isCorrect = chosen === correct;
        
        sessionAnswers.push({
            hsk_level: q.level,
            lesson: q.lesson,
            question_no: q.no,
            skill: q.skill || 'listening',
            type: q.type,
            category: q.category || window.practiceCategory || 'practice',
            user_answer: chosen,
            is_correct: isCorrect,
            response_time_ms: perQuestionTimeMs
        });
    });

    score += groupCorrect;
    document.getElementById('score-val').textContent = score;
    if (entry) entry.checked = true;
    updateNav();
    applyPracticeHanText(group);
}

function highlightAnswer(block, q, blockId, chosen, correct, isCorrect) {
    if (!block) return;
    const type = q.type;
    const optEntries = Object.entries(q.options || {});
    const allImgOpts = optEntries.every(([, v]) => isImageFilename(String(v)));

    if (type === 1) {
        block.querySelectorAll('.tf-btn').forEach(btn => {
            btn.disabled = true;
            if (btn.dataset.key === correct) btn.classList.add('correct-ans');
            if (!isCorrect && btn.dataset.key === chosen) btn.classList.add('wrong-ans');
        });
    } else if (type === 4) {
        // Show correct key sequence
        block.querySelectorAll('.chip').forEach(chip => { chip.onclick = null; });
        const fb = document.getElementById(`feedback-${blockId}`);
        if (!isCorrect && fb) {
            const correctNames = correct.split('').map(k => `${k}: ${q.options[k] || k}`).join(' → ');
            fb.textContent = t('practice.correct_order', { order: correct });
        }
        block.querySelectorAll('.chip').forEach(chip => {
            chip.classList.add(isCorrect ? 'correct-chip' : 'wrong-chip');
        });
    } else if (type === 5 && allImgOpts) {
        block.querySelectorAll('.img-option').forEach(cell => {
            cell.classList.add('disabled');
            cell.onclick = null;
            if (cell.dataset.key === correct) cell.classList.add('correct-ans');
            if (!isCorrect && cell.dataset.key === chosen) cell.classList.add('wrong-ans');
        });
    } else if (type === 5 && q.skill === 'listening' && block === null) {
        // handled at group level by feedback
    } else {
        block.querySelectorAll('.mc-option').forEach(btn => {
            btn.disabled = true;
            if (btn.dataset.key === correct) btn.classList.add('correct-ans');
            if (!isCorrect && btn.dataset.key === chosen) btn.classList.add('wrong-ans');
        });
    }
}

// ── Finish / Submit ─────────────────────────────────────────────

async function finishPractice() {
    if (!allGroupsChecked()) {
        // Safety: jump to the first still-unchecked group instead of submitting early.
        const i = firstUncheckedAfter(-1);
        if (i !== -1) { currentGroupIndex = i; renderGroup(); }
        return;
    }
    stopAudio();
    const finishBtn = document.getElementById('btn-finish');
    if (finishBtn) { finishBtn.disabled = true; finishBtn.textContent = t('practice.submitting'); }

    try {
        await fetch('/api/practice/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: practiceSessionId,
                hsk_level: NUM,
                lesson: window.lessonId,
                answers: sessionAnswers
            })
        });
    } catch (e) {
        console.error("Failed to submit practice progress", e);
    }

    document.getElementById('result-number').textContent = NUM;
    document.getElementById('result-score').textContent  = `${score} / ${totalQuestions}`;
    const pct = totalQuestions > 0 ? score / totalQuestions : 0;
    const resultIcon = document.getElementById('result-emoji');
    const resultIconName = pct >= 0.9 ? 'fa-trophy' : pct >= 0.7 ? 'fa-circle-check' : pct >= 0.5 ? 'fa-chart-line' : 'fa-rotate-right';
    resultIcon.innerHTML = `<i class="fa-solid ${resultIconName}" aria-hidden="true"></i>`;
    showScreen('screen-result');
}

// ── Boot ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
