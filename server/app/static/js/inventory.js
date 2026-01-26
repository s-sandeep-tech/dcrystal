function toggleRow(id) {
    const children = document.querySelectorAll('.child-' + id);
    const icon = document.getElementById('icon-' + id);
    if (children.length > 0) {
        const isHidden = children[0].classList.contains('hidden');
        children.forEach(row => {
            if (isHidden) {
                row.classList.remove('hidden');
            } else {
                row.classList.add('hidden');
            }
        });
        if (icon) {
            icon.textContent = isHidden ? 'expand_more' : 'chevron_right';
        }
    }
}

let currentZoom = parseFloat(localStorage.getItem('inventory-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('inventory-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

// View Toggling logic with AJAX loading
async function setView(view) {
    localStorage.setItem('inventory-view', view);

    // Update buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.remove('bg-white', 'dark:bg-gray-700', 'shadow-sm', 'text-primary');
        btn.classList.add('text-gray-500', 'hover:text-gray-700');
    });

    const activeBtn = document.getElementById('btn-' + view);
    if (activeBtn) {
        activeBtn.classList.add('bg-white', 'dark:bg-gray-700', 'shadow-sm', 'text-primary');
        activeBtn.classList.remove('text-gray-500', 'hover:text-gray-700');
    }

    // Toggle view containers
    const containers = document.querySelectorAll('.dashboard-view');
    containers.forEach(viewDiv => {
        viewDiv.classList.add('hidden');
    });

    const activeView = document.getElementById('view-' + view);
    if (activeView) {
        activeView.classList.remove('hidden');

        // Check if content needs to be loaded via AJAX
        if (activeView.getAttribute('data-loaded') === 'false') {
            try {
                const response = await fetch(`/partial/${view}`, {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                    }
                });
                if (!response.ok) throw new Error('Failed to fetch view');
                const html = await response.text();

                // Inject HTML and mark as loaded
                activeView.innerHTML = html;
                activeView.setAttribute('data-loaded', 'true');

                // Re-initialize any expanded rows in the new content if needed
                activeView.querySelectorAll('tr[class*="child-"]').forEach((row) => {
                    row.classList.add('hidden');
                });
            } catch (error) {
                console.error('Error loading view:', error);
                activeView.innerHTML = `
                    <div class="flex flex-col items-center justify-center h-64 text-red-500">
                        <span class="material-symbols-outlined text-4xl">error</span>
                        <p class="text-[11px] mt-2 font-bold uppercase">Error loading view. Please try again.</p>
                    </div>
                `;
            }
        }
    }
}

// Initialize rows
document.addEventListener('DOMContentLoaded', () => {
    // Apply saved zoom
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    // Apply saved view
    const savedView = localStorage.getItem('inventory-view') || 'make';
    setView(savedView);

    // Hide all child rows by default
    document.querySelectorAll('tr[class*="child-"]').forEach((row) => {
        row.classList.add('hidden');
    });

    // Optionally expand the first one for demonstration
    toggleRow('row1');
});
