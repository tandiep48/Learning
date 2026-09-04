// train_type_picker.js — shared "choose which skills to train" popup shown before a
// training session starts. Multi-select; every skill is checked by default (= train all).
// The two trainer engines have different skill sets, so the caller passes `engine` and
// gets back that engine's native skill ids via onStart(selectedIds).
//
//   TrainTypePicker.open({ engine: 'vocab' | 'lesson', onStart(selectedTypeIds) })
const TrainTypePicker = (() => {
    // Engine -> ordered skills. `id` is exactly what the trainer expects (VocabTrainer's
    // activityTypes / a lesson task's `type`); `labelKey` is the i18n label.
    const ENGINES = {
        vocab: [
            { id: 'typing',  labelKey: 'train_picker.skill_typing' },
            { id: 'listen',  labelKey: 'train_picker.skill_listening' },
            { id: 'reading', labelKey: 'train_picker.skill_reading' },
        ],
        lesson: [
            { id: 'listening', labelKey: 'train_picker.skill_listening' },
            { id: 'meaning',   labelKey: 'train_picker.skill_meaning' },
            { id: 'typing',    labelKey: 'train_picker.skill_typing' },
            { id: 'reorder',   labelKey: 'train_picker.skill_reorder' },
        ],
    };

    let _overlay = null;
    let _onStart = null;

    function _ensureDom() {
        if (_overlay) return;
        _overlay = document.createElement('div');
        _overlay.className = 'ttp-overlay';
        _overlay.innerHTML = `
            <div class="ttp-card" role="dialog" aria-modal="true">
                <h2 class="ttp-title"></h2>
                <p class="ttp-subtitle"></p>
                <div class="ttp-options"></div>
                <div class="ttp-error" aria-live="polite"></div>
                <div class="ttp-actions">
                    <button type="button" class="btn secondary ttp-cancel"></button>
                    <button type="button" class="btn primary ttp-start"></button>
                </div>
            </div>`;
        document.body.appendChild(_overlay);
        _overlay.addEventListener('click', (e) => { if (e.target === _overlay) hide(); });
        _overlay.querySelector('.ttp-cancel').addEventListener('click', hide);
        _overlay.querySelector('.ttp-start').addEventListener('click', _submit);
    }

    function _selected() {
        return [..._overlay.querySelectorAll('.ttp-check:checked')].map(c => c.value);
    }

    function _submit() {
        const chosen = _selected();
        if (!chosen.length) {
            _overlay.querySelector('.ttp-error').textContent = t('train_picker.select_one');
            return;
        }
        const cb = _onStart;
        hide();
        if (cb) cb(chosen);
    }

    function open({ engine = 'vocab', onStart } = {}) {
        const skills = ENGINES[engine] || ENGINES.vocab;
        _onStart = onStart;
        _ensureDom();

        _overlay.querySelector('.ttp-title').textContent = t('train_picker.title');
        _overlay.querySelector('.ttp-subtitle').textContent = t('train_picker.subtitle');
        _overlay.querySelector('.ttp-cancel').textContent = t('train_picker.cancel');
        _overlay.querySelector('.ttp-start').textContent = t('train_picker.start');
        _overlay.querySelector('.ttp-error').textContent = '';

        const box = _overlay.querySelector('.ttp-options');
        box.innerHTML = '';
        skills.forEach(skill => {
            const label = document.createElement('label');
            label.className = 'ttp-option';
            label.innerHTML = `
                <input type="checkbox" class="ttp-check" value="${skill.id}" checked>
                <span class="ttp-option-label">${t(skill.labelKey)}</span>`;
            box.appendChild(label);
        });
        // Clear any stale error the moment the learner changes the selection.
        box.addEventListener('change', () => { _overlay.querySelector('.ttp-error').textContent = ''; });

        _overlay.classList.add('open');
    }

    function hide() {
        _onStart = null;
        if (_overlay) _overlay.classList.remove('open');
    }

    return { open, hide };
})();
