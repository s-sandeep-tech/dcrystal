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
let makeHeaderFilter;
let sectionHeaderFilter;
let purityHeaderFilter;
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
    
    makeHeaderFilter = new HeaderFilter({
        id: 'make',
        title: 'Make Wise',
        onApply: (values) => {
            applyFilters();
        },
        onClear: () => {
            applyFilters();
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
        }
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
            { id: 'filter-business-head', data: data.business_heads }
        ];

        if (locationMultiSelect) {
            locationMultiSelect.populateOptions(data.locations);
        }

        if (branchStatusMultiSelect) {
            branchStatusMultiSelect.populateOptions(data.branch_statuses);
        }

        if (branchTypeMultiSelect) {
            branchTypeMultiSelect.populateOptions(data.branch_types);
        }

        if (stateMultiSelect) {
            stateMultiSelect.populateOptions(data.states);
        }

        if (makeHeaderFilter) {
            makeHeaderFilter.setOptions(data.makes);
        }

        if (sectionHeaderFilter) {
            sectionHeaderFilter.setOptions(data.sections);
        }

        if (purityHeaderFilter) {
            purityHeaderFilter.setOptions(data.purities);
        }

        if (collectionHeaderFilter) {
            collectionHeaderFilter.setOptions(data.collections);
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

        // Optimization: Don't send sort_order if sort_by is empty
        if (!filterValues.sort_by) {
            params.delete('sort_order');
        } else if (filterValues.sort_order === 'none') {
            params.delete('sort_by');
            params.delete('sort_order');
        }

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
    filterValues.branch_type = ''; // Will be set by multi-select below
    filterValues.branch_status = ''; // Will be set by multi-select below
    filterValues.business_head = document.getElementById('filter-business-head').value;

    if (locationMultiSelect) {
        filterValues.location = locationMultiSelect.getValues().join(',');
    }

    if (branchStatusMultiSelect) {
        filterValues.branch_status = branchStatusMultiSelect.getValues().join(',');
    }

    if (branchTypeMultiSelect) {
        filterValues.branch_type = branchTypeMultiSelect.getValues().join(',');
    }

    if (stateMultiSelect) {
        filterValues.state = stateMultiSelect.getValues().join(',');
    }

    filterValues.purity = document.getElementById('filter-purity').value;
    filterValues.classification = document.getElementById('filter-classification').value;
    filterValues.make = document.getElementById('filter-make').value;
    filterValues.collection = document.getElementById('filter-collection').value;
    filterValues.section = document.getElementById('filter-section').value;
    filterValues.prov_type = document.getElementById('filter-prov-type').value;
    filterValues.provision_mode = document.getElementById('filter-provision-mode').value;

    // Combine Sidebar Make and Header Filter Makes
    const makeSelect = document.getElementById('filter-make');
    let sidebarMake = makeSelect ? makeSelect.value : '';
    let headerMakes = makeHeaderFilter ? makeHeaderFilter.selectedValues : [];
    let combinedMakes = new Set(headerMakes);
    if (sidebarMake) combinedMakes.add(sidebarMake);
    filterValues.make = Array.from(combinedMakes).join(',');

    // Combine Sidebar Section and Header Filter Sections
    const sectionSelect = document.getElementById('filter-section');
    let sidebarSection = sectionSelect ? sectionSelect.value : '';
    let headerSections = sectionHeaderFilter ? sectionHeaderFilter.selectedValues : [];
    let combinedSections = new Set(headerSections);
    if (sidebarSection) combinedSections.add(sidebarSection);
    filterValues.section = Array.from(combinedSections).join(',');

    // Combine Sidebar Purity and Header Filter Purities
    const puritySelect = document.getElementById('filter-purity');
    let sidebarPurity = puritySelect ? puritySelect.value : '';
    let headerPurities = purityHeaderFilter ? purityHeaderFilter.selectedValues : [];
    let combinedPurities = new Set(headerPurities);
    if (sidebarPurity) combinedPurities.add(sidebarPurity);
    filterValues.purity = Array.from(combinedPurities).join(',');

    // Combine Sidebar Collection and Header Filter Collections
    const collectionSelect = document.getElementById('filter-collection');
    let sidebarCollection = collectionSelect ? collectionSelect.value : '';
    let headerCollections = collectionHeaderFilter ? collectionHeaderFilter.selectedValues : [];
    let combinedCollections = new Set(headerCollections);
    if (sidebarCollection) combinedCollections.add(sidebarCollection);
    filterValues.collection = Array.from(combinedCollections).join(',');
    
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

    if (branchStatusMultiSelect) {
        branchStatusMultiSelect.reset();
    }

    if (branchTypeMultiSelect) {
        branchTypeMultiSelect.reset();
    }

    if (makeHeaderFilter) {
        makeHeaderFilter.setSelectedValues([]);
    }

    if (sectionHeaderFilter) {
        sectionHeaderFilter.setSelectedValues([]);
    }

    if (purityHeaderFilter) {
        purityHeaderFilter.setSelectedValues([]);
    }

    if (collectionHeaderFilter) {
        collectionHeaderFilter.setSelectedValues([]);
    }

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



