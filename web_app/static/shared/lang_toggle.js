(function () {
    const ALLOWED_LANGS = new Set(['en', 'vi']);

    // Reads the saved UI language from the server and syncs the select box.
    async function loadSavedLang() {
        const select = document.getElementById('ui-language-select');
        if (!select) return;
        try {
            const res = await fetch('/api/user/ui-language');
            const data = await res.json();
            if (res.ok && data.ui_language && select.value !== data.ui_language) {
                select.value = data.ui_language;
            }
        } catch (_) { }
    }

    // Persists the chosen language then reloads so server-rendered strings refresh.
    async function saveLang(lang) {
        if (!ALLOWED_LANGS.has(lang)) return;
        try {
            await fetch('/api/user/ui-language', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ui_language: lang }),
            });
        } catch (e) {
            console.warn('Could not save UI language:', e);
        }
        location.reload();
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadSavedLang();
        document.getElementById('ui-language-select')?.addEventListener('change', e => saveLang(e.target.value));
    });
})();
