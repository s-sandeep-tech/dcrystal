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

function formatNumber(num, decimals = 0) {
    const n = parseFloat(num);
    return new Intl.NumberFormat('en-IN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(isNaN(n) ? 0 : n);
}

function updateSummaryCards(data) {
    const mappings = {
        'stat-pending-accept-wt': { val: data.pendingToAcceptedWt, dec: 3 },
        'stat-pending-accept-pcs': { val: data.pendingToAcceptedPcs, suffix: ' Pcs' },
        'stat-rejected-wt': { val: data.rejectedWt, dec: 3 },
        'stat-rejected-pcs': { val: data.rejectedPcs, suffix: ' Pcs' },
        'stat-hm-failed-wt': { val: data.hmFailedWt, dec: 3 },
        'stat-hm-failed-pcs': { val: data.hmFailedPcs, suffix: ' Pcs' },
        'stat-hm-test-cut-wt': { val: data.hmTestCutWt, dec: 3 },
        'stat-hm-test-cut-pcs': { val: data.hmTestCutPcs, suffix: ' Pcs' },
        'stat-qc-pending-wt': { val: data.qcPendingWt, dec: 3 },
        'stat-qc-pending-pcs': { val: data.qcPendingPcs, suffix: ' Pcs' },
        'stat-qc-rejected-wt': { val: data.qcRejectedWt, dec: 3 },
        'stat-qc-rejected-pcs': { val: data.qcRejectedPcs, suffix: ' Pcs' },
        'stat-not-barcoded-wt': { val: data.notBarcodedWt, dec: 3 },
        'stat-not-barcoded-pcs': { val: data.notBarcodedPcs, suffix: ' Pcs' }
    };

    for (const [id, config] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            let formatted = formatNumber(config.val || 0, config.dec || 0);
            el.textContent = config.suffix ? `${formatted}${config.suffix}` : formatted;
        }
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
        btn.classList.remove('bg-primary', 'text-white', 'border-primary', 'hover:bg-primary/90');
        btn.classList.add('bg-white', 'dark:bg-gray-900', 'text-gray-700', 'dark:text-gray-300', 'border-gray-200', 'dark:border-gray-700', 'hover:bg-gray-50', 'dark:hover:bg-gray-800');
    });

    if (days) {
        const activeBtn = document.getElementById(`preset-${days}d`);
        if (activeBtn) {
            activeBtn.classList.add('bg-primary', 'text-white', 'border-primary', 'hover:bg-primary/90');
            activeBtn.classList.remove('bg-white', 'dark:bg-gray-900', 'text-gray-700', 'dark:text-gray-300', 'border-gray-200', 'dark:border-gray-700', 'hover:bg-gray-50', 'dark:hover:bg-gray-800');
        }
    }
}
function setStatusFilter(status) {
    const urlParams = new URLSearchParams(window.location.search);
    const currentStatus = urlParams.get('status_filter');

    if (status === currentStatus) {
        urlParams.delete('status_filter');
        updateStatusUI(null);
    } else {
        urlParams.set('status_filter', status);
        updateStatusUI(status);
    }

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function updateStatusUI(status) {
    document.querySelectorAll('.status-preset-btn').forEach(btn => {
        btn.classList.remove('bg-primary', 'text-white', 'border-primary', 'hover:bg-primary/90');
        btn.classList.add('bg-white', 'dark:bg-gray-900', 'text-gray-700', 'dark:text-gray-300', 'border-gray-200', 'dark:border-gray-700', 'hover:bg-gray-50', 'dark:hover:bg-gray-800');
    });

    if (status) {
        const activeBtn = document.getElementById(`status-preset-${status}`);
        if (activeBtn) {
            activeBtn.classList.add('bg-primary', 'text-white', 'border-primary', 'hover:bg-primary/90');
            activeBtn.classList.remove('bg-white', 'dark:bg-gray-900', 'text-gray-700', 'dark:text-gray-300', 'border-gray-200', 'dark:border-gray-700', 'hover:bg-gray-50', 'dark:hover:bg-gray-800');
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

        const statsMeta = activeView.querySelector('.stats-meta');
        if (statsMeta) {
            updateSummaryCards(statsMeta.dataset);
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
        'filter-order-type', 'filter-order-request-type',
        'filter-division', 'filter-group', 'filter-purity'
    ];

    filterIds.forEach(id => {
        const val = document.getElementById(id)?.value?.trim();
        const paramKey = id.replace('filter-', '').replace(/-/g, '_');
        if (val) urlParams.set(paramKey, val);
        else urlParams.delete(paramKey);
    });

    const activeDays = urlParams.get('days');
    if (activeDays) urlParams.set('days', activeDays);

    const enableDateRange = document.getElementById('enable-date-range')?.checked;
    const dateFrom = document.getElementById('filter-date-from')?.value;
    const dateTo = document.getElementById('filter-date-to')?.value;

    if (enableDateRange) {
        urlParams.set('use_date_range', 'true');
        if (dateFrom) urlParams.set('date_from', dateFrom);
        else urlParams.delete('date_from');
        if (dateTo) urlParams.set('date_to', dateTo);
        else urlParams.delete('date_to');

        // If custom range is enabled, clear the days preset
        urlParams.delete('days');
        updatePresetUI(null);
    } else {
        urlParams.delete('use_date_range');
        urlParams.delete('date_from');
        urlParams.delete('date_to');
    }

    const activeStatus = urlParams.get('status_filter');
    if (activeStatus) urlParams.set('status_filter', activeStatus);

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
        'filter-order-type', 'filter-order-request-type', 'hierarchy-search',
        'filter-division', 'filter-group', 'filter-purity'
    ];

    filterIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    const enableDateRange = document.getElementById('enable-date-range');
    if (enableDateRange) enableDateRange.checked = false;
    const dateFrom = document.getElementById('filter-date-from');
    if (dateFrom) dateFrom.value = '';
    const dateTo = document.getElementById('filter-date-to');
    if (dateTo) dateTo.value = '';

    updatePresetUI(null);
    updateStatusUI(null);

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

    if (urlParams.has('status_filter')) {
        updateStatusUI(urlParams.get('status_filter'));
    }

    loadViewData();
});
