let currentZoom = parseFloat(localStorage.getItem('location-make-zoom')) || 1.0;
let makeMultiSelect;

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
        location: document.getElementById('filter-location')?.value || '',
        division: document.getElementById('filter-division')?.value || '',
        group: document.getElementById('filter-group')?.value || '',
        purity: document.getElementById('filter-purity')?.value || '',
        supplier: document.getElementById('filter-supplier')?.value || '',
        classification: document.getElementById('filter-classification')?.value || '',
        make: makeMultiSelect ? makeMultiSelect.getValues().join(',') : '',
        collection: document.getElementById('filter-collection')?.value || '',
        order_type: document.getElementById('filter-order-type')?.value || '',
        customer_order_type: document.getElementById('filter-customer-order-type')?.value || '',
        is_msme: document.getElementById('filter-is-msme')?.value || '',
        order_ro: document.getElementById('filter-order-ro')?.value || '',
        qc_ro: document.getElementById('filter-qc-ro')?.value || '',
        order_request_type: document.getElementById('filter-order-request-type')?.value || '',
        provision_type: document.getElementById('filter-provision-type')?.value || '',
        branch_provision_type: document.getElementById('filter-branch-provision-type')?.value || '',
        branch_type: document.getElementById('filter-branch-type')?.value || '',
        classification_owner: document.getElementById('filter-classification-owner')?.value || '',
        collection_owner: document.getElementById('filter-collection-owner')?.value || '',
        make_owner: document.getElementById('filter-make-owner')?.value || '',
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
    window.location.search = params.toString();
}

function resetGlobalFilters() {
    window.location.search = '';
}

function changePerPage(val) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', val);
    urlParams.set('page', 1);
    window.location.search = urlParams.toString();
}

function changePage(page) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    window.location.search = urlParams.toString();
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
