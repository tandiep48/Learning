/* ============================================================
   PRACTICE PAGE SHELL – sidebar design (all questions listed, jump
   to any of them; bottom nav is Check + Finish only). Used by direct
   practice/exam entry (/practice/<number>/<lesson_id>[/<progress>]).
   Question rendering, audio, and scoring live in practice_engine.js,
   loaded before this file.
   ============================================================ */

function setNavBtn(id, visible) {
    const el = document.getElementById(id);
    if (el) el.style.display = visible ? '' : 'none';
}

// 'unanswered' | 'correct' | 'incorrect' — pure query over engine state,
// reused by the sidebar to render each question's status.
function groupStatus(i) {
    const entry = groupSaved[i];
    if (!entry || !entry.checked) return 'unanswered';
    return entry.correctCount === entry.correctTotal ? 'correct' : 'incorrect';
}

function jumpToGroup(i) {
    if (i < 0 || i >= groups.length) return;
    currentGroupIndex = i;
    renderGroup();
}

function renderSidebar() {
    const list = document.getElementById('ps-sidebar-list');
    list.innerHTML = '';
    groups.forEach((g, i) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'ps-sidebar-item';
        item.textContent = i + 1;
        item.setAttribute('aria-label', t('practice.question_number', { n: i + 1 }));
        item.onclick = () => jumpToGroup(i);
        list.appendChild(item);
    });
    updateSidebar();
}

function updateSidebar() {
    const items = document.querySelectorAll('#ps-sidebar-list .ps-sidebar-item');
    items.forEach((item, i) => {
        const status = groupStatus(i);
        item.classList.toggle('correct', status === 'correct');
        item.classList.toggle('incorrect', status === 'incorrect');
        item.classList.toggle('active', i === currentGroupIndex);
        item.innerHTML = status === 'correct'
            ? '<i class="fa-solid fa-check" aria-hidden="true"></i>'
            : status === 'incorrect'
                ? '<i class="fa-solid fa-xmark" aria-hidden="true"></i>'
                : String(i + 1);
    });
}

function updateNav() {
    const idx = currentGroupIndex;
    const checked = !!groupSaved[idx]?.checked;
    const everyChecked = allGroupsChecked();

    setNavBtn('btn-check', !checked);
    setNavBtn('btn-finish', everyChecked);

    const checkBtn = document.getElementById('btn-check');
    if (checkBtn && !checked) checkBtn.textContent = t('practice.check');
    if (!checked) updateCheckButton();

    const checkedCount = groups.filter((_, i) => groupSaved[i]?.checked).length;
    document.getElementById('progress-fill').style.width =
        Math.round((checkedCount / groups.length) * 100) + '%';

    updateSidebar();
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
        renderSidebar();
        renderGroup();
        showScreen('screen-practice');
    } catch (e) {
        alert(t('practice.load_failed'));
    }
}

// ── Boot ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
