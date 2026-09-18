/**
 * Supplier Capacity & Backlog Analysis - Interactive Frontend Controller
 * Supports Hierarchical Drill-down (Supplier -> Make), 14-point Filters,
 * Analytical Lag Metrics, Dynamic Accordion, and Excel Export.
 */

let state = {
    page: 1,
    perPage: 50,
    totalPages: 1,
    totalRecords: 0,
    sortBy: 'supplier',
    sortOrder: 'asc',
    statusFilter: 'all',
    search: '',
    filters: {
        party: '',
        make: '',
        order_ro: '',
        location: '',
        provision_type: '',
        branch_type: '',
        division: '',
        group: '',
        purity: '',
        classification: '',
        collection: '',
        order_type: '',
        order_request_type: '',
        is_msme: '',
        vendor_type: ''
    },
    expandedSuppliers: new Set(),
    zoomLevel: 1.0,
    cachedData: []
};

let searchDebounceTimer = null;

document.addEventListener('DOMContentLoaded', () => {
    fetchReportData();
});

function toggleCapacityFilters() {
    const sidebar = document.getElementById('capacity-sidebar');
    const button = document.getElementById('capacity-filter-toggle');
    if (!sidebar || !button) return;

    const hidden = sidebar.style.display !== 'none';
    sidebar.style.display = hidden ? 'none' : '';
    button.setAttribute('aria-expanded', String(!hidden));
    const label = hidden ? 'Show filters' : 'Hide filters';
    button.setAttribute('aria-label', label);
    button.title = label;
}

function adjustZoom(delta, reset = false) {
    if (reset) {
        state.zoomLevel = 1.0;
    } else {
        state.zoomLevel = Math.max(0.7, Math.min(1.4, state.zoomLevel + delta));
    }
    const container = document.getElementById('grid-scroll-container');
    if (container) {
        container.style.zoom = state.zoomLevel;
    }
    const zoomText = document.getElementById('zoom-level');
    if (zoomText) {
        zoomText.innerText = Math.round(state.zoomLevel * 100) + '%';
    }
}

function buildQueryString() {
    const params = new URLSearchParams();
    params.set('page', state.page);
    params.set('per_page', state.perPage);
    params.set('sort_by', state.sortBy);
    params.set('sort_order', state.sortOrder);
    if (state.statusFilter && state.statusFilter !== 'all') {
        params.set('status', state.statusFilter);
    }
    if (state.search) {
        params.set('search', state.search);
    }
    for (const [k, v] of Object.entries(state.filters)) {
        if (v && String(v).trim()) {
            params.set(k, String(v).trim());
        }
    }
    return params.toString();
}

function updateActiveFilterBadges() {
    let count = 0;
    const chipsContainer = document.getElementById('filter-tag-chips');
    const tagsBar = document.getElementById('active-filter-tags');
    if (!chipsContainer || !tagsBar) return;

    chipsContainer.innerHTML = '';

    for (const [k, v] of Object.entries(state.filters)) {
        if (v && String(v).trim()) {
            count++;
            const chip = document.createElement('span');
            chip.className = 'inline-flex items-center gap-1 bg-blue-100 dark:bg-blue-900/60 text-blue-800 dark:text-blue-200 px-2 py-0.5 rounded font-medium text-[9px] border border-blue-200 dark:border-blue-800';
            const displayValue = k === 'vendor_type' ? (v === 'discount' ? 'Discount Vendor' : 'Non Discount Vendor') : v;
            chip.innerHTML = `<span>${k.replace('_', ' ')}: <b>${escapeHtml(displayValue)}</b></span><button onclick="removeFilter('${k}')" class="text-blue-600 hover:text-blue-900 font-bold ml-1">×</button>`;
            chipsContainer.appendChild(chip);
        }
    }

    if (state.search) {
        count++;
        const chip = document.createElement('span');
        chip.className = 'inline-flex items-center gap-1 bg-blue-100 dark:bg-blue-900/60 text-blue-800 dark:text-blue-200 px-2 py-0.5 rounded font-medium text-[9px] border border-blue-200 dark:border-blue-800';
        chip.innerHTML = `<span>search: <b>${state.search}</b></span><button onclick="removeFilter('search')" class="text-blue-600 hover:text-blue-900 font-bold ml-1">×</button>`;
        chipsContainer.appendChild(chip);
    }

    const badge = document.getElementById('active-filter-badge');
    if (badge) {
        if (count > 0) {
            badge.innerText = count;
            badge.classList.remove('hidden');
            tagsBar.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
            tagsBar.classList.add('hidden');
        }
    }
}

function removeFilter(key) {
    if (key === 'search') {
        state.search = '';
        const searchInput = document.getElementById('filter-search');
        if (searchInput) searchInput.value = '';
    } else if (state.filters.hasOwnProperty(key)) {
        state.filters[key] = '';
        const el = document.getElementById(`adv-filter-${key.replace('_', '-')}`);
        if (el) el.value = '';
        if (key === 'make') {
            const qMake = document.getElementById('quick-filter-make');
            if (qMake) qMake.value = '';
        }
        if (key === 'division') {
            const qDiv = document.getElementById('quick-filter-division');
            if (qDiv) qDiv.value = '';
        }
    }
    state.page = 1;
    fetchReportData();
}

async function fetchReportData() {
    const spinner = document.getElementById('table-loading-spinner');
    const emptyState = document.getElementById('table-empty-state');
    const tbody = document.getElementById('capacity-table-body');
    if (spinner) spinner.classList.remove('hidden');
    if (emptyState) emptyState.classList.add('hidden');

    updateActiveFilterBadges();

    try {
        const query = buildQueryString();
        const res = await fetch(`/api/party-make-capacity/data?${query}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();

        if (result.status === 'success') {
            state.cachedData = result.data || [];
            updateKpiCards(result.kpis || {});
            renderTableRows(result.data || []);
            updatePaginationUI(result.pagination || {});
        } else {
            console.error('API returned error:', result.message);
        }
    } catch (err) {
        console.error('Failed to fetch capacity data:', err);
    } finally {
        if (spinner) spinner.classList.add('hidden');
    }
}

function updateKpiCards(kpis) {
    const setElem = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = val;
    };

    setElem('kpi-total-capacity', formatNumber(kpis.total_capacity_kg, 3));
    setElem('kpi-total-wip', formatNumber(kpis.total_wip_kg, 3));
    setElem('kpi-net-diff', (kpis.net_diff_kg >= 0 ? '+' : '') + formatNumber(kpis.net_diff_kg, 3));
    const hasCapacity = Number(kpis.total_capacity_kg) > 0;
    setElem('kpi-utilization', hasCapacity ? formatNumber(kpis.overall_utilization_pct, 1) + '%' : 'N/A');
    setElem('kpi-overloaded-count', kpis.over_capacity_count || 0);
    setElem('kpi-transit-lag', formatNumber(kpis.total_transit_kg, 3));

    const setTone = (id, tone) => {
        const el = document.getElementById(id + '-value');
        if (el) el.dataset.tone = tone;
    };
    const balance = Number(kpis.net_diff_kg || 0);
    setTone('kpi-net-diff', balance < 0 ? 'danger' : balance > 0 ? 'good' : 'neutral');
    setTone('kpi-utilization', !hasCapacity ? 'neutral' : kpis.overall_utilization_pct > 100 ? 'danger' : 'good');
    setTone('kpi-overloaded-count', kpis.over_capacity_count > 0 ? 'danger' : 'neutral');
    setElem('kpi-net-diff-status', balance < 0 ? 'Capacity deficit' : balance > 0 ? 'Capacity headroom' : 'Balanced');
    setElem('kpi-overloaded-count-status', 'of ' + (kpis.total_suppliers_count || 0) + ' parties');
    setElem('kpi-utilization-status', hasCapacity ? 'Backlog / monthly capacity' : 'No allocated capacity');
}

function renderTableRows(suppliers) {
    const tbody = document.getElementById('capacity-table-body');
    const emptyState = document.getElementById('table-empty-state');
    if (!tbody) return;

    tbody.innerHTML = '';

    if (!suppliers || suppliers.length === 0) {
        if (emptyState) emptyState.classList.remove('hidden');
        return;
    }
    if (emptyState) emptyState.classList.add('hidden');

    suppliers.forEach((sup, idx) => {
        const supSafeId = encodeURIComponent(sup.supplier);
        const isExpanded = state.expandedSuppliers.has(sup.supplier);

        // Level 1: Supplier Parent Row
        const parentTr = document.createElement('tr');
        parentTr.id = `sup-row-${supSafeId}`;
        parentTr.className = 'bg-parent-row border-b border-gray-200 dark:border-gray-800 font-bold hover:bg-blue-50/40 dark:hover:bg-gray-800/60 transition-colors cursor-pointer select-none';
        parentTr.classList.toggle('capacity-no-orders', sup.is_orders === false);
        parentTr.onclick = (e) => {
            // Don't toggle if clicking a specific drilldown button
            if (e.target.closest('.no-accordion')) return;
            toggleAccordion(sup.supplier);
        };

        const diffColor = sup.diff < 0 ? 'text-rose-600 dark:text-rose-400 font-extrabold' : 'text-emerald-600 dark:text-emerald-400 font-extrabold';
        const diffSign = sup.diff >= 0 ? '+' : '';

        // Mini utilization bar styling
        let utilColor = 'bg-emerald-500';
        let utilTextColor = 'text-emerald-700 dark:text-emerald-300';
        if (sup.utilization_pct > 120) {
            utilColor = 'bg-rose-600';
            utilTextColor = 'text-rose-700 dark:text-rose-300';
        } else if (sup.utilization_pct > 100) {
            utilColor = 'bg-amber-500';
            utilTextColor = 'text-amber-700 dark:text-amber-300';
        }

        parentTr.innerHTML = `
            <!-- Col 1: Supplier Name + Expander -->
            <td class="sticky-col-1 px-3 py-2 border-r border-gray-200 dark:border-gray-800 bg-inherit">
                <div class="flex items-center gap-1.5">
                    <button class="p-0.5 rounded text-gray-400 hover:text-primary transition-transform">
                        <span class="material-symbols-outlined text-[16px]">${isExpanded ? 'remove_circle' : 'add_circle'}</span>
                    </button>
                    <span class="truncate max-w-[200px]" title="${escapeHtml(sup.supplier)}">${escapeHtml(sup.supplier)}</span>
                    <span class="text-[9px] font-normal px-1.5 py-0.2 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded-full">
                        ${sup.makes.length}
                    </span>
                    ${sup.is_msme ? '<span class="text-[8px] font-bold px-1 py-0.2 bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 rounded">MSME</span>' : ''}
                </div>
            </td>

            <!-- Col 3: Capacity Kg -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800 font-extrabold">
                ${sup.actual_capacity == null ? '-' : formatNumber(sup.actual_capacity, 3)}
            </td>
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800 text-blue-700 dark:text-blue-300 font-extrabold">
                ${formatNumber(sup.capacity_wt_kg_per_month, 3)}
            </td>

            <!-- Col 11: Total Wt in KG -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800 font-extrabold text-gray-900 dark:text-gray-100">
                ${formatNumber(sup.total_wt_in_kg, 4)}
            </td>

            <!-- Col 12: Diff (KG) -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800 ${diffColor}">
                ${diffSign}${formatNumber(sup.diff, 3)}
            </td>

            <!-- Col 13: Utilization % -->
            <td class="px-2 py-2 border-r border-gray-200 dark:border-gray-800">
                <div class="flex items-center gap-1.5 justify-end">
                    <span class="font-bold text-[10px] ${utilTextColor}">${sup.utilization_pct}%</span>
                    <div class="w-10 bg-gray-200 dark:bg-gray-700 h-1.5 rounded-full overflow-hidden">
                        <div class="${utilColor} h-full rounded-full" style="width: ${Math.min(100, sup.utilization_pct)}%"></div>
                    </div>
                </div>
            </td>

            <!-- Col 14: Primary Bottleneck Stage -->
            <td class="px-2 py-2 text-center border-r border-gray-200 dark:border-gray-800">
                <span class="inline-block px-1.5 py-0.5 rounded text-[8px] font-bold ${getBottleneckBadgeClass(sup.primary_bottleneck)}">
                    ${sup.primary_bottleneck}
                </span>
            </td>

            <!-- Col 15: QC Rework % -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800 ${sup.qc_rework_pct > 5 ? 'text-rose-600 font-bold' : 'text-gray-500'}">
                ${sup.qc_rework_pct}%
            </td>

            <!-- Col 4: Process Wt -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800">${formatNumber(sup.process_pending_wt, 3)}</td>

            <!-- Col 5: Barcode Wt -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800">${formatNumber(sup.barcode_pending_wt, 3)}</td>

            <!-- Col 6: Hallmark Wt -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800">${formatNumber(sup.hallmark_pending_wt, 3)}</td>

            <!-- Col 7: QC Issue Wt -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800 ${sup.qc_issue_pending_wt > 0 ? 'text-rose-600 font-bold' : ''}">
                ${formatNumber(sup.qc_issue_pending_wt, 3)}
            </td>

            <!-- Col 8: QC Complete Wt -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800">${formatNumber(sup.qc_complete_pending_wt, 3)}</td>

            <!-- Col 9: Invoice Wt -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800">${formatNumber(sup.invoice_pending_wt, 3)}</td>

            <!-- Col 10: Total WIP Wt (g) -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800 font-extrabold text-gray-900 dark:text-gray-100">
                ${formatNumber(sup.total_wt, 3)}
            </td>

            <!-- Col 16: In-Transit Lag Wt -->
            <td class="px-2 py-2 text-right border-r border-gray-200 dark:border-gray-800 text-cyan-600 dark:text-cyan-400">
                ${formatNumber(sup.receipt_pending_wt, 3)}
            </td>

            <!-- Col 17: RO Count -->
            <td class="px-2 py-2 text-center text-gray-500">
                ${sup.ro_count}
            </td>
        `;
        tbody.appendChild(parentTr);

        // Level 2: Make Child Rows (Indented under Supplier)
        sup.makes.forEach((m) => {
            const childTr = document.createElement('tr');
            childTr.className = `child-row bg-child-row border-b border-gray-100 dark:border-gray-850 hover:bg-blue-50/20 dark:hover:bg-gray-800/40 transition-colors ${isExpanded ? '' : 'hidden'}`;
            childTr.classList.toggle('capacity-no-orders', m.is_orders === false);
            childTr.setAttribute('data-parent-supplier', sup.supplier);

            const mDiffColor = m.diff < 0 ? 'text-rose-600 dark:text-rose-400 font-bold' : 'text-emerald-600 dark:text-emerald-400 font-bold';
            const mDiffSign = m.diff >= 0 ? '+' : '';

            childTr.innerHTML = `
                <!-- Col 1: Make Name Indented -->
                <td class="sticky-col-1 px-3 py-1.5 capacity-child-indent border-r border-gray-200 dark:border-gray-800 bg-inherit" style="padding-left: 34px !important;">
                    <div class="flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
                        <span class="material-symbols-outlined text-[13px] text-gray-400">precision_manufacturing</span>
                        ${m.is_orders === false ? `<span class="font-medium">${escapeHtml(m.make)}</span>` : `
                        <span class="font-medium hover:text-primary cursor-pointer no-accordion" onclick="openDrilldown('${escapeHtml(sup.supplier)}', '${escapeHtml(m.make)}')">
                            ${escapeHtml(m.make)}
                        </span>
                        <button onclick="openDrilldown('${escapeHtml(sup.supplier)}', '${escapeHtml(m.make)}')" class="no-accordion ml-1 text-gray-400 hover:text-primary" title="Inspect Orders">
                            <span class="material-symbols-outlined text-[12px]">open_in_new</span>
                        </button>
                        `}
                    </div>
                </td>

                <!-- Col 3: Capacity Kg -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800 font-medium">
                    ${m.actual_capacity == null ? '-' : formatNumber(m.actual_capacity, 3)}
                </td>
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800 font-medium">
                    ${formatNumber(m.capacity_wt_kg_per_month, 3)}
                </td>

                <!-- Col 11: Total Wt in KG -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800 font-bold">
                    ${formatNumber(m.total_wt_in_kg, 4)}
                </td>

                <!-- Col 12: Diff (KG) -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800 ${mDiffColor}">
                    ${mDiffSign}${formatNumber(m.diff, 3)}
                </td>

                <!-- Col 13: Utilization % -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800">
                    <span class="text-[9px] font-semibold">${m.utilization_pct}%</span>
                </td>

                <!-- Col 14: Bottleneck Stage -->
                <td class="px-2 py-1.5 text-center border-r border-gray-200 dark:border-gray-800">
                    <span class="inline-block px-1 py-0.2 rounded text-[7px] font-bold ${getBottleneckBadgeClass(m.primary_bottleneck)}">
                        ${m.primary_bottleneck}
                    </span>
                </td>

                <!-- Col 15: QC Rework % -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800 text-gray-500">
                    ${m.qc_rework_pct}%
                </td>

                <!-- Col 4: Process Wt -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800">${formatNumber(m.process_pending_wt, 3)}</td>

                <!-- Col 5: Barcode Wt -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800">${formatNumber(m.barcode_pending_wt, 3)}</td>

                <!-- Col 6: Hallmark Wt -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800">${formatNumber(m.hallmark_pending_wt, 3)}</td>

                <!-- Col 7: QC Issue Wt -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800 ${m.qc_issue_pending_wt > 0 ? 'text-rose-600' : ''}">
                    ${formatNumber(m.qc_issue_pending_wt, 3)}
                </td>

                <!-- Col 8: QC Complete Wt -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800">${formatNumber(m.qc_complete_pending_wt, 3)}</td>

                <!-- Col 9: Invoice Wt -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800">${formatNumber(m.invoice_pending_wt, 3)}</td>

                <!-- Col 10: Total WIP Wt (g) -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800 font-bold">
                    ${formatNumber(m.total_wt, 3)}
                </td>

                <!-- Col 16: Transit Lag Wt -->
                <td class="px-2 py-1.5 text-right border-r border-gray-200 dark:border-gray-800 text-cyan-600 dark:text-cyan-400">
                    ${formatNumber(m.receipt_pending_wt, 3)}
                </td>

                <!-- Col 17: RO Count -->
                <td class="px-2 py-1.5 text-center text-gray-400">
                    ${m.ro_count}
                </td>
            `;
            tbody.appendChild(childTr);
        });
    });
}

function getBottleneckBadgeClass(stage) {
    switch (stage) {
        case 'PROCESS':
            return 'bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200';
        case 'BARCODE':
            return 'bg-blue-100 text-blue-800 dark:bg-blue-900/60 dark:text-blue-200';
        case 'HALLMARK':
            return 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/60 dark:text-indigo-200';
        case 'QC ISSUE':
            return 'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-200';
        case 'QC COMPLETE':
            return 'bg-purple-100 text-purple-800 dark:bg-purple-900/60 dark:text-purple-200';
        case 'INVOICE':
            return 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/60 dark:text-cyan-200';
        default:
            return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
    }
}

function toggleAccordion(supplierName) {
    if (state.expandedSuppliers.has(supplierName)) {
        state.expandedSuppliers.delete(supplierName);
    } else {
        state.expandedSuppliers.add(supplierName);
    }
    // Re-render from cached data instantly without re-fetching
    renderTableRows(state.cachedData);
}

function toggleAllAccordions() {
    const btn = document.getElementById('btn-toggle-all');
    const icon = document.getElementById('toggle-all-icon');
    const text = document.getElementById('toggle-all-text');

    if (state.expandedSuppliers.size === state.cachedData.length && state.cachedData.length > 0) {
        state.expandedSuppliers.clear();
        if (icon) icon.innerText = 'unfold_more';
        if (text) text.innerText = 'Expand All';
    } else {
        state.cachedData.forEach(s => state.expandedSuppliers.add(s.supplier));
        if (icon) icon.innerText = 'unfold_less';
        if (text) text.innerText = 'Collapse All';
    }
    renderTableRows(state.cachedData);
}

function setStatusFilter(status) {
    state.statusFilter = status;
    state.page = 1;

    document.querySelectorAll('.status-pill').forEach(btn => {
        btn.className = 'status-pill px-2 py-1 font-medium text-gray-600 dark:text-gray-300 hover:text-primary';
    });

    const activeBtn = document.getElementById(`pill-${status === 'over_capacity' ? 'over' : (status === 'under_capacity' ? 'under' : (status === 'severe_overload' ? 'severe' : 'all'))}`);
    if (activeBtn) {
        activeBtn.className = 'status-pill px-2 py-1 font-semibold rounded bg-white dark:bg-gray-700 text-primary shadow-xs';
    }

    fetchReportData();
}

function onSearchDebounced(val) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        state.search = val.trim();
        state.page = 1;
        fetchReportData();
    }, 300);
}

function onFilterChange() {
    const qMake = document.getElementById('quick-filter-make');
    const qDiv = document.getElementById('quick-filter-division');
    if (qMake) state.filters.make = qMake.value;
    if (qDiv) state.filters.division = qDiv.value;
    state.page = 1;
    fetchReportData();
}

function sortByColumn(col) {
    if (state.sortBy === col) {
        state.sortOrder = (state.sortOrder === 'asc') ? 'desc' : 'asc';
    } else {
        state.sortBy = col;
        state.sortOrder = 'desc';
    }
    fetchReportData();
}

function updatePaginationUI(p) {
    state.totalPages = p.total_pages || 1;
    state.totalRecords = p.total_records || 0;

    const rangeElem = document.getElementById('page-record-range');
    const totalElem = document.getElementById('page-total-count');
    const currentInfo = document.getElementById('page-current-info');
    const prevBtn = document.getElementById('btn-prev-page');
    const nextBtn = document.getElementById('btn-next-page');

    const start = state.totalRecords === 0 ? 0 : (p.page - 1) * p.per_page + 1;
    const end = Math.min(state.totalRecords, p.page * p.per_page);

    if (rangeElem) rangeElem.innerText = `${start} - ${end}`;
    if (totalElem) totalElem.innerText = state.totalRecords;
    if (currentInfo) currentInfo.innerText = `${p.page} / ${state.totalPages}`;

    if (prevBtn) prevBtn.disabled = (p.page <= 1);
    if (nextBtn) nextBtn.disabled = (p.page >= state.totalPages);
}

function changePage(delta) {
    const target = state.page + delta;
    if (target >= 1 && target <= state.totalPages) {
        state.page = target;
        fetchReportData();
    }
}

function onPerPageChange(val) {
    state.perPage = parseInt(val, 10);
    state.page = 1;
    fetchReportData();
}

/* ─── Advanced Filter Drawer Functions ─── */
function openFilterDrawer() {
    const drawer = document.getElementById('filter-drawer');
    if (drawer) drawer.classList.remove('hidden');

    // Populate drawer controls with current state
    const setVal = (id, v) => {
        const el = document.getElementById(id);
        if (el) el.value = v || '';
    };

    setVal('adv-filter-party', state.filters.party);
    setVal('adv-filter-make', state.filters.make);
    setVal('adv-filter-order-ro', state.filters.order_ro);
    setVal('adv-filter-location', state.filters.location);
    setVal('adv-filter-division', state.filters.division);
    setVal('adv-filter-group', state.filters.group);
    setVal('adv-filter-purity', state.filters.purity);
    setVal('adv-filter-classification', state.filters.classification);
    setVal('adv-filter-collection', state.filters.collection);
    setVal('adv-filter-provision-type', state.filters.provision_type);
    setVal('adv-filter-branch-type', state.filters.branch_type);
    setVal('adv-filter-order-type', state.filters.order_type);
    setVal('adv-filter-order-request-type', state.filters.order_request_type);
    setVal('adv-filter-is-msme', state.filters.is_msme);
    setVal('adv-filter-vendor-type', state.filters.vendor_type);
}

function closeFilterDrawer() {
    const drawer = document.getElementById('filter-drawer');
    if (drawer) drawer.classList.add('hidden');
}

function applyDrawerFilters() {
    const getVal = (id) => {
        const el = document.getElementById(id);
        return el ? el.value.trim() : '';
    };

    state.statusFilter = getVal('capacity-status') || 'all';
    state.filters.party = getVal('adv-filter-party');
    state.filters.make = getVal('adv-filter-make');
    state.filters.order_ro = getVal('adv-filter-order-ro');
    state.filters.location = getVal('adv-filter-location');
    state.filters.division = getVal('adv-filter-division');
    state.filters.group = getVal('adv-filter-group');
    state.filters.purity = getVal('adv-filter-purity');
    state.filters.classification = getVal('adv-filter-classification');
    state.filters.collection = getVal('adv-filter-collection');
    state.filters.provision_type = getVal('adv-filter-provision-type');
    state.filters.branch_type = getVal('adv-filter-branch-type');
    state.filters.order_type = getVal('adv-filter-order-type');
    state.filters.order_request_type = getVal('adv-filter-order-request-type');
    state.filters.is_msme = getVal('adv-filter-is-msme');
    state.filters.vendor_type = getVal('adv-filter-vendor-type');

    // Sync quick filters
    const qMake = document.getElementById('quick-filter-make');
    if (qMake) qMake.value = state.filters.make;
    const qDiv = document.getElementById('quick-filter-division');
    if (qDiv) qDiv.value = state.filters.division;

    closeFilterDrawer();
    state.page = 1;
    fetchReportData();
}

function resetDrawerFilters() {
    for (const k in state.filters) {
        state.filters[k] = '';
    }
    openFilterDrawer(); // refresh drawer fields to empty
}

function resetAllFilters() {
    for (const k in state.filters) {
        state.filters[k] = '';
    }
    state.search = '';
    state.statusFilter = 'all';
    state.page = 1;
    document.querySelectorAll('#capacity-sidebar select').forEach(control => {
        control.value = control.id === 'capacity-status' ? 'all' : '';
    });

    const s = document.getElementById('filter-search');
    if (s) s.value = '';
    const qMake = document.getElementById('quick-filter-make');
    if (qMake) qMake.value = '';
    const qDiv = document.getElementById('quick-filter-division');
    if (qDiv) qDiv.value = '';

    document.querySelectorAll('.status-pill').forEach(btn => {
        btn.className = 'status-pill px-2 py-1 font-medium text-gray-600 dark:text-gray-300 hover:text-primary';
    });
    const activeBtn = document.getElementById('pill-all');
    if (activeBtn) {
        activeBtn.className = 'status-pill px-2 py-1 font-semibold rounded bg-white dark:bg-gray-700 text-primary shadow-xs';
    }

    fetchReportData();
}

/* ─── Order Drilldown Modal Functions ─── */
let drilldownRequest = 0;
async function openDrilldown(supplier, make, page = 1) {
    const supplierRow = state.cachedData.find(row => row.supplier === supplier);
    const makeRow = supplierRow?.makes.find(row => row.make === make);
    if (supplierRow?.is_orders === false || makeRow?.is_orders === false) return;
    const requestId = ++drilldownRequest;
    const modal = document.getElementById('drilldown-modal');
    const subtitle = document.getElementById('drilldown-subtitle');
    const tbody = document.getElementById('drilldown-table-body');
    const spinner = document.getElementById('drilldown-spinner');

    if (!modal) return;
    modal.classList.remove('hidden');
    if (subtitle) subtitle.innerText = `${supplier} ➔ ${make}`;
    if (tbody) tbody.innerHTML = '';
    if (spinner) spinner.classList.remove('hidden');
    const previous = document.getElementById('drilldown-prev');
    const next = document.getElementById('drilldown-next');
    previous.disabled = next.disabled = true;
    document.getElementById('drilldown-count').textContent = 'Loading records...';
    document.getElementById('drilldown-page').textContent = '';

    try {
        const queryParams = new URLSearchParams();
        queryParams.set('supplier', supplier);
        queryParams.set('page', page);
        if (make) queryParams.set('make', make);

        // Pass along active filters
        for (const [k, v] of Object.entries(state.filters)) {
            if (v && String(v).trim()) queryParams.set(k, String(v).trim());
        }

        const res = await fetch(`/api/party-make-capacity/drilldown?${queryParams.toString()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();
        if (requestId !== drilldownRequest) return;
        if (result.status !== 'success') throw new Error(result.message || 'Request failed');
        document.getElementById('drilldown-count').textContent = `${result.total ?? result.count} records`;
        document.getElementById('drilldown-page').textContent = `${result.page || page} / ${result.pages || 1}`;
        previous.disabled = page <= 1;
        next.disabled = page >= (result.pages || 1);
        previous.onclick = () => openDrilldown(supplier, make, page - 1);
        next.onclick = () => openDrilldown(supplier, make, page + 1);

        if (spinner) spinner.classList.add('hidden');

        if (result.status === 'success' && result.data && tbody) {
            if (result.data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="13" class="text-center py-6 text-gray-400">No backlog records match these filters</td></tr>';
                return;
            }
            result.data.forEach(o => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-blue-50/20 dark:hover:bg-gray-800/40';
                tr.classList.toggle('capacity-no-orders', o.is_orders === false);
                tr.innerHTML = `
                    <td class="px-3 py-2 font-semibold text-gray-700 dark:text-gray-200">${escapeHtml(o.order_ro)}</td>
                    <td class="px-3 py-2 text-gray-700 dark:text-gray-300 text-xs">${escapeHtml(o.location)}</td>
                    <td class="px-3 py-2 text-xs text-gray-700 dark:text-gray-300">${escapeHtml(o.division)} / ${escapeHtml(o.group)}</td>
                    <td class="px-3 py-2 text-xs text-gray-700 dark:text-gray-300">${escapeHtml(o.purity)}</td>
                    <td class="px-3 py-2 text-[10px] uppercase font-medium text-gray-500">${escapeHtml(o.order_type)}</td>
                    <td class="px-3 py-2 text-right text-xs">${formatNumber(o.process_pending_wt, 3)}</td>
                    <td class="px-3 py-2 text-right">${formatNumber(o.barcode_pending_wt, 3)}</td>
                    <td class="px-3 py-2 text-right text-xs">${formatNumber(o.hallmark_pending_wt, 3)}</td>
                    <td class="px-3 py-2 text-right">${formatNumber(o.qc_issue_pending_wt, 3)}</td>
                    <td class="px-3 py-2 text-right text-xs">${formatNumber(o.qc_complete_pending_wt, 3)}</td>
                    <td class="px-3 py-2 text-right">${formatNumber(o.invoice_pending_wt, 3)}</td>
                    <td class="px-3 py-2 text-right font-bold text-xs text-gray-900 dark:text-gray-100">${formatNumber(o.total_wt, 3)}</td>
                    <td class="px-3 py-2 text-right text-xs text-cyan-600 font-semibold">${formatNumber(o.receipt_pending_wt, 3)}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        if (requestId !== drilldownRequest) return;
        console.error('Failed to load drilldown:', err);
        if (spinner) spinner.classList.add('hidden');
        document.getElementById('drilldown-count').textContent = 'Unable to load records';
        if (tbody) tbody.innerHTML = '<tr><td colspan="13" class="text-center py-6 text-red-500">Unable to load backlog details. Close and reopen to retry.</td></tr>';
    }
}

function closeDrilldownModal() {
    drilldownRequest++;
    const modal = document.getElementById('drilldown-modal');
    if (modal) modal.classList.add('hidden');
}

/* ─── Excel Export Function ─── */
function exportToExcel() {
    const query = buildQueryString();
    window.location.href = `/api/party-make-capacity/export?${query}`;
}

/* ─── Helper Functions ─── */
function formatNumber(val, decimals = 3) {
    if (val === null || val === undefined || isNaN(val)) return '0.000';
    return Number(val).toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
