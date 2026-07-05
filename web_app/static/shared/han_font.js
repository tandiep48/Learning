(function () {
    const DEFAULT_FONT = 'Noto Sans';
    const ALLOWED_FONTS = new Set(['SimSun', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Noto Sans']);
    const DEFAULT_SCRIPT = 'simplified';
    const OPENCC_CDN = 'https://cdn.jsdelivr.net/npm/opencc-js@1.0.5/dist/umd/full.js';
    const HAN_CHAR_RE = /[㐀-䶿一-鿿豈-﫿]/;
    const SKIP_SELECTOR = 'script,style,textarea,input,select,[data-han-skip]';

    let _converter = null;
    let _openccLoading = false;
    let _openccCallbacks = [];
    const _originals = new WeakMap();

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

    function convertText(text) {
        return _converter ? _converter(text) : text;
    }

    function originalTextOf(node) {
        const parent = node.parentElement;
        if (parent && parent.hasAttribute('data-original')) {
            return parent.getAttribute('data-original');
        }
        if (!_originals.has(node)) _originals.set(node, node.nodeValue);
        return _originals.get(node);
    }

    function convertTextNode(node) {
        if (!node.nodeValue || !HAN_CHAR_RE.test(node.nodeValue)) return;
        const parent = node.parentElement;
        if (!parent || parent.closest(SKIP_SELECTOR)) return;
        const next = convertText(originalTextOf(node));
        if (node.nodeValue !== next) node.nodeValue = next;
    }

    function convertAllIn(root) {
        if (!root) return;
        if (root.nodeType === Node.TEXT_NODE) {
            convertTextNode(root);
            return;
        }
        if (root.nodeType !== Node.ELEMENT_NODE) return;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) convertTextNode(walker.currentNode);
    }

    function applyScriptToPage() {
        convertAllIn(document.body);
    }

    function restoreOriginals(root) {
        if (!root || root.nodeType !== Node.ELEMENT_NODE) return;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            const node = walker.currentNode;
            const original = _originals.get(node);
            if (original !== undefined && node.nodeValue !== original) {
                node.nodeValue = original;
            }
        }
    }

    function loadOpenCC(callback) {
        if (window.OpenCC) { callback(window.OpenCC); return; }
        _openccCallbacks.push(callback);
        if (_openccLoading) return;
        _openccLoading = true;
        const s = document.createElement('script');
        s.src = OPENCC_CDN;
        s.onload = () => {
            _openccLoading = false;
            const cbs = _openccCallbacks.splice(0);
            cbs.forEach(cb => cb(window.OpenCC));
        };
        s.onerror = () => {
            _openccLoading = false;
            _openccCallbacks = [];
            console.warn('Failed to load opencc-js');
        };
        document.head.appendChild(s);
    }

    function applyScript(script) {
        const select = document.getElementById('hanzi-script-select');
        if (select && select.value !== script) select.value = script;

        if (script === 'traditional') {
            loadOpenCC(OpenCC => {
                _converter = OpenCC.Converter({ from: 'cn', to: 'tw' });
                applyScriptToPage();
            });
        } else {
            _converter = null;
            applyScriptToPage();
        }
    }

    function startObserver() {
        if (!window.MutationObserver) return;
        const observer = new MutationObserver(mutations => {
            if (!_converter) return;
            for (const mut of mutations) {
                for (const node of mut.addedNodes) {
                    convertAllIn(node);
                }
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    async function loadSavedFont() {
        const select = document.getElementById('hanzi-font-select');
        applyFont(select?.dataset.currentFont || DEFAULT_FONT);
        if (!select) return;
        try {
            const res = await fetch('/api/user/hanzi-font');
            const data = await res.json();
            if (res.ok && data.hanzi_font) applyFont(data.hanzi_font);
        } catch (_) { }
    }

    async function loadSavedScript() {
        const select = document.getElementById('hanzi-script-select');
        if (!select) return;
        applyScript(select.dataset.currentScript || DEFAULT_SCRIPT);
        try {
            const res = await fetch('/api/user/hanzi-script');
            const data = await res.json();
            if (res.ok && data.hanzi_script) applyScript(data.hanzi_script);
        } catch (_) { }
    }

    async function saveFont(font) {
        applyFont(font);
        try {
            const res = await fetch('/api/user/hanzi-font', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hanzi_font: font }),
            });
            const data = await res.json();
            if (res.ok && data.hanzi_font) applyFont(data.hanzi_font);
        } catch (e) { console.warn('Could not save Hanzi font:', e); }
    }

    async function saveScript(script) {
        applyScript(script);
        try {
            await fetch('/api/user/hanzi-script', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hanzi_script: script }),
            });
        } catch (e) { console.warn('Could not save Hanzi script:', e); }
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadSavedFont();
        loadSavedScript();
        startObserver();
        document.getElementById('hanzi-font-select')?.addEventListener('change', e => saveFont(e.target.value));
        document.getElementById('hanzi-script-select')?.addEventListener('change', e => saveScript(e.target.value));
    });

    window.HanziFont = { applyFont };
    window.HanziSettings = { applyFont, applyScript, convertText, restoreOriginals };
})();
