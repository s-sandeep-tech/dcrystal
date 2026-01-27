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

let currentZoom = parseFloat(localStorage.getItem('shortstatus-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('shortstatus-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

// View Toggling logic with AJAX loading
async function setView(view) {
    localStorage.setItem('shortstatus-view', view);

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
        await loadViewData(view);
    }
}

async function loadViewData(view) {
    const activeView = document.getElementById('view-' + view);
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/shortstatus/partial?${searchParams}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch view');
        const html = await response.text();

        // Inject HTML and mark as loaded
        activeView.innerHTML = html;

        // Parse stats metadata if present
        const statsScript = activeView.querySelector('#stats-metadata');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent);
                updateDashboardStats(stats);
            } catch (e) {
                console.error('Error parsing stats metadata:', e);
            }
        }

        // Parse pagination metadata
        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
        }

        // Re-initialize any expanded rows
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

function updateDashboardStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-total-items': stats.total_items,
        'stat-total-weight': stats.total_weight,
        'stat-unique-products': stats.unique_products,
        'stat-avg-weight': stats.avg_weight
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) el.textContent = value || '0';
    }
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const filters = {
        'division': 'filter-division',
        'group': 'filter-group',
        'purity': 'filter-purity',
        'classification': 'filter-classification',
        'make': 'filter-make',
        'collection': 'filter-collection',
        'section': 'filter-section',
        'product_type': 'filter-product-type'
    };

    for (const [key, id] of Object.entries(filters)) {
        const val = document.getElementById(id)?.value;
        if (val) urlParams.set(key, val);
        else urlParams.delete(key);
    }

    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    const currentView = localStorage.getItem('shortstatus-view') || 'make';
    loadViewData(currentView);
}

function resetGlobalFilters() {
    const filters = [
        'filter-division', 'filter-group', 'filter-purity',
        'filter-classification', 'filter-make', 'filter-collection',
        'filter-section', 'filter-product-type'
    ];
    filters.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = "";
    });

    const urlParams = new URL(window.location.href).searchParams;
    filters.forEach(id => urlParams.delete(id.replace('filter-', '')));
    urlParams.set('page', 1);

    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    const currentView = localStorage.getItem('shortstatus-view') || 'make';
    loadViewData(currentView);
}

function setDatePreset(preset) {
    const urlParams = new URL(window.location.href).searchParams;
    urlParams.set('date_range', preset);
    urlParams.set('page', 1);

    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.remove('border-primary', 'bg-primary/5', 'text-primary');
        btn.classList.add('border-gray-200', 'dark:border-gray-700');
    });
    const activeBtn = document.getElementById('preset-' + preset);
    if (activeBtn) {
        activeBtn.classList.add('border-primary', 'bg-primary/5', 'text-primary');
    }

    const currentView = localStorage.getItem('shortstatus-view') || 'make';
    loadViewData(currentView);
}

function updatePaginationControls(meta) {
    const page = parseInt(meta.page);
    const perPage = parseInt(meta.perPage);
    const total = parseInt(meta.total);
    const hasPrev = meta.hasPrev === 'true';
    const hasNext = meta.hasNext === 'true';
    const prevNum = meta.prevNum;
    const nextNum = meta.nextNum;

    const start = (page - 1) * perPage + 1;
    const end = Math.min(page * perPage, total);
    const infoSpan = document.getElementById('pagination-info');
    if (infoSpan) {
        infoSpan.textContent = total > 0 ? `${start}-${end} of ${total}` : '0-0 of 0';
    }

    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');

    if (btnPrev) {
        btnPrev.disabled = !hasPrev;
        btnPrev.onclick = hasPrev ? () => changePage(prevNum) : null;
        btnPrev.classList.toggle('opacity-50', !hasPrev);
        btnPrev.classList.toggle('cursor-not-allowed', !hasPrev);
    }

    if (btnNext) {
        btnNext.disabled = !hasNext;
        btnNext.onclick = hasNext ? () => changePage(nextNum) : null;
        btnNext.classList.toggle('opacity-50', !hasNext);
        btnNext.classList.toggle('cursor-not-allowed', !hasNext);
    }

    const select = document.getElementById('per-page-select');
    if (select) select.value = perPage;
}

function changePerPage(perPage) {
    if (!perPage) return;
    const urlParams = new URL(window.location.href).searchParams;
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    const currentView = localStorage.getItem('shortstatus-view') || 'make';
    loadViewData(currentView);
}

function changePage(page) {
    if (!page) return;
    const urlParams = new URL(window.location.href).searchParams;
    urlParams.set('page', page);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    const currentView = localStorage.getItem('shortstatus-view') || 'make';
    loadViewData(currentView);
}

let filterOptionsLoaded = false;
function initFilterListeners() {
    const filters = [
        'filter-division', 'filter-group', 'filter-purity', 'filter-classification',
        'filter-make', 'filter-collection', 'filter-section', 'filter-product-type'
    ];

    filters.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('focus', () => {
                if (!filterOptionsLoaded) {
                    loadFilterOptions();
                }
            }, { once: true });
        }
    });
}

async function loadFilterOptions() {
    if (filterOptionsLoaded) return;

    const filters = {
        'divisions': 'filter-division',
        'groups': 'filter-group',
        'purities': 'filter-purity',
        'classifications': 'filter-classification',
        'makes': 'filter-make',
        'collections': 'filter-collection',
        'sections': 'filter-section',
        'product_types': 'filter-product-type'
    };

    Object.values(filters).forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.dataset.pendingValue = el.value;
            el.innerHTML = `<option value="">Loading...</option>`;
            el.disabled = true;
        }
    });

    try {
        const response = await fetch('/api/shortstatus/options', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) throw new Error('Failed to fetch options');
        const options = await response.json();

        const mapping = {
            'divisions': 'All Divisions', 'groups': 'All Groups', 'purities': 'All Purities',
            'classifications': 'All Classifications', 'makes': 'All Makes', 'collections': 'All Collections',
            'sections': 'All Sections', 'product_types': 'All Product Types'
        };

        for (const [key, id] of Object.entries(filters)) {
            const el = document.getElementById(id);
            if (el && options[key]) {
                const pendingValue = el.dataset.pendingValue;
                let html = `<option value="">${mapping[key]}</option>`;
                options[key].forEach(opt => {
                    html += `<option value="${opt}" ${opt === pendingValue ? 'selected' : ''}>${opt}</option>`;
                });
                el.innerHTML = html;
                el.disabled = false;
            }
        }
        filterOptionsLoaded = true;
    } catch (error) {
        console.error('Error loading filter options:', error);
        Object.values(filters).forEach(id => {
            const el = document.getElementById(id);
            if (el) el.disabled = false;
        });
    }
}

// Initialize rows
document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    const savedView = localStorage.getItem('shortstatus-view') || 'make';
    setView(savedView);

    initFilterListeners();
});
