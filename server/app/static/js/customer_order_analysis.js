let currentZoom = parseFloat(localStorage.getItem('customer-order-zoom')) || 1.0;
let reportController;
let currentHierarchyMode = 'location';
let currentSortBy = 'primary';
let currentSortOrder = 'asc';

// MultiSelect Instances
const multiSelects = {};

window.addEventListener('load', () => loadCustomerOrderReport(), { once: true });

function toggleSort(column) {
    if (currentSortBy === column) {
        currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortBy = column;
        currentSortOrder = (column === 'primary' || column === 'location' || column === 'section') ? 'asc' : 'desc';
    }
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('sort_by', currentSortBy);
    urlParams.set('sort_order', currentSortOrder);
    urlParams.set('page', 1);
    history.replaceState(null, '', `${window.location.pathname}?${urlParams}`);
    loadCustomerOrderReport();
}
window.toggleSort = toggleSort;

async function loadCustomerOrderReport() {
    reportController?.abort();
    const controller = new AbortController();
    reportController = controller;

    const body = document.getElementById('view-customer-order-analysis');
    const stats = document.getElementById('customer-order-stats');
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
        if (!urlParams.has('hierarchy_mode')) {
            urlParams.set('hierarchy_mode', currentHierarchyMode);
        } else {
            currentHierarchyMode = urlParams.get('hierarchy_mode');
            updateHierarchyModeButtons(currentHierarchyMode);
        }

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

        const response = await fetch(`/api/customer-order-analysis/data?${urlParams.toString()}`, {
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
                    if (element) element.textContent = `${value}${key.endsWith('_pcs') ? ' Pcs' : ''}`;
                }
            }
            const totalBar = document.getElementById('stat-total-bar');
            if (totalBar) totalBar.style.width = '100%';
        }

        const levelLabel = currentHierarchyMode === 'section' ? 'sections' : 'locations';
        if (info) info.textContent = `Showing ${data.count} of ${data.total} ${levelLabel}`;

        updateBadgeText();
        adjustZoom(0);
    } catch (error) {
        if (error.name === 'AbortError' || controller !== reportController) return;
        if (info) info.textContent = 'Report unavailable';
        if (body) {
            body.innerHTML = '<div class="p-6 text-center text-xs text-red-500" role="alert">Unable to load report data. <button class="text-primary underline ml-1" onclick="loadCustomerOrderReport()">Retry</button></div>';
        }
    } finally {
        if (controller === reportController) {
            if (stats) stats.setAttribute('aria-busy', 'false');
            if (body) body.setAttribute('aria-busy', 'false');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    adjustZoom(0);
    const opts = window.customerOrderFilterOptions || {};
    const urlParams = new URLSearchParams(window.location.search);

    if (typeof CustomMultiSelect !== 'undefined') {
        const configs = [
            { id: 'filter-order-status-container', key: 'order_status', label: 'Order Status', defaultText: 'All Order Statuses', options: opts.orderStatuses },
            { id: 'filter-state-container', key: 'state', label: 'State', defaultText: 'All States', options: opts.states },
            { id: 'filter-location-container', key: 'location', label: 'Location', defaultText: 'All Locations', options: opts.locations },
            { id: 'filter-business-head-container', key: 'business_head', label: 'Business Head', defaultText: 'All Business Heads', options: opts.businessHeads },
            { id: 'filter-order-ro-container', key: 'order_ro', label: 'Regional Office', defaultText: 'All ROs', options: opts.orderRos },
            { id: 'filter-branch-type-container', key: 'branch_type', label: 'Branch Type', defaultText: 'All Branch Types', options: opts.branchTypes },
            { id: 'filter-division-container', key: 'division', label: 'Division', defaultText: 'All Divisions', options: opts.divisions },
            { id: 'filter-group-category-container', key: 'group_category', label: 'Group Category', defaultText: 'All Categories', options: opts.groupCategories },
            { id: 'filter-group-container', key: 'group', label: 'Group', defaultText: 'All Groups', options: opts.groups },
            { id: 'filter-classification-container', key: 'classification', label: 'Classification', defaultText: 'All Classifications', options: opts.classifications },
            { id: 'filter-sub-classification-container', key: 'sub_classification', label: 'Sub Classification', defaultText: 'All Sub Classifications', options: opts.subClassifications },
            { id: 'filter-make-container', key: 'make', label: 'Make', defaultText: 'All Makes', options: opts.makes },
            { id: 'filter-section-container', key: 'section', label: 'Section', defaultText: 'All Sections', options: opts.sections },
            { id: 'filter-collection-container', key: 'collection', label: 'Collection', defaultText: 'All Collections', options: opts.collections },
            { id: 'filter-purity-container', key: 'purity', label: 'Purity', defaultText: 'All Purities', options: opts.purities },
            { id: 'filter-supplier-container', key: 'supplier', label: 'Supplier', defaultText: 'All Suppliers', options: opts.suppliers },
            { id: 'filter-party-type-container', key: 'party_type', label: 'Supplier Type', defaultText: 'All Supplier Types', options: opts.partyTypes },
            { id: 'filter-customer-order-type-container', key: 'customer_order_type', label: 'Order Type', defaultText: 'All Order Types', options: opts.customerOrderTypes },
            { id: 'filter-classification-owner-container', key: 'classification_owner', label: 'Classification Owner', defaultText: 'All Owners', options: opts.classificationOwners },
            { id: 'filter-make-owner-container', key: 'make_owner', label: 'Make Owner', defaultText: 'All Owners', options: opts.makeOwners },
            { id: 'filter-collection-owner-container', key: 'collection_owner', label: 'Collection Owner', defaultText: 'All Owners', options: opts.collectionOwners },
            { id: 'filter-shop-manager-container', key: 'shop_manager', label: 'Shop Manager', defaultText: 'All Shop Managers', options: opts.shopManagers },
            { id: 'filter-gender-container', key: 'gender', label: 'Gender', defaultText: 'All Genders', options: opts.genders },
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
    const expFrom = urlParams.get('expected_delivery_date_from');
    if (expFrom) {
        const el = document.getElementById('filter-expected-delivery-from');
        if (el) el.value = expFrom;
    }
    const expTo = urlParams.get('expected_delivery_date_to');
    if (expTo) {
        const el = document.getElementById('filter-expected-delivery-to');
        if (el) el.value = expTo;
    }
    const orderAge = urlParams.get('order_age');
    if (orderAge) {
        const el = document.getElementById('filter-order-age');
        if (el) el.value = orderAge;
    }
    const advLinked = urlParams.get('advance_linked');
    if (advLinked) {
        const el = document.getElementById('filter-advance-linked');
        if (el) el.value = advLinked;
    }
    const delivPeriod = urlParams.get('delivery_period') || urlParams.get('expected_delivery_period');
    if (delivPeriod) {
        const el = document.getElementById('filter-delivery-period');
        if (el) el.value = delivPeriod;
    }

    // Mode check
    const modeParam = urlParams.get('hierarchy_mode');
    if (modeParam) {
        currentHierarchyMode = modeParam;
        updateHierarchyModeButtons(currentHierarchyMode);
    }
});

function switchHierarchyMode(mode) {
    if (currentHierarchyMode === mode) return;
    currentHierarchyMode = mode;
    updateHierarchyModeButtons(mode);

    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('hierarchy_mode', mode);
    urlParams.set('page', 1);
    history.replaceState(null, '', `${window.location.pathname}?${urlParams}`);
    loadCustomerOrderReport();
}

function updateHierarchyModeButtons(mode) {
    const locBtn = document.getElementById('mode-location');
    const secBtn = document.getElementById('mode-section');
    if (mode === 'section') {
        secBtn?.classList.add('bg-white', 'dark:bg-gray-700', 'shadow-xs', 'text-primary');
        secBtn?.classList.remove('hover:text-primary');
        locBtn?.classList.remove('bg-white', 'dark:bg-gray-700', 'shadow-xs', 'text-primary');
        locBtn?.classList.add('hover:text-primary');
    } else {
        locBtn?.classList.add('bg-white', 'dark:bg-gray-700', 'shadow-xs', 'text-primary');
        locBtn?.classList.remove('hover:text-primary');
        secBtn?.classList.remove('bg-white', 'dark:bg-gray-700', 'shadow-xs', 'text-primary');
        secBtn?.classList.add('hover:text-primary');
    }
    updateBadgeText();
}

function updateBadgeText() {
    const badge = document.getElementById('current-level-badge');
    if (!badge) return;
    badge.textContent = currentHierarchyMode === 'section' ? 'Section ➔ Classification' : 'Location ➔ Make';
}

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('customer-order-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

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

    const reOrder = document.getElementById('filter-re-order')?.value;
    if (reOrder) filters['re_order'] = reOrder;

    const reqFrom = document.getElementById('filter-request-date-from')?.value;
    if (reqFrom) filters['request_date_from'] = reqFrom;

    const reqTo = document.getElementById('filter-request-date-to')?.value;
    if (reqTo) filters['request_date_to'] = reqTo;

    const expFrom = document.getElementById('filter-expected-delivery-from')?.value;
    if (expFrom) filters['expected_delivery_date_from'] = expFrom;

    const expTo = document.getElementById('filter-expected-delivery-to')?.value;
    if (expTo) filters['expected_delivery_date_to'] = expTo;

    const orderAgeVal = document.getElementById('filter-order-age')?.value;
    if (orderAgeVal) filters['order_age'] = orderAgeVal;

    const advLinkedVal = document.getElementById('filter-advance-linked')?.value;
    if (advLinkedVal) filters['advance_linked'] = advLinkedVal;

    const delivPeriodVal = document.getElementById('filter-delivery-period')?.value;
    if (delivPeriodVal) filters['delivery_period'] = delivPeriodVal;

    const searchVal = document.getElementById('hierarchy-search')?.value?.trim();
    if (searchVal) filters['search'] = searchVal;

    filters['hierarchy_mode'] = currentHierarchyMode;

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
    history.replaceState(null, '', `${window.location.pathname}?${params}`);
    loadCustomerOrderReport();
}

function resetGlobalFilters() {
    window.location.search = '';
}

function changePerPage(val) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', val);
    urlParams.set('page', 1);
    history.replaceState(null, '', `${window.location.pathname}?${urlParams}`);
    loadCustomerOrderReport();
}

function changePage(page) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    history.replaceState(null, '', `${window.location.pathname}?${urlParams}`);
    loadCustomerOrderReport();
}

function onSearchInput(val) {
    const filter = val.toLowerCase().trim();
    const rows = document.querySelectorAll('#table-area table tbody tr.parent-row');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(filter) ? '' : 'none';
    });
}

// Tree-Grid Toggle Action for Level 1 -> Level 2
async function toggleRow(btn, level, value) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        let nextTr = tr.nextElementSibling;
        while (nextTr) {
            const nextLevel = nextTr.dataset.level;
            if (nextLevel === level) break;

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
            params.set('hierarchy_mode', currentHierarchyMode);

            const token = localStorage.getItem('access_token');
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch(`/partial/customer-order-analysis?${params.toString()}`, { headers });
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
            console.error('Error expanding row:', e);
            icon.textContent = 'error';
        }
    }
}

// Leaf Modal Handler
async function openLeafModal(location, make, section, classification) {
    const modal = document.getElementById('leaf-detail-modal');
    const overlay = document.getElementById('modal-overlay');
    const content = document.getElementById('leaf-detail-content');

    if (!modal || !overlay || !content) return;

    modal.classList.remove('hidden');
    overlay.classList.remove('hidden');
    content.innerHTML = `<div class="p-8 text-center text-gray-500 flex flex-col items-center justify-center h-full">
        <span class="animate-spin material-symbols-outlined text-4xl text-primary mb-2">sync</span>
        Loading order details...
    </div>`;

    const filters = getFilterValues();
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
        if (v) params.set(k, v);
    }
    if (location) params.set('parent_location', location);
    if (make) params.set('parent_make', make);
    if (section) params.set('parent_section', section);
    if (classification) params.set('parent_classification', classification);

    try {
        const token = localStorage.getItem('access_token');
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch(`/partial/customer-order-analysis/leaf_detail?${params.toString()}`, { headers });
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
}

function toggleModalSupplier(btn, supplierId) {
    const icon = btn.querySelector('.material-symbols-outlined');
    const rows = document.querySelectorAll(`tr.modal-detail-row[data-supplier-id="${supplierId}"]`);
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        icon.textContent = 'add_circle';
        rows.forEach(r => r.classList.add('hidden'));
    } else {
        icon.textContent = 'remove_circle';
        rows.forEach(r => r.classList.remove('hidden'));
    }
}

async function triggerCustomerOrderSync() {
    const btn = document.getElementById('btn-sync-report');
    if (!btn) return;
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined text-[14px] animate-spin">sync</span><span>Syncing...</span>';
    try {
        const headers = { 'Content-Type': 'application/json' };
        const token = localStorage.getItem('access_token');
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch('/api/sync/customer-order-analysis', {
            method: 'POST',
            headers
        });
        const data = await response.json();
        if (data.status === 'success') {
            btn.innerHTML = '<span class="material-symbols-outlined text-[14px] text-green-500">check_circle</span><span>Queued</span>';
            setTimeout(() => {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
                loadCustomerOrderReport();
            }, 3000);
        } else {
            alert(data.message || 'Sync failed to queue');
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    } catch (e) {
        console.error('Error triggering sync:', e);
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

function toggleCustomerOrderFilters() {
    const sidebar = document.getElementById('customer-order-filter-sidebar');
    const button = document.getElementById('customer-order-filter-toggle');
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
    } else {
        sidebar.classList.add('hidden');
        sidebar.style.display = 'none';
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-label', 'Show filters');
        button.title = 'Show filters';
        button.classList.remove('text-primary');
        button.classList.add('text-gray-400');
    }
}

window.toggleCustomerOrderFilters = toggleCustomerOrderFilters;
