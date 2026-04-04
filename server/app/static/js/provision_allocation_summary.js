let currentPage = 1;
let perPage = 2000;
let currentSearch = '';

// Filter variables
let filters = {
    location: '',
    branch_type: '',
    business_head: '',
    purity: '',
    classification: '',
    make: '',
    collection: '',
    section: '',
    prov_type: '',
    provision_mode: ''
};

document.addEventListener('DOMContentLoaded', () => {
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

        populateSelect('filter-branch-type', data.branch_types);
        populateSelect('filter-business-head', data.business_heads);
        populateSelect('filter-purity', data.purities);
        populateSelect('filter-classification', data.classifications);
        populateSelect('filter-make', data.makes);
        populateSelect('filter-collection', data.collections);
        populateSelect('filter-section', data.sections);
        populateSelect('filter-prov-type', data.prov_types);
        populateSelect('filter-provision-mode', data.provision_modes);

        // Populate Custom Location Dropdown
        const locContainer = document.getElementById('filter-location-options');
        if (locContainer) {
            locContainer.innerHTML = '';
            data.locations.forEach(optVal => {
                const label = document.createElement('label');
                label.className = 'flex items-center gap-2 px-2 py-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer rounded-sm location-option';
                
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.value = optVal;
                cb.className = 'location-checkbox rounded border-gray-300 text-primary focus:ring-primary w-3 h-3';
                cb.addEventListener('change', updateLocationTriggerText);
                
                const span = document.createElement('span');
                span.className = 'text-[11px] text-gray-700 dark:text-gray-300 select-none location-text';
                span.textContent = optVal;
                
                label.appendChild(cb);
                label.appendChild(span);
                locContainer.appendChild(label);
            });
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
    const locCheckboxes = document.querySelectorAll('.location-checkbox:checked');
    const selectedLocations = Array.from(locCheckboxes).map(cb => cb.value);
    filters.location = selectedLocations.join(',');
    
    filters.branch_type = document.getElementById('filter-branch-type').value;
    filters.business_head = document.getElementById('filter-business-head').value;
    filters.purity = document.getElementById('filter-purity').value;
    filters.classification = document.getElementById('filter-classification').value;
    filters.make = document.getElementById('filter-make').value;
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
    document.querySelectorAll('.location-checkbox').forEach(cb => cb.checked = false);
    updateLocationTriggerText();
    
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

// Custom Location Dropdown Actions
function toggleLocationDropdown() {
    const dropdown = document.getElementById('filter-location-dropdown');
    const icon = document.getElementById('filter-location-icon');
    if (dropdown.classList.contains('hidden')) {
        dropdown.classList.remove('hidden');
        if(icon) icon.style.transform = 'rotate(180deg)';
        const searchInput = document.getElementById('filter-location-search');
        if(searchInput) searchInput.focus();
    } else {
        dropdown.classList.add('hidden');
        if(icon) icon.style.transform = 'rotate(0deg)';
    }
}

function filterLocationOptions() {
    const searchInput = document.getElementById('filter-location-search');
    if(!searchInput) return;
    const searchValue = searchInput.value.toLowerCase();
    const options = document.querySelectorAll('.location-option');
    options.forEach(opt => {
        const textNode = opt.querySelector('.location-text');
        if(!textNode) return;
        const text = textNode.textContent.toLowerCase();
        if (text.includes(searchValue)) {
            opt.style.display = 'flex';
        } else {
            opt.style.display = 'none';
        }
    });
}

function updateLocationTriggerText() {
    const checked = document.querySelectorAll('.location-checkbox:checked');
    const textEl = document.getElementById('filter-location-text');
    if(!textEl) return;
    
    if (checked.length === 0) {
        textEl.textContent = 'All Locations';
    } else if (checked.length === 1) {
        textEl.textContent = checked[0].value;
    } else {
        textEl.textContent = `${checked.length} Selected`;
    }
}

document.addEventListener('click', (e) => {
    const container = document.getElementById('location-dropdown-container');
    const dropdown = document.getElementById('filter-location-dropdown');
    const icon = document.getElementById('filter-location-icon');
    
    if (container && dropdown && !container.contains(e.target)) {
        dropdown.classList.add('hidden');
        if(icon) icon.style.transform = 'rotate(0deg)';
    }
});
