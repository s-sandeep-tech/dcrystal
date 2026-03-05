let currentZoom = parseFloat(localStorage.getItem('orderpendingrejection-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.5), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('orderpendingrejection-zoom', currentZoom);

    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

function setDatePreset(days) {
    const urlParams = new URLSearchParams(window.location.search);
    if (days) {
        urlParams.set('days', days);
    } else {
        urlParams.delete('days');
    }
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
    updatePresetUI(days);
}

function updatePresetUI(days) {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.remove('bg-primary', 'text-white', 'border-primary');
        btn.classList.add('bg-white', 'dark:bg-gray-900', 'text-gray-700', 'dark:text-gray-300', 'border-gray-200', 'dark:border-gray-700');
    });

    if (days) {
        const activeBtn = document.getElementById(`preset-${days}d`);
        if (activeBtn) {
            activeBtn.classList.add('bg-primary', 'text-white', 'border-primary');
            activeBtn.classList.remove('bg-white', 'dark:bg-gray-900', 'text-gray-700', 'dark:text-gray-300', 'border-gray-200', 'dark:border-gray-700');
        }
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-report');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/orderpendingrejection?${searchParams}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Failed to fetch view: ${errorText}`);
        }
        const html = await response.text();
        activeView.innerHTML = html;

        // Parse pagination & Level from the meta div in partial
        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
            updateLevelBadge(metaDiv.dataset.level);
        }

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Error loading data: ${error.message}</div>`;
    }
}

function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge) {
        badge.textContent = (level || 'PARTY').replace('_', ' ');
    }
}

async function toggleRow(btn, level, value, grandparents = {}) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        // Collapse: Remove all logic-descendant rows
        let nextTr = tr.nextElementSibling;
        const levelOrder = ['party', 'purchase_ro', 'division', 'group', 'purity', 'classification', 'make', 'collection'];
        const currentLevelIdx = levelOrder.indexOf(level);

        while (nextTr) {
            const nextLevel = nextTr.dataset.level;
            const nextLevelIdx = levelOrder.indexOf(nextLevel);

            // If next row is at same level or higher in hierarchy, stop
            if (nextLevelIdx <= currentLevelIdx) break;

            const toRemove = nextTr;
            nextTr = nextTr.nextElementSibling;
            toRemove.remove();
        }
        icon.textContent = 'add_circle';
        tr.classList.remove('bg-blue-50/50');
    } else {
        // Expand: Fetch children
        icon.textContent = 'hourglass_empty';

        try {
            const urlParams = new URLSearchParams(window.location.search);
            const params = new URLSearchParams(urlParams);
            params.set('parent_level', level);
            params.set('parent_value', value);

            if (grandparents.grandparent_party) params.set('grandparent_party', grandparents.grandparent_party);
            if (grandparents.grandparent_ro) params.set('grandparent_ro', grandparents.grandparent_ro);
            if (grandparents.grandparent_division) params.set('grandparent_division', grandparents.grandparent_division);
            if (grandparents.grandparent_group) params.set('grandparent_group', grandparents.grandparent_group);
            if (grandparents.grandparent_purity) params.set('grandparent_purity', grandparents.grandparent_purity);
            if (grandparents.grandparent_classification) params.set('grandparent_classification', grandparents.grandparent_classification);
            if (grandparents.grandparent_make) params.set('grandparent_make', grandparents.grandparent_make);

            const response = await fetch(`/partial/orderpendingrejection?${params.toString()}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });

            if (!response.ok) throw new Error("Failed to load children");
            const html = await response.text();

            const template = document.createElement('template');
            template.innerHTML = html;
            const newRows = template.content.querySelectorAll('tr');

            let referenceNode = tr;
            newRows.forEach(newRow => {
                newRow.classList.add('child-row', 'animate-fade-in');
                referenceNode.parentNode.insertBefore(newRow, referenceNode.nextSibling);
                referenceNode = newRow;
            });

            icon.textContent = 'remove_circle';
            tr.classList.add('bg-blue-50/50');

        } catch (e) {
            console.error(e);
            icon.textContent = 'error';
        }
    }
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const filterIds = [
        'filter-classification-owner', 'filter-make-owner', 'filter-collection-owner',
        'filter-classification', 'filter-make', 'filter-collection',
        'filter-supplier', 'filter-order-ro', 'filter-batch',
        'filter-order-type', 'filter-order-request-type'
    ];

    filterIds.forEach(id => {
        const val = document.getElementById(id)?.value?.trim();
        const paramKey = id.replace('filter-', '').replace(/-/g, '_');
        if (val) urlParams.set(paramKey, val);
        else urlParams.delete(paramKey);
    });

    const activeDays = urlParams.get('days');
    if (activeDays) urlParams.set('days', activeDays);

    const searchVal = document.getElementById('hierarchy-search')?.value?.trim();
    if (searchVal) urlParams.set('search', searchVal);
    else urlParams.delete('search');

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const filterIds = [
        'filter-classification-owner', 'filter-make-owner', 'filter-collection-owner',
        'filter-classification', 'filter-make', 'filter-collection',
        'filter-supplier', 'filter-order-ro', 'filter-batch',
        'filter-order-type', 'filter-order-request-type', 'hierarchy-search'
    ];

    filterIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    updatePresetUI(null);

    const urlParams = new URLSearchParams();
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

function onSearchInput(value) {
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
        applyGlobalFilters();
    }, 600);
}

function updatePaginationControls(meta) {
    const page = parseInt(meta.page);
    const perPage = parseInt(meta.perPage);
    const total = parseInt(meta.total);
    const hasPrev = meta.hasPrev === 'true';
    const hasNext = meta.hasNext === 'true';

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
        btnPrev.onclick = hasPrev ? () => changePage(page - 1) : null;
    }
    if (btnNext) {
        btnNext.disabled = !hasNext;
        btnNext.onclick = hasNext ? () => changePage(page + 1) : null;
    }
}

function changePage(page) {
    if (!page || page < 1) return;
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    updateUrlAndLoad(urlParams);
}

function changePerPage(perPage) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    const urlParams = new URLSearchParams(window.location.search);
    // Sync filters from URL
    const filterIds = [
        'filter-classification-owner', 'filter-make-owner', 'filter-collection-owner',
        'filter-classification', 'filter-make', 'filter-collection',
        'filter-supplier', 'filter-order-ro', 'filter-batch',
        'filter-order-type', 'filter-order-request-type', 'hierarchy-search'
    ];
    filterIds.forEach(id => {
        const paramKey = id.replace('filter-', '').replace('hierarchy-', '').replace(/-/g, '_');
        if (urlParams.has(paramKey)) {
            const el = document.getElementById(id);
            if (el) el.value = urlParams.get(paramKey);
        }
    });

    if (urlParams.has('days')) {
        updatePresetUI(urlParams.get('days'));
    }

    loadViewData();
});
