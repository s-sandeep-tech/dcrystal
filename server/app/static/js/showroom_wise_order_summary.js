let currentZoom = parseFloat(localStorage.getItem('showroom-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('showroom-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-showroom');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/showroom?${searchParams}`, {
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

        // Initialize from the new content
        initializeViewFromDOM(activeView);

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    }
}

function initializeViewFromDOM(activeView) {
    if (!activeView) activeView = document.getElementById('view-showroom');
    if (!activeView) return;

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
}

function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge) {
        badge.textContent = level?.toUpperCase().replace('_', ' ') || 'BUSINESS HEAD';
    }
}

function updateDashboardStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-total-order-wt': stats.total_order_wt,
        'stat-accepted-wt': stats.accepted_wt,
        'stat-rejected-wt': stats.rejected_wt,
        'stat-cancelled-wt': stats.cancelled_wt,
        'stat-pending-to-accept-wt': stats.pending_to_accepted_wt,
        'stat-barcoded-wt': stats.barcoded_wt,
        'stat-hallmarked-wt': stats.hm_passed_wt,
        'stat-qc-passed-wt': stats.qc_passed_wt,
        'stat-invoiced-wt': stats.invoiced_wt,
        'stat-delivered-wt': stats.delivered_wt,
        'stat-pending-to-deliver-wt': stats.pending_to_deliver_wt
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value !== undefined ? parseFloat(value).toFixed(3) : '0.000';
        }
    }
}

async function toggleRow(btn) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const level = tr.dataset.level;
    const businessHead = tr.dataset.businessHead;
    const classificationOwner = tr.dataset.classificationOwner;
    const makeOwner = tr.dataset.makeOwner;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        let nextTr = tr.nextElementSibling;
        while (nextTr) {
            const nextLevel = nextTr.dataset.level;
            if (level === 'business_head' && nextLevel === 'business_head') break;
            if (level === 'classification_owner' && (nextLevel === 'classification_owner' || nextLevel === 'business_head')) break;
            if (level === 'make_owner' && (nextLevel === 'make_owner' || nextLevel === 'classification_owner' || nextLevel === 'business_head')) break;

            const toRemove = nextTr;
            nextTr = nextTr.nextElementSibling;
            toRemove.remove();
        }
        icon.textContent = 'add_circle';
        tr.classList.remove('bg-blue-50/50');
    } else {
        icon.textContent = 'hourglass_empty';

        try {
            const urlParams = new URLSearchParams(window.location.search);
            const params = new URLSearchParams(urlParams);
            
            // Set expansion context
            params.set('parent_level', level);
            if (businessHead) params.set('business_head', businessHead);
            if (classificationOwner) params.set('classification_owner', classificationOwner);
            if (makeOwner) params.set('make_owner', makeOwner);

            // Determine which value to identify the expansion target to the backend
            let parentValue = '';
            if (level === 'business_head') parentValue = businessHead;
            else if (level === 'classification_owner') parentValue = classificationOwner;
            else if (level === 'make_owner') parentValue = makeOwner;
            params.set('parent_value', parentValue);

            const response = await fetch(`/partial/showroom?${params.toString()}`, {
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
            tr.classList.add('bg-blue-50/50');

        } catch (e) {
            console.error(e);
            icon.textContent = 'error';
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
    
    // Clear expansion state when applying filters
    urlParams.delete('parent_level');
    urlParams.delete('parent_value');
    
    const filterIds = [
        'business_head', 'classification_owner', 'make_owner', 'collection_owner',
        'division', 'group_name', 'purity', 'classification', 'make', 'collection',
        'party', 'location', 'purchase_ro', 'order_type', 'order_request_type',
        'provision_type', 'branch_provision_type'
    ];
    
    filterIds.forEach(id => {
        const val = document.getElementById(`filter-${id}`)?.value;
        if (val) urlParams.set(id, val);
        else urlParams.delete(id);
    });

    const searchVal = document.getElementById('hierarchy-search')?.value;
    if (searchVal) urlParams.set('search', searchVal);
    else urlParams.delete('search');

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const filterIds = [
        'business_head', 'classification_owner', 'make_owner', 'collection_owner',
        'division', 'group_name', 'purity', 'classification', 'make', 'collection',
        'party', 'location', 'purchase_ro', 'order_type', 'order_request_type',
        'provision_type', 'branch_provision_type'
    ];
    
    filterIds.forEach(id => {
        const el = document.getElementById(`filter-${id}`);
        if (el) el.value = '';
    });

    const search = document.getElementById('hierarchy-search');
    if (search) search.value = '';

    const urlParams = new URLSearchParams();
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
    loadFilterOptions();
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

    const start = total > 0 ? (page - 1) * perPage + 1 : 0;
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
    urlParams.delete('parent_level');
    urlParams.delete('parent_value');
    urlParams.set('page', page);
    updateUrlAndLoad(urlParams);
}

function changePerPage(perPage) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.delete('parent_level');
    urlParams.delete('parent_value');
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

async function loadFilterOptions() {
    try {
        const response = await fetch(`/api/showroom/options`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const options = await response.json();
        const urlParams = new URLSearchParams(window.location.search);

        const mappings = [
            { id: 'filter-business_head', list: options.business_heads, label: 'Business Head' },
            { id: 'filter-classification_owner', list: options.classification_owners, label: 'Classification Owner' },
            { id: 'filter-make_owner', list: options.make_owners, label: 'Make Owner' },
            { id: 'filter-collection_owner', list: options.collection_owners, label: 'Collection Owner' },
            { id: 'filter-division', list: options.divisions, label: 'Division' },
            { id: 'filter-group_name', list: options.groups, label: 'Group' },
            { id: 'filter-purity', list: options.purities, label: 'Purity' },
            { id: 'filter-classification', list: options.classifications, label: 'Classification' },
            { id: 'filter-make', list: options.makes, label: 'Make' },
            { id: 'filter-collection', list: options.collections, label: 'Collection' },
            { id: 'filter-party', list: options.parties, label: 'Party' },
            { id: 'filter-location', list: options.locations, label: 'Location' },
            { id: 'filter-purchase_ro', list: options.purchase_ros, label: 'Purchase RO' },
            { id: 'filter-order_type', list: options.order_types, label: 'Order Type' },
            { id: 'filter-order_request_type', list: options.order_request_types, label: 'Order Request Type' },
            { id: 'filter-provision_type', list: options.provision_types, label: 'Provision Type' },
            { id: 'filter-branch_provision_type', list: options.branch_provision_types, label: 'Branch Provision Type' }
        ];

        mappings.forEach(m => {
            populateSelect(m.id, m.list, `All ${m.label}s`, urlParams.get(m.id.replace('filter-', '')));
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

function showDetails(business_head, classification_owner, make_owner, collection_owner) {
    const modal = document.getElementById('detailsModal');
    const content = document.getElementById('detailsModalContent');

    if (!modal || !content) return;

    // Update Modal Subtitle with Parent Context
    const subtitle = document.getElementById('detailsModalSubtitle');
    if (subtitle) {
        const parts = [];
        if (business_head && business_head !== 'Unknown') parts.push(`BUSINESS HEAD = ${business_head}`);
        if (classification_owner) parts.push(`OWNER = ${classification_owner}`);
        if (make_owner) parts.push(`MAKE = ${make_owner}`);
        if (collection_owner) parts.push(`COLLECTION = ${collection_owner}`);
        subtitle.textContent = parts.join(' | ');
    }

    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    content.innerHTML = `
        <div class="flex flex-col items-center justify-center h-full py-24 text-gray-400">
            <div class="size-8 border-2 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-[10px] font-medium uppercase tracking-widest">Fetching details...</p>
        </div>
    `;

    // Inherit all current global filters
    const params = new URLSearchParams(window.location.search);
    
    // Apply specific hierarchy constraints
    if (business_head && business_head !== 'Unknown') params.set('business_head', business_head);
    if (classification_owner && classification_owner !== '') params.set('classification_owner', classification_owner);
    if (make_owner && make_owner !== '') params.set('make_owner', make_owner);
    if (collection_owner && collection_owner !== '') params.set('collection_owner', collection_owner);

    // Remove tree pagination params
    params.delete('page');
    params.delete('per_page');

    fetch(`/api/showroom/details?${params.toString()}`, {
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
        console.error('Error:', error);
        content.innerHTML = `<div class="p-12 text-center text-red-500">Error loading details.</div>`;
    });
}

function closeDetailsModal() {
    const modal = document.getElementById('detailsModal');
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

function drillDownFromModal(filterId, value) {
    console.log('drillDownFromModal called:', filterId, value);
    const el = document.getElementById(`filter-${filterId}`);
    if (el) {
        console.log('Found filter element:', el.id);
        
        // Try exact match first
        el.value = value;
        
        // If not found (value preserved if invalid in some browsers, but check), try trimming
        if (el.value !== value && value) {
            const trimmed = value.trim();
            for (let i = 0; i < el.options.length; i++) {
                if (el.options[i].value.trim() === trimmed) {
                    el.selectedIndex = i;
                    console.log('Found trimmed match at index:', i);
                    break;
                }
            }
        }

        closeDetailsModal();
        applyGlobalFilters();
        
        // Scroll to sidebar and highlight the changed filter briefly
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
        setTimeout(() => {
            el.classList.remove('ring-2', 'ring-primary', 'ring-offset-2');
        }, 2000);
    } else {
        console.warn('Filter element not found:', `filter-${filterId}`);
    }
}

async function toggleModalRow(btn, currentLevel, value) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';
    
    // Define hierarchy of the modal tree
    const hierarchy = ['location', 'division', 'group_name', 'purity', 'classification', 'make', 'collection', 'party', 'orders'];
    const currentIndex = hierarchy.indexOf(currentLevel);
    const nextLevel = hierarchy[currentIndex + 1];

    if (isExpanded) {
        // Collapse: remove all next sibling rows that have a deeper modal-level
        let nextTr = tr.nextElementSibling;
        while (nextTr && nextTr.classList.contains('modal-child-row')) {
            const nextLevelIdx = hierarchy.indexOf(nextTr.dataset.modalLevel);
            if (nextLevelIdx <= currentIndex) break;
            
            const toRemove = nextTr;
            nextTr = nextTr.nextElementSibling;
            toRemove.remove();
        }
        icon.textContent = 'add_circle';
        tr.classList.remove('bg-blue-50/50');
    } else {
        // Expand
        icon.textContent = 'hourglass_empty';
        
        try {
            // Get global filters from window URL
            const urlParams = new URLSearchParams(window.location.search);
            
            // Get context from modal wrapper
            const modalContext = document.querySelector('.modal-context');
            if (modalContext) {
                const ds = modalContext.dataset;
                if (ds.businessHead) urlParams.set('business_head', ds.businessHead);
                if (ds.classificationOwner) urlParams.set('classification_owner', ds.classificationOwner);
                if (ds.makeOwner) urlParams.set('make_owner', ds.makeOwner);
                if (ds.collectionOwner) urlParams.set('collection_owner', ds.collectionOwner);
            }
            
            // Append all dataset attributes from current row as filters
            const dataset = tr.dataset;
            hierarchy.forEach(col => {
                const camelCol = col.replace(/_([a-z])/g, g => g[1].toUpperCase());
                if (dataset[camelCol]) {
                    urlParams.set(col, dataset[camelCol]);
                }
            });
            
            urlParams.set('modal_level', nextLevel);
            urlParams.set('is_modal_child', 'true');
            
            const response = await fetch(`/api/showroom/details?${urlParams.toString()}`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
            });
            
            if (!response.ok) throw new Error("Failed to load modal children");
            const html = await response.text();
            
            const template = document.createElement('template');
            template.innerHTML = html;
            const newRows = template.content.querySelectorAll('tr');
            
            let referenceNode = tr;
            newRows.forEach(newRow => {
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

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;
    
    const activeView = document.getElementById('view-showroom');
    if (activeView && activeView.querySelector('.enterprise-grid')) {
        // Content already present from server-side render, just initialize
        console.log('Initializing from server-rendered content');
        initializeViewFromDOM(activeView);
    } else {
        // No content, fetch it
        loadViewData();
    }
    
    loadFilterOptions();
});
