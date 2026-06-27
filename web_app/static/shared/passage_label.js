(function () {
    function formatPassageLabel(passageId, fallback = '') {
        const raw = String(passageId || '').trim();
        const parts = raw.split('_');
        if (parts.length >= 3) {
            const hsk = parts[0].replace(/^H/i, '');
            return `HSK ${hsk} - lesson ${parts[1]} - ${parts[2]}`;
        }
        return fallback || raw;
    }

    window.formatPassageLabel = formatPassageLabel;
})();
