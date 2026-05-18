let currentPage = 1;
let perPage = 2000;
let currentSearch = '';

// Filter variables
let filters = {
    location: '',
    branch_type: '',
    branch_status: '',
    business_head: '',
    state: '',
    purity: '',

    classification: '',
    make: '',
    collection: '',
    section: '',
    prov_type: '',
    provision_mode: ''
};

let locationMultiSelect, stateMultiSelect, branchTypeMultiSelect, branchStatusMultiSelect, makeMultiSelect;


document.addEventListener('DOMContentLoaded', () => {
    locationMultiSelect = new CustomMultiSelect({
        containerId: 'filter-location-container',
        label: 'Location',
        defaultText: 'All Locations',
        options: []
    });
    
    stateMultiSelect = new CustomMultiSelect({
        containerId: 'filter-state-container',
        label: 'State',
        defaultText: 'All States',
        options: []
    });


    branchTypeMultiSelect = new CustomMultiSelect({
        containerId: 'filter-branch-type-container',
        label: 'Branch Type',
        defaultText: 'All Branch Types',
        options: []
    });

    branchStatusMultiSelect = new CustomMultiSelect({
        containerId: 'filter-branch-status-container',
        label: 'Branch Status',
        defaultText: 'All Branch Statuses',
        options: []
    });

    makeMultiSelect = new CustomMultiSelect({
        containerId: 'filter-make-container',
        label: 'Make',
        defaultText: 'All Makes',
        options: []
    });

    loadOptions();
    loadReport();

    // Pagination Listeners
    document.getElementById('btn-prev').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadReport();
        }
    });

    document.getElementById('btn-next').addEventListener('click', () => {
        currentPage++;
        loadReport();
    });
});

async function loadOptions() {
    try {
        const response = await fetch('/api/provision-allocation/options', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const data = await response.json();

        const populateSelect = (id, options) => {
            const select = document.getElementById(id);
            if (!select) return;
            // Clear existing options except the first one
            while (select.options.length > 1) {
                select.remove(1);
            }
            options.forEach(optVal => {
                const opt = document.createElement('option');
                opt.value = optVal;
                opt.textContent = optVal;
                select.appendChild(opt);
            });
        };

        // populateSelect('filter-branch-type', data.branch_types);
        // populateSelect('filter-branch-status', data.branch_statuses);
        
        if (branchTypeMultiSelect) {
            branchTypeMultiSelect.populateOptions(data.branch_types);
        }
        if (branchStatusMultiSelect) {
            branchStatusMultiSelect.populateOptions(data.branch_statuses);
        }
        populateSelect('filter-business-head', data.business_heads);
        populateSelect('filter-purity', data.purities);
        populateSelect('filter-classification', data.classifications);
        if (makeMultiSelect) {
            makeMultiSelect.populateOptions(data.makes);
        }
        populateSelect('filter-collection', data.collections);
        populateSelect('filter-section', data.sections);
        populateSelect('filter-prov-type', data.prov_types);
        populateSelect('filter-provision-mode', data.provision_modes);
        // Populate Custom Location Dropdown using reusable script
        if (locationMultiSelect) {
            locationMultiSelect.populateOptions(data.locations);
        }
        if (stateMultiSelect) {
            stateMultiSelect.populateOptions(data.states);
        }


    } catch (err) {
        console.error('Failed to load filter options:', err);
    }
}

async function loadReport() {
    const tableArea = document.getElementById('view-provision-allocation');
    const loader = document.getElementById('report-loader');
    
    tableArea.classList.add('opacity-50', 'pointer-events-none');
    if (loader) loader.classList.remove('hidden');

    try {
        const params = new URLSearchParams({
            page: currentPage,
            per_page: perPage,
            search: currentSearch,
            ...filters
        });

        const response = await fetch(`/partial/provision-allocation?${params}`, {
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
        tableArea.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Failed to load data.</div>`;
    } finally {
        tableArea.classList.remove('opacity-50', 'pointer-events-none');
        if (loader) loader.classList.add('hidden');
    }
}

function onSearchInput(val) {
    currentSearch = val;
    currentPage = 1;
    // Debounce search
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => loadReport(), 300);
}

function applyFilters() {
    if (locationMultiSelect) {
        filters.location = locationMultiSelect.getValues().join(',');
    }
    
    if (branchTypeMultiSelect) {
        filters.branch_type = branchTypeMultiSelect.getValues().join(',');
    }
    if (branchStatusMultiSelect) {
        filters.branch_status = branchStatusMultiSelect.getValues().join(',');
    }
    if (stateMultiSelect) {
        filters.state = stateMultiSelect.getValues().join(',');
    }
    filters.business_head = document.getElementById('filter-business-head').value;

    filters.purity = document.getElementById('filter-purity').value;
    filters.classification = document.getElementById('filter-classification').value;
    if (makeMultiSelect) {
        filters.make = makeMultiSelect.getValues().join(',');
    }
    filters.collection = document.getElementById('filter-collection').value;
    filters.section = document.getElementById('filter-section').value;
    filters.prov_type = document.getElementById('filter-prov-type').value;
    filters.provision_mode = document.getElementById('filter-provision-mode').value;
    
    currentPage = 1;
    loadReport();
}

function resetFilters() {
    Object.keys(filters).forEach(key => {
        if (key === 'location') return; // Skip location, handled separately
        filters[key] = '';
        const el = document.getElementById(`filter-${key.replace('_', '-')}`);
        if (el) el.value = '';
    });
    
    filters.location = '';
    if (locationMultiSelect) {
        locationMultiSelect.reset();
    }
    if (branchTypeMultiSelect) {
        branchTypeMultiSelect.reset();
    }
    if (branchStatusMultiSelect) {
        branchStatusMultiSelect.reset();
    }
    if (stateMultiSelect) {
        stateMultiSelect.reset();
    }
    if (makeMultiSelect) {
        makeMultiSelect.reset();
    }

    
    document.getElementById('report-search').value = '';
    currentSearch = '';
    currentPage = 1;
    loadReport();
}

function changePerPage(val) {
    perPage = parseInt(val);
    currentPage = 1;
    loadReport();
}

function adjustZoom(delta, reset = false) {
    const main = document.getElementById('provision-allocation-main');
    let currentZoom = parseFloat(main.getAttribute('data-zoom') || '1');

    if (reset) currentZoom = 1;
    else currentZoom += delta;

    currentZoom = Math.max(0.7, Math.min(1.5, currentZoom));
    main.style.zoom = currentZoom;
    main.setAttribute('data-zoom', currentZoom);
    document.getElementById('zoom-level').textContent = `${Math.round(currentZoom * 100)}%`;
}

async function exportToExcel() {
    const btn = document.getElementById('btn-export-excel');
    if (!btn) return;
    const icon = document.getElementById('export-btn-icon');
    const label = document.getElementById('export-btn-label');
    const originalIcon = icon ? icon.innerText : 'download';
    const originalLabel = label ? label.innerText : 'Export Excel';

    try {
        // Disable button and show loading state
        btn.disabled = true;
        if (icon) {
            icon.innerText = 'sync';
            icon.classList.add('animate-spin');
        }
        if (label) label.innerText = 'Queuing...';

        // Extract current active filters
        const activeFilters = {
            search: currentSearch,
            location: filters.location,
            branch_type: filters.branch_type,
            branch_status: filters.branch_status,
            business_head: filters.business_head,
            state: filters.state,
            purity: filters.purity,
            classification: filters.classification,
            make: filters.make,
            collection: filters.collection,
            section: filters.section,
            prov_type: filters.prov_type,
            provision_mode: filters.provision_mode
        };

        const response = await fetch('/api/provision-allocation-summary/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({
                filters: activeFilters,
                socket_id: window.socket?.id
            })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.message || 'Failed to queue export');
        }

        showToast('Success', 'Export job enqueued. You will be notified when the file is ready.', 'success');

    } catch (error) {
        console.error('Export error:', error);
        showToast('Error', error.message || 'Failed to trigger export', 'error');
    } finally {
        // Restore button state
        btn.disabled = false;
        if (icon) {
            icon.innerText = originalIcon;
            icon.classList.remove('animate-spin');
        }
        if (label) label.innerText = originalLabel;
    }
}


