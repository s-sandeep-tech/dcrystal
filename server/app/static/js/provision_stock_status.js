let currentSearch = '';
let filterValues = {
    location: '',
    purity: '',
    classification: '',
    make: '',
    collection: '',
    section: '',
    prov_type: '',
    provision_mode: '',
    branch_type: '',
    branch_status: '',
    business_head: ''
};
let locationMultiSelect;

document.addEventListener('DOMContentLoaded', () => {
    locationMultiSelect = new CustomMultiSelect({
        containerId: 'filter-location-container',
        label: 'Location',
        defaultText: 'All Locations',
        options: []
    });
    
    loadOptions();
    loadReport();
});

async function loadOptions() {
    try {
        const response = await fetch('/api/provision-stock-status/options', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const data = await response.json();

        const config = [
            { id: 'filter-purity', data: data.purities },
            { id: 'filter-classification', data: data.classifications },
            { id: 'filter-make', data: data.makes },
            { id: 'filter-collection', data: data.collections },
            { id: 'filter-section', data: data.sections },
            { id: 'filter-prov-type', data: data.prov_types },
            { id: 'filter-provision-mode', data: data.provision_modes },
            { id: 'filter-branch-type', data: data.branch_types },
            { id: 'filter-branch-status', data: data.branch_statuses },
            { id: 'filter-business-head', data: data.business_heads }
        ];

        if (locationMultiSelect) {
            locationMultiSelect.populateOptions(data.locations);
        }

        config.forEach(item => {
            const select = document.getElementById(item.id);
            if (select && item.data) {
                item.data.forEach(opt => {
                    const el = document.createElement('option');
                    el.value = opt;
                    el.textContent = opt;
                    select.appendChild(el);
                });
            }
        });
    } catch (err) {
        console.error('Failed to load filter options:', err);
    }
}

async function loadReport() {
    const tableArea = document.getElementById('view-provision-stock-status');
    const mainContainer = document.getElementById('table-area');
    const progressBar = document.getElementById('report-progress');
    if (!tableArea) return;
    
    mainContainer.classList.add('opacity-50', 'pointer-events-none');
    if (progressBar) progressBar.classList.remove('hidden');

    try {
        const params = new URLSearchParams({
            search: currentSearch,
            ...filterValues
        });

        const response = await fetch(`/partial/provision-stock-status?${params}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const html = await response.text();
        tableArea.innerHTML = html;

        // Re-execute scripts in the partial
        const scripts = tableArea.getElementsByTagName('script');
        for (let i = 0; i < scripts.length; i++) {
            eval(scripts[i].innerText);
        }
    } catch (err) {
        console.error('Failed to load report:', err);
        tableArea.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Failed to load data: ${err.message}</div>`;
    } finally {
        mainContainer.classList.remove('opacity-50', 'pointer-events-none');
        if (progressBar) progressBar.classList.add('hidden');
    }
}

function onSearchInput(val) {
    currentSearch = val;
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
        loadReport();
    }, 300);
}

function applyFilters() {
    if (locationMultiSelect) {
        filterValues.location = locationMultiSelect.getValues().join(',');
    }
    filterValues.purity = document.getElementById('filter-purity').value;
    filterValues.classification = document.getElementById('filter-classification').value;
    filterValues.make = document.getElementById('filter-make').value;
    filterValues.collection = document.getElementById('filter-collection').value;
    filterValues.section = document.getElementById('filter-section').value;
    filterValues.prov_type = document.getElementById('filter-prov-type').value;
    filterValues.provision_mode = document.getElementById('filter-provision-mode').value;
    filterValues.branch_type = document.getElementById('filter-branch-type').value;
    filterValues.branch_status = document.getElementById('filter-branch-status').value;
    filterValues.business_head = document.getElementById('filter-business-head').value;
    
    loadReport();
}

function resetFilters() {
    // Reset internal state
    Object.keys(filterValues).forEach(key => filterValues[key] = '');
    currentSearch = '';
    
    // Reset UI elements
    const filterIds = [
        'filter-purity', 'filter-classification', 
        'filter-make', 'filter-collection', 'filter-section', 
        'filter-prov-type', 'filter-provision-mode',
        'filter-branch-type', 'filter-branch-status', 'filter-business-head'
    ];
    filterIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    if (locationMultiSelect) {
        locationMultiSelect.reset();
    }
    
    const searchInput = document.getElementById('report-search');
    if (searchInput) searchInput.value = '';
    
    loadReport();
}

function adjustZoom(delta, reset = false) {
    const main = document.getElementById('provision-stock-status-main');
    if (!main) return;
    
    let currentZoom = parseFloat(main.getAttribute('data-zoom') || '1');

    if (reset) currentZoom = 1;
    else currentZoom += delta;

    currentZoom = Math.max(0.7, Math.min(1.5, currentZoom));
    main.style.zoom = currentZoom;
    main.setAttribute('data-zoom', currentZoom);
    
    const zoomText = document.getElementById('zoom-level');
    if (zoomText) zoomText.textContent = `${Math.round(currentZoom * 100)}%`;
}
