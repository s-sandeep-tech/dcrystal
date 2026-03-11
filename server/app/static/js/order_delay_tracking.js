let currentZoom = parseFloat(localStorage.getItem('order-delay-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('order-delay-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-order-delay');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    // Show loading spinner while fetching
    activeView.innerHTML = `
        <div class="flex flex-col items-center justify-center py-32 text-gray-400">
            <div class="size-8 border-2 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-[10px] font-medium uppercase tracking-widest italic animate-pulse">Loading report data...</p>
        </div>
    `;

    try {
        const response = await fetch(`/partial/orderdelaytracking?${searchParams}`, {
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
                
                // Also update level badge if it exists in the meta
                const metaDiv = activeView.querySelector('.pagination-meta');
                if (metaDiv) {
                    updateLevelBadge(metaDiv.dataset.level, stats.row_count);
                }
            } catch (e) {
                console.error('Error parsing stats metadata:', e);
            }
        }

        // Parse pagination & Level
        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
            // The updateLevelBadge call was moved into the statsScript block
        }

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    }
}

function updateLevelBadge(level, count = 0) {
    const badge = document.getElementById('current-level-badge');
    if (!badge) return;

    let icon = 'layers';
    let text = 'Classification';

    if (level === 'make_owner') {
        icon = 'factory';
        text = 'Make Owner';
    } else if (level === 'collection_owner') {
        icon = 'inventory_2';
        text = 'Collection Owner';
    }

    badge.innerHTML = `
        <span class="material-symbols-outlined text-[16px]">${icon}</span>
        <span>${text} (${count})</span>
    `;
}

function updateDashboardStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-delay-1-2': stats.delay_1_2_days,
        'stat-delay-3-4': stats.delay_3_4_days,
        'stat-delay-5-10': stats.delay_5_10_days,
        'stat-delay-more-10': stats.delay_more_than_10_days,
        'stat-qc-delay-1-2': stats.qc_delay_1_2_days,
        'stat-qc-delay-3-4': stats.qc_delay_3_4_days,
        'stat-qc-delay-5-10': stats.qc_delay_5_10_days,
        'stat-qc-delay-more-10': stats.qc_delay_more_than_10_days
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value || 0;
        }
    }
}

async function toggleRow(btn, level, value, grandparentValue = null) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        // Collapse: Hide all children
        let nextTr = tr.nextElementSibling;
        while (nextTr) {
            const nextLevel = nextTr.dataset.level;

            // Stop if we hit a row at the same or higher level than the one being collapsed
            if (level === 'classification_owner' && nextLevel === 'classification_owner') break;
            if (level === 'make_owner' && (nextLevel === 'make_owner' || nextLevel === 'classification_owner')) break;

            const toRemove = nextTr;
            nextTr = nextTr.nextElementSibling;
            toRemove.remove();
        }
        icon.textContent = 'add_circle';
        tr.classList.remove('bg-blue-50/30');
    } else {
        // Expand: Fetch children
        icon.textContent = 'hourglass_empty'; // Loading state

        try {
            const urlParams = new URLSearchParams(window.location.search);
            const params = new URLSearchParams(urlParams);
            params.set('parent_level', level);
            params.set('parent_value', value);
            if (grandparentValue) params.set('grandparent_value', grandparentValue);

            const response = await fetch(`/partial/orderdelaytracking?${params.toString()}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });

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
            tr.classList.add('bg-blue-50/30');

        } catch (e) {
            console.error(e);
            icon.textContent = 'error';
        }
    }
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

function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

async function loadFilterOptions() {
    try {
        const response = await fetch(`/api/orderdelaytracking/options`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const options = await response.json();

        populateSelect('filter-supplier', options.suppliers, 'Party');
        populateSelect('filter-classification-owner', options.classification_owners, 'Classification Owner');
        populateSelect('filter-make-owner', options.make_owners, 'Make Owner');
        populateSelect('filter-collection-owner', options.collection_owners, 'Collection Owner');
        populateSelect('filter-make', options.makes, 'Make');
        populateSelect('filter-collection', options.collections, 'Collection');

        // Restore values from URL
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('supplier')) document.getElementById('filter-supplier').value = urlParams.get('supplier');
        if (urlParams.get('classification_owner')) document.getElementById('filter-classification-owner').value = urlParams.get('classification_owner');
        if (urlParams.get('make_owner')) document.getElementById('filter-make-owner').value = urlParams.get('make_owner');
        if (urlParams.get('collection_owner')) document.getElementById('filter-collection-owner').value = urlParams.get('collection_owner');
        if (urlParams.get('make')) document.getElementById('filter-make').value = urlParams.get('make');
        if (urlParams.get('collection')) document.getElementById('filter-collection').value = urlParams.get('collection');

    } catch (e) {
        console.error('Error loading options:', e);
    }
}

function populateSelect(id, list, placeholder) {
    const el = document.getElementById(id);
    if (!el) return;
    let html = `<option value="">All ${placeholder}s</option>`;
    list.forEach(item => {
        html += `<option value="${item}">${item}</option>`;
    });
    el.innerHTML = html;
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const supplier = document.getElementById('filter-supplier').value;
    const co = document.getElementById('filter-classification-owner').value;
    const mo = document.getElementById('filter-make-owner').value;
    const coll = document.getElementById('filter-collection-owner').value;
    const make = document.getElementById('filter-make').value;
    const collection = document.getElementById('filter-collection').value;
    const searchVal = document.getElementById('hierarchy-search')?.value;

    if (supplier) urlParams.set('supplier', supplier); else urlParams.delete('supplier');
    if (co) urlParams.set('classification_owner', co); else urlParams.delete('classification_owner');
    if (mo) urlParams.set('make_owner', mo); else urlParams.delete('make_owner');
    if (coll) urlParams.set('collection_owner', coll); else urlParams.delete('collection_owner');
    if (make) urlParams.set('make', make); else urlParams.delete('make');
    if (collection) urlParams.set('collection', collection); else urlParams.delete('collection');
    if (searchVal) urlParams.set('search', searchVal); else urlParams.delete('search');

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.delete('supplier');
    urlParams.delete('classification_owner');
    urlParams.delete('make_owner');
    urlParams.delete('collection_owner');
    urlParams.delete('make');
    urlParams.delete('collection');
    urlParams.delete('search');
    urlParams.set('page', 1);

    document.getElementById('filter-supplier').value = '';
    document.getElementById('filter-classification-owner').value = '';
    document.getElementById('filter-make-owner').value = '';
    document.getElementById('filter-collection-owner').value = '';
    document.getElementById('filter-make').value = '';
    document.getElementById('filter-collection').value = '';

    const search = document.getElementById('hierarchy-search');
    if (search) search.value = '';

    updateUrlAndLoad(urlParams);
}

function onSearchInput(value) {
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
        applyGlobalFilters();
    }, 500);
}

async function showDetails(co, mo, colo) {
    const modal = document.getElementById('detailsModal');
    const content = document.getElementById('detailsModalContent');
    const title = document.getElementById('modalTitle');
    const subtitle = document.getElementById('modalSubtitle');

    if (!modal || !content) return;

    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Store context for subsequent drill-downs in modal
    content.dataset.co = co;
    content.dataset.mo = mo;
    content.dataset.colo = colo;

    title.textContent = "Loading Details...";
    subtitle.textContent = `${co} > ${mo} > ${colo}`;

    content.innerHTML = `
        <div class="flex flex-col items-center justify-center grow py-24 text-gray-400">
            <div class="size-8 border-2 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-[10px] font-medium uppercase tracking-widest italic">Retrieving aggregate delay data...</p>
        </div>
    `;

    try {
        const urlParams = new URLSearchParams(window.location.search);
        const params = new URLSearchParams();
        params.set('classification_owner', co);
        params.set('make_owner', mo);
        params.set('collection_owner', colo);

        // Pass existing global filters to the modal constraints
        if (urlParams.get('supplier')) params.set('supplier', urlParams.get('supplier'));
        if (urlParams.get('make')) params.set('make', urlParams.get('make'));
        if (urlParams.get('collection')) params.set('collection', urlParams.get('collection'));
        if (urlParams.get('search')) params.set('search', urlParams.get('search'));

        const response = await fetch(`/api/orderdelaytracking/details?${params.toString()}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch details');
        const html = await response.text();

        title.textContent = `Delay Details: ${colo}`;
        content.innerHTML = html;
    } catch (error) {
        console.error('Error fetching details:', error);
        content.innerHTML = `<div class="p-12 text-center text-red-500 font-bold uppercase tracking-widest text-[10px]">Failed to load analytical details. Please try again.</div>`;
    }
}

async function toggleModalRow(btn, level, value, grandparentValue = null) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const content = document.getElementById('detailsModalContent');
    if (!content) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        // Collapse: Hide all children
        let nextTr = tr.nextElementSibling;
        while (nextTr) {
            const nextLevel = nextTr.dataset.level;

            // Stop if we hit a row at the same or higher level than the one being collapsed
            if (level === 'party' && nextLevel === 'party') break;
            if (level === 'make' && (nextLevel === 'make' || nextLevel === 'party')) break;

            const toRemove = nextTr;
            nextTr = nextTr.nextElementSibling;
            toRemove.remove();
        }
        icon.textContent = 'add_circle';
        tr.classList.remove('bg-blue-50/20');
    } else {
        // Expand: Fetch children
        icon.textContent = 'hourglass_empty'; // Loading state

        try {
            const urlParams = new URLSearchParams(window.location.search);
            const params = new URLSearchParams();
            // Use stored context
            params.set('classification_owner', content.dataset.co);
            params.set('make_owner', content.dataset.mo);
            params.set('collection_owner', content.dataset.colo);

            // Pass existing global filters to the modal constraints
            if (urlParams.get('supplier')) params.set('supplier', urlParams.get('supplier'));
            if (urlParams.get('make')) params.set('make', urlParams.get('make'));
            if (urlParams.get('collection')) params.set('collection', urlParams.get('collection'));
            if (urlParams.get('search')) params.set('search', urlParams.get('search'));

            // Add modal-specific drill-down params
            params.set('modal_parent_level', level);
            params.set('modal_parent_value', value);
            if (grandparentValue) params.set('modal_grandparent_value', grandparentValue);

            const response = await fetch(`/api/orderdelaytracking/details?${params.toString()}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });

            if (!response.ok) throw new Error("Failed to load modal children");
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
            tr.classList.add('bg-blue-50/20');

        } catch (e) {
            console.error(e);
            icon.textContent = 'error';
        }
    }
}

function closeDetailsModal() {
    const modal = document.getElementById('detailsModal');
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    // Sync UI from URL
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('search')) document.getElementById('hierarchy-search').value = urlParams.get('search');

    loadViewData();
    loadFilterOptions();
});
