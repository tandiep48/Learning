const HSK_COLORS = {
    "HSK1": "#d9d9d8",
    "HSK2": "#d0f1d2",
    "HSK3": "#99d8e9",
    "HSK4": "#fce084",
    "HSK5": "#fcb86f",
    "HSK6": "#ee5550"
};

const LESSON_COLORS = {
    "H1-1": "#f5f5f5", "H1-10": "#f5f5f5", "H1-11": "#f5f5f5", "H1-12": "#f5f5f5",
    "H1-2": "#f5f5f5", "H1-3": "#f5f5f5", "H1-4": "#f5f5f5", "H1-5": "#f5f5f5",
    "H1-6": "#f5f5f5", "H1-7": "#f5f5f5", "H1-8": "#f5f5f5", "H1-9": "#f5f5f5",
    "H2-1": "#94af84", "H2-10": "#bbd3a3", "H2-11": "#b4d4af", "H2-12": "#b8dcc2",
    "H2-13": "#a2fab0", "H2-14": "#d0f1c2", "H2-15": "#6fa68f", "H2-2": "#9cc29b",
    "H2-3": "#cdf7c7", "H2-4": "#a7caa9", "H2-5": "#b3deb0", "H2-6": "#b8f0ed",
    "H2-7": "#cee7d1", "H2-8": "#b2cc9f", "H2-9": "#b5e3bc",
    "H3-1": "#a4cedc", "H3-10": "#8ba9cf", "H3-11": "#83b6d5", "H3-12": "#afddea",
    "H3-13": "#b8d3e8", "H3-14": "#b1d3ef", "H3-15": "#bce5f7", "H3-16": "#a9cacf",
    "H3-17": "#9abee0", "H3-18": "#9ad2e3", "H3-2": "#b2dee1", "H3-3": "#9ed6ed",
    "H3-4": "#99c7df", "H3-5": "#a4dae6", "H3-6": "#064288", "H3-7": "#9ecddd",
    "H3-8": "#a6c8ca", "H3-9": "#83cfe7",
    "H4-1": "#fee9bc", "H4-10": "#fff3cb", "H4-11": "#f6d892", "H4-12": "#fdeb99",
    "H4-13": "#fef2c2", "H4-14": "#fbdc81", "H4-15": "#feeab5", "H4-16": "#fef2dc",
    "H4-17": "#fdeaa6", "H4-18": "#f9eac9", "H4-19": "#fef1ce", "H4-2": "#f7df9f",
    "H4-20": "#fde69a", "H4-21": "#fde9a0", "H4-3": "#ffeabf", "H4-4": "#fdf0c3",
    "H4-5": "#fef9c2", "H4-6": "#fbdf74", "H4-7": "#feedc1", "H4-8": "#fde295",
    "H4-9": "#feef9c",
    "H5-1": "#fc8f3c", "H5-10": "#fabf7d", "H5-11": "#fbcb8b", "H5-12": "#f9be56",
    "H5-13": "#f8874d", "H5-14": "#f5a66b", "H5-15": "#fcb660", "H5-16": "#fee5cf",
    "H5-17": "#f6b57b", "H5-18": "#f9ad61", "H5-19": "#f9c498", "H5-2": "#faa346",
    "H5-20": "#f7c592", "H5-21": "#ec9c47", "H5-22": "#df8d39", "H5-23": "#fa8751",
    "H5-24": "#fabe75", "H5-25": "#fbd1a7", "H5-26": "#d0713b", "H5-27": "#fcdebc",
    "H5-28": "#f57f59", "H5-29": "#faad69", "H5-3": "#e68260", "H5-30": "#ec9957",
    "H5-4": "#de6d29", "H5-5": "#fbe2c3", "H5-6": "#f7ab79", "H5-7": "#fca641",
    "H5-8": "#f07c41", "H5-9": "#f99750",
    "H6-1": "#de6258", "H6-10": "#db4841", "H6-11": "#d66158", "H6-12": "#f07577",
    "H6-13": "#f25e5e", "H6-14": "#ec4944", "H6-15": "#ef7d7d", "H6-16": "#e54b4b",
    "H6-17": "#f35055", "H6-18": "#ee575e", "H6-19": "#f1aba9", "H6-2": "#e55b51",
    "H6-20": "#e63636", "H6-21": "#fa8179", "H6-22": "#d75e56", "H6-23": "#bd3b3b",
    "H6-24": "#e87d75", "H6-25": "#e56f6b", "H6-26": "#c05950", "H6-27": "#e5554d",
    "H6-28": "#e26b57", "H6-29": "#e65b46", "H6-3": "#ef4850", "H6-30": "#d63432",
    "H6-4": "#ee5648", "H6-5": "#e13f3a", "H6-6": "#f3514f", "H6-7": "#db4f52",
    "H6-8": "#e83d33", "H6-9": "#cf6565"
};

const Picker = {
    currentHskLevel: null,
    groupedPassages: {},
    onPassageSelected: null,
    progressSummary: null,

    init(onPassageSelectedCallback, titlePrefix = "Select HSK Level", autoShow = true) {
        this.onPassageSelected = onPassageSelectedCallback;
        const mainTitle = document.getElementById('picker-main-title');
        if (mainTitle) mainTitle.innerText = titlePrefix;
        if (autoShow) {
            this.showLevelPicker();
        }
    },

    switchScreen(screenId) {
        document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
        const target = document.getElementById(screenId);
        if (target) target.classList.add('active');

        // Update the width of the recent panel to match the screen's main content width
        const recentPanel = document.getElementById('learning-recent-panel');
        if (recentPanel) {
            if (screenId === 'picker-screen-part') {
                recentPanel.style.maxWidth = '800px';
                recentPanel.style.margin = '0 auto 22px auto';
            } else {
                recentPanel.style.maxWidth = '1080px';
                recentPanel.style.margin = '0 auto 22px auto';
            }
        }
    },

    hide() {
        document.querySelectorAll('.picker-screen').forEach(el => el.classList.remove('active'));
    },

    showLevelPicker() {
        this.currentHskLevel = null;
        this.progressSummary = null;
        this.hideLessonActionCard();
        this.switchScreen('picker-screen-level');
    },

    async showLessonPicker(hskLevel) {
        this.currentHskLevel = hskLevel;
        document.getElementById('picker-lesson-title').innerText = `Select Lesson`;
        document.getElementById('picker-lesson-sub').innerText = hskLevel;
        document.getElementById('picker-lesson-list').innerHTML = '<div class="loader" style="margin: 20px auto;"></div><p style="text-align:center;color:var(--text-muted);">Loading lessons...</p>';

        const levelScreen = document.getElementById('picker-screen-level');
        if (levelScreen && levelScreen.dataset.hskImages) {
            try {
                const images = JSON.parse(levelScreen.dataset.hskImages);
                if (images[hskLevel]) {
                    document.getElementById('lesson-picker-hsk-image').src = images[hskLevel];
                }
            } catch (e) {
                console.error('Failed to parse HSK images:', e);
            }
        }
        if (typeof HSK_COLORS !== 'undefined' && HSK_COLORS[hskLevel]) {
            document.getElementById('lesson-picker-header').style.backgroundColor = HSK_COLORS[hskLevel];
        }

        this.switchScreen('picker-screen-lesson');

        try {
            const [res, progressSummary] = await Promise.all([
                fetch(`/api/lesson/passages?hsk_level=${hskLevel}`),
                this.loadPickerProgress(hskLevel),
            ]);
            const data = await res.json();
            this.progressSummary = progressSummary;

            // Hardcode HSK 1 Lesson 1 (Basic/Advanced Pinyin)
            if (hskLevel === 'HSK1') {
                // Remove any existing Lesson 1 parts if they exist from API
                data.passages = data.passages.filter(p => !p.passage_id.startsWith('H1_1_'));
                // Inject ONE hardcoded pinyin page so the lesson card appears
                data.passages.push({ passage_id: 'H1_1_1', hsk_level: 'HSK1' });
            }

            // Group passages by lesson
            this.groupedPassages = {};
            data.passages.forEach(p => {
                const parts = p.passage_id.split('_');
                const lessonNum = parts.length >= 2 ? parts[1] : 'Other';
                if (!this.groupedPassages[lessonNum]) {
                    this.groupedPassages[lessonNum] = [];
                }
                this.groupedPassages[lessonNum].push(p);
            });

            this.renderLessons();

        } catch (e) {
            console.error(e);
            document.getElementById('picker-lesson-list').innerHTML = `<p style="color:var(--danger); text-align:center;">Failed to load lessons.</p>`;
        }
    },

    async loadPickerProgress(hskLevel) {
        try {
            const res = await fetch(`/api/lesson/picker-progress?hsk_level=${encodeURIComponent(hskLevel)}`);
            if (!res.ok) return null;
            return await res.json();
        } catch (e) {
            console.warn('Could not load picker progress', e);
            return null;
        }
    },

    renderLessons() {
        const container = document.getElementById('picker-lesson-list');
        container.innerHTML = '';

        // Sort lessons numerically if possible
        const lessons = Object.keys(this.groupedPassages).sort((a, b) => {
            if (a === 'Other') return 1;
            if (b === 'Other') return -1;
            return parseInt(a) - parseInt(b);
        });

        if (lessons.length === 0) {
            container.innerHTML = '<p style="color:var(--text-muted); text-align:center;">No lessons found for this level.</p>';
            return;
        }

        document.getElementById('picker-lesson-sub').innerText = `${lessons.length} lesson${lessons.length !== 1 ? 's' : ''} available`;

        lessons.forEach(lessonNum => {
            const card = document.createElement('div');
            card.className = 'lesson-card';

            const count = this.groupedPassages[lessonNum].length;
            const prefix = lessonNum === 'Other' ? '' : 'Lesson ';
            const progress = this.progressSummary?.lessons?.[lessonNum];

            const isPinyinLesson = this.currentHskLevel === 'HSK1' && lessonNum === '1';
            const countLabel = isPinyinLesson ? 'Pinyin Guide' : `${count} part${count !== 1 ? 's' : ''}`;

            const hskKey = (this.currentHskLevel || '').replace('HSK', 'H');
            const imgPath = `/lesson-image/${hskKey}/${hskKey.toLowerCase()}-lesson-${lessonNum}.png`;

            const progressHtml = progress
                ? `<div class="picker-progress-lines">
                    ${this._progressBar(progress.learned_words, progress.total_words, 'Words')}
                    ${this._progressBar(progress.lesson_learned, progress.lesson_total, 'Lesson')}
                   </div>`
                : '';

            card.innerHTML = `
                <div class="lesson-card-img-wrap">
                    <img class="lesson-card-img" src="${imgPath}" alt="Lesson ${lessonNum}" loading="lazy"
                         onerror="this.parentElement.style.display='none'">
                </div>
                <div class="lesson-card-body">
                    <div class="lesson-card-title">${this.escapeHtml(prefix + lessonNum)}</div>
                    ${progressHtml}
                    <div class="lesson-card-count">${countLabel}</div>
                </div>
            `;

            card.addEventListener('click', () => {
                if (isPinyinLesson) {
                    window.location.href = '/lesson/basic-pinyin';
                    return;
                }
                this.showPartPicker(lessonNum);
            });
            container.appendChild(card);
        });
    },

    showPartPicker(lessonNum) {
        const prefix = lessonNum === 'Other' ? 'Other Passages' : `Lesson ${lessonNum}`;
        document.getElementById('picker-part-title').innerText = `Select Part`;
        
        const subtitleEl = document.querySelector('#part-picker-header .subtitle');
        if (subtitleEl) subtitleEl.innerText = `${this.currentHskLevel} — ${prefix}`;
        
        const hskKey = (this.currentHskLevel || '').replace('HSK', 'H');
        const imgPath = `/lesson-image/${hskKey}/${hskKey.toLowerCase()}-lesson-${lessonNum}.png`;
        const colorKey = `${hskKey}-${lessonNum}`;
        
        const partImgEl = document.getElementById('part-picker-lesson-image');
        if (partImgEl) partImgEl.src = imgPath;
        
        const partHeaderEl = document.getElementById('part-picker-header');
        if (partHeaderEl && LESSON_COLORS[colorKey]) {
            partHeaderEl.style.backgroundColor = LESSON_COLORS[colorKey];
        }

        this.switchScreen('picker-screen-part');

        const container = document.getElementById('picker-part-list');
        container.innerHTML = '';

        const parts = [...(this.groupedPassages[lessonNum] || [])].sort((a, b) => this.getPartNumber(a.passage_id) - this.getPartNumber(b.passage_id));
        this.renderLessonActionCard(lessonNum, parts);

        parts.forEach(p => {
            // e.g. H1_10_3 => Part 3
            const pParts = p.passage_id.split('_');
            const partName = pParts.length >= 3 ? `Part ${pParts[2]}` : p.passage_id;

            const btn = document.createElement('div');
            btn.className = 'part-list-item';

            const progress = this.progressSummary?.parts?.[p.passage_id];
            const progressHtml = progress
                ? `<div class="picker-progress-lines picker-progress-lines-centered">
                    ${this._progressBar(progress.learned_words, progress.total_words, 'Words')}
                    ${this._progressBar(progress.lesson_learned, progress.lesson_total, 'Lesson')}
                   </div>`
                : '';

            btn.innerHTML = `
                <div class="part-list-title">${this.escapeHtml(partName)}</div>
                ${progressHtml}
            `;

            btn.addEventListener('click', () => {
                this.hide();
                if (this.onPassageSelected) {
                    this.onPassageSelected(p);
                }
            });
            container.appendChild(btn);
        });
    },

    hideLessonActionCard() {
        const actionCard = document.getElementById('picker-lesson-action-card');
        if (actionCard) {
            actionCard.hidden = true;
            actionCard.innerHTML = '';
        }
    },

    renderLessonActionCard(lessonNum, parts) {
        const actionCard = document.getElementById('picker-lesson-action-card');
        if (!actionCard) return;

        const progress = this.progressSummary?.lessons?.[lessonNum];
        const wordsPct = this._progressPct(progress?.learned_words, progress?.total_words);
        const lessonPct = this._progressPct(progress?.lesson_learned, progress?.lesson_total);
        const canStartVocab = wordsPct === 100 && parts.length > 0;
        const canStartLesson = lessonPct === 100 && parts.length > 0;
        const partCount = parts.length;

        actionCard.hidden = false;
        actionCard.innerHTML = `
            <div class="picker-lesson-action-header">
                <div>
                    <div class="picker-lesson-action-title">Full Lesson Trainer</div>
                    <div class="picker-lesson-action-sub">${partCount} part${partCount !== 1 ? 's' : ''} in this lesson</div>
                </div>
                <div class="picker-lesson-action-buttons">
                    <button type="button" class="picker-action-btn" data-action="vocab" ${canStartVocab ? '' : 'disabled'}>Vocab Trainer</button>
                    <button type="button" class="picker-action-btn" data-action="lesson" ${canStartLesson ? '' : 'disabled'}>Lesson Trainer</button>
                </div>
            </div>
            <div class="picker-lesson-progress">
                ${progress ? this._progressBar(progress.learned_words, progress.total_words, 'Words') : this._emptyProgressBar('Words')}
                ${progress ? this._progressBar(progress.lesson_learned, progress.lesson_total, 'Lesson') : this._emptyProgressBar('Lesson')}
            </div>
        `;

        actionCard.querySelector('[data-action="vocab"]')?.addEventListener('click', () => {
            if (canStartVocab) this.startLessonWideVocabTrainer(lessonNum, parts);
        });
        actionCard.querySelector('[data-action="lesson"]')?.addEventListener('click', () => {
            if (canStartLesson) this.startLessonWideLessonTrainer(lessonNum, parts);
        });
    },

    startLessonWideVocabTrainer(lessonNum, parts) {
        sessionStorage.setItem('lessonWideVocabTrainer', JSON.stringify(this.buildLessonTrainerPayload(lessonNum, parts)));
        window.location.href = '/vocab-training';
    },

    startLessonWideLessonTrainer(lessonNum, parts) {
        sessionStorage.setItem('lessonWideLessonTrainer', JSON.stringify(this.buildLessonTrainerPayload(lessonNum, parts)));
        window.location.href = '/lesson';
    },

    buildLessonTrainerPayload(lessonNum, parts) {
        return {
            hsk_level: this.currentHskLevel,
            lesson: lessonNum,
            passage_ids: parts.map(p => p.passage_id).filter(Boolean),
        };
    },

    // Returns a coloured progress bar HTML string.
    // ≤25% → red, 26–50% → yellow, ≥51% → green
    _progressBar(done, total, label) {
        if (!total || total === 0) return '';
        const pct = this._progressPct(done, total);
        let colorClass;
        if (pct <= 25) colorClass = 'pct-red';
        else if (pct <= 50) colorClass = 'pct-orange';
        else if (pct <= 75) colorClass = 'pct-yellow';
        else colorClass = 'pct-green';
        return `<div class="picker-progress-row">
            <span class="picker-progress-label">${label}</span>
            <div class="picker-progress-track ${colorClass}" role="progressbar" aria-label="${label} progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}">
                <span class="picker-progress-fill" style="width:${pct}%"></span>
            </div>
            <span class="picker-progress-pct">${Number(done) || 0} / ${total}</span>
        </div>`;
    },

    _emptyProgressBar(label) {
        return `<div class="picker-progress-row">
            <span class="picker-progress-label">${label}</span>
            <div class="picker-progress-track pct-red" role="progressbar" aria-label="${label} progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
                <span class="picker-progress-fill" style="width:0%"></span>
            </div>
            <span class="picker-progress-pct">0 / 0</span>
        </div>`;
    },

    _progressPct(done, total) {
        if (!total || total === 0) return 0;
        return Math.max(0, Math.min(100, Math.round(((Number(done) || 0) / total) * 100)));
    },

    getPartNumber(passageId) {
        const parts = String(passageId || '').split('_');
        const part = parts.length >= 3 ? Number(parts[2]) : Number.MAX_SAFE_INTEGER;
        return Number.isFinite(part) ? part : Number.MAX_SAFE_INTEGER;
    },

    escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
};
