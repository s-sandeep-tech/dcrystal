let currentZoom = parseFloat(localStorage.getItem('location-make-zoom')) || 1.0;
let makeMultiSelect;
let locationMultiSelect;
let branchTypeMultiSelect;
let orderTypeMultiSelect;
let reportController;

window.addEventListener('load', () => loadLocationMakeReport(), { once: true });

async function loadLocationMakeReport() {
    reportController?.abort();
    const controller = new AbortController();
    reportController = controller;
    const body = document.getElementById('view-location-make-pending');
    const stats = document.getElementById('location-make-stats');
    const info = document.getElementById('pagination-info');
    stats.setAttribute('aria-busy', 'true');
    body.setAttribute('aria-busy', 'true');
    info.textContent = 'Loading report...';
    body.innerHTML = '<div class="p-6 flex items-center justify-center gap-2 text-xs text-gray-500" role="status"><span class="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></span>Loading report...</div>';
    try {
        const headers = {};
        const token = localStorage.getItem('access_token');
        if (token) headers.Authorization = `Bearer ${token}`;
        const response = await fetch(`/api/location-make-pending-order-summary/data${window.location.search}`, { headers, signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (controller !== reportController) return;
        body.innerHTML = data.html;
        for (const [key, value] of Object.entries(data.stats)) {
            const id = key.replaceAll('_', '-');
            if (key.endsWith('_perc')) {
                const bar = document.getElementById(`stat-${id.replace(/-perc$/, '-bar')}`);
                if (bar) bar.style.width = `${value}%`;
            } else {
                const element = document.getElementById(`stat-${id}`);
                if (element) element.textContent = `${value}${key.endsWith('_pcs') ? ' Pcs' : ''}`;
            }
        }
        document.getElementById('stat-total-bar').style.width = '100%';
        info.textContent = `Showing ${data.count} of ${data.total} locations`;
        adjustZoom(0);
    } catch (error) {
        if (error.name === 'AbortError' || controller !== reportController) return;
        info.textContent = 'Report unavailable';
        body.innerHTML = '<div class="p-6 text-center text-xs text-red-500" role="alert">Unable to load report data. <button class="text-primary underline" onclick="loadLocationMakeReport()">Retry</button></div>';
    } finally {
        if (controller === reportController) {
            stats.setAttribute('aria-busy', 'false');
            body.setAttribute('aria-busy', 'false');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    adjustZoom(0);

    if (typeof CustomMultiSelect !== 'undefined') {
        makeMultiSelect = new CustomMultiSelect({
            containerId: 'filter-make-container',
            label: 'Make',
            defaultText: 'All Makes',
            options: window.locationMakePendingAvailableMakes || []
        });

        const urlParams = new URLSearchParams(window.location.search);
        locationMultiSelect = new CustomMultiSelect({
            containerId: 'filter-location-container',
            label: 'Location',
            defaultText: 'All Locations',
            options: window.locationMakePendingAvailableLocations || []
        });
        const selectedLocations = (urlParams.get('location') || '').split(',').map(v => v.trim()).filter(Boolean);
        document.querySelectorAll('.filter-location-container-checkbox').forEach(cb => {
            cb.checked = selectedLocations.includes(cb.value);
        });
        locationMultiSelect.updateTriggerText();
        branchTypeMultiSelect = new CustomMultiSelect({
            containerId: 'filter-branch-type-container',
            label: 'Branch Type',
            defaultText: 'All Branch Types',
            options: window.locationMakePendingAvailableBranchTypes || []
        });
        const selectedBranchTypes = (urlParams.get('branch_type') || '').split(',').map(v => v.trim()).filter(Boolean);
        document.querySelectorAll('.filter-branch-type-container-checkbox').forEach(cb => {
            cb.checked = selectedBranchTypes.includes(cb.value);
        });
        branchTypeMultiSelect.updateTriggerText();
        orderTypeMultiSelect = new CustomMultiSelect({
            containerId: 'filter-order-type-container',
            label: 'Order Type',
            defaultText: 'All Order Types',
            options: window.locationMakePendingAvailableOrderTypes || []
        });
        const selectedOrderTypes = (urlParams.get('order_type') || '').split(',').map(v => v.trim()).filter(Boolean);
        document.querySelectorAll('.filter-order-type-container-checkbox').forEach(cb => {
            cb.checked = selectedOrderTypes.includes(cb.value);
        });
        orderTypeMultiSelect.updateTriggerText();
        const makeVal = urlParams.get('make');
        if (makeVal && makeMultiSelect) {
            const selectedMakes = makeVal.split(',').map(v => v.trim()).filter(Boolean);
            document.querySelectorAll('.filter-make-container-checkbox').forEach(cb => {
                cb.checked = selectedMakes.includes(cb.value);
            });
            makeMultiSelect.updateTriggerText();
        }
    }
});

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('location-make-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

function getFilterValues() {
    return {
        location: locationMultiSelect ? locationMultiSelect.getValues().join(',') : '',
        division: document.getElementById('filter-division')?.value || '',
        group: document.getElementById('filter-group')?.value || '',
        purity: document.getElementById('filter-purity')?.value || '',
        supplier: document.getElementById('filter-supplier')?.value || '',
        classification: document.getElementById('filter-classification')?.value || '',
        make: makeMultiSelect ? makeMultiSelect.getValues().join(',') : '',
        collection: document.getElementById('filter-collection')?.value || '',
        order_type: orderTypeMultiSelect ? orderTypeMultiSelect.getValues().join(',') : '',
        customer_order_type: document.getElementById('filter-customer-order-type')?.value || '',
        is_msme: document.getElementById('filter-is-msme')?.value || '',
        order_ro: document.getElementById('filter-order-ro')?.value || '',
        qc_ro: document.getElementById('filter-qc-ro')?.value || '',
        order_request_type: document.getElementById('filter-order-request-type')?.value || '',
        provision_type: document.getElementById('filter-provision-type')?.value || '',
        branch_provision_type: document.getElementById('filter-branch-provision-type')?.value || '',
        branch_type: branchTypeMultiSelect ? branchTypeMultiSelect.getValues().join(',') : '',
        classification_owner: document.getElementById('filter-classification-owner')?.value || '',
        collection_owner: document.getElementById('filter-collection-owner')?.value || '',
        make_owner: document.getElementById('filter-make-owner')?.value || '',
        business_head: document.getElementById('filter-business-head')?.value || '',
        search: document.getElementById('hierarchy-search')?.value || ''
    };
}

function applyFilters() {
    const params = new URLSearchParams();
    const filters = getFilterValues();
    for (const [k, v] of Object.entries(filters)) {
        if (v) params.set(k, v);
    }
    const perPage = document.getElementById('per-page-select')?.value;
    if (perPage) params.set('per_page', perPage);
    history.replaceState(null, '', `${window.location.pathname}?${params}`);
    loadLocationMakeReport();
}

function resetGlobalFilters() {
    window.location.search = '';
}

function changePerPage(val) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', val);
    urlParams.set('page', 1);
    history.replaceState(null, '', `${window.location.pathname}?${urlParams}`);
    loadLocationMakeReport();
}

function changePage(page) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    history.replaceState(null, '', `${window.location.pathname}?${urlParams}`);
    loadLocationMakeReport();
}

function onSearchInput(val) {
    const filter = val.toLowerCase().trim();
    const rows = document.querySelectorAll('#table-area table tbody tr.parent-row');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(filter) ? '' : 'none';
    });
}

// Tree-Grid Toggle Action for Location -> Make
async function toggleRow(btn, level, value) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        let nextTr = tr.nextElementSibling;
        while (nextTr) {
            const nextLevel = nextTr.dataset.level;
            if (nextLevel === 'location') break;

            const toRemove = nextTr;
            nextTr = nextTr.nextElementSibling;
            toRemove.remove();
        }
        icon.textContent = 'add_circle';
        tr.classList.remove('bg-blue-50/50');
    } else {
        icon.textContent = 'hourglass_empty';

        try {
            const urlParams = new URLSearchParams(window.location.search);
            const params = new URLSearchParams(urlParams);
            params.set('parent_level', level);
            params.set('parent_value', value);

            const token = localStorage.getItem('access_token');
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch(`/partial/location-make-pending-order-summary?${params.toString()}`, { headers });
            if (!response.ok) throw new Error("Failed to load children");

            const html = await response.text();
            const template = document.createElement('template');
            template.innerHTML = html;
            const newRows = template.content.querySelectorAll('tr');

            let referenceNode = tr;
            newRows.forEach(newRow => {
                newRow.classList.add('child-row');
                newRow.classList.add('animate-fade-in');
                referenceNode.parentNode.insertBefore(newRow, referenceNode.nextSibling);
                referenceNode = newRow;
            });

            icon.textContent = 'remove_circle';
            tr.classList.add('bg-blue-50/50');
        } catch (e) {
            console.error('Error expanding row:', e);
            icon.textContent = 'error';
        }
    }
}

// Leaf Modal Handler
async function openLeafModal(location, make) {
    const modal = document.getElementById('leaf-detail-modal');
    const overlay = document.getElementById('modal-overlay');
    const content = document.getElementById('leaf-detail-content');

    if (!modal || !overlay || !content) return;

    modal.classList.remove('hidden');
    overlay.classList.remove('hidden');
    content.innerHTML = `<div class="p-8 text-center text-gray-500 flex flex-col items-center justify-center h-full">
        <span class="animate-spin material-symbols-outlined text-4xl text-primary mb-2">sync</span>
        Loading order details...
    </div>`;

    const filters = getFilterValues();
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
        if (v) params.set(k, v);
    }
    params.set('parent_location', location);
    params.set('parent_make', make);

    try {
        const token = localStorage.getItem('access_token');
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch(`/partial/location-make-pending-order-summary/leaf_detail?${params.toString()}`, { headers });
        if (!response.ok) throw new Error('Failed to fetch details');
        content.innerHTML = await response.text();
    } catch (e) {
        console.error('Error opening leaf modal:', e);
        content.innerHTML = `<div class="p-8 text-center text-red-500">Error loading details. Please close and try again.</div>`;
    }
}

function closeLeafModal() {
    const modal = document.getElementById('leaf-detail-modal');
    const overlay = document.getElementById('modal-overlay');
    if (modal) modal.classList.add('hidden');
    if (overlay) overlay.classList.add('hidden');
}

function toggleModalSupplier(btn, supplierId) {
    const icon = btn.querySelector('.material-symbols-outlined');
    const rows = document.querySelectorAll(`tr.modal-detail-row[data-supplier-id="${supplierId}"]`);
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        icon.textContent = 'add_circle';
        rows.forEach(r => r.classList.add('hidden'));
    } else {
        icon.textContent = 'remove_circle';
        rows.forEach(r => r.classList.remove('hidden'));
    }
}
