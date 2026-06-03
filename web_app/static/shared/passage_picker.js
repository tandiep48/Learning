const Picker = {
    currentHskLevel: null,
    groupedPassages: {},
    onPassageSelected: null,
    
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
        this.switchScreen('picker-screen-level');
    },

    async showLessonPicker(hskLevel) {
        this.currentHskLevel = hskLevel;
        document.getElementById('picker-lesson-title').innerText = `${hskLevel} — Select Lesson`;
        document.getElementById('picker-lesson-list').innerHTML = '<div class="loader" style="margin: 20px auto;"></div><p style="text-align:center;color:var(--text-muted);">Loading lessons...</p>';
        this.switchScreen('picker-screen-lesson');

        try {
            const url = `/api/lesson/passages?hsk_level=${hskLevel}`;
            const res = await fetch(url);
            const data = await res.json();
            
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
            
            card.innerHTML = `
                <div class="lesson-card-left">
                    <div class="lesson-card-title">${prefix}${lessonNum}</div>
                </div>
                <div class="lesson-card-count">${count} part${count !== 1 ? 's' : ''}</div>
            `;
            
            card.addEventListener('click', () => {
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
        
        const parts = this.groupedPassages[lessonNum] || [];
        
        parts.forEach(p => {
            // e.g. H1_10_3 => Part 3
            const pParts = p.passage_id.split('_');
            const partName = pParts.length >= 3 ? `Part ${pParts[2]}` : p.passage_id;
            
            const btn = document.createElement('div');
            btn.className = 'dash-card';
            btn.style.padding = '15px';
            btn.style.cursor = 'pointer';
            btn.style.textAlign = 'center';
            btn.style.display = 'flex';
            btn.style.alignItems = 'center';
            btn.style.justifyContent = 'center';
            
            btn.innerHTML = `<div class="dash-title" style="margin:0;">${partName}</div>`;
            
            btn.addEventListener('click', () => {
                this.hide();
                if (this.onPassageSelected) {
                    this.onPassageSelected(p);
                }
            });
            container.appendChild(btn);
        });
    }
};
