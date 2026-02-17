// Zoom management
let currentZoom = parseFloat(localStorage.getItem('branchstock-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('branchstock-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.classList.toggle('hidden', !show);
        overlay.classList.toggle('flex', show);
    }
}

// Data loading logic
async function loadViewData() {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    showLoading(true);

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/allocated_barcodes?${searchParams}`);
        if (!response.ok) throw new Error('Failed to fetch data');
        const html = await response.text();

        // Inject HTML directly into table-area
        tableArea.innerHTML = html;

        // Parse stats metadata
        const statsScript = tableArea.querySelector('#stats-metadata');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent);
                updateDashboardStats(stats);
            } catch (e) {
                console.error('Error parsing stats metadata:', e);
            }
        }

        // Initialize table sorting
        initTableSorting();

    } catch (error) {
        console.error('Error loading data:', error);
        activeView.innerHTML = `
            <div class="flex flex-col items-center justify-center h-64 text-red-500">
                <span class="material-symbols-outlined text-4xl">error</span>
                <p class="text-[11px] mt-2 font-bold uppercase">Error loading summary view. Please try again.</p>
            </div>
        `;
    } finally {
        showLoading(false);
    }
}

function updateDashboardStats(stats) {
    if (!stats) return;

    // Helper to set text content
    const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val !== undefined ? val : '0';
    };

    // Helper to set progress ring offset (36 is viewBox size, 16 is radius)
    const setRing = (id, pct) => {
        const ring = document.getElementById(id);
        if (ring) {
            const r = 16;
            const circ = 2 * Math.PI * r;
            const offset = circ - (Math.min(100, Math.max(0, pct)) / 100) * circ;
            ring.style.strokeDasharray = `${circ} ${circ}`;
            ring.style.strokeDashoffset = offset;
        }
    };

    // Helper for progress bars
    const setBar = (id, pct) => {
        const bar = document.getElementById(id);
        if (bar) bar.style.width = Math.min(100, Math.max(0, pct)) + '%';
    };

    // 1. Provision
    setText('stat-provision-pieces', stats.provision_pieces);

    // 2. Stock & Fill Bar
    setText('stat-stock-pieces', stats.stock_pieces);
    const fr = parseFloat(stats.fulfillment_rate) || 0;
    setBar('stat-stock-fill-bar', fr);

    // 3. Shortage & Bar
    setText('stat-short-pieces', stats.short_pieces);
    const shortPct = parseFloat(stats.short_percentage) || 0;
    setText('stat-short-percentage', shortPct.toFixed(1) + '%');
    setBar('stat-short-bar', shortPct);

    // 4. Excess
    setText('stat-excess-pieces', stats.excess_pieces);

    // 5. Fulfillment (Progress Ring)
    setText('stat-fulfillment-rate', fr.toFixed(1) + '%');
    setRing('stat-fulfillment-ring', fr);
    const fIcon = document.getElementById('stat-fulfillment-icon');
    if (fIcon) {
        fIcon.textContent = fr >= 90 ? 'check_circle' : (fr >= 70 ? 'pending' : 'error');
        fIcon.className = `material-symbols-outlined text-sm ${fr >= 90 ? 'text-emerald-500' : (fr >= 70 ? 'text-amber-500' : 'text-red-500')}`;
    }

    // 6. Locations & Coverage
    setText('stat-total-locations', stats.total_locations);
    const cov = parseFloat(stats.coverage_score) || 0;
    setText('stat-coverage-score', cov.toFixed(1) + '%');
    setBar('stat-coverage-bar', cov);

    // 7. Prov Weight
    setText('stat-provision-weight', stats.provision_weight);
    setText('stat-avg-provision-weight', stats.avg_provision_weight + 'g avg');

    // 8. Stock Weight
    setText('stat-stock-weight', stats.stock_weight);
    setText('stat-avg-stock-weight', stats.avg_stock_weight + 'g avg');

    // Dynamic scale for weight bars (relative to each other)
    const pw = parseFloat(stats.provision_weight.replace(/,/g, '')) || 0;
    const sw = parseFloat(stats.stock_weight.replace(/,/g, '')) || 0;
    const maxW = Math.max(pw, sw, 1);

    // Prov weight bar is div-based in HTML
    const pWBar = document.querySelector('[id="stat-provision-weight"]').parentElement.nextElementSibling.firstElementChild;
    if (pWBar) pWBar.style.width = (pw / maxW * 100) + '%';
    const stockWeightBar = document.getElementById('stat-stock-weight-bar');
    if (stockWeightBar) stockWeightBar.style.width = (sw / maxW * 100) + '%';
}


function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const filterIds = {
        'location': 'filter-location',
        'zone': 'filter-zone',
        'state': 'filter-state',
        'business_head': 'filter-business-head'
    };

    for (const [key, id] of Object.entries(filterIds)) {
        const val = document.getElementById(id)?.value;
        if (val) urlParams.set(key, val);
        else urlParams.delete(key);
    }

    const searchVal = document.getElementById('hierarchy-search')?.value;
    if (searchVal) urlParams.set('search', searchVal);
    else urlParams.delete('search');

    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

function resetGlobalFilters() {
    const selects = document.querySelectorAll('aside select');
    selects.forEach(s => s.value = "");
    const searchInput = document.getElementById('hierarchy-search');
    if (searchInput) searchInput.value = "";
    applyGlobalFilters();
}

let searchTimeout;
function onSearchInput(value) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        applyGlobalFilters();
    }, 500);
}

// Initializing filters (AJAX)
async function initializeFilters() {
    try {
        const response = await fetch('/api/branchstockprovision/options');
        const options = await response.json();

        const mappings = {
            'location': 'filter-location',
            'zone': 'filter-zone',
            'state': 'filter-state',
            'business_head': 'filter-business-head'
        };

        for (const [key, id] of Object.entries(mappings)) {
            const select = document.getElementById(id);
            if (select && options[key]) {
                const currentVal = new URLSearchParams(window.location.search).get(key);
                options[key].forEach(opt => {
                    const o = document.createElement('option');
                    o.value = opt;
                    o.textContent = opt;
                    if (opt === currentVal) o.selected = true;
                    select.appendChild(o);
                });
            }
        }
    } catch (e) {
        console.error('Error loading filter options:', e);
    }
}

function onFilterChange() {
    // Optional: Real-time filter apply or just wait for explicit button click
    // applyGlobalFilters(); 
}

function changePage(page) {
    if (!page) return;
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

function applyFilters() {
    // Handles per-page changes from the pagination bar
    const urlParams = new URLSearchParams(window.location.search);
    const perPageFilter = document.getElementById('per-page-select');
    if (perPageFilter) {
        urlParams.set('per_page', perPageFilter.value);
    }
    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

// Table Sorting State
let sortState = {
    columnIndex: null,
    direction: null // 'asc', 'desc', or null
};

function initTableSorting() {
    const table = document.querySelector('.enterprise-grid');
    if (!table) return;

    const headers = table.querySelectorAll('thead th');
    const tbody = table.querySelector('tbody');

    if (!tbody) return;

    // Store original row order
    const originalRows = Array.from(tbody.querySelectorAll('tr'));

    headers.forEach((header, index) => {
        // Make headers clickable
        header.style.cursor = 'pointer';
        header.style.userSelect = 'none';

        // Add hover effect
        header.addEventListener('mouseenter', () => {
            if (sortState.columnIndex !== index) {
                header.style.backgroundColor = 'rgba(0,0,0,0.05)';
            }
        });
        header.addEventListener('mouseleave', () => {
            if (sortState.columnIndex !== index) {
                header.style.backgroundColor = '';
            }
        });

        // Add click handler
        header.addEventListener('click', () => {
            sortTable(index, header, tbody, originalRows);
        });
    });
}

function sortTable(columnIndex, header, tbody, originalRows) {
    const rows = Array.from(tbody.querySelectorAll('tr'));

    // Determine sort direction
    let direction;
    if (sortState.columnIndex === columnIndex) {
        if (sortState.direction === 'asc') {
            direction = 'desc';
        } else if (sortState.direction === 'desc') {
            direction = null; // Reset to original
        } else {
            direction = 'asc';
        }
    } else {
        direction = 'asc';
    }

    // Clear all header indicators
    const allHeaders = tbody.closest('table').querySelectorAll('thead th');
    allHeaders.forEach(h => {
        h.style.backgroundColor = '';
        const existingIcon = h.querySelector('.sort-icon');
        if (existingIcon) existingIcon.remove();
    });

    // If resetting to original order
    if (direction === null) {
        sortState.columnIndex = null;
        sortState.direction = null;

        // Restore original order
        originalRows.forEach(row => tbody.appendChild(row));
        return;
    }

    // Update sort state
    sortState.columnIndex = columnIndex;
    sortState.direction = direction;

    // Add visual indicator
    header.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
    const icon = document.createElement('span');
    icon.className = 'sort-icon material-symbols-outlined';
    icon.style.fontSize = '12px';
    icon.style.marginLeft = '4px';
    icon.style.verticalAlign = 'middle';
    icon.textContent = direction === 'asc' ? 'arrow_upward' : 'arrow_downward';
    header.appendChild(icon);

    // Sort rows
    const sortedRows = rows.sort((a, b) => {
        const cellA = a.cells[columnIndex];
        const cellB = b.cells[columnIndex];

        if (!cellA || !cellB) return 0;

        // Extract text content, handling nested elements
        let valueA = cellA.textContent.trim();
        let valueB = cellB.textContent.trim();

        // Try to parse as numbers
        const numA = parseFloat(valueA.replace(/,/g, ''));
        const numB = parseFloat(valueB.replace(/,/g, ''));

        let comparison = 0;

        if (!isNaN(numA) && !isNaN(numB)) {
            // Numeric comparison
            comparison = numA - numB;
        } else {
            // String comparison
            comparison = valueA.localeCompare(valueB);
        }

        return direction === 'asc' ? comparison : -comparison;
    });

    // Reorder DOM
    sortedRows.forEach(row => tbody.appendChild(row));
}

// Init on load
document.addEventListener('DOMContentLoaded', () => {
    adjustZoom(0); // Set initial zoom from local storage
    initializeFilters();
    loadViewData();

    // Handle browser back/forward
    window.addEventListener('popstate', () => {
        loadViewData();
    });
});
