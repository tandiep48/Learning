document.addEventListener('DOMContentLoaded', () => {
    loadProfileSummary();
    const form = document.getElementById('avatar-form');
    if (form) {
        form.addEventListener('submit', uploadAvatar);
    }
});

async function loadProfileSummary() {
    try {
        const res = await fetch('/api/user/profile-summary');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to load profile.');
        renderProfile(data);
    } catch (e) {
        setAvatarMessage(e.message || 'Failed to load profile.', 'error');
    }
}

function renderProfile(data) {
    renderAvatar(data.user?.avatar_url);
    const totals = data.time_totals_ms || {};
    document.getElementById('stat-vocab-time').textContent = formatDuration(totals.vocab || 0);
    document.getElementById('stat-lesson-time').textContent = formatDuration(totals.lesson || 0);
    document.getElementById('stat-practice-time').textContent = formatDuration(totals.practice || 0);
    document.getElementById('stat-exam-time').textContent = formatDuration(totals.exam || 0);

    renderBreakdown('vocab-breakdown', data.vocab_mode_time_ms || [], item => item.mode);
    renderBreakdown('lesson-breakdown', data.lesson_mode_time_ms || [], item => item.mode);
    renderBreakdown('practice-breakdown', data.practice_skill_time_ms || [], item => `${item.category} ${item.skill}`);
    renderLearnedWords(data.learned_words || []);
}

function renderAvatar(url) {
    const img = document.getElementById('profile-avatar-img');
    const fallback = document.getElementById('profile-avatar-fallback');
    if (url) {
        img.src = url;
        img.style.display = 'block';
        fallback.style.display = 'none';
    } else {
        img.removeAttribute('src');
        img.style.display = 'none';
        fallback.style.display = 'flex';
    }
}

function renderBreakdown(id, rows, labelFn) {
    const container = document.getElementById(id);
    if (!container) return;
    if (!rows.length) {
        container.innerHTML = '<div class="profile-list-row"><span>No time yet</span><strong>0m</strong></div>';
        return;
    }
    container.innerHTML = rows.map(row => `
        <div class="profile-list-row">
            <span>${escapeHtml(labelFn(row))}</span>
            <strong>${formatDuration(row.time_ms || 0)}</strong>
        </div>
    `).join('');
}

function renderLearnedWords(words) {
    const count = document.getElementById('learned-count');
    const list = document.getElementById('learned-vocab-list');
    count.textContent = `${words.length} word${words.length === 1 ? '' : 's'}`;
    if (!words.length) {
        list.innerHTML = '<div class="profile-list-row"><span>No mastered vocabulary yet.</span></div>';
        return;
    }
    list.innerHTML = words.map(item => `
        <div class="profile-vocab-chip">
            <div class="profile-vocab-word">${escapeHtml(item.word || '')}</div>
            <div class="profile-vocab-date">${formatDate(item.learned_at)}</div>
        </div>
    `).join('');
}

async function uploadAvatar(e) {
    e.preventDefault();
    const input = document.getElementById('avatar-input');
    if (!input.files.length) {
        setAvatarMessage('Choose an avatar file first.', 'error');
        return;
    }
    const formData = new FormData();
    formData.append('avatar', input.files[0]);
    setAvatarMessage('Uploading...', '');

    try {
        const res = await fetch('/api/user/avatar', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Upload failed.');
        renderAvatar(data.avatar_url);
        setAvatarMessage('Avatar updated.', 'success');
        input.value = '';
    } catch (err) {
        setAvatarMessage(err.message || 'Upload failed.', 'error');
    }
}

function setAvatarMessage(message, type) {
    const el = document.getElementById('avatar-message');
    el.textContent = message;
    el.className = `profile-message ${type || ''}`;
}

function formatDuration(ms) {
    const seconds = Math.round((Number(ms) || 0) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    if (minutes < 60) return remainingSeconds ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return remainingMinutes ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

function formatDate(value) {
    if (!value) return 'Date unknown';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Date unknown';
    return date.toLocaleDateString();
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
