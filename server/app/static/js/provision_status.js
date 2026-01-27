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

// AJAX Data Loading
async function loadProvisionData() {
    const loadingOverlay = document.getElementById('loading-overlay');
    const tableArea = document.getElementById('table-area');
    if (loadingOverlay) loadingOverlay.classList.remove('hidden');
    if (loadingOverlay) loadingOverlay.classList.add('flex');

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/provisionstatus/partial?${searchParams}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch report');
        const html = await response.text();

        if (tableArea) tableArea.innerHTML = html;

        // Update stats from the partial's metadata
        const statsScript = tableArea?.querySelector('#stats-metadata');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent);
                updateHeaderStats(stats);
            } catch (e) {
                console.error('Error parsing stats metadata:', e);
            }
        }

        // Update URL state
        window.history.pushState({}, '', window.location.pathname + '?' + searchParams);

    } catch (error) {
        console.error('Error loading report:', error);
        if (tableArea) {
            tableArea.innerHTML = `
                <div class="flex flex-col items-center justify-center h-64 text-red-500">
                    <span class="material-symbols-outlined text-4xl">error</span>
                    <p class="text-[11px] mt-2 font-bold uppercase">Error loading report. Please try again.</p>
                </div>
            `;
        }
    } finally {
        if (loadingOverlay) {
            loadingOverlay.classList.add('hidden');
            loadingOverlay.classList.remove('flex');
        }
    }
}

function updateHeaderStats(stats) {
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

// Pagination and Filtering handlers
function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    const filters = {
        'division': 'filter-division',
        'group': 'filter-group',
        'purity': 'filter-purity',
        'classification': 'filter-classification',
        'make': 'filter-make',
        'collection': 'filter-collection',
        'party': 'filter-party',
        'section': 'filter-section',
        'product_type': 'filter-product-type',
        'business_head': 'filter-business-head'
    };

    for (const [key, id] of Object.entries(filters)) {
        const val = document.getElementById(id)?.value;
        if (val) urlParams.set(key, val);
        else urlParams.delete(key);
    }

    const searchVal = document.getElementById('hierarchy-search')?.value;
    if (searchVal) urlParams.set('search', searchVal);
    else urlParams.delete('search');

    urlParams.set('page', 1); // Reset to first page on filter change

    // Using AJAX instead of window.location.href
    const newUrl = window.location.pathname + '?' + urlParams.toString();
    window.history.replaceState({}, '', newUrl); // Update URL params before fetch
    loadProvisionData();
}

function resetGlobalFilters() {
    const filters = [
        'filter-division', 'filter-group', 'filter-purity',
        'filter-classification', 'filter-make', 'filter-collection',
        'filter-party', 'filter-section', 'filter-product-type',
        'filter-business-head', 'hierarchy-search'
    ];
    filters.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = "";
    });

    window.history.replaceState({}, '', window.location.pathname);
    loadProvisionData();
}

function changePage(page) {
    if (!page) return;
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    window.history.replaceState({}, '', window.location.pathname + '?' + urlParams.toString());
    loadProvisionData();
}

function applyFilters() {
    // This handles per-page changes (design consistent with short_status)
    const urlParams = new URLSearchParams(window.location.search);
    const perPage = document.getElementById('per-page-select')?.value;
    if (perPage) urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    window.history.replaceState({}, '', window.location.pathname + '?' + urlParams.toString());
    loadProvisionData();
}

let searchTimeout;
function onSearchInput(value) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        applyGlobalFilters();
    }, 500);
}

// AJAX Filter Options Loading
async function loadFilterOptions() {
    try {
        const response = await fetch('/api/provisionstatus/options', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch filter options');
        const data = await response.json();

        const urlParams = new URLSearchParams(window.location.search);

        const mappings = {
            'divisions': { id: 'filter-division', param: 'division' },
            'groups': { id: 'filter-group', param: 'group' },
            'purities': { id: 'filter-purity', param: 'purity' },
            'classifications': { id: 'filter-classification', param: 'classification' },
            'makes': { id: 'filter-make', param: 'make' },
            'collections': { id: 'filter-collection', param: 'collection' },
            'parties': { id: 'filter-party', param: 'party' },
            'sections': { id: 'filter-section', param: 'section' },
            'product_types': { id: 'filter-product-type', param: 'product_type' },
            'business_heads': { id: 'filter-business-head', param: 'business_head' }
        };

        for (const [key, config] of Object.entries(mappings)) {
            const select = document.getElementById(config.id);
            if (!select) continue;

            const activeVal = urlParams.get(config.param);

            // Keep first option (All...)
            const firstOption = select.options[0];
            select.innerHTML = '';
            select.appendChild(firstOption);

            if (data[key]) {
                data[key].forEach(opt => {
                    const option = document.createElement('option');
                    option.value = opt;
                    option.textContent = opt;
                    if (opt === activeVal) option.selected = true;
                    select.appendChild(option);
                });
            }
        }
    } catch (error) {
        console.error('Error loading filter options:', error);
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

    // Sync search input from URL
    const urlParams = new URLSearchParams(window.location.search);
    const searchVal = urlParams.get('search');
    const searchInput = document.getElementById('hierarchy-search');
    if (searchInput && searchVal) {
        searchInput.value = searchVal;
    }

    // Load dynamic filters
    loadFilterOptions();

    // Initial load of provision data
    loadProvisionData();
});
