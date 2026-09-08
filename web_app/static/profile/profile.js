document.addEventListener('DOMContentLoaded', () => {
    loadProfileSummary();

    const avatarForm = document.getElementById('avatar-form');
    if (avatarForm) {
        avatarForm.addEventListener('submit', uploadAvatar);
    }

    document.getElementById('avatar-trigger')?.addEventListener('click', openAvatarModal);
    document.querySelectorAll('[data-avatar-close]').forEach(el => {
        el.addEventListener('click', closeAvatarModal);
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeAvatarModal();
    });

    const passwordForm = document.getElementById('password-form');
    if (passwordForm) {
        passwordForm.addEventListener('submit', changePassword);
    }
});

function openAvatarModal() {
    const modal = document.getElementById('avatar-modal');
    if (modal) modal.hidden = false;
}

function closeAvatarModal() {
    const modal = document.getElementById('avatar-modal');
    if (modal) modal.hidden = true;
}

async function loadProfileSummary() {
    try {
        const res = await fetch('/api/user/profile-summary');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || t('profile.failed_load_profile'));
        renderAvatar(data.user?.avatar_url);
    } catch (e) {
        setAvatarMessage(e.message || t('profile.failed_load_profile'), 'error');
    }
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

async function uploadAvatar(e) {
    e.preventDefault();
    const input = document.getElementById('avatar-input');
    if (!input.files.length) {
        setAvatarMessage(t('profile.choose_avatar_first'), 'error');
        return;
    }
    const formData = new FormData();
    formData.append('avatar', input.files[0]);
    setAvatarMessage(t('profile.uploading'), '');

    try {
        const res = await fetch('/api/user/avatar', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || t('profile.upload_failed'));
        renderAvatar(data.avatar_url);
        setAvatarMessage(t('profile.avatar_updated'), 'success');
        input.value = '';
        setTimeout(closeAvatarModal, 800);
    } catch (err) {
        setAvatarMessage(err.message || t('profile.upload_failed'), 'error');
    }
}

async function changePassword(e) {
    e.preventDefault();
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;

    if (!newPassword || !confirmPassword) {
        setPasswordMessage(t('profile.new_password_required'), 'error');
        return;
    }

    if (newPassword !== confirmPassword) {
        setPasswordMessage(t('profile.passwords_do_not_match'), 'error');
        return;
    }

    setPasswordMessage(t('profile.updating_password'), '');
    try {
        const res = await fetch('/api/user/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_password: newPassword, confirm_password: confirmPassword })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || t('profile.could_not_update_password'));
        document.getElementById('new-password').value = '';
        document.getElementById('confirm-password').value = '';
        setPasswordMessage(t('profile.password_updated'), 'success');
    } catch (err) {
        setPasswordMessage(err.message || t('profile.could_not_update_password'), 'error');
    }
}

function setAvatarMessage(message, type) {
    const el = document.getElementById('avatar-message');
    el.textContent = message;
    el.className = `profile-message ${type || ''}`;
}

function setPasswordMessage(message, type) {
    const el = document.getElementById('password-message');
    el.textContent = message;
    el.className = `profile-message ${type || ''}`;
}
