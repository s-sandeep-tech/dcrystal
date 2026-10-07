let currentZoom = parseFloat(localStorage.getItem('fulfilment-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('fulfilment-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadFulfilmentViewData() {
    const activeView = document.getElementById('view-customer-order-fulfilment');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/customerorderfulfilmentsummary?${searchParams}`, {
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

        // Parse pagination & Stats
        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
            const levelBadge = document.getElementById('current-level-badge');
            if (levelBadge && metaDiv.dataset.hierarchyName) {
                levelBadge.textContent = metaDiv.dataset.hierarchyName;
            }
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
    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Error loading report data: ${error.message}</div>`;
    }
}

function updateHeaderStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-ordered-wt': stats.ordered_wt,
        'stat-ordered-pcs': stats.ordered_pcs,
        'stat-rejected-wt': stats.rejected_wt,
        'stat-rejected-pcs': stats.rejected_pcs,
        'stat-cancelled-wt': stats.cancelled_wt,
        'stat-cancelled-pcs': stats.cancelled_pcs,
        'stat-approved-wt': stats.approved_wt,
        'stat-approved-pcs': stats.approved_pcs,
        'stat-accepted-wt': stats.accepted_wt,
        'stat-accepted-pcs': stats.accepted_pcs,
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
        'stat-pending-to-be-delv-pcs': stats.pending_to_be_delv_pcs
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            if (id.endsWith('-pcs')) {
                const cleanValue = value ? value.toString().replace(/ Pcs/gi, '') : '0';
                el.textContent = cleanValue + ' Pcs';
            } else if (id.endsWith('-wt')) {
                let formattedValue = '0.000';
                if (value) {
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
        'stat-rejected-bar': stats.rejected_perc,
        'stat-cancelled-bar': stats.cancelled_perc,
        'stat-approved-bar': stats.approved_perc,
        'stat-accepted-bar': stats.accepted_perc,
        'stat-barcoded-bar': stats.barcoded_perc,
        'stat-hallmarked-bar': stats.hallmarked_perc,
        'stat-qc-passed-bar': stats.qc_passed_perc,
        'stat-invoiced-bar': stats.invoiced_perc,
        'stat-delivered-bar': stats.delivered_perc,
        'stat-pending-to-be-delv-bar': stats.pending_to_be_delv_perc
    };

    for (const [id, perc] of Object.entries(barMappings)) {
        const el = document.getElementById(id);
        if (el) el.style.width = (perc || 0) + '%';
    }
}

// Tree-Grid Toggle Action for dynamic hierarchies
async function toggleFulfilmentRow(btn) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const levelIdx = parseInt(tr.dataset.level, 10);
    const icon = btn.querySelector('.material-symbols-outlined');
    if (!icon) return;

    const isExpanded = icon.textContent.trim() === 'remove_circle';

    if (isExpanded) {
        let nextTr = tr.nextElementSibling;
        while (nextTr && nextTr.dataset.level !== undefined) {
            const nextLevel = parseInt(nextTr.dataset.level, 10);
            if (isNaN(nextLevel) || nextLevel <= levelIdx) break;

            const toRemove = nextTr;
            nextTr = nextTr.nextElementSibling;
            toRemove.remove();
        }
        icon.textContent = 'add_circle';
        tr.classList.remove('bg-blue-50/50');
    } else {
        icon.textContent = 'hourglass_empty';

        let path = [];
        try {
            path = JSON.parse(tr.dataset.path || tr.getAttribute('data-path') || '[]');
        } catch (e) {
            console.error('Error parsing row path:', e, tr.dataset.path);
        }

        try {
            const urlParams = new URLSearchParams(window.location.search);
            const params = new URLSearchParams(urlParams);
            params.set('parent_level', levelIdx);
            params.set('parent_path', JSON.stringify(path));

            const headers = {};
            const token = localStorage.getItem('access_token');
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch(`/partial/customerorderfulfilmentsummary?${params.toString()}`, {
                headers: headers
            });

            if (!response.ok) throw new Error("Failed to load children");
            const html = await response.text();

            if (html && html.trim()) {
                tr.insertAdjacentHTML('afterend', html);
            }

            icon.textContent = 'remove_circle';
            tr.classList.add('bg-blue-50/50');

        } catch (e) {
            console.error('Failed to toggle row:', e);
            icon.textContent = 'add_circle';
        }
    }
}
window.toggleFulfilmentRow = toggleFulfilmentRow;

function changeHierarchy(hierarchyId) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('hierarchy', hierarchyId);
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function applyFulfilmentFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const configs = {
        'report_month': 'filter-report-month',
        'report_date': 'filter-report-date',
        'current_stage': 'filter-current-stage',
        'party': 'filter-party',
        'make': 'filter-make',
        'collection': 'filter-collection',
        'ornament_type': 'filter-ornament-type',
        'customer_order_type': 'filter-customer-order-type',
        'order_ageing_days': 'filter-order-ageing-days',
        'delivery_delay_days': 'filter-delivery-delay-days',
        'delay_status': 'filter-delay-status',
        'delay_bucket': 'filter-delay-bucket',
        'manager_approval_tat': 'filter-manager-approval-tat',
        'collection_owner_approval_tat': 'filter-collection-owner-approval-tat',
        'customer_approval_tat': 'filter-customer-approval-tat',
        'party_acceptance_tat': 'filter-party-acceptance-tat',
        'office_delivery_tat': 'filter-office-delivery-tat',
        'shop_delivery_tat': 'filter-shop-delivery-tat',
        'overall_order_tat': 'filter-overall-order-tat',
        'expected_vs_actual_delivery_days': 'filter-expected-vs-actual-delivery-days',
        'days_to_expected_delivery': 'filter-days-to-expected-delivery',
        'delivery_status': 'filter-delivery-status',
        'with_reference_status': 'filter-with-reference-status',
        'search': 'hierarchy-search'
    };

    for (const [param, id] of Object.entries(configs)) {
        const el = document.getElementById(id);
        if (!el) continue;

        let val;
        if (el.type === 'checkbox') {
            val = el.checked ? 'true' : 'false';
        } else {
            val = el.value.trim();
        }

        if (val && val !== 'false') {
            urlParams.set(param, val);
        } else {
            urlParams.delete(param);
        }
    }

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetFulfilmentFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    const configs = {
        'report_month': 'filter-report-month',
        'report_date': 'filter-report-date',
        'current_stage': 'filter-current-stage',
        'party': 'filter-party',
        'make': 'filter-make',
        'collection': 'filter-collection',
        'ornament_type': 'filter-ornament-type',
        'customer_order_type': 'filter-customer-order-type',
        'order_ageing_days': 'filter-order-ageing-days',
        'delivery_delay_days': 'filter-delivery-delay-days',
        'delay_status': 'filter-delay-status',
        'delay_bucket': 'filter-delay-bucket',
        'manager_approval_tat': 'filter-manager-approval-tat',
        'collection_owner_approval_tat': 'filter-collection-owner-approval-tat',
        'customer_approval_tat': 'filter-customer-approval-tat',
        'party_acceptance_tat': 'filter-party-acceptance-tat',
        'office_delivery_tat': 'filter-office-delivery-tat',
        'shop_delivery_tat': 'filter-shop-delivery-tat',
        'overall_order_tat': 'filter-overall-order-tat',
        'expected_vs_actual_delivery_days': 'filter-expected-vs-actual-delivery-days',
        'days_to_expected_delivery': 'filter-days-to-expected-delivery',
        'delivery_status': 'filter-delivery-status',
        'with_reference_status': 'filter-with-reference-status',
        'search': 'hierarchy-search'
    };

    Object.entries(configs).forEach(([param, id]) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (el.type === 'checkbox') el.checked = false;
        else el.value = '';
        urlParams.delete(param);
    });

    urlParams.delete('all_rejected');
    urlParams.delete('order_status_filter');
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadFulfilmentViewData();
}

function onSearchInput(value) {
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
        applyFulfilmentFilters();
    }, 500);
}

function updatePaginationControls(meta) {
    if (!meta) return;
    const page = parseInt(meta.page) || 1;
    const perPage = parseInt(meta.perPage) || 50;
    const total = parseInt(meta.total) || 0;
    const hasPrev = meta.hasPrev === 'true';
    const hasNext = meta.hasNext === 'true';

    const start = total > 0 ? (page - 1) * perPage + 1 : 0;
    const end = Math.min(page * perPage, total);
    const infoSpan = document.getElementById('pagination-info');
    if (infoSpan) {
        infoSpan.textContent = total > 0 ? `${start}-${end} of ${total.toLocaleString()}` : '0-0 of 0';
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

function toggleFulfilmentFilters() {
    const sidebar = document.getElementById('fulfilment-filter-sidebar');
    const button = document.getElementById('fulfilment-filter-toggle');
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
        localStorage.setItem('fulfilment_filter_visible', 'true');
    } else {
        sidebar.classList.add('hidden');
        sidebar.style.display = 'none';
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-label', 'Show filters');
        button.title = 'Show filters';
        button.classList.remove('text-primary');
        button.classList.add('text-gray-400');
        localStorage.setItem('fulfilment_filter_visible', 'false');
    }
}
window.toggleFulfilmentFilters = toggleFulfilmentFilters;

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) zoomLevel.textContent = Math.round(currentZoom * 100) + '%';

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('search')) {
        const searchInput = document.getElementById('hierarchy-search');
        if (searchInput) searchInput.value = urlParams.get('search');
    }

    if (localStorage.getItem('fulfilment_filter_visible') === 'false') {
        const sidebar = document.getElementById('fulfilment-filter-sidebar');
        const button = document.getElementById('fulfilment-filter-toggle');
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
});
