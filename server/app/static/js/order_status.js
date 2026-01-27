function toggleRow(id) {
    const children = document.querySelectorAll('.child-' + id);
    const icon = document.getElementById('icon-' + id);
    const parentRow = icon ? icon.closest('tr') : null;
    const subExpanders = parentRow ? parentRow.querySelectorAll('.sub-expander') : [];

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

        subExpanders.forEach(se => {
            se.textContent = isHidden ? 'unfold_less' : 'unfold_more';
        });
    }
}

let currentZoom = parseFloat(localStorage.getItem('orderstatus-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('orderstatus-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

// View Toggling logic with AJAX loading
async function setView(view) {
    localStorage.setItem('orderstatus-view', view);

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
        // Always reload data when switching views to ensure pagination consistency if params changed
        // Or checks if data-loaded is false. 
        // If we switch views, we might want to reset to page 1 OR keep page.
        // Let's keep current URL params.
        await loadViewData(view);
    }
}

async function loadViewData(view) {
    const activeView = document.getElementById('view-' + view);
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/${view}?${searchParams}`, {
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
        'stat-total-orders': stats.total_orders,
        'stat-dispatched': stats.dispatched,
        'stat-in-process': stats.in_process,
        'stat-delayed': stats.delayed,
        'stat-active-slots': stats.active_slots,
        'stat-sla-index': stats.sla_index,
        'stat-quality-score': stats.quality_score,
        'stat-fulfillment-text': stats.fulfillment
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) el.textContent = value || '0';
    }

    const bar = document.getElementById('stat-fulfillment-bar');
    if (bar) {
        bar.style.width = stats.fulfillment || '0%';
    }
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    // Select Filters
    const filters = {
        'division': 'filter-division',
        'group': 'filter-group',
        'purity': 'filter-purity',
        'classification': 'filter-classification',
        'make': 'filter-make',
        'collection': 'filter-collection',
        'party': 'filter-party',
        'make_owner': 'filter-make-owner',
        'collection_owner': 'filter-collection-owner',
        'classification_owner': 'filter-classification-owner',
        'business_head': 'filter-business-head'
    };

    for (const [key, id] of Object.entries(filters)) {
        const val = document.getElementById(id)?.value;
        if (val) urlParams.set(key, val);
        else urlParams.delete(key);
    }

    // Search Filter
    const searchVal = document.getElementById('hierarchy-search')?.value;
    if (searchVal) urlParams.set('search', searchVal);
    else urlParams.delete('search');

    urlParams.set('page', 1); // Reset to page 1

    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    const currentView = localStorage.getItem('orderstatus-view') || 'make';
    loadViewData(currentView);
}

function resetGlobalFilters() {
    // Reset all select elements
    const selects = [
        'filter-division', 'filter-group', 'filter-purity',
        'filter-classification', 'filter-make', 'filter-collection', 'filter-party',
        'filter-make-owner', 'filter-collection-owner', 'filter-classification-owner', 'filter-business-head'
    ];
    selects.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = "";
    });

    // Reset search
    const search = document.getElementById('hierarchy-search');
    if (search) search.value = "";

    const urlParams = new URL(window.location.href).searchParams;
    const keysToDelete = [
        'division', 'group', 'purity', 'classification', 'make', 'collection', 'party',
        'search', 'make_owner', 'collection_owner', 'classification_owner', 'business_head'
    ];
    keysToDelete.forEach(k => urlParams.delete(k));
    urlParams.set('page', 1);

    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    const currentView = localStorage.getItem('orderstatus-view') || 'make';
    loadViewData(currentView);
}

function setDatePreset(preset) {
    const urlParams = new URL(window.location.href).searchParams;
    urlParams.set('date_range', preset);
    urlParams.set('page', 1);

    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    // Update buttons UI
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.remove('border-primary', 'bg-primary/5', 'text-primary');
        btn.classList.add('border-gray-200', 'dark:border-gray-700');
    });
    const activeBtn = document.getElementById('preset-' + preset);
    if (activeBtn) {
        activeBtn.classList.remove('border-gray-200', 'dark:border-gray-700');
        activeBtn.classList.add('border-primary', 'bg-primary/5', 'text-primary');
    }

    const currentView = localStorage.getItem('orderstatus-view') || 'make';
    loadViewData(currentView);
}

let searchTimeout;
function onSearchInput(value) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        applyGlobalFilters();
    }, 500);
}

function updatePaginationControls(meta) {
    const page = parseInt(meta.page);
    const perPage = parseInt(meta.perPage);
    const total = parseInt(meta.total);
    const hasPrev = meta.hasPrev === 'true';
    const hasNext = meta.hasNext === 'true';
    const prevNum = meta.prevNum;
    const nextNum = meta.nextNum;

    // Update Info Text
    const start = (page - 1) * perPage + 1;
    const end = Math.min(page * perPage, total);
    const infoSpan = document.getElementById('pagination-info');
    if (infoSpan) {
        infoSpan.textContent = total > 0 ? `${start}-${end} of ${total}` : '0-0 of 0';
    }

    // Update Buttons
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');

    if (btnPrev) {
        btnPrev.disabled = !hasPrev;
        if (hasPrev) {
            btnPrev.classList.remove('opacity-50', 'cursor-not-allowed');
            btnPrev.onclick = () => changePage(prevNum);
        } else {
            btnPrev.classList.add('opacity-50', 'cursor-not-allowed');
            btnPrev.onclick = null;
        }
    }

    if (btnNext) {
        btnNext.disabled = !hasNext;
        if (hasNext) {
            btnNext.classList.remove('opacity-50', 'cursor-not-allowed');
            btnNext.onclick = () => changePage(nextNum);
        } else {
            btnNext.classList.add('opacity-50', 'cursor-not-allowed');
            btnNext.onclick = null;
        }
    }

    // Update Select
    const select = document.getElementById('per-page-select');
    if (select) {
        select.value = perPage;
    }
}

function changePage(page) {
    if (!page) return;
    const urlParams = new URL(window.location.href).searchParams;
    urlParams.set('page', page);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    const currentView = localStorage.getItem('orderstatus-view') || 'make';
    loadViewData(currentView);
}

function changePerPage(perPage) {
    if (!perPage) return;
    const urlParams = new URL(window.location.href).searchParams;
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1); // Reset to first page
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    const currentView = localStorage.getItem('orderstatus-view') || 'make';
    loadViewData(currentView);
}

// Initialize rows
document.addEventListener('DOMContentLoaded', () => {
    // Apply saved zoom
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    // Apply saved view
    const savedView = localStorage.getItem('orderstatus-view') || 'make';
    setView(savedView);

    // Sync filters from URL to UI
    const urlParams = new URLSearchParams(window.location.search);
    const filters = {
        'division': 'filter-division',
        'group': 'filter-group',
        'purity': 'filter-purity',
        'classification': 'filter-classification',
        'make': 'filter-make',
        'collection': 'filter-collection',
        'party': 'filter-party',
        'make_owner': 'filter-make-owner',
        'collection_owner': 'filter-collection-owner',
        'classification_owner': 'filter-classification-owner',
        'business_head': 'filter-business-head'
    };
    for (const [key, id] of Object.entries(filters)) {
        const val = urlParams.get(key);
        if (val) {
            const el = document.getElementById(id);
            if (el) el.value = val;
        }
    }
    const searchVal = urlParams.get('search');
    if (searchVal) {
        const el = document.getElementById('hierarchy-search');
        if (el) el.value = searchVal;
    }

    const dateRange = urlParams.get('date_range');
    if (dateRange) {
        const activeBtn = document.getElementById('preset-' + dateRange);
        if (activeBtn) {
            activeBtn.classList.remove('border-gray-200', 'dark:border-gray-700');
            activeBtn.classList.add('border-primary', 'bg-primary/5', 'text-primary');
        }
    }

    initFilterListeners();
});

let globalOptionsLoaded = false;
function initFilterListeners() {
    const filters = [
        'filter-division', 'filter-group', 'filter-purity', 'filter-classification',
        'filter-make', 'filter-collection', 'filter-party', 'filter-make-owner',
        'filter-collection-owner', 'filter-classification-owner', 'filter-business-head'
    ];

    filters.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('focus', () => {
                if (!globalOptionsLoaded) {
                    loadFilterOptions();
                }
            }, { once: true });
        }
    });
}

async function loadFilterOptions() {
    if (globalOptionsLoaded) return;

    const filters = {
        'divisions': 'filter-division',
        'groups': 'filter-group',
        'purities': 'filter-purity',
        'classifications': 'filter-classification',
        'makes': 'filter-make',
        'collections': 'filter-collection',
        'parties': 'filter-party',
        'make_owners': 'filter-make-owner',
        'collection_owners': 'filter-collection-owner',
        'classification_owners': 'filter-classification-owner',
        'business_heads': 'filter-business-head'
    };

    // Show loading status in all selects
    Object.values(filters).forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            const currentVal = el.value;
            el.dataset.pendingValue = currentVal;
            el.innerHTML = `<option value="">Loading...</option>`;
            el.disabled = true;
        }
    });

    try {
        const response = await fetch('/api/orderstatus/options', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch options');
        const options = await response.json();

        const mapping = {
            'divisions': 'All Divisions',
            'groups': 'All Groups',
            'purities': 'All Purities',
            'classifications': 'All Classifications',
            'makes': 'All Makes',
            'collections': 'All Collections',
            'parties': 'All Parties',
            'make_owners': 'All Make Owners',
            'collection_owners': 'All Collection Owners',
            'classification_owners': 'All Class-Owners',
            'business_heads': 'All Business Heads'
        };

        // Populate selects
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
                delete el.dataset.pendingValue;
            }
        }
        globalOptionsLoaded = true;
    } catch (error) {
        console.error('Error loading filter options:', error);
        // Reset to initial state on error
        Object.values(filters).forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.disabled = false;
                // You might want to restore the "All ..." option here
            }
        });
    }
}
