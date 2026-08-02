// ── Custom multi-select dropdown ──────────────────────────────
// A button that opens a checkbox panel; keeps the multi-select behaviour without
// the clunky native <select multiple> list box. Shared by the vocab picker and
// the Learn Together setup. Depends only on the global i18n helper `t()`.
const MultiSelect = {
    registry: {},

    init(rootId, placeholder, onChange) {
        this.registry[rootId] = { selected: new Set(), options: [], placeholder, onChange };
        this._renderLabel(rootId);
    },

    setOptions(rootId, options) {
        const reg = this.registry[rootId];
        if (!reg) return;
        reg.options = options;
        reg.selected = new Set();
        const panel = document.getElementById(`${rootId}-panel`);
        panel.innerHTML = '';
        if (options.length) this._renderSelectAll(rootId, panel);
        let currentGroup = null;
        options.forEach(opt => {
            if (opt.group && opt.group !== currentGroup) {
                currentGroup = opt.group;
                const gl = document.createElement('div');
                gl.className = 'ms-group-label';
                gl.textContent = opt.group;
                panel.appendChild(gl);
            }
            const row = document.createElement('label');
            row.className = 'ms-option';
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = opt.value;
            cb.onchange = () => this._toggle(rootId, opt.value, cb.checked);
            const span = document.createElement('span');
            span.textContent = opt.label;
            row.appendChild(cb);
            row.appendChild(span);
            panel.appendChild(row);
        });
        this._renderLabel(rootId);
        this._setDisabled(rootId, options.length === 0);
    },

    // "Select all" row pinned to the top of the panel; toggles every option at once.
    _renderSelectAll(rootId, panel) {
        const row = document.createElement('label');
        row.className = 'ms-option ms-option-all';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ms-select-all';
        cb.onchange = () => this._toggleAll(rootId, cb.checked);
        const span = document.createElement('span');
        span.textContent = t('vocab.select_all');
        row.appendChild(cb);
        row.appendChild(span);
        panel.appendChild(row);
    },

    clear(rootId) {
        const reg = this.registry[rootId];
        if (!reg) return;
        reg.options = [];
        reg.selected = new Set();
        const panel = document.getElementById(`${rootId}-panel`);
        if (panel) panel.innerHTML = '';
        this._renderLabel(rootId);
        this._setDisabled(rootId, true);
    },

    values(rootId) {
        const reg = this.registry[rootId];
        return reg ? Array.from(reg.selected) : [];
    },

    toggle(rootId) {
        const root = document.getElementById(rootId);
        if (!root) return;
        const willOpen = !root.classList.contains('open');
        document.querySelectorAll('.ms-dropdown.open').forEach(el => el.classList.remove('open'));
        if (willOpen) root.classList.add('open');
    },

    _toggle(rootId, value, checked) {
        const reg = this.registry[rootId];
        if (!reg) return;
        if (checked) reg.selected.add(value);
        else reg.selected.delete(value);
        this._syncSelectAll(rootId);
        this._renderLabel(rootId);
        if (reg.onChange) reg.onChange();
    },

    _toggleAll(rootId, checked) {
        const reg = this.registry[rootId];
        if (!reg) return;
        reg.selected = checked ? new Set(reg.options.map(o => o.value)) : new Set();
        const panel = document.getElementById(`${rootId}-panel`);
        panel?.querySelectorAll('.ms-option:not(.ms-option-all) input[type="checkbox"]')
            .forEach(cb => { cb.checked = checked; });
        this._renderLabel(rootId);
        if (reg.onChange) reg.onChange();
    },

    // Keep the "select all" checkbox in sync when individual options change.
    _syncSelectAll(rootId) {
        const reg = this.registry[rootId];
        const allCb = document.querySelector(`#${rootId}-panel .ms-select-all`);
        if (allCb && reg) allCb.checked = reg.options.length > 0 && reg.selected.size === reg.options.length;
    },

    _renderLabel(rootId) {
        const reg = this.registry[rootId];
        const labelEl = document.querySelector(`#${rootId} .ms-label`);
        if (!reg || !labelEl) return;
        const n = reg.selected.size;
        if (n === 0) {
            labelEl.textContent = reg.placeholder;
            labelEl.classList.add('ms-placeholder');
        } else if (n === 1) {
            const opt = reg.options.find(o => o.value === Array.from(reg.selected)[0]);
            labelEl.textContent = opt ? opt.label : '1';
            labelEl.classList.remove('ms-placeholder');
        } else {
            labelEl.textContent = t('vocab.n_selected', { n });
            labelEl.classList.remove('ms-placeholder');
        }
    },

    _setDisabled(rootId, disabled) {
        const toggle = document.querySelector(`#${rootId} .ms-toggle`);
        if (toggle) toggle.disabled = disabled;
        if (disabled) {
            const root = document.getElementById(rootId);
            if (root) root.classList.remove('open');
        }
    },
};

// Close any open dropdown when clicking outside of it.
document.addEventListener('click', (e) => {
    if (!e.target.closest('.ms-dropdown')) {
        document.querySelectorAll('.ms-dropdown.open').forEach(el => el.classList.remove('open'));
    }
});
