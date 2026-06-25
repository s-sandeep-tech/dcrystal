let currentZoom = parseFloat(localStorage.getItem('ownerwise-zoom')) || 1.0;
let makeMultiSelect;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('ownerwise-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-ownerwise');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/ownerwise?${searchParams}`, {
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

        // Parse pagination & Level & Stats
        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
            updateLevelBadge(metaDiv.dataset.level);
        }

        const statsScript = activeView.querySelector('#stats-metadata');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent);
                updateHeaderStats(stats);
            } catch (e) {
                console.error("Error parsing stats metadata:", e);
            }
        }

        updateOrderStatusFilterBtnState();

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    }
}

function updateHeaderStats(stats) {
    if (!stats) return;
    const mappings = {
        'stat-ordered-wt': stats.ordered_wt,
        'stat-ordered-pcs': stats.ordered_pcs,
        'stat-accepted-wt': stats.accepted_wt,
        'stat-accepted-pcs': stats.accepted_pcs,
        'stat-rejected-wt': stats.rejected_wt,
        'stat-rejected-pcs': stats.rejected_pcs,
        'stat-barcoded-wt': stats.barcoded_wt,
        'stat-barcoded-pcs': stats.barcoded_pcs,
        'stat-hallmarked-wt': stats.hallmarked_wt,
        'stat-hallmarked-pcs': stats.hallmarked_pcs,
        'stat-qc-passed-wt': stats.qc_passed_wt,
        'stat-qc-passed-pcs': stats.qc_passed_pcs,
        'stat-invoiced-wt': stats.invoiced_wt,
        'stat-invoiced-pcs': stats.invoiced_pcs,
        'stat-delivered-wt': stats.delivered_wt,
        'stat-delivered-pcs': stats.delivered_pcs,
        'stat-pending-to-be-delv-wt': stats.pending_to_be_delv_wt,
        'stat-pending-to-be-delv-pcs': stats.pending_to_be_delv_pcs,
        'stat-cancelled-wt': stats.cancelled_wt,
        'stat-cancelled-pcs': stats.cancelled_pcs
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            if (id.endsWith('-pcs')) {
                // Formatting pieces: ensuring " Pcs" suffix
                const cleanValue = value ? value.toString().replace(/ Pcs/gi, '') : '0';
                el.textContent = cleanValue + ' Pcs';
            } else if (id.endsWith('-wt')) {
                // Formatting weights: ensuring 3 decimal places
                let formattedValue = '0.000';
                if (value) {
                    // If it's already a formatted string from backend (e.g., "1,234.567"), use it
                    if (typeof value === 'string' && value.includes('.')) {
                        formattedValue = value;
                    } else {
                        formattedValue = parseFloat(value).toLocaleString(undefined, {
                            minimumFractionDigits: 3,
                            maximumFractionDigits: 3
                        });
                    }
                }
                el.textContent = formattedValue;
            } else {
                el.textContent = value || '0';
            }
        }
    }

    const barMappings = {
        'stat-accepted-bar': stats.accepted_perc,
        'stat-rejected-bar': stats.rejected_perc,
        'stat-barcoded-bar': stats.barcoded_perc,
        'stat-hallmarked-bar': stats.hallmarked_perc,
        'stat-qc-passed-bar': stats.qc_passed_perc,
        'stat-invoiced-bar': stats.invoiced_perc,
        'stat-delivered-bar': stats.delivered_perc,
        'stat-pending-to-be-delv-bar': stats.pending_to_be_delv_perc,
        'stat-cancelled-bar': stats.cancelled_perc
    };

    for (const [id, perc] of Object.entries(barMappings)) {
        const el = document.getElementById(id);
        if (el) el.style.width = (perc || 0) + '%';
    }
}



function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge) {
        badge.textContent = level ? level.replace('_', ' ').toUpperCase() : 'CLASSIFICATION OWNER';
    }
}

// Tree-Grid Toggle Action
async function toggleRow(btn, level, value, grandparentValue = null) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        let nextTr = tr.nextElementSibling;
        while (nextTr) {
            const nextLevel = nextTr.dataset.level;
            if (level === 'classification_owner' && nextLevel === 'classification_owner') break;
            if (level === 'make_owner' && (nextLevel === 'make_owner' || nextLevel === 'classification_owner')) break;

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
            if (grandparentValue) params.set('grandparent_value', grandparentValue);

            const response = await fetch(`/partial/ownerwise?${params.toString()}`, {
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

const ownerStatusFilterButtons = {
    all_rejected: {
        id: 'btn-all-rejected',
        activeClasses: ['bg-red-50', 'dark:bg-red-900/20', 'text-red-600', 'border-red-200', 'dark:border-red-800']
    },
    active_orders: {
        id: 'btn-active-orders',
        activeClasses: ['bg-orange-50', 'dark:bg-orange-900/20', 'text-orange-600', 'border-orange-200', 'dark:border-orange-800']
    },
    received_orders: {
        id: 'btn-received-orders',
        activeClasses: ['bg-emerald-50', 'dark:bg-emerald-900/20', 'text-emerald-600', 'border-emerald-200', 'dark:border-emerald-800']
    }
};

const ownerStatusInactiveClasses = ['bg-white', 'dark:bg-gray-800', 'text-gray-500', 'border-gray-200', 'dark:border-gray-700'];

function getCurrentOrderStatusFilter(urlParams) {
    if (urlParams.get('all_rejected') === 'true') return 'all_rejected';
    return urlParams.get('order_status_filter') || '';
}

function toggleOrderStatusFilter(filterName) {
    const urlParams = new URLSearchParams(window.location.search);
    const currentFilter = getCurrentOrderStatusFilter(urlParams);

    urlParams.delete('all_rejected');
    if (currentFilter === filterName) {
        urlParams.delete('order_status_filter');
    } else {
        urlParams.set('order_status_filter', filterName);
    }

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function toggleAllRejected() {
    toggleOrderStatusFilter('all_rejected');
}

function updateOrderStatusFilterBtnState() {
    const urlParams = new URLSearchParams(window.location.search);
    const activeFilter = getCurrentOrderStatusFilter(urlParams);

    Object.entries(ownerStatusFilterButtons).forEach(([filterName, config]) => {
        const btn = document.getElementById(config.id);
        if (!btn) return;
        const activeClasses = config.activeClasses;
        btn.classList.remove(...ownerStatusInactiveClasses, ...activeClasses);
        btn.classList.add(...(activeFilter === filterName ? activeClasses : ownerStatusInactiveClasses));
    });
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const configs = {
        'division': 'filter-division',
        'group': 'filter-group',
        'purity': 'filter-purity',
        'classification': 'filter-classification',
        'order_type': 'filter-order-type',
        'supplier': 'filter-supplier',
        'classification_owner': 'filter-class-owner',
        'collection_owner': 'filter-coll-owner',
        'make_owner': 'filter-make-owner',
        'search': 'hierarchy-search',
        'from_date': 'filter-from-date',
        'to_date': 'filter-to-date',
        'enable_date_filter': 'enable-date-filter',
        'order_ro': 'filter-order-ro',
        'order_request_type': 'filter-order-request-type',
        'provision_type': 'filter-provision-type',
        'branch_provision_type': 'filter-branch-provision-type',
        'branch_type': 'filter-branch-type',
        'age': 'filter-age'
    };

    for (const [param, id] of Object.entries(configs)) {
        const el = document.getElementById(id);
        if (!el) continue;

        let val;
        if (el.type === 'checkbox') {
            val = el.checked ? 'true' : 'false';
        } else {
            val = el.value;
        }

        if (val && val !== 'false') urlParams.set(param, val);
        else urlParams.delete(param);
    }

    if (makeMultiSelect) {
        const makeVal = makeMultiSelect.getValues().join(',');
        if (makeVal) urlParams.set('make', makeVal);
        else urlParams.delete('make');
    }

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    const configs = {
        'division': 'filter-division',
        'group': 'filter-group',
        'purity': 'filter-purity',
        'classification': 'filter-classification',
        'order_type': 'filter-order-type',
        'supplier': 'filter-supplier',
        'classification_owner': 'filter-class-owner',
        'collection_owner': 'filter-coll-owner',
        'make_owner': 'filter-make-owner',
        'search': 'hierarchy-search',
        'from_date': 'filter-from-date',
        'to_date': 'filter-to-date',
        'enable_date_filter': 'enable-date-filter',
        'order_ro': 'filter-order-ro',
        'order_request_type': 'filter-order-request-type',
        'provision_type': 'filter-provision-type',
        'branch_provision_type': 'filter-branch-provision-type',
        'branch_type': 'filter-branch-type',
        'age': 'filter-age'
    };

    Object.entries(configs).forEach(([param, id]) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (el.type === 'checkbox') el.checked = false;
        else el.value = '';
        urlParams.delete(param);
    });

    if (makeMultiSelect) makeMultiSelect.reset();
    urlParams.delete('make');

    toggleDateInputs();
    urlParams.delete('all_rejected');
    urlParams.delete('order_status_filter');

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}


function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
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
    try {
        const response = await fetch(`/api/orderstatus/options`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const options = await response.json();

        populateSelect('filter-division', options.divisions, 'All Divisions');
        populateSelect('filter-business-head', options.business_heads, 'All Business Heads');

        // Sync from URL
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('division')) document.getElementById('filter-division').value = urlParams.get('division');
        if (urlParams.get('business_head')) document.getElementById('filter-business-head').value = urlParams.get('business_head');

    } catch (e) {
        console.error('Error loading options:', e);
    }
}

function populateSelect(id, list, placeholder) {
    const el = document.getElementById(id);
    if (!el) return;
    let html = `<option value="">${placeholder}</option>`;
    list.forEach(item => {
        html += `<option value="${item}">${item}</option>`;
    });
    el.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('search')) document.getElementById('hierarchy-search').value = urlParams.get('search');

    makeMultiSelect = new CustomMultiSelect({
        containerId: 'filter-make-container',
        label: 'Make',
        defaultText: 'All Makes',
        options: window.ownerWiseAvailableMakes || []
    });

    const makeVal = urlParams.get('make');
    if (makeVal && makeMultiSelect) {
        const selectedMakes = makeVal.split(',').map(value => value.trim()).filter(Boolean);
        document.querySelectorAll('.filter-make-container-checkbox').forEach(cb => {
            cb.checked = selectedMakes.includes(cb.value);
        });
        makeMultiSelect.updateTriggerText();
    }

    loadViewData();
    loadFilterOptions();
    updateOrderStatusFilterBtnState();
});

function toggleDateInputs() {
    const isEnabled = document.getElementById('enable-date-filter')?.checked;
    const container = document.getElementById('date-inputs');
    if (container) {
        if (isEnabled) {
            container.classList.remove('opacity-50', 'pointer-events-none');
        } else {
            container.classList.add('opacity-50', 'pointer-events-none');
        }
    }
}
