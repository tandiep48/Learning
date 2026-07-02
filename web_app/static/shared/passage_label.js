(function () {
    function formatPassageLabel(passageId, fallback = '') {
        const raw = String(passageId || '').trim();
        if (raw === 'H1_5_99') return 'HSK 1 - Lesson 5 - Number';
        const parts = raw.split('_');
        if (parts.length >= 3) {
            const hsk = parts[0].replace(/^H/i, '');
            return `HSK ${hsk} - lesson ${parts[1]} - ${parts[2]}`;
        }
        return fallback || raw;
    }

    /**
     * Renders a breadcrumb into `containerId` based on the passageId.
     * Crumbs: HSK N → Lesson N → Part N  (each clickable to go back to that picker screen)
     */
    function buildBreadcrumb(containerId, passageId) {
        const el = document.getElementById(containerId);
        if (!el || !passageId) return;

        const raw   = String(passageId).trim();
        const parts = raw.split('_');
        if (parts.length < 3) { el.innerHTML = ''; return; }

        const hskCode   = parts[0];                              // e.g. H1
        const hskNum    = hskCode.replace(/^H/i, '');           // e.g. 1
        const lessonNum = parts[1];                              // e.g. 2
        const partNum   = parts[2];                             // e.g. 1
        const partLabel = raw === 'H1_5_99' ? 'Number' : `Part ${partNum}`;

        // Build URLs so each crumb navigates back to the right picker state
        const hskUrl    = `/learning`;
        const lessonUrl = `/learning?passage_id=${encodeURIComponent(raw)}&show_parts=false&pick=hsk`;
        const partUrl   = `/learning?passage_id=${encodeURIComponent(raw)}&show_parts=false`;

        el.innerHTML = `
          <nav class="breadcrumb" aria-label="breadcrumb">
            <div class="breadcrumb-item">
              <a href="${hskUrl}" title="Select HSK level">HSK ${hskNum}</a>
            </div>
            <span class="breadcrumb-sep">›</span>
            <div class="breadcrumb-item">
              <a href="${partUrl}" title="Select lesson">Lesson ${lessonNum}</a>
            </div>
            <span class="breadcrumb-sep">›</span>
            <div class="breadcrumb-item active" aria-current="page">${partLabel}</div>
          </nav>`;
    }

    window.formatPassageLabel = formatPassageLabel;
    window.buildBreadcrumb    = buildBreadcrumb;
})();
