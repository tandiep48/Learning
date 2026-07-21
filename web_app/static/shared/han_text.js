(function () {
    // A run is one or more Han ideographs plus adjacent CJK punctuation/fullwidth chars.
    // ASCII digits (0-9) and spaces are included as "surrounding" chars so numbers embedded in
    // Chinese text (e.g. 9\u70b925, 300 \u5143) get sized with the hanzi. A run still requires at least
    // one ideograph, so standalone Latin-context numbers (1. 2.) are left untouched.
    const HAN_TEXT_RE = /([\u3000-\u303f\uff00-\uff65 0-9]*[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff][\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uff65 0-9]*)/g;
    const SIZED_CLASS = 'hsk-sized-han';
    const HAN_CLASS = 'han-text';
    const WRAPPED_ATTR = 'data-han-text';
    const SKIP_SELECTOR = [
        'script',
        'style',
        'textarea',
        'input',
        'select',
        '[data-han-skip]'
    ].join(',');

    function normalizeHskLevel(level) {
        const match = String(level || '').match(/(?:HSK|H)?\s*(\d+)/i);
        return match ? Number(match[1]) : null;
    }

    function fontSizeForLevel(level) {
        const hsk = normalizeHskLevel(level);
        if (hsk === 1 || hsk === 2) return '32px';
        if (hsk === 3 || hsk === 4) return '28px';
        if (hsk === 5 || hsk === 6) return '24px';
        return '';
    }

    function unwrapExisting(container) {
        container.querySelectorAll(`[${WRAPPED_ATTR}]`).forEach(span => {
            span.replaceWith(document.createTextNode(span.getAttribute('data-original') || span.textContent || ''));
        });
    }

    function shouldSkipTextNode(node) {
        const parent = node.parentElement;
        HAN_TEXT_RE.lastIndex = 0;
        if (!parent || !node.nodeValue || !HAN_TEXT_RE.test(node.nodeValue)) {
            HAN_TEXT_RE.lastIndex = 0;
            return true;
        }
        HAN_TEXT_RE.lastIndex = 0;
        return Boolean(parent.closest(SKIP_SELECTOR));
    }

    function wrapTextNode(node, shouldSize) {
        const text = node.nodeValue;
        const fragment = document.createDocumentFragment();
        let lastIndex = 0;

        text.replace(HAN_TEXT_RE, (match, _group, offset) => {
            if (offset > lastIndex) {
                fragment.appendChild(document.createTextNode(text.slice(lastIndex, offset)));
            }

            const span = document.createElement('span');
            span.className = shouldSize ? `${HAN_CLASS} ${SIZED_CLASS}` : HAN_CLASS;
            span.setAttribute(WRAPPED_ATTR, 'true');
            span.setAttribute('data-original', match);
            span.textContent = window.HanziSettings?.convertText(match) ?? match;
            fragment.appendChild(span);
            lastIndex = offset + match.length;
            return match;
        });

        if (lastIndex < text.length) {
            fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
        }

        node.replaceWith(fragment);
    }

    function apply(container, hskLevel) {
        if (!container) return;
        const size = fontSizeForLevel(hskLevel);

        if (size) {
            container.style.setProperty('--han-content-size', size);
        } else {
            container.style.removeProperty('--han-content-size');
        }

        unwrapExisting(container);
        window.HanziSettings?.restoreOriginals?.(container);

        const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
            acceptNode(node) {
                return shouldSkipTextNode(node)
                    ? NodeFilter.FILTER_REJECT
                    : NodeFilter.FILTER_ACCEPT;
            }
        });

        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach(node => wrapTextNode(node, Boolean(size)));
    }

    window.HanText = {
        apply,
        fontSizeForLevel,
        normalizeHskLevel
    };
})();
