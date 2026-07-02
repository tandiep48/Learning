(function () {
    const DEFAULT_FONT = 'Noto Sans';
    const ALLOWED_FONTS = new Set(['SimSun', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Noto Sans']);

    function fontStack(font) {
        const chosen = ALLOWED_FONTS.has(font) ? font : DEFAULT_FONT;
        return `'${chosen}', 'Noto Sans', Arial, Helvetica, sans-serif`;
    }

    function applyFont(font) {
        const chosen = ALLOWED_FONTS.has(font) ? font : DEFAULT_FONT;
        document.documentElement.style.setProperty('--han-font-family', fontStack(chosen));
        const select = document.getElementById('hanzi-font-select');
        if (select && select.value !== chosen) select.value = chosen;
    }

    async function loadSavedFont() {
        const select = document.getElementById('hanzi-font-select');
        const initial = select?.dataset.currentFont || DEFAULT_FONT;
        applyFont(initial);
        if (!select) return;

        try {
            const response = await fetch('/api/user/hanzi-font');
            const data = await response.json();
            if (response.ok && data.hanzi_font) applyFont(data.hanzi_font);
        } catch (e) {
            applyFont(DEFAULT_FONT);
        }
    }

    async function saveFont(font) {
        applyFont(font);
        try {
            const response = await fetch('/api/user/hanzi-font', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hanzi_font: font })
            });
            const data = await response.json();
            if (!response.ok || data.error) throw new Error(data.error || 'Save failed');
            applyFont(data.hanzi_font || font);
        } catch (e) {
            console.warn('Could not save Hanzi font:', e);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadSavedFont();
        document.getElementById('hanzi-font-select')?.addEventListener('change', (event) => {
            saveFont(event.target.value);
        });
    });

    window.HanziFont = { applyFont };
})();
