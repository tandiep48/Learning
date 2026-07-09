(function () {
    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = value || '';
        return div.innerHTML;
    }

    function progressLabel(progress) {
        if (!progress) return '-';
        const text = String(progress);
        if (text.includes('-')) {
            const [a, b] = text.split('-');
            return t('recommend.questions_range', { a, b });
        }
        return t('recommend.question_single', { n: text });
    }

    function recommendationKey(item) {
        return [
            item.category || 'practice',
            item.level,
            item.lesson,
            item.progress,
        ].join('|');
    }

    function createSelection(options = {}) {
        let selectedItems = [];
        const onChange = typeof options.onChange === 'function' ? options.onChange : function () {};

        function isSelected(rec) {
            const key = recommendationKey(rec);
            return selectedItems.some(item => recommendationKey(item) === key);
        }

        function setSelected(rec, checked) {
            const key = recommendationKey(rec);
            if (checked) {
                if (!selectedItems.some(item => recommendationKey(item) === key)) {
                    selectedItems.push({
                        level: rec.level,
                        lesson: rec.lesson,
                        progress: rec.progress,
                        category: rec.category || 'practice',
                    });
                }
            } else {
                selectedItems = selectedItems.filter(item => recommendationKey(item) !== key);
            }
            onChange(selectedItems.slice());
        }

        function buildCard(rec) {
            const card = document.createElement('div');
            card.className = 'rec-card';

            const skillIcon = rec.skill === 'listening'
                ? '<i class="fa-solid fa-headphones-simple" aria-hidden="true"></i>'
                : '<i class="fa-solid fa-book-open" aria-hidden="true"></i>';
            const skillLabel = rec.skill === 'listening'
                ? t('recommend.listening')
                : rec.skill === 'reading'
                    ? t('recommend.reading')
                    : '';
            const qCount = rec.question_count != null
                ? rec.question_count
                : (rec.questions ? rec.questions.length : 0);
            const categoryLabel = rec.category === 'exam'
                ? `<i class="fa-solid fa-file-lines" aria-hidden="true"></i><span>${t('dashboard.exam')}</span>`
                : `<i class="fa-solid fa-list-check" aria-hidden="true"></i><span>${t('dashboard.exercise')}</span>`;
            const categoryClass = rec.category === 'exam' ? 'badge-exam' : 'badge-practice';
            const recentWords = Array.isArray(rec.recent_matched_words) ? rec.recent_matched_words.slice(0, 6) : [];
            const focusHtml = recentWords.length
                ? `<div class="rec-new-focus">${t('recommend.new_focus', { words: recentWords.map(escapeHtml).join(', ') })}</div>`
                : '';
            const selected = isSelected(rec);
            const statusLabels = {
                'Not start': t('recommend.status_not_start'),
                'Finish and success': t('recommend.status_finish_success'),
                'Finish and fail': t('recommend.status_finish_fail'),
            };
            const statusText = statusLabels[rec.status] || statusLabels['Not start'];

            card.classList.toggle('selected', selected);
            card.innerHTML = `
                <div class="rec-card-header">
                    <input type="checkbox" class="rec-card-checkbox" ${selected ? 'checked' : ''} aria-label="${t('recommend.select_lesson_aria', { n: rec.lesson })}">
                    <span class="hsk-badge hsk-${rec.level}">HSK ${rec.level}</span>
                    <span class="rec-card-title">${t('picker.lesson_prefix')} ${rec.lesson}</span>
                </div>
                <div class="rec-card-meta">
                    <span class="rec-card-skill">${skillIcon} ${skillLabel}</span>
                    <span class="category-badge ${categoryClass}">${categoryLabel}</span>
                    <span class="status-badge">${statusText}</span>
                </div>
                <div class="rec-progress-label">${progressLabel(rec.progress)} &middot; ${t('recommend.question_count', { count: qCount })}</div>
                ${focusHtml}
            `;

            const checkbox = card.querySelector('.rec-card-checkbox');
            checkbox.addEventListener('click', event => event.stopPropagation());
            checkbox.addEventListener('change', () => {
                setSelected(rec, checkbox.checked);
                card.classList.toggle('selected', checkbox.checked);
            });
            card.addEventListener('click', () => {
                checkbox.checked = !checkbox.checked;
                setSelected(rec, checkbox.checked);
                card.classList.toggle('selected', checkbox.checked);
            });

            return card;
        }

        function startSelected(referrer) {
            if (!selectedItems.length) return;
            sessionStorage.setItem('multi_practice_queue', JSON.stringify(selectedItems));
            sessionStorage.setItem('practice_referrer', referrer || 'recommend');
            window.location.href = '/practice/multi';
        }

        return {
            buildCard,
            getSelected: () => selectedItems.slice(),
            getSelectedCount: () => selectedItems.length,
            setSelected,
            startSelected,
        };
    }

    window.RecommendCards = {
        createSelection,
        escapeHtml,
        progressLabel,
    };
})();
