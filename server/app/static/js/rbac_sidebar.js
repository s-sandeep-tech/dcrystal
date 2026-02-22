document.addEventListener('DOMContentLoaded', async () => {
    const sidebarContainer = document.getElementById('dynamicSidebarMenu');

    // Check if we already have menus cached in localStorage to prevent flicker
    const cachedMenusStr = localStorage.getItem('rbac_menus');
    if (cachedMenusStr) {
        try {
            renderSidebar(JSON.parse(cachedMenusStr));
        } catch (e) {
            console.error('Failed to parse cached menus', e);
        }
    }

    try {
        const token = localStorage.getItem('access_token');
        if (!token) return;

        const response = await fetch('/api/auth/me/menus', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            const newMenusStr = JSON.stringify(data.menus);
            const newPermsStr = JSON.stringify(data.permissions);

            // Store globally for other scripts
            window.rbacPermissions = data.permissions;

            // Smart Update: Only re-render and update cache if something changed
            if (newMenusStr !== cachedMenusStr) {
                console.log('RBAC: Menu changes detected, updating sidebar...');
                localStorage.setItem('rbac_menus', newMenusStr);
                localStorage.setItem('rbac_perms', newPermsStr);
                renderSidebar(data.menus);
            } else {
                // Permissions might have changed even if menu structure didn't (rare but possible)
                localStorage.setItem('rbac_perms', newPermsStr);
            }

            // Dispatch event so other components know RBAC is loaded
            document.dispatchEvent(new CustomEvent('rbacLoaded'));
        } else if (response.status === 401) {
            // Handled by global fetch interceptor in base.js
        } else {
            console.error('Failed to fetch menus:', response.status);
            if (!cachedMenusStr) {
                sidebarContainer.innerHTML = `<div class="text-[10px] text-red-500 text-center px-2">Menu Load Failed</div>`;
            }
        }
    } catch (error) {
        console.error('Error fetching RBAC menus:', error);
    }
});

function renderSidebar(menus) {
    const sidebarContainer = document.getElementById('dynamicSidebarMenu');
    if (!sidebarContainer) return;

    let html = '';
    const currentPath = window.location.pathname;

    menus.forEach(menu => {
        // Simple 1-level sidebar rendering for now based on base.html structure
        // If it has children, you might want an accordion, but sticking to existing design:
        const isActive = currentPath === menu.url || (menu.url !== '/' && currentPath.startsWith(menu.url));
        const activeClass = isActive ? 'bg-primary/10 text-primary' : 'text-gray-400 hover:text-primary';

        let targetUrl = menu.url || '#';

        html += `
            <a class="p-2 rounded ${activeClass} transition-colors relative group" 
               href="${targetUrl}" 
               title="${menu.title}">
                <span class="material-symbols-outlined">${menu.icon || 'circle'}</span>
                
                <!-- Tooltip for collapsed sidebar -->
                <div class="absolute left-full ml-2 top-1/2 -translate-y-1/2 px-2 py-1 bg-gray-900 text-white text-[10px] rounded opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-[100]">
                    ${menu.title}
                </div>
            </a>
        `;

        // If we want to render children inline (flattened for this specific UI)
        if (menu.children && menu.children.length > 0) {
            menu.children.forEach(child => {
                const isChildActive = currentPath === child.url;
                const childActiveClass = isChildActive ? 'bg-primary/10 text-primary' : 'text-gray-400 hover:text-primary';
                html += `
                    <a class="p-2 rounded ${childActiveClass} transition-colors relative group ml-2 scale-90" 
                       href="${child.url || '#'}" 
                       title="${child.title}">
                        <span class="material-symbols-outlined">${child.icon || 'subdirectory_arrow_right'}</span>
                        <div class="absolute left-full ml-2 top-1/2 -translate-y-1/2 px-2 py-1 bg-gray-900 text-white text-[10px] rounded opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-[100]">
                            ${child.title}
                        </div>
                    </a>
                `;
            });
        }
    });

    sidebarContainer.innerHTML = html;
}

// Global utility func to check permissions in JS
window.hasPermission = function (permName) {
    const cached = localStorage.getItem('rbac_perms');
    if (!cached) return false;
    const perms = JSON.parse(cached);
    return perms.includes('ADMIN') || perms.includes(permName);
};
