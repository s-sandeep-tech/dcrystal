// Auth Check - Execute immediately
if (!localStorage.getItem('access_token') && window.location.pathname !== '/login') {
    window.location.href = '/login';
}

async function handleLogout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
    } catch (e) { console.error('Logout sync failed', e); }
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
}

document.addEventListener('DOMContentLoaded', () => {
    // User Identity & Avatar
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    const avatarEl = document.getElementById('userAvatar');
    if (avatarEl && user.username) {
        avatarEl.textContent = user.username.substring(0, 2).toUpperCase();
        avatarEl.setAttribute('title', user.username);
    }

    // Logout Buttons
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }

    const logoutBtnHeader = document.getElementById('logoutBtnHeader');
    if (logoutBtnHeader) {
        logoutBtnHeader.addEventListener('click', handleLogout);
    }

    // User Menu Toggle
    const userMenuBtn = document.getElementById('userMenuBtn');
    const userDropdown = document.getElementById('userDropdown');

    if (userMenuBtn && userDropdown) {
        userMenuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            userDropdown.classList.toggle('hidden');
            // Close notification dropdown if open
            const notifDropdown = document.getElementById('notifDropdown');
            if (notifDropdown) notifDropdown.classList.add('hidden');
        });
    }

    // Global click to close dropdowns
    document.addEventListener('click', (e) => {
        const userMenuContainer = document.getElementById('userMenuContainer');
        if (userMenuContainer && !userMenuContainer.contains(e.target)) {
            const userDropdown = document.getElementById('userDropdown');
            if (userDropdown) userDropdown.classList.add('hidden');
        }
    });

    // Global fetch interceptor for 401s
    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
        const response = await originalFetch(...args);
        if (response.status === 401 && !args[0].includes('/api/auth/login')) {
            console.warn('Unauthorized request detected. Redirecting to login.');
            handleLogout();
        }
        return response;
    };
});
