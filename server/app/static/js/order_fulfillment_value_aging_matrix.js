let currentZoom = parseFloat(localStorage.getItem('matrix-zoom')) || 1.0;
let locationMultiSelect;

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

function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const filterIds = [
        'purchase_office', 'supplier_name', 'group_name', 'section_name', 'purity', 'location_type', 'location'
    ];

    filterIds.forEach(id => {
        let val;
        if (id === 'location' && locationMultiSelect) {
            val = locationMultiSelect.getValues().join(',');
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
        'purchase_office', 'supplier_name', 'group_name', 'section_name', 'purity', 'location_type', 'location'
    ];

    filterIds.forEach(id => {
        if (id === 'location' && locationMultiSelect) {
            locationMultiSelect.reset();
        } else {
            const el = document.getElementById(`filter-${id}`);
            if (el) el.value = '';
        }
    });

    const urlParams = new URLSearchParams();
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
        const urlParams = new URLSearchParams(window.location.search);

        const mappings = [
            { id: 'filter-purchase_office', list: options.purchase_offices, label: 'Purchase Office' },
            { id: 'filter-supplier_name', list: options.supplier_names, label: 'Supplier Name' },
            { id: 'filter-group_name', list: options.groups, label: 'Group Name' },
            { id: 'filter-section_name', list: options.sections, label: 'Section Name' },
            { id: 'filter-purity', list: options.purities, label: 'Purity' },
            { id: 'filter-location_type', list: options.location_types, label: 'Location Type' },
            { id: 'filter-location', list: options.locations, label: 'Location' }
        ];

        mappings.forEach(m => {
            if (m.id === 'filter-location') {
                if (locationMultiSelect) {
                    locationMultiSelect.populateOptions(m.list || []);
                    // Restore selection from URL
                    const selectedVals = urlParams.get('location');
                    if (selectedVals) {
                        const vals = selectedVals.split(',');
                        document.querySelectorAll(`.filter-location-container-checkbox`).forEach(cb => {
                            if (vals.includes(cb.value)) {
                                cb.checked = true;
                            }
                        });
                        locationMultiSelect.updateTriggerText();
                    }
                }
            } else {
                populateSelect(m.id, m.list, `All ${m.label}s`, urlParams.get(m.id.replace('filter-', '')));
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
    list.forEach(item => {
        html += `<option value="${item}" ${item === selectedValue ? 'selected' : ''}>${item}</option>`;
    });
    el.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    // Initialize custom multiselect component for locations
    locationMultiSelect = new CustomMultiSelect({
        containerId: 'filter-location-container',
        label: 'Location',
        defaultText: 'All Locations',
        options: []
    });

    loadViewData();
    loadFilterOptions();
});
