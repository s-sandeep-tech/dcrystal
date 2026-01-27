let currentZoom = parseFloat(localStorage.getItem('branchweight-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('branchweight-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-branch');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/branch?${searchParams}`, {
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

        // Parse stats
        const statsScript = activeView.querySelector('#stats-metadata');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent);
                updateDashboardStats(stats);
            } catch (e) {
                console.error('Error parsing stats metadata:', e);
            }
        }

        // Parse pagination & Level
        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
            updateLevelBadge(metaDiv.dataset.level);
        }

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    }
}

function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge) {
        badge.textContent = level || 'ZONE';
    }
}

function updateDashboardStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-stock-weight': stats.stock_weight,
        'stat-stock-pieces': stats.stock_pieces,
        'stat-provision-weight': stats.provision_weight,
        'stat-provision-pieces': stats.provision_pieces,
        'stat-short-weight': stats.short_weight,
        'stat-short-pieces': stats.short_pieces,
        'stat-max-allocate': stats.max_allocate,
        'stat-max-refill': stats.max_refill
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            if (id.includes('pieces')) el.textContent = value + ' pcs';
            else el.textContent = value !== undefined ? parseFloat(value).toFixed(3) : '0.000';
        }
    }
}

// Tree-Grid Toggle Action
async function toggleRow(btn, level, value, grandparentValue = null) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        // Collapse: Hide all children
        // We find all rows that are children of this row based on hierarchy
        // A simple way is to look for next siblings until we hit a row of the same level or higher

        let nextTr = tr.nextElementSibling;
        while (nextTr) {
            // If we encounter a row that is NOT a child (same level or higher up), stop
            // But how do we know? We can mark rows with 'data-level'.
            // Zone > State > Location.
            const nextLevel = nextTr.dataset.level;

            // If we are expanding Zone (level=zone), stop if next is Zone.
            // If we are expanding State (level=state), stop if next is State or Zone.

            if (level === 'zone' && nextLevel === 'zone') break;
            if (level === 'state' && (nextLevel === 'state' || nextLevel === 'zone')) break;

            // Remove or Hide? Re-fetching is safer for data consistency but hiding is faster.
            // For now, let's remove them to keep state simple.
            const toRemove = nextTr;
            nextTr = nextTr.nextElementSibling;
            toRemove.remove();
        }
        icon.textContent = 'add_circle';
        tr.classList.remove('bg-blue-50/50');
    } else {
        // Expand: Fetch children
        icon.textContent = 'hourglass_empty'; // Loading state

        try {
            const urlParams = new URLSearchParams(window.location.search);
            // Keep search params but add parent info
            const params = new URLSearchParams(urlParams);
            params.set('parent_level', level);
            params.set('parent_value', value);
            if (grandparentValue) params.set('grandparent_value', grandparentValue);

            const response = await fetch(`/partial/branch?${params.toString()}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });

            if (!response.ok) throw new Error("Failed to load children");
            const html = await response.text();

            // Insert HTML after current row
            // The HTML returns TRs.
            const template = document.createElement('template');
            template.innerHTML = html;
            const newRows = template.content.querySelectorAll('tr');

            // We need to reverse insert so order is preserved when inserting after
            let referenceNode = tr;
            newRows.forEach(newRow => {
                // Mark as child for styling if needed
                newRow.classList.add('child-row');
                newRow.classList.add('animate-fade-in'); // Add animation class if exists
                referenceNode.parentNode.insertBefore(newRow, referenceNode.nextSibling);
                referenceNode = newRow;
            });

            icon.textContent = 'remove_circle';
            tr.classList.add('bg-blue-50/50');

        } catch (e) {
            console.error(e);
            icon.textContent = 'error';
        }
    }
}



function onZoneChange(val) {
    const urlParams = new URLSearchParams(window.location.search);
    if (val) urlParams.set('zone', val);
    else urlParams.delete('zone');

    urlParams.delete('state');
    urlParams.delete('location');
    urlParams.set('page', 1);

    updateUrlAndLoad(urlParams);
    loadFilterOptions(); // Refresh dependent options
}

function onStateChange(val) {
    const urlParams = new URLSearchParams(window.location.search);
    if (val) urlParams.set('state', val);
    else urlParams.delete('state');

    urlParams.delete('location');
    urlParams.set('page', 1);

    updateUrlAndLoad(urlParams);
    loadFilterOptions(); // Refresh dependent options
}

function onLocationChange(val) {
    const urlParams = new URLSearchParams(window.location.search);
    if (val) urlParams.set('location', val);
    else urlParams.delete('location');
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetDrillDown() {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.delete('zone');
    urlParams.delete('state');
    urlParams.delete('location');
    urlParams.set('page', 1);

    document.getElementById('filter-zone').value = '';
    document.getElementById('filter-state').value = '';
    document.getElementById('filter-location').value = '';

    updateUrlAndLoad(urlParams);
    loadFilterOptions();
}

function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    const bh = document.getElementById('filter-business-head')?.value;
    if (bh) urlParams.set('business_head', bh);
    else urlParams.delete('business_head');

    const searchVal = document.getElementById('hierarchy-search')?.value;
    if (searchVal) urlParams.set('search', searchVal);
    else urlParams.delete('search');

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.delete('business_head');
    urlParams.delete('search');
    urlParams.delete('zone');
    urlParams.delete('state');
    urlParams.delete('location');

    const bh = document.getElementById('filter-business-head');
    if (bh) bh.value = '';
    const search = document.getElementById('hierarchy-search');
    if (search) search.value = '';

    document.getElementById('filter-zone').value = '';
    document.getElementById('filter-state').value = '';
    document.getElementById('filter-location').value = '';

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
    loadFilterOptions(); // Reload options after reset to ensure all options are available
}

function onSearchInput(value) {
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
        applyGlobalFilters();
    }, 500);
}

function updatePaginationControls(meta) {
    const page = parseInt(meta.page);
    const perPage = parseInt(meta.perPage);
    const total = parseInt(meta.total);
    const hasPrev = meta.hasPrev === 'true';
    const hasNext = meta.hasNext === 'true';

    const start = (page - 1) * perPage + 1;
    const end = Math.min(page * perPage, total);
    const infoSpan = document.getElementById('pagination-info');
    if (infoSpan) {
        infoSpan.textContent = total > 0 ? `${start}-${end} of ${total}` : '0-0 of 0';
    }

    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    if (btnPrev) {
        btnPrev.disabled = !hasPrev;
        btnPrev.onclick = hasPrev ? () => changePage(parseInt(meta.prevNum)) : null;
    }
    if (btnNext) {
        btnNext.disabled = !hasNext;
        btnNext.onclick = hasNext ? () => changePage(parseInt(meta.nextNum)) : null;
    }
}

function changePage(page) {
    if (!page) return;
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    updateUrlAndLoad(urlParams);
}

function changePerPage(perPage) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

async function loadFilterOptions() {
    const urlParams = new URLSearchParams(window.location.search);
    const zone = urlParams.get('zone') || '';
    const state = urlParams.get('state') || '';

    try {
        const response = await fetch(`/api/branchweight/options?zone=${zone}&state=${state}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const options = await response.json();

        populateSelect('filter-zone', options.zones, 'All Zones', urlParams.get('zone'));
        populateSelect('filter-state', options.states, 'All States', urlParams.get('state'));
        populateSelect('filter-location', options.locations, 'All Locations', urlParams.get('location'));
        populateSelect('filter-business-head', options.business_heads, 'All Business Heads', urlParams.get('business_head'));

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

    // Sync UI from URL
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('search')) document.getElementById('hierarchy-search').value = urlParams.get('search');

    // Initial Load only if not already loaded (though browser might cache)
    // We call loadViewData anyway to ensure fresh data
    loadViewData();
    loadFilterOptions();
});

function showAllocatedBarcodes(location) {
    const modal = document.getElementById('barcodeModal');
    const content = document.getElementById('barcodeModalContent');

    if (!modal || !content) return;

    // Show modal
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Show loading state
    content.innerHTML = `
        <div class="flex flex-col items-center justify-center h-full py-24 text-gray-400">
            <div class="size-8 border-2 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-[10px] font-medium uppercase tracking-widest">Fetching details for ${location}...</p>
        </div>
    `;

    // Fetch data
    fetch(`/api/branchweight/allocated-barcodes?location=${encodeURIComponent(location)}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch details');
            return response.text();
        })
        .then(html => {
            content.innerHTML = html;
        })
        .catch(error => {
            console.error('Error fetching barcodes:', error);
            content.innerHTML = `
            <div class="p-12 text-center text-red-500">
                <span class="material-symbols-outlined text-4xl mb-2">error</span>
                <p class="text-xs font-bold">Failed to load barcode details.</p>
                <p class="text-[10px] mt-1 text-gray-400">${error.message}</p>
            </div>
        `;
        });
}

function showRefillBarcodes(location) {
    const modal = document.getElementById('barcodeModal');
    const content = document.getElementById('barcodeModalContent');

    if (!modal || !content) return;

    // Show modal
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Show loading state
    content.innerHTML = `
        <div class="flex flex-col items-center justify-center h-full py-24 text-gray-400">
            <div class="size-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-[10px] font-medium uppercase tracking-widest">Fetching refill details for ${location}...</p>
        </div>
    `;

    // Fetch data
    fetch(`/api/branchweight/refill-barcodes?location=${encodeURIComponent(location)}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch refill details');
            return response.text();
        })
        .then(html => {
            content.innerHTML = html;
        })
        .catch(error => {
            console.error('Error fetching refill barcodes:', error);
            content.innerHTML = `
            <div class="p-12 text-center text-red-500">
                <span class="material-symbols-outlined text-4xl mb-2">error</span>
                <p class="text-xs font-bold">Failed to load refill details.</p>
                <p class="text-[10px] mt-1 text-gray-400">${error.message}</p>
            </div>
        `;
        });
}

function closeBarcodeModal() {
    const modal = document.getElementById('barcodeModal');
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

// Modal Tree-Grid Toggle
function toggleModalRow(rowId) {
    const table = document.getElementById('barcode-tree-grid');
    if (!table) return;

    const icon = document.getElementById(`icon-${rowId}`);
    if (!icon) return;

    // expand_more (chevron down) means it IS collapsed and we WANT to expand.
    // expand_less (chevron up) means it IS expanded and we WANT to collapse.
    const isExpanding = icon.textContent === 'expand_more';

    // Toggle icon and rotation
    if (isExpanding) {
        icon.textContent = 'expand_less';
        icon.style.transform = 'rotate(-180deg)';
    } else {
        icon.textContent = 'expand_more';
        icon.style.transform = 'rotate(0deg)';
    }

    // Toggle children visibility
    const children = table.querySelectorAll(`.child-of-${rowId}`);

    children.forEach(child => {
        if (isExpanding) {
            // ONLY show immediate children. 
            // How to determine immediate? 
            // If we are zone (mz-), show states (ms-) that are child-of-mz-.
            // But don't show locations (ml-) if the state is not expanded.

            // Actually, a simpler approach:
            // When expanding, we only show rows that are DIRECT descendants.
            // But since we use nested classes, we can check if the row has OTHER parent classes that are still collapsed.

            // Check if all OTHER parents of this child are expanded.
            const classes = Array.from(child.classList);
            const parentClasses = classes.filter(c => c.startsWith('child-of-') && c !== `child-of-${rowId}`);

            let allParentsExpanded = true;
            for (const pc of parentClasses) {
                const parentId = pc.replace('child-of-', '');
                const parentIcon = document.getElementById(`icon-${parentId}`);
                if (parentIcon && parentIcon.textContent === 'expand_more') {
                    allParentsExpanded = false;
                    break;
                }
            }

            if (allParentsExpanded) {
                child.classList.remove('hidden');
            }
        } else {
            // HIDING: Hide everything that is a descendant
            child.classList.add('hidden');

            // Reset icons of sub-parents that might be expanded
            const subParentIcon = child.querySelector('.material-symbols-outlined[id^="icon-"]');
            if (subParentIcon) {
                subParentIcon.textContent = 'expand_more';
                subParentIcon.style.transform = 'rotate(0deg)';
            }
        }
    });
}
