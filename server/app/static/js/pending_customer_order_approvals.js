let currentZoom = parseFloat(localStorage.getItem('pending-approvals-zoom')) || 1.0;
let reportController;
let currentSortBy = 'primary';
let currentSortOrder = 'asc';

// MultiSelect Instances dictionary
const multiSelects = {};

function toggleSort(column) {
    if (currentSortBy === column) {
        currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortBy = column;
        currentSortOrder = (column === 'primary' || column === 'bh' || column === 'business_head') ? 'asc' : 'desc';
    }
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('sort_by', currentSortBy);
    urlParams.set('sort_order', currentSortOrder);
    urlParams.set('page', 1);
    history.replaceState(null, '', `${window.location.pathname}?${urlParams.toString()}`);
    loadApprovalsReport();
}
window.toggleSort = toggleSort;

async function loadApprovalsReport() {
    reportController?.abort();
    const controller = new AbortController();
    reportController = controller;

    const body = document.getElementById('view-pending-customer-order-approvals');
    const stats = document.getElementById('approvals-stats');
    const info = document.getElementById('pagination-info');

    if (stats) stats.setAttribute('aria-busy', 'true');
    if (body) {
        body.setAttribute('aria-busy', 'true');
        body.innerHTML = '<div class="p-6 flex items-center justify-center gap-2 text-xs text-gray-500" role="status"><span class="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></span>Loading report...</div>';
    }
    if (info) info.textContent = 'Loading report...';

    try {
        const headers = {};
        const token = localStorage.getItem('access_token');
        if (token) headers.Authorization = `Bearer ${token}`;

        const urlParams = new URLSearchParams(window.location.search);

        if (urlParams.has('sort_by')) {
            currentSortBy = urlParams.get('sort_by');
        } else {
            urlParams.set('sort_by', currentSortBy);
        }
        if (urlParams.has('sort_order')) {
            currentSortOrder = urlParams.get('sort_order');
        } else {
            urlParams.set('sort_order', currentSortOrder);
        }

        const response = await fetch(`/api/pending-customer-order-approvals/data?${urlParams.toString()}`, {
            headers,
            signal: controller.signal
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (controller !== reportController) return;

        if (body) body.innerHTML = data.html;

        // Update Stats values and progress bars
        if (data.stats) {
            for (const [key, value] of Object.entries(data.stats)) {
                const id = key.replaceAll('_', '-');
                if (key.endsWith('_perc')) {
                    const bar = document.getElementById(`stat-${id.replace(/-perc$/, '-bar')}`);
                    if (bar) bar.style.width = `${value}%`;
                } else {
                    const element = document.getElementById(`stat-${id}`);
                    if (element) {
                        if (key.endsWith('_pcs')) {
                            const pcsVal = (value !== undefined && value !== null && value !== '') ? value : '0';
                            element.textContent = `${pcsVal} Pcs`;
                        } else {
                            const wtVal = (value !== undefined && value !== null && value !== '') ? value : '0.000';
                            element.textContent = wtVal;
                        }
                    }
                }
            }
            const totalBar = document.getElementById('stat-total-bar');
            if (totalBar) totalBar.style.width = '100%';
        }

        if (info) info.textContent = `Showing ${data.count} of ${data.total} `;

        updateBadgeText();
        adjustZoom(0);
        updateActiveFilterChips();
    } catch (error) {
        if (error.name === 'AbortError' || controller !== reportController) return;
        console.error('Error loading approvals report:', error);
        if (info) info.textContent = 'Report unavailable';
        if (body) {
            body.innerHTML = '<div class="p-6 text-center text-xs text-red-500" role="alert">Unable to load report data. <button class="text-primary underline ml-1" onclick="loadApprovalsReport()">Retry</button></div>';
        }
    } finally {
        if (controller === reportController) {
            if (stats) stats.setAttribute('aria-busy', 'false');
            if (body) body.setAttribute('aria-busy', 'false');
        }
    }
}

let isInitialized = false;

function initializeApprovalsPage() {
    if (isInitialized) return;
    isInitialized = true;

    adjustZoom(0);

    const filterDataEl = document.getElementById('approvals-filter-data');
    let opts = {};
    if (filterDataEl && filterDataEl.dataset.options) {
        try {
            const raw = JSON.parse(filterDataEl.dataset.options);
            opts = Object.fromEntries(Object.entries(raw).map(([key, value]) => [
                key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase()), value
            ]));
        } catch (e) {
            console.error('Error parsing filter options:', e);
        }
    }

    const urlParams = new URLSearchParams(window.location.search);

    if (typeof CustomMultiSelect !== 'undefined') {
        const configs = [
            { id: 'filter-business-head-container', key: 'business_head', label: 'Business Head', defaultText: 'All Business Heads', options: opts.businessHeads },
            { id: 'filter-location-container', key: 'location', label: 'Location', defaultText: 'All Locations', options: opts.locations },
            { id: 'filter-state-container', key: 'state', label: 'State', defaultText: 'All States', options: opts.states },
            { id: 'filter-classification-owner-container', key: 'classification_owner', label: 'Classification Owner', defaultText: 'All Classification Owners', options: opts.classificationOwners },
            { id: 'filter-make-owner-container', key: 'make_owner', label: 'Make Owner', defaultText: 'All Make Owners', options: opts.makeOwners },
            { id: 'filter-collection-owner-container', key: 'collection_owner', label: 'Collection Owner', defaultText: 'All Collection Owners', options: opts.collectionOwners },
            { id: 'filter-request-type-container', key: 'request_type', label: 'Request Type', defaultText: 'All Request Types', options: opts.requestTypes },
            { id: 'filter-order-item-type-container', key: 'order_item_type', label: 'Order Item Type', defaultText: 'All Item Types', options: opts.orderItemTypes },
            { id: 'filter-order-ro-container', key: 'order_ro', label: 'Regional Office', defaultText: 'All ROs', options: opts.orderRos },
            { id: 'filter-division-container', key: 'division', label: 'Division', defaultText: 'All Divisions', options: opts.divisions },
            { id: 'filter-group-category-container', key: 'group_category', label: 'Group Category', defaultText: 'All Categories', options: opts.groupCategories },
            { id: 'filter-group-container', key: 'group', label: 'Group', defaultText: 'All Groups', options: opts.groups },
            { id: 'filter-make-container', key: 'make', label: 'Make', defaultText: 'All Makes', options: opts.makes },
            { id: 'filter-classification-container', key: 'classification', label: 'Classification', defaultText: 'All Classifications', options: opts.classifications },
            { id: 'filter-collection-container', key: 'collection', label: 'Collection', defaultText: 'All Collections', options: opts.collections },
            { id: 'filter-purity-container', key: 'purity', label: 'Purity', defaultText: 'All Purities', options: opts.purities },
            { id: 'filter-party-name-container', key: 'party_name', label: 'Party / Supplier', defaultText: 'All Parties', options: opts.partyNames },
            { id: 'filter-reorder-container', key: 'reorder', label: 'Reorder (Y/N)', defaultText: 'All Reorder Status', options: opts.reorderOptions },
            { id: 'filter-combine-order-status-container', key: 'combine_order_status', label: 'Combine Order Status', defaultText: 'All Order Statuses', options: opts.combineOrderStatuses },
        ];

        configs.forEach(cfg => {
            const container = document.getElementById(cfg.id);
            if (!container) return;

            multiSelects[cfg.key] = new CustomMultiSelect({
                containerId: cfg.id,
                label: cfg.label,
                defaultText: cfg.defaultText,
                options: cfg.options || []
            });

            const paramVal = urlParams.get(cfg.key);
            if (paramVal) {
                const selected = paramVal.split(',').map(v => v.trim()).filter(Boolean);
                document.querySelectorAll(`.${cfg.id}-checkbox`).forEach(cb => {
                    cb.checked = selected.includes(cb.value);
                });
                multiSelects[cfg.key].updateTriggerText();
            }
        });
    }

    // Set initial Request No value
    const reqNo = urlParams.get('request_no');
    if (reqNo) {
        const el = document.getElementById('filter-request-no');
        if (el) el.value = reqNo;
    }

    // Set initial date range values
    const reqFrom = urlParams.get('request_date_from');
    if (reqFrom) {
        const el = document.getElementById('filter-request-date-from');
        if (el) el.value = reqFrom;
    }
    const reqTo = urlParams.get('request_date_to');
    if (reqTo) {
        const el = document.getElementById('filter-request-date-to');
        if (el) el.value = reqTo;
    }

    const delivPeriod = urlParams.get('customer_delivery_period') || urlParams.get('delivery_period');
    if (delivPeriod) {
        const el = document.getElementById('filter-customer-delivery-period');
        if (el) el.value = delivPeriod;
    }
    const delivFrom = urlParams.get('customer_delivery_date_from');
    if (delivFrom) {
        const el = document.getElementById('filter-customer-delivery-from');
        if (el) el.value = delivFrom;
    }
    const delivTo = urlParams.get('customer_delivery_date_to');
    if (delivTo) {
        const el = document.getElementById('filter-customer-delivery-to');
        if (el) el.value = delivTo;
    }

    // Restore filter sidebar visibility if previously toggled
    if (localStorage.getItem('pending_approvals_filter_visible') === 'false') {
        const sidebar = document.getElementById('approvals-filter-sidebar');
        const button = document.getElementById('approvals-filter-toggle');
        if (sidebar && button) {
            sidebar.classList.add('hidden');
            sidebar.style.display = 'none';
            button.setAttribute('aria-expanded', 'false');
            button.setAttribute('aria-label', 'Show filters');
            button.title = 'Show filters';
            button.classList.remove('text-primary');
            button.classList.add('text-gray-400');
        }
    }

    updateActiveFilterChips();
    loadApprovalsReport();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApprovalsPage);
} else {
    initializeApprovalsPage();
}

window.addEventListener('popstate', () => {
    loadApprovalsReport();
});

function getFilterValues() {
    const filters = {};
    for (const [key, selectInstance] of Object.entries(multiSelects)) {
        if (selectInstance && typeof selectInstance.getValues === 'function') {
            const vals = selectInstance.getValues();
            if (vals.length > 0) {
                filters[key] = vals.join(',');
            }
        }
    }

    const reqNo = document.getElementById('filter-request-no')?.value?.trim();
    if (reqNo) filters['request_no'] = reqNo;

    const reqFrom = document.getElementById('filter-request-date-from')?.value;
    if (reqFrom) filters['request_date_from'] = reqFrom;

    const reqTo = document.getElementById('filter-request-date-to')?.value;
    if (reqTo) filters['request_date_to'] = reqTo;

    const delivPeriod = document.getElementById('filter-customer-delivery-period')?.value;
    if (delivPeriod) filters['customer_delivery_period'] = delivPeriod;

    const delivFrom = document.getElementById('filter-customer-delivery-from')?.value;
    if (delivFrom) filters['customer_delivery_date_from'] = delivFrom;

    const delivTo = document.getElementById('filter-customer-delivery-to')?.value;
    if (delivTo) filters['customer_delivery_date_to'] = delivTo;

    const searchVal = document.getElementById('hierarchy-search')?.value?.trim();
    if (searchVal) filters['search'] = searchVal;

    return filters;
}

function applyFilters() {
    const params = new URLSearchParams();
    const filters = getFilterValues();
    for (const [k, v] of Object.entries(filters)) {
        if (v) params.set(k, v);
    }
    const perPage = document.getElementById('per-page-select')?.value;
    if (perPage) params.set('per_page', perPage);

    params.set('sort_by', currentSortBy);
    params.set('sort_order', currentSortOrder);
    params.set('page', 1);

    history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`);
    updateActiveFilterChips();
    loadApprovalsReport();
}

function resetGlobalFilters() {
    for (const selectInstance of Object.values(multiSelects)) {
        if (selectInstance && typeof selectInstance.reset === 'function') {
            selectInstance.reset();
        }
    }
    const reqNo = document.getElementById('filter-request-no');
    if (reqNo) reqNo.value = '';
    const reqFrom = document.getElementById('filter-request-date-from');
    if (reqFrom) reqFrom.value = '';
    const reqTo = document.getElementById('filter-request-date-to');
    if (reqTo) reqTo.value = '';
    const delivPeriod = document.getElementById('filter-customer-delivery-period');
    if (delivPeriod) delivPeriod.value = '';
    const delivFrom = document.getElementById('filter-customer-delivery-from');
    if (delivFrom) delivFrom.value = '';
    const delivTo = document.getElementById('filter-customer-delivery-to');
    if (delivTo) delivTo.value = '';
    const searchVal = document.getElementById('hierarchy-search');
    if (searchVal) searchVal.value = '';

    const urlParams = new URLSearchParams();
    urlParams.set('sort_by', currentSortBy);
    urlParams.set('sort_order', currentSortOrder);
    const perPage = document.getElementById('per-page-select')?.value;
    if (perPage) urlParams.set('per_page', perPage);

    history.replaceState(null, '', `${window.location.pathname}?${urlParams.toString()}`);
    updateActiveFilterChips();
    loadApprovalsReport();
}

function updateActiveFilterChips() {
    // Active filters bar removed per user request
    return;
}

function removeFilterChip(key) {
    if (multiSelects[key] && typeof multiSelects[key].reset === 'function') {
        multiSelects[key].reset();
    }
    if (key === 'request_no') {
        const el = document.getElementById('filter-request-no');
        if (el) el.value = '';
    }
    if (key === 'request_date_from') {
        const el = document.getElementById('filter-request-date-from');
        if (el) el.value = '';
    }
    if (key === 'request_date_to') {
        const el = document.getElementById('filter-request-date-to');
        if (el) el.value = '';
    }
    if (key === 'customer_delivery_period' || key === 'delivery_period') {
        const el = document.getElementById('filter-customer-delivery-period');
        if (el) el.value = '';
    }
    if (key === 'customer_delivery_date_from') {
        const el = document.getElementById('filter-customer-delivery-from');
        if (el) el.value = '';
    }
    if (key === 'customer_delivery_date_to') {
        const el = document.getElementById('filter-customer-delivery-to');
        if (el) el.value = '';
    }
    if (key === 'search') {
        const el = document.getElementById('hierarchy-search');
        if (el) el.value = '';
    }

    const urlParams = new URLSearchParams(window.location.search);
    urlParams.delete(key);
    urlParams.set('page', 1);
    history.replaceState(null, '', `${window.location.pathname}?${urlParams.toString()}`);
    updateActiveFilterChips();
    loadApprovalsReport();
}

function updateBadgeText() {
    const badge = document.getElementById('stat-badge-text');
    if (badge) badge.textContent = 'BH → Classification Owner → Make Owner → Collection Owner';
}

function changePage(page) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    history.replaceState(null, '', `${window.location.pathname}?${urlParams.toString()}`);
    loadApprovalsReport();
}

function changePerPage(perPage) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    history.replaceState(null, '', `${window.location.pathname}?${urlParams.toString()}`);
    loadApprovalsReport();
}

function adjustZoom(delta, reset = false) {
    if (reset) currentZoom = 1.0;
    else currentZoom = Math.min(1.5, Math.max(0.7, currentZoom + delta));

    localStorage.setItem('pending-approvals-zoom', currentZoom);
    const zoomText = document.getElementById('zoom-level');
    if (zoomText) zoomText.textContent = `${Math.round(currentZoom * 100)}%`;

    const tableArea = document.getElementById('table-area');
    if (tableArea) {
        tableArea.style.zoom = currentZoom;
    }
}

let searchTimer;
function onSearchInput(val) {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        filterTableLocally(val);
    }, 200);
}

function filterTableLocally(query) {
    const filter = (query || '').toLowerCase().trim();
    const rows = document.querySelectorAll('#view-pending-customer-order-approvals tbody tr');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(filter) ? '' : 'none';
    });
}

// Hierarchical Tree-Grid Expand/Collapse:
// Level 1: BH -> Level 2: Classification Owner -> Level 3: Make Owner -> Level 4: Collection Owner
async function toggleRow(btn, level, value) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        let nextTr = tr.nextElementSibling;
        const levelOrder = { 'bh': 1, 'classification_owner': 2, 'make_owner': 3, 'collection_owner': 4 };
        const currentRank = levelOrder[level] || 1;

        while (nextTr) {
            const nextLevel = nextTr.dataset.level;
            const nextRank = levelOrder[nextLevel] || 1;
            if (nextRank <= currentRank) break;

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
            params.set('parent_level', level);
            params.set('parent_value', value);

            if (level === 'classification_owner') {
                params.set('bh_value', tr.dataset.bh || '');
            } else if (level === 'make_owner') {
                params.set('bh_value', tr.dataset.bh || '');
                params.set('classification_owner_value', tr.dataset.classificationOwner || '');
            }

            const token = localStorage.getItem('access_token');
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch(`/partial/pending-customer-order-approvals?${params.toString()}`, { headers });
            if (!response.ok) throw new Error("Failed to load children");

            const html = await response.text();
            const template = document.createElement('template');
            template.innerHTML = html;
            const newRows = template.content.querySelectorAll('tr');

            let referenceNode = tr;
            newRows.forEach(newRow => {
                newRow.classList.add('child-row');
                newRow.classList.add('animate-fade-in');
                if (level === 'bh') {
                    newRow.dataset.bh = value;
                } else if (level === 'classification_owner') {
                    newRow.dataset.bh = tr.dataset.bh || '';
                    newRow.dataset.classificationOwner = value;
                } else if (level === 'make_owner') {
                    newRow.dataset.bh = tr.dataset.bh || '';
                    newRow.dataset.classificationOwner = tr.dataset.classificationOwner || '';
                    newRow.dataset.makeOwner = value;
                }

                referenceNode.parentNode.insertBefore(newRow, referenceNode.nextSibling);
                referenceNode = newRow;
            });

            icon.textContent = 'remove_circle';
            tr.classList.add('bg-blue-50/50');
        } catch (e) {
            console.error('Error expanding row:', e);
            icon.textContent = 'error';
        }
    }
}

// Leaf Detail Modal Handler
async function openLeafModal(bh, classification_owner, make_owner, collection_owner) {
    const modal = document.getElementById('leaf-detail-modal');
    const overlay = document.getElementById('modal-overlay');
    const content = document.getElementById('leaf-detail-content');

    if (!modal || !overlay || !content) return;

    modal.classList.remove('hidden');
    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    content.innerHTML = `<div class="p-8 text-center text-gray-500 flex flex-col items-center justify-center h-full">
        <span class="animate-spin material-symbols-outlined text-4xl text-primary mb-2">sync</span>
        Loading customer order approval details...
    </div>`;

    const urlParams = new URLSearchParams(window.location.search);
    const params = new URLSearchParams(urlParams);
    if (bh) params.set('parent_bh', bh);
    if (classification_owner) params.set('parent_classification_owner', classification_owner);
    if (make_owner) params.set('parent_make_owner', make_owner);
    if (collection_owner) params.set('parent_collection_owner', collection_owner);

    try {
        const token = localStorage.getItem('access_token');
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch(`/partial/pending-customer-order-approvals/leaf_detail?${params.toString()}`, { headers });
        if (!response.ok) throw new Error('Failed to fetch details');
        content.innerHTML = await response.text();
    } catch (e) {
        console.error('Error opening leaf modal:', e);
        content.innerHTML = `<div class="p-8 text-center text-red-500">Error loading details. Please close and try again.</div>`;
    }
}

function closeLeafModal() {
    const modal = document.getElementById('leaf-detail-modal');
    const overlay = document.getElementById('modal-overlay');
    if (modal) modal.classList.add('hidden');
    if (overlay) overlay.classList.add('hidden');
    document.body.style.overflow = '';
}

function switchApprovalLeafView(view) {
    document.querySelectorAll('#leaf-detail-content [data-co-panel]').forEach(panel => {
        panel.hidden = panel.dataset.coPanel !== view;
    });
    document.querySelectorAll('#leaf-detail-content [data-co-view]').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.coView === view));
    });
}

function filterApprovalLeaf(query) {
    const search = (query || '').trim().toLowerCase();
    const records = document.querySelectorAll('#leaf-detail-content [data-co-search]');
    let matches = 0;
    records.forEach(record => {
        record.hidden = !record.dataset.coSearch.includes(search);
        if (!record.hidden) matches++;
    });
    const empty = document.getElementById('approval-leaf-no-matches');
    if (empty) empty.hidden = matches > 0 || !search;
}

document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !document.getElementById('leaf-detail-modal')?.classList.contains('hidden')) {
        closeLeafModal();
    }
});

function toggleApprovalsFilters() {
    const sidebar = document.getElementById('approvals-filter-sidebar');
    const button = document.getElementById('approvals-filter-toggle');
    if (!sidebar || !button) return;
    const isHidden = sidebar.classList.contains('hidden') || sidebar.style.display === 'none';
    if (isHidden) {
        sidebar.classList.remove('hidden');
        sidebar.style.display = '';
        button.setAttribute('aria-expanded', 'true');
        button.setAttribute('aria-label', 'Hide filters');
        button.title = 'Hide filters';
        button.classList.add('text-primary');
        button.classList.remove('text-gray-400');
        localStorage.setItem('pending_approvals_filter_visible', 'true');
    } else {
        sidebar.classList.add('hidden');
        sidebar.style.display = 'none';
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-label', 'Show filters');
        button.title = 'Show filters';
        button.classList.remove('text-primary');
        button.classList.add('text-gray-400');
        localStorage.setItem('pending_approvals_filter_visible', 'false');
    }
}

// Global window assignments for inline event handlers
window.toggleApprovalsFilters = toggleApprovalsFilters;
window.applyFilters = applyFilters;
window.resetGlobalFilters = resetGlobalFilters;
window.removeFilterChip = removeFilterChip;
window.toggleRow = toggleRow;
window.openLeafModal = openLeafModal;
window.closeLeafModal = closeLeafModal;
window.switchApprovalLeafView = switchApprovalLeafView;
window.filterApprovalLeaf = filterApprovalLeaf;
window.changePage = changePage;
window.changePerPage = changePerPage;
window.adjustZoom = adjustZoom;
window.onSearchInput = onSearchInput;
window.loadApprovalsReport = loadApprovalsReport;
