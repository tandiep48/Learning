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
        document.getElementById('picker-lesson-title').innerText = `${hskLevel} — Select Lesson`;
        document.getElementById('picker-lesson-list').innerHTML = '<div class="loader" style="margin: 20px auto;"></div><p style="text-align:center;color:var(--text-muted);">Loading lessons...</p>';
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
        document.getElementById('picker-part-title').innerText = `${this.currentHskLevel} — ${prefix}`;
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
        else if (pct <= 50) colorClass = 'pct-yellow';
        else colorClass = 'pct-green';
        return `<div class="picker-progress-row">
            <span class="picker-progress-label">${label}</span>
            <div class="picker-progress-track ${colorClass}" role="progressbar" aria-label="${label} progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}">
                <span class="picker-progress-fill" style="width:${pct}%"></span>
            </div>
            <span class="picker-progress-pct">${pct}%</span>
        </div>`;
    },

    _emptyProgressBar(label) {
        return `<div class="picker-progress-row">
            <span class="picker-progress-label">${label}</span>
            <div class="picker-progress-track pct-red" role="progressbar" aria-label="${label} progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
                <span class="picker-progress-fill" style="width:0%"></span>
            </div>
            <span class="picker-progress-pct">0%</span>
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
