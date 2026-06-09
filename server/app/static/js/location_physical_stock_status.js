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
    business_head: '',
    state: '',
    sort_by: '',
    sort_order: 'none'
};
let locationMultiSelect;
let stateMultiSelect;
let branchTypeMultiSelect;
let branchStatusMultiSelect;
let makeMultiSelect;
let makeHeaderFilter;
let sectionHeaderFilter;
let purityHeaderFilter;
let collectionMultiSelect;
let collectionHeaderFilter;

document.addEventListener('DOMContentLoaded', () => {
    locationMultiSelect = new CustomMultiSelect({
        containerId: 'filter-location-container',
        label: 'Location',
        defaultText: 'All Locations',
        options: []
    });

    branchStatusMultiSelect = new CustomMultiSelect({
        containerId: 'filter-branch-status-container',
        label: 'Branch Status',
        defaultText: 'All Branch Statuses',
        options: []
    });

    branchTypeMultiSelect = new CustomMultiSelect({
        containerId: 'filter-branch-type-container',
        label: 'Branch Type',
        defaultText: 'All Branch Types',
        options: []
    });

    stateMultiSelect = new CustomMultiSelect({
        containerId: 'filter-state-container',
        label: 'State',
        defaultText: 'All States',
        options: []
    });
    makeMultiSelect = new CustomMultiSelect({
        containerId: 'filter-make-container',
        label: 'Make',
        defaultText: 'All Makes',
        options: [],
        onSearch: async (query, callback) => {
            try {
                const response = await fetch(`/api/location-physical-stock-status/makes/search?q=${encodeURIComponent(query)}`, {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
                });
                const data = await response.json();
                callback(data);
            } catch (err) {
                console.error('Make search failed:', err);
                callback([]);
            }
        }
    });

    collectionMultiSelect = new CustomMultiSelect({
        containerId: 'filter-collection-container',
        label: 'Collection',
        defaultText: 'All Collections',
        options: [],
        onSearch: async (query, callback) => {
            try {
                const response = await fetch(`/api/location-physical-stock-status/collections/search?q=${encodeURIComponent(query)}`, {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
                });
                const data = await response.json();
                callback(data);
            } catch (err) {
                console.error('Collection search failed:', err);
                callback([]);
            }
        }
    });

    makeHeaderFilter = new HeaderFilter({
        id: 'make',
        title: 'Make Wise',
        onApply: (values) => {
            applyFilters();
        },
        onClear: () => {
            applyFilters();
        },
        onSearch: async (query, callback) => {
            try {
                const response = await fetch(`/api/location-physical-stock-status/makes/search?q=${encodeURIComponent(query)}`, {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
                });
                const data = await response.json();
                callback(data);
            } catch (err) {
                console.error('Make header search failed:', err);
                callback([]);
            }
        }
    });

    sectionHeaderFilter = new HeaderFilter({
        id: 'section',
        title: 'Section Wise',
        onApply: (values) => {
            applyFilters();
        },
        onClear: () => {
            applyFilters();
        }
    });

    purityHeaderFilter = new HeaderFilter({
        id: 'purity',
        title: 'Purity Wise',
        onApply: (values) => {
            applyFilters();
        },
        onClear: () => {
            applyFilters();
        }
    });

    collectionHeaderFilter = new HeaderFilter({
        id: 'collection',
        title: 'Collection Wise',
        onApply: (values) => {
            applyFilters();
        },
        onClear: () => {
            applyFilters();
        },
        onSearch: async (query, callback) => {
            try {
                const response = await fetch(`/api/location-physical-stock-status/collections/search?q=${encodeURIComponent(query)}`, {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
                });
                const data = await response.json();
                callback(data);
            } catch (err) {
                console.error('Collection header search failed:', err);
                callback([]);
            }
        }
    });

    loadOptions();
    loadReport();
});

async function loadOptions() {
    try {
        const response = await fetch('/api/location-physical-stock-status/options', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const data = await response.json();

        const config = [
            { id: 'filter-purity', data: data.purities },
            { id: 'filter-classification', data: data.classifications },
            { id: 'filter-section', data: data.sections },
            { id: 'filter-prov-type', data: data.prov_types },
            { id: 'filter-provision-mode', data: data.provision_modes },
            { id: 'filter-business-head', data: data.business_heads }
        ];

        if (locationMultiSelect) locationMultiSelect.populateOptions(data.locations);
        if (branchStatusMultiSelect) branchStatusMultiSelect.populateOptions(data.branch_statuses);
        if (branchTypeMultiSelect) branchTypeMultiSelect.populateOptions(data.branch_types);
        if (stateMultiSelect) stateMultiSelect.populateOptions(data.states);
        // makeMultiSelect is now dynamic
        if (makeHeaderFilter) makeHeaderFilter.setOptions([]); 
        if (sectionHeaderFilter) sectionHeaderFilter.setOptions(data.sections);
        if (purityHeaderFilter) purityHeaderFilter.setOptions(data.purities);
        // collectionMultiSelect is now dynamic
        if (collectionHeaderFilter) collectionHeaderFilter.setOptions([]); // Initially empty or we can add search here too

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
    const tableArea = document.getElementById('view-location-physical-stock-status');
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

        // Optimization: Don't send sort_order if sort_by is empty
        if (!filterValues.sort_by) {
            params.delete('sort_order');
        } else if (filterValues.sort_order === 'none') {
            params.delete('sort_by');
            params.delete('sort_order');
        }

        const response = await fetch(`/partial/location-physical-stock-status?${params}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const html = await response.text();
        tableArea.innerHTML = html;

        // Re-execute scripts in the partial
        const scripts = tableArea.getElementsByTagName('script');
        for (let i = 0; i < scripts.length; i++) {
            eval(scripts[i].innerText);
        }

        // Apply filter highlight to header icons if filtered
        if (makeHeaderFilter && makeHeaderFilter.selectedValues.length > 0) {
            const icon = document.querySelector('.header-filter-container[data-id="make"]');
            if (icon) icon.classList.add('filtered');
        }
        if (sectionHeaderFilter && sectionHeaderFilter.selectedValues.length > 0) {
            const icon = document.querySelector('.header-filter-container[data-id="section"]');
            if (icon) icon.classList.add('filtered');
        }
        if (purityHeaderFilter && purityHeaderFilter.selectedValues.length > 0) {
            const icon = document.querySelector('.header-filter-container[data-id="purity"]');
            if (icon) icon.classList.add('filtered');
        }
        if (collectionHeaderFilter && collectionHeaderFilter.selectedValues.length > 0) {
            const icon = document.querySelector('.header-filter-container[data-id="collection"]');
            if (icon) icon.classList.add('filtered');
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
    filterValues.branch_type = '';
    filterValues.branch_status = '';
    filterValues.business_head = document.getElementById('filter-business-head').value;

    if (locationMultiSelect) filterValues.location = locationMultiSelect.getValues().join(',');
    if (branchStatusMultiSelect) filterValues.branch_status = branchStatusMultiSelect.getValues().join(',');
    if (branchTypeMultiSelect) filterValues.branch_type = branchTypeMultiSelect.getValues().join(',');
    if (stateMultiSelect) filterValues.state = stateMultiSelect.getValues().join(',');

    filterValues.purity = document.getElementById('filter-purity').value;
    filterValues.classification = document.getElementById('filter-classification').value;
    filterValues.section = document.getElementById('filter-section').value;
    filterValues.prov_type = document.getElementById('filter-prov-type').value;
    filterValues.provision_mode = document.getElementById('filter-provision-mode').value;

    // Combine Sidebar and Header Filter
    let sidebarMakes = makeMultiSelect ? makeMultiSelect.getValues() : [];
    let headerMakes = makeHeaderFilter ? makeHeaderFilter.selectedValues : [];
    let combinedMakes = new Set([...sidebarMakes, ...headerMakes]);
    filterValues.make = Array.from(combinedMakes).join(',');

    const sectionSelect = document.getElementById('filter-section');
    let sidebarSection = sectionSelect ? sectionSelect.value : '';
    let headerSections = sectionHeaderFilter ? sectionHeaderFilter.selectedValues : [];
    let combinedSections = new Set(headerSections);
    if (sidebarSection) combinedSections.add(sidebarSection);
    filterValues.section = Array.from(combinedSections).join(',');

    const puritySelect = document.getElementById('filter-purity');
    let sidebarPurity = puritySelect ? puritySelect.value : '';
    let headerPurities = purityHeaderFilter ? purityHeaderFilter.selectedValues : [];
    let combinedPurities = new Set(headerPurities);
    if (sidebarPurity) combinedPurities.add(sidebarPurity);
    filterValues.purity = Array.from(combinedPurities).join(',');

    let sidebarCollections = collectionMultiSelect ? collectionMultiSelect.getValues() : [];
    let headerCollections = collectionHeaderFilter ? collectionHeaderFilter.selectedValues : [];
    let combinedCollections = new Set([...sidebarCollections, ...headerCollections]);
    filterValues.collection = Array.from(combinedCollections).join(',');
    
    loadReport();
}

function resetFilters() {
    Object.keys(filterValues).forEach(key => filterValues[key] = '');
    currentSearch = '';
    
    const filterIds = [
        'filter-purity', 'filter-classification', 
        'filter-section', 
        'filter-prov-type', 'filter-provision-mode',
        'filter-business-head'
    ];
    filterIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    if (locationMultiSelect) locationMultiSelect.reset();
    if (branchStatusMultiSelect) branchStatusMultiSelect.reset();
    if (branchTypeMultiSelect) branchTypeMultiSelect.reset();
    if (stateMultiSelect) stateMultiSelect.reset();
    if (makeMultiSelect) makeMultiSelect.reset();
    if (collectionMultiSelect) collectionMultiSelect.reset();
    
    if (makeHeaderFilter) makeHeaderFilter.setSelectedValues([]);
    if (sectionHeaderFilter) sectionHeaderFilter.setSelectedValues([]);
    if (purityHeaderFilter) purityHeaderFilter.setSelectedValues([]);
    if (collectionHeaderFilter) collectionHeaderFilter.setSelectedValues([]);

    filterValues.sort_by = '';
    filterValues.sort_order = 'none';

    const searchInput = document.getElementById('report-search');
    if (searchInput) searchInput.value = '';
    
    loadReport();
}

function toggleSort(column) {
    if (filterValues.sort_by === column) {
        if (filterValues.sort_order === 'asc') {
            filterValues.sort_order = 'desc';
        } else if (filterValues.sort_order === 'desc') {
            filterValues.sort_order = 'none';
            filterValues.sort_by = '';
        } else {
            filterValues.sort_order = 'asc';
        }
    } else {
        filterValues.sort_by = column;
        filterValues.sort_order = 'asc';
    }
    loadReport();
}

function adjustZoom(delta, reset = false) {
    const main = document.getElementById('location-physical-stock-status-main');
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

// Global toggle for header filters
function toggleHeaderFilter(event, id) {
    event.stopPropagation();
    const icon = event.currentTarget;
    
    if (id === 'make' && makeHeaderFilter) {
        if (makeHeaderFilter.isOpen) {
            makeHeaderFilter.close();
            icon.classList.remove('active');
        } else {
            document.querySelectorAll('.header-filter-container').forEach(el => el.classList.remove('active'));
            icon.classList.add('active');
            makeHeaderFilter.render(icon);
        }
    } else if (id === 'section' && sectionHeaderFilter) {
        if (sectionHeaderFilter.isOpen) {
            sectionHeaderFilter.close();
            icon.classList.remove('active');
        } else {
            document.querySelectorAll('.header-filter-container').forEach(el => el.classList.remove('active'));
            icon.classList.add('active');
            sectionHeaderFilter.render(icon);
        }
    } else if (id === 'purity' && purityHeaderFilter) {
        if (purityHeaderFilter.isOpen) {
            purityHeaderFilter.close();
            icon.classList.remove('active');
        } else {
            document.querySelectorAll('.header-filter-container').forEach(el => el.classList.remove('active'));
            icon.classList.add('active');
            purityHeaderFilter.render(icon);
        }
    } else if (id === 'collection' && collectionHeaderFilter) {
        if (collectionHeaderFilter.isOpen) {
            collectionHeaderFilter.close();
            icon.classList.remove('active');
        } else {
            document.querySelectorAll('.header-filter-container').forEach(el => el.classList.remove('active'));
            icon.classList.add('active');
            collectionHeaderFilter.render(icon);
        }
    }
}

/**
 * Drill-down Modal Functions
 */

async function openDrillDownModal(sectionName) {
    const modal = document.getElementById('drillDownModal');
    const container = document.getElementById('drillDownContainer');
    const title = document.getElementById('drillDownTitle');
    const loader = document.getElementById('modal-loader');
    const contentArea = document.getElementById('modal-content-area');
    const progressBar = document.getElementById('modal-progress');

    if (!modal || !container) return;

    // Show modal structure
    modal.classList.remove('hidden');
    // Trigger animation next frame
    requestAnimationFrame(() => {
        container.classList.remove('translate-x-full');
    });

    // Set title
    title.textContent = `${sectionName} - Section Drill-down`;

    // Show loading state
    loader.classList.remove('hidden');
    if (progressBar) progressBar.classList.remove('hidden');
    contentArea.innerHTML = '';

    try {
        // Collect all current report filters
        const params = new URLSearchParams({
            ...filterValues,
            drill_section: sectionName // Explicitly filter by the clicked section
        });

        const response = await fetch(`/api/location-physical-stock-status/drilldown?${params}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });

        if (!response.ok) throw new Error('Failed to fetch drill-down data');

        const html = await response.text();
        contentArea.innerHTML = html;

    } catch (err) {
        console.error('Drill-down error:', err);
        contentArea.innerHTML = `
            <div class="flex flex-col items-center justify-center h-full p-12 text-center">
                <span class="material-symbols-outlined text-4xl text-red-500 mb-4">error</span>
                <h4 class="text-sm font-bold text-gray-800 dark:text-white mb-2">Something went wrong</h4>
                <p class="text-xs text-gray-500">${err.message}</p>
                <button onclick="openDrillDownModal('${sectionName}')" class="mt-6 px-4 py-2 bg-primary text-white text-[10px] font-bold rounded uppercase tracking-wider">Try Again</button>
            </div>
        `;
    } finally {
        loader.classList.add('hidden');
        if (progressBar) progressBar.classList.add('hidden');
    }
}

function closeDrillDownModal() {
    const modal = document.getElementById('drillDownModal');
    const container = document.getElementById('drillDownContainer');

    if (!modal || !container) return;

    // Trigger close animation
    container.classList.add('translate-x-full');

    // Hide backdrop after animation
    setTimeout(() => {
        modal.classList.add('hidden');
    }, 300);
}

async function exportToExcel() {
    const btn = document.getElementById('btn-export-excel');
    if (!btn) return;

    const COOLDOWN_MS = 2 * 60 * 1000; // 2 minutes
    const lastExportTime = localStorage.getItem('last_stock_export_time');
    const now = Date.now();

    if (lastExportTime) {
        const timePassed = now - parseInt(lastExportTime, 10);
        if (timePassed < COOLDOWN_MS) {
            showToast('Warning', 'Already export is in progress...', 'warning');
            return;
        }
    }

    const icon = document.getElementById('export-btn-icon');
    const label = document.getElementById('export-btn-label');
    const originalIcon = icon ? icon.innerText : 'download';
    const originalLabel = label ? label.innerText : 'Export';

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
            location: filterValues.location,
            purity: filterValues.purity,
            classification: filterValues.classification,
            make: filterValues.make,
            collection: filterValues.collection,
            section: filterValues.section,
            prov_type: filterValues.prov_type,
            provision_mode: filterValues.provision_mode,
            branch_type: filterValues.branch_type,
            branch_status: filterValues.branch_status,
            business_head: filterValues.business_head,
            state: filterValues.state,
            sort_by: filterValues.sort_by,
            sort_order: filterValues.sort_order
        };

        const response = await fetch('/api/location-physical-stock-status/export', {
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

        localStorage.setItem('last_stock_export_time', Date.now().toString());
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
