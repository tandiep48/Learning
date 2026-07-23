/* ============================================================
   PRACTICE PAGE SHELL – bottom-nav design (Previous / Check / Skip / Finish).
   Used only by /practice/multi (recommend's entry point). Question
   rendering, audio, and scoring live in practice_engine.js, loaded
   before this file.
   ============================================================ */

function setNavBtn(id, visible) {
    const el = document.getElementById(id);
    if (el) el.style.display = visible ? '' : 'none';
}

function updateNav() {
    const idx = currentGroupIndex;
    const checked = !!groupSaved[idx]?.checked;
    const everyChecked = allGroupsChecked();

    setNavBtn('btn-prev', idx > 0);
    setNavBtn('btn-check', !checked);
    setNavBtn('btn-finish', everyChecked);
    setNavBtn('btn-next', !everyChecked && firstUncheckedAfter(idx) !== -1);

    const checkBtn = document.getElementById('btn-check');
    if (checkBtn && !checked) checkBtn.textContent = t('practice.check');
    if (!checked) updateCheckButton();

    const checkedCount = groups.filter((_, i) => groupSaved[i]?.checked).length;
    document.getElementById('progress-fill').style.width =
        Math.round((checkedCount / groups.length) * 100) + '%';
}

function goPrevGroup() {
    if (currentGroupIndex > 0) { currentGroupIndex--; renderGroup(); }
}
function goNextGroup() {
    const i = firstUncheckedAfter(currentGroupIndex);
    if (i !== -1) { currentGroupIndex = i; renderGroup(); }
}

// ── Init ────────────────────────────────────────────────────

async function init() {
    showScreen('screen-loading');

    // Context-aware Back button — read and clear referrer set by previous page
    const referrer = sessionStorage.getItem('practice_referrer');
    sessionStorage.removeItem('practice_referrer');
    const backBtn = document.querySelector('.p-back-btn');
    if (backBtn) {
        if (referrer === 'recommend') {
            backBtn.href = '/recommend';
            backBtn.title = t('practice_select.back_to_recommendations');
        } else if (referrer && referrer.startsWith('exam-')) {
            const lvl = referrer.split('-')[1];
            backBtn.href = `/practice/${lvl}?category=exam`;
            backBtn.title = t('practice.back_to_hsk_exam', { level: lvl });
        } else if (referrer && referrer.startsWith('practice-')) {
            const lvl = referrer.split('-')[1];
            backBtn.href = `/practice/${lvl}`;
            backBtn.title = t('practice.back_to_hsk_lessons', { level: lvl });
        } else {
            backBtn.href = '/practice';
            backBtn.title = t('practice.back_to_practice');
        }

        const resultBackBtn = document.getElementById('result-back-btn');
        if (resultBackBtn) {
            resultBackBtn.href = backBtn.href;
            resultBackBtn.textContent = '← ' + backBtn.title;
        }
    }

    try {
        const ok = await loadPracticeSession();
        if (!ok) return;
        renderGroup();
        showScreen('screen-practice');
    } catch (e) {
        alert(t('practice.load_failed'));
    }
}

// ── Boot ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
