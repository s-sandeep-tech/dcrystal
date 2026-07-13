let currentZoom = parseFloat(localStorage.getItem('matrix-zoom')) || 1.0;
let locationMultiSelect;
let purchaseOfficeMultiSelect;
let supplierNameMultiSelect;
let sectionNameMultiSelect;
let purityMultiSelect;
let matrixDetailRequest;

function getMatrixMode() {
    return new URLSearchParams(window.location.search).get('matrix_mode') || 'order_to_delivery';
}

function updateMatrixModeButtons() {
    const activeMode = getMatrixMode();
    document.querySelectorAll('.matrix-mode-btn').forEach(btn => {
        btn.classList.remove('bg-white', 'dark:bg-gray-700', 'shadow-sm', 'text-primary');
        btn.classList.add('text-gray-500', 'hover:text-gray-700');
    });

    const activeBtn = document.getElementById(`btn-${activeMode.replace(/_/g, '-')}`);
    if (activeBtn) {
        activeBtn.classList.add('bg-white', 'dark:bg-gray-700', 'shadow-sm', 'text-primary');
        activeBtn.classList.remove('text-gray-500', 'hover:text-gray-700');
    }
}

function setMatrixMode(mode) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('matrix_mode', mode);
    updateUrlAndLoad(urlParams);
    updateMatrixModeButtons();
}

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('matrix-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-matrix');
    if (!activeView) return;

    const loader = document.getElementById('loader-overlay');
    if (loader) loader.classList.remove('hidden');

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/order_fulfillment_value_aging_matrix?${searchParams}`, {
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

        initializeViewFromDOM(activeView);

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    } finally {
        if (loader) loader.classList.add('hidden');
    }
}

function initializeViewFromDOM(activeView) {
    if (!activeView) activeView = document.getElementById('view-matrix');
    if (!activeView) return;

    // Parse stats from metadata attributes
    const metaDiv = activeView.querySelector('#matrix-metadata');
    if (metaDiv) {
        updateDashboardStats(metaDiv.dataset);
    }
}

function updateDashboardStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-total-order-amount': stats.totalOrderAmount ? stats.totalOrderAmount + ' L' : '0.00 L',
        'stat-total-delivered-amount': stats.totalDeliveredAmount ? stats.totalDeliveredAmount + ' L' : '0.00 L',
        'stat-total-net-weight': stats.totalNetWeight ? stats.totalNetWeight + ' g' : '0.00 g',
        'stat-total-gross-weight': stats.totalGrossWeight ? stats.totalGrossWeight + ' g' : '0.00 g',
        'stat-total-diamond-carat': stats.totalDiamondCarat ? stats.totalDiamondCarat + ' Cts' : '0.00 Cts',
        'stat-total-colour-stone-carat': stats.totalColourStoneCarat ? stats.totalColourStoneCarat + ' Cts' : '0.00 Cts',
        'stat-num-order-buckets': stats.numOrderBuckets || '0',
        'stat-highest-delivery-bucket': stats.highestDeliveryBucket || 'N/A'
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
        }
    }
}

function closeMatrixDetailModal() {
    const modal = document.getElementById('matrix-detail-modal');
    if (!modal) return;

    if (matrixDetailRequest) {
        matrixDetailRequest.abort();
        matrixDetailRequest = null;
    }
    modal.classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
}

async function openMatrixDetailModal(cell) {
    const modal = document.getElementById('matrix-detail-modal');
    const content = document.getElementById('matrix-detail-content');
    const subtitle = document.getElementById('matrix-detail-subtitle');
    if (!modal || !content || !subtitle) return;

    const orderDateRange = cell.dataset.orderDateRange;
    const invDateRange = cell.dataset.invDateRange;
    subtitle.textContent = `Order ${orderDateRange} / Invoice ${invDateRange}`;
    content.innerHTML = `
        <div class="flex min-h-40 items-center justify-center gap-2 text-xs font-semibold text-gray-500">
            <span class="size-4 animate-spin rounded-full border-2 border-gray-200 border-t-primary"></span>
            Loading details...
        </div>`;
    modal.classList.remove('hidden');
    document.body.classList.add('overflow-hidden');

    if (matrixDetailRequest) matrixDetailRequest.abort();
    const requestController = new AbortController();
    matrixDetailRequest = requestController;

    const params = new URLSearchParams(window.location.search);
    params.set('order_date_range', orderDateRange);
    params.set('inv_date_range', invDateRange);

    try {
        const response = await fetch(`/partial/order_fulfillment_value_aging_matrix/cell_details?${params.toString()}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            signal: requestController.signal
        });
        const html = await response.text();
        if (!response.ok) throw new Error(html || 'Unable to load invoice details.');
        content.innerHTML = html;
    } catch (error) {
        if (error.name === 'AbortError') return;
        console.error('Error loading matrix cell details:', error);
        content.innerHTML = `
            <div class="flex min-h-48 flex-col items-center justify-center px-6 text-center">
                <span class="material-symbols-outlined mb-2 text-3xl text-red-400">error</span>
                <p class="text-xs font-bold text-red-600">Unable to load invoice details.</p>
            </div>`;
    } finally {
        if (matrixDetailRequest === requestController) matrixDetailRequest = null;
    }
}

// Helper function to decode commas and ensure they match url search params correctly
function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const filterIds = [
        'purchase_office', 'supplier_name', 'group_name', 'section_name', 'purity', 'location_type', 'location', 'locationstatus'
    ];

    filterIds.forEach(id => {
        let val;
        if (id === 'location' && locationMultiSelect) {
            val = locationMultiSelect.getValues().join(',');
        } else if (id === 'purchase_office' && purchaseOfficeMultiSelect) {
            val = purchaseOfficeMultiSelect.getValues().join(',');
        } else if (id === 'supplier_name' && supplierNameMultiSelect) {
            val = supplierNameMultiSelect.getValues().join(',');
        } else if (id === 'section_name' && sectionNameMultiSelect) {
            val = sectionNameMultiSelect.getValues().join(',');
        } else if (id === 'purity' && purityMultiSelect) {
            val = purityMultiSelect.getValues().join(',');
        } else {
            val = document.getElementById(`filter-${id}`)?.value;
        }
        if (val) urlParams.set(id, val);
        else urlParams.delete(id);
    });

    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const filterIds = [
        'purchase_office', 'supplier_name', 'group_name', 'section_name', 'purity', 'location_type', 'location', 'locationstatus'
    ];

    filterIds.forEach(id => {
        if (id === 'location' && locationMultiSelect) {
            locationMultiSelect.reset();
        } else if (id === 'purchase_office' && purchaseOfficeMultiSelect) {
            purchaseOfficeMultiSelect.reset();
        } else if (id === 'supplier_name' && supplierNameMultiSelect) {
            supplierNameMultiSelect.reset();
        } else if (id === 'section_name' && sectionNameMultiSelect) {
            sectionNameMultiSelect.reset();
        } else if (id === 'purity' && purityMultiSelect) {
            purityMultiSelect.reset();
        } else {
            const el = document.getElementById(`filter-${id}`);
            if (el) el.value = '';
        }
    });

    const urlParams = new URLSearchParams();
    urlParams.set('matrix_mode', getMatrixMode());
    updateUrlAndLoad(urlParams);
    loadFilterOptions();
}

async function loadFilterOptions() {
    try {
        const response = await fetch(`/api/order_fulfillment_value_aging_matrix/options`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const options = await response.json();
        if (!response.ok) {
            throw new Error(options.error || 'Unable to load filter options.');
        }
        const urlParams = new URLSearchParams(window.location.search);

        const mappings = [
            { id: 'filter-purchase_office', list: options.purchase_offices, label: 'Purchase Office', ms: purchaseOfficeMultiSelect, param: 'purchase_office', checkboxClass: 'filter-purchase_office-container-checkbox' },
            { id: 'filter-supplier_name', list: options.supplier_names, label: 'Supplier Name', ms: supplierNameMultiSelect, param: 'supplier_name', checkboxClass: 'filter-supplier_name-container-checkbox' },
            { id: 'filter-group_name', list: options.groups, label: 'Group Name' },
            { id: 'filter-section_name', list: options.sections, label: 'Section Name', ms: sectionNameMultiSelect, param: 'section_name', checkboxClass: 'filter-section_name-container-checkbox' },
            { id: 'filter-purity', list: options.purities, label: 'Purity', ms: purityMultiSelect, param: 'purity', checkboxClass: 'filter-purity-container-checkbox' },
            { id: 'filter-location_type', list: options.location_types, label: 'Location Type' },
            { id: 'filter-location', list: (options.locations || []).map(l => ({ value: l.id, label: l.name })), label: 'Location', ms: locationMultiSelect, param: 'location', checkboxClass: 'filter-location-container-checkbox' },
            { id: 'filter-locationstatus', list: options.location_statuses || [], label: 'Location Status', placeholder: 'All Location Statuses' }
        ];

        mappings.forEach(m => {
            if (m.ms) {
                m.ms.populateOptions(m.list || []);
                // Restore selection from URL
                const selectedVals = urlParams.get(m.param);
                if (selectedVals) {
                    const vals = selectedVals.split(',').map(v => v.trim());
                    document.querySelectorAll(`.${m.checkboxClass}`).forEach(cb => {
                        if (vals.includes(cb.value.toString().trim())) {
                            cb.checked = true;
                        }
                    });
                    m.ms.updateTriggerText();
                }
            } else {
                populateSelect(m.id, m.list, m.placeholder || `All ${m.label}s`, urlParams.get(m.id.replace('filter-', '')));
            }
        });

    } catch (e) {
        console.error('Error loading options:', e);
    }
}

function populateSelect(id, list, placeholder, selectedValue) {
    const el = document.getElementById(id);
    if (!el) return;
    let html = `<option value="">${placeholder}</option>`;
    (list || []).forEach(item => {
        html += `<option value="${item}" ${item === selectedValue ? 'selected' : ''}>${item}</option>`;
    });
    el.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;
    updateMatrixModeButtons();

    // Initialize custom multiselect components
    purchaseOfficeMultiSelect = new CustomMultiSelect({
        containerId: 'filter-purchase_office-container',
        label: 'Purchase Office',
        defaultText: 'All Purchase Offices',
        options: []
    });

    supplierNameMultiSelect = new CustomMultiSelect({
        containerId: 'filter-supplier_name-container',
        label: 'Supplier Name',
        defaultText: 'All Suppliers',
        options: []
    });

    sectionNameMultiSelect = new CustomMultiSelect({
        containerId: 'filter-section_name-container',
        label: 'Section Name',
        defaultText: 'All Sections',
        options: []
    });

    purityMultiSelect = new CustomMultiSelect({
        containerId: 'filter-purity-container',
        label: 'Purity',
        defaultText: 'All Purities',
        options: []
    });

    locationMultiSelect = new CustomMultiSelect({
        containerId: 'filter-location-container',
        label: 'Location',
        defaultText: 'All Locations',
        options: []
    });

    loadViewData();
    loadFilterOptions();

    document.addEventListener('click', event => {
        const cell = event.target.closest('.matrix-detail-cell');
        if (cell) openMatrixDetailModal(cell);
        if (event.target.closest('[data-matrix-modal-close]')) closeMatrixDetailModal();
    });

    document.addEventListener('keydown', event => {
        if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('.matrix-detail-cell')) {
            event.preventDefault();
            openMatrixDetailModal(event.target);
        } else if (event.key === 'Escape') {
            closeMatrixDetailModal();
        }
    });
});
