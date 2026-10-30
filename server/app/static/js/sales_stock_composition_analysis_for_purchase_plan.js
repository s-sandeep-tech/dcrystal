/**
 * Sales & Stock Composition Analysis for Purchase Plan
 * Standalone JavaScript View
 */

document.addEventListener('DOMContentLoaded', () => {
    resetPurchasePlanTopStats();
    initPurchasePlanFilters();
    loadPurchasePlanReportData();
});

function resetPurchasePlanTopStats() {
    const ids = ['stat-sales-weight', 'stat-provision-weight', 'stat-turn-weight'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '-';
    });
    const factorLabel = document.getElementById('purchase-plan-fy-factor-label');
    if (factorLabel) factorLabel.textContent = 'Loading factor...';
}

let purchasePlanSearch = '';
let purchasePlanZoom = 1.0;
let purchasePlanSearchTimeout = null;
let appliedPurchasePlanParams = new URLSearchParams();
let latestPurchasePlanSalesDate = '';
const purchasePlanSortKeys = ['label', 'sales_composition', 'stock_composition', 'weight_turn'];
const initialPurchasePlanParams = new URLSearchParams(window.location.search);
let purchasePlanSortBy = purchasePlanSortKeys.includes(initialPurchasePlanParams.get('sort_by'))
    ? initialPurchasePlanParams.get('sort_by') : 'label';
let purchasePlanSortOrder = initialPurchasePlanParams.get('sort_order') === 'desc' ? 'desc' : 'asc';

let purchasePlanFilterValues = {
    date: '',
    division: 'Gold',
    location: '',
    section: '',
    classification: '',
    make: '',
    purity: '',
    search: ''
};

let purchasePlanLocationSelect = null;
let purchasePlanSectionSelect = null;
let purchasePlanClassificationSelect = null;
let purchasePlanMakeSelect = null;
let purchasePlanPuritySelect = null;

function togglePurchasePlanFilters() {
    const sidebar = document.getElementById('purchase-plan-filter-sidebar');
    const button = document.getElementById('purchase-plan-filter-toggle');
    if (!sidebar || !button) return;
    const isHidden = sidebar.style.display !== 'none';
    sidebar.style.display = isHidden ? 'none' : '';
    button.setAttribute('aria-expanded', String(!isHidden));
    const label = isHidden ? 'Show filters' : 'Hide filters';
    button.setAttribute('aria-label', label);
    button.title = label;
}

function adjustPurchasePlanZoom(delta, reset = false) {
    const main = document.getElementById('sales-stock-composition-analysis-for-purchase-plan-main');
    if (!main) return;

    if (reset) {
        purchasePlanZoom = 1.0;
    } else {
        purchasePlanZoom += delta;
    }

    purchasePlanZoom = Math.max(0.7, Math.min(1.5, purchasePlanZoom));
    main.style.zoom = purchasePlanZoom;

    const zoomText = document.getElementById('purchase-plan-zoom-level');
    if (zoomText) zoomText.textContent = `${Math.round(purchasePlanZoom * 100)}%`;
}

function onPurchasePlanSearchInput(val) {
    purchasePlanSearch = (val || '').trim();
    clearTimeout(purchasePlanSearchTimeout);
    purchasePlanSearchTimeout = setTimeout(() => {
        const query = purchasePlanSearch.toLowerCase();
        const rows = document.querySelectorAll('#purchase-plan-composition-table tbody tr');
        rows.forEach(r => {
            if (!query) {
                r.style.display = '';
                return;
            }
            const labelText = r.querySelector('td:first-child')?.textContent?.toLowerCase() || '';
            r.style.display = labelText.includes(query) ? '' : 'none';
        });
    }, 200);
}

function collectPurchasePlanFilterValues() {
    purchasePlanFilterValues.date = document.getElementById('purchase-plan-filter-max-date')?.value || '';
    purchasePlanFilterValues.division = document.getElementById('purchase-plan-filter-division')?.value || '';
    purchasePlanFilterValues.location = purchasePlanLocationSelect ? purchasePlanLocationSelect.getValues().join(',') : '';
    purchasePlanFilterValues.section = purchasePlanSectionSelect ? purchasePlanSectionSelect.getValues().join(',') : '';
    purchasePlanFilterValues.classification = purchasePlanClassificationSelect ? purchasePlanClassificationSelect.getValues().join(',') : '';
    purchasePlanFilterValues.make = purchasePlanMakeSelect ? purchasePlanMakeSelect.getValues().join(',') : '';
    purchasePlanFilterValues.purity = purchasePlanPuritySelect ? purchasePlanPuritySelect.getValues().join(',') : '';
    purchasePlanFilterValues.search = purchasePlanSearch;
}

function buildPurchasePlanRequestParams() {
    collectPurchasePlanFilterValues();
    const params = new URLSearchParams();

    const divisionVal = document.getElementById('purchase-plan-filter-division')?.value || '';
    if (divisionVal) params.append('division', divisionVal);

    for (const [key, ctrl] of [
        ['branch_id', purchasePlanLocationSelect],
        ['section', purchasePlanSectionSelect],
        ['classification', purchasePlanClassificationSelect],
        ['make', purchasePlanMakeSelect],
        ['purity', purchasePlanPuritySelect]
    ]) {
        for (const v of ctrl?.getValues() || []) params.append(key, v);
    }
    if (purchasePlanFilterValues.search) params.set('search', purchasePlanFilterValues.search);
    if (purchasePlanFilterValues.date) params.set('date', purchasePlanFilterValues.date);
    params.set('sort_by', purchasePlanSortBy);
    params.set('sort_order', purchasePlanSortOrder);

    return params;
}

async function getPurchasePlanAuthHeaders() {
    const token = localStorage.getItem('access_token');
    return {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    };
}

function applyPurchasePlanFilterOptions(data) {
    if (!data) return;

    latestPurchasePlanSalesDate = data.dates?.[0] || latestPurchasePlanSalesDate || '';
    const dateInput = document.getElementById('purchase-plan-filter-max-date');
    if (dateInput && !dateInput.value) dateInput.value = latestPurchasePlanSalesDate;

    const divisionSelect = document.getElementById('purchase-plan-filter-division');
    if (divisionSelect) {
        const currentDiv = divisionSelect.value || 'Gold';
        if (data.divisions && data.divisions.length > 0) {
            divisionSelect.innerHTML = '<option value="">All Divisions</option>';
            data.divisions.forEach(div => {
                const opt = document.createElement('option');
                opt.value = div;
                opt.textContent = div;
                divisionSelect.appendChild(opt);
            });
        }
        const targetDiv = currentDiv || 'Gold';
        const matchedOpt = Array.from(divisionSelect.options).find(o => o.value.toLowerCase() === targetDiv.toLowerCase());
        if (matchedOpt) {
            divisionSelect.value = matchedOpt.value;
            purchasePlanFilterValues.division = matchedOpt.value;
        } else if (targetDiv) {
            const opt = document.createElement('option');
            opt.value = targetDiv;
            opt.textContent = targetDiv;
            opt.selected = true;
            divisionSelect.appendChild(opt);
            purchasePlanFilterValues.division = targetDiv;
        }
    }

    if (!purchasePlanLocationSelect) {
        purchasePlanLocationSelect = new CustomMultiSelect({
            containerId: 'purchase-plan-filter-location-container',
            label: 'Location',
            defaultText: 'All Locations',
            options: data.locations || []
        });
    }

    if (!purchasePlanSectionSelect) {
        purchasePlanSectionSelect = new CustomMultiSelect({
            containerId: 'purchase-plan-filter-section-container',
            label: 'Section',
            defaultText: 'All Sections',
            options: data.sections || []
        });
    }

    if (!purchasePlanClassificationSelect) {
        purchasePlanClassificationSelect = new CustomMultiSelect({
            containerId: 'purchase-plan-filter-classification-container',
            label: 'Classification',
            defaultText: 'All Classifications',
            options: data.classifications || []
        });
    }

    if (!purchasePlanMakeSelect) {
        purchasePlanMakeSelect = new CustomMultiSelect({
            containerId: 'purchase-plan-filter-make-container',
            label: 'Make',
            defaultText: 'All Makes',
            options: data.makes || []
        });
    }

    if (!purchasePlanPuritySelect) {
        purchasePlanPuritySelect = new CustomMultiSelect({
            containerId: 'purchase-plan-filter-purity-container',
            label: 'Purity',
            defaultText: 'All Purities',
            options: data.purities || []
        });
    }
}

async function initPurchasePlanFilters() {
    const optionsEl = document.getElementById('purchase-plan-filter-options-data');
    if (optionsEl) {
        try {
            const initialOptions = JSON.parse(optionsEl.textContent || '{}');
            if (initialOptions && Object.keys(initialOptions).length > 0) {
                applyPurchasePlanFilterOptions(initialOptions);
                return;
            }
        } catch (e) {
            console.warn('Could not parse initial purchase plan filter options:', e);
        }
    }

    try {
        const headers = await getPurchasePlanAuthHeaders();
        const response = await fetch('/api/sales-stock-composition-analysis-for-purchase-plan/options', { headers });
        if (!response.ok) return;

        const data = await response.json();
        applyPurchasePlanFilterOptions(data);
    } catch (err) {
        console.error('Failed to initialize purchase plan filters:', err);
    }
}

async function loadPurchasePlanReportData(requestParams = null) {
    const container = document.getElementById('view-sales-stock-composition-analysis-for-purchase-plan');
    const tableArea = document.getElementById('purchase-plan-table-area');
    const progressBar = document.getElementById('purchase-plan-report-progress');

    if (!container) return;

    resetPurchasePlanTopStats();
    if (tableArea) tableArea.classList.add('opacity-50', 'pointer-events-none');
    if (progressBar) progressBar.classList.remove('hidden');

    if (!container.querySelector('table')) {
        container.innerHTML = `
            <div class="h-full flex flex-col items-center justify-center p-12 text-center text-gray-500">
                <span class="material-symbols-outlined text-4xl text-primary animate-spin mb-3">progress_activity</span>
                <p class="text-sm font-bold text-gray-700 dark:text-gray-200">Loading Sales &amp; Stock Composition Analysis for Purchase Plan...</p>
                <p class="mt-1 text-xs text-gray-400">Fetching report data via AJAX...</p>
            </div>
        `;
    }

    try {
        const params = requestParams || buildPurchasePlanRequestParams();
        const headers = await getPurchasePlanAuthHeaders();

        const response = await fetch(`/partial/sales-stock-composition-analysis-for-purchase-plan?${params.toString()}`, { headers });
        if (!response.ok) throw new Error('Unable to load report');
        const html = await response.text();
        container.innerHTML = html;
        appliedPurchasePlanParams = new URLSearchParams(params);

        const statsScript = document.getElementById('partial-purchase-plan-stats-data');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent || '{}');
                updatePurchasePlanTopStats(stats);
            } catch (parseErr) {
                console.warn('Could not parse partial purchase plan stats:', parseErr);
                resetPurchasePlanTopStats();
            }
        } else {
            resetPurchasePlanTopStats();
        }

        const searchInput = document.getElementById('purchase-plan-report-search');
        if (searchInput && searchInput.value) {
            onPurchasePlanSearchInput(searchInput.value);
        }
    } catch (err) {
        console.error('Failed to load purchase plan report:', err);
        container.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Failed to load data: ${err.message}</div>`;
        resetPurchasePlanTopStats();
    } finally {
        if (tableArea) tableArea.classList.remove('opacity-50', 'pointer-events-none');
        if (progressBar) progressBar.classList.add('hidden');
    }
}

function updatePurchasePlanTopStats(stats) {
    const salesWeightEl = document.getElementById('stat-sales-weight');
    const provisionWeightEl = document.getElementById('stat-provision-weight');
    const turnWeightEl = document.getElementById('stat-turn-weight');
    const factorLabel = document.getElementById('purchase-plan-fy-factor-label');

    if (!stats || Object.keys(stats).length === 0) {
        resetPurchasePlanTopStats();
        return;
    }

    if (salesWeightEl) {
        salesWeightEl.textContent = stats.sales_weight != null
            ? (Number(stats.sales_weight) / 1000).toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 })
            : '-';
    }
    if (provisionWeightEl) {
        provisionWeightEl.textContent = stats.provision_weight != null
            ? (Number(stats.provision_weight) / 1000).toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 })
            : '-';
    }
    if (turnWeightEl) {
        turnWeightEl.textContent = stats.turn_na_b ? 'NA-B' : stats.turn_weight != null
            ? `${Number(stats.turn_weight).toFixed(2)}%`
            : (stats.turn_weight === null ? 'N/A' : '-');
    }
    if (factorLabel && stats.location_factors) {
        const factors = stats.location_factors;
        if (stats.missing_factor) {
            factorLabel.textContent = 'Annualisation unavailable for locations with no transaction date';
        } else if (factors.length === 0) {
            factorLabel.textContent = 'No dated locations';
        } else if (stats.factor != null) {
            const item = factors[0];
            factorLabel.textContent = `${item.fy_label} · As on ${item.date} · ${item.inclusive_fy_days}/${item.inclusive_elapsed_days} = ${Number(item.factor).toFixed(4)}`;
        } else {
            const dates = factors.map(item => item.date).sort();
            factorLabel.textContent = `Location-wise factors · ${factors.length} locations · ${dates[0]} to ${dates[dates.length - 1]}`;
        }
    } else if (factorLabel && stats.factor) {
        factorLabel.textContent = stats.cutoff_date
            ? `${stats.fy_label} · As on ${stats.cutoff_date} · ${stats.inclusive_fy_days}/${stats.inclusive_elapsed_days} = ${Number(stats.factor).toFixed(4)}`
            : `${stats.fy_label || 'FY'} · Factor: ${Number(stats.factor).toFixed(2)}`;
    }
}

async function togglePurchasePlanBranch(rowElem, path) {
    if (!rowElem) return;
    if (!path && rowElem.dataset.path) {
        try {
            path = JSON.parse(rowElem.dataset.path);
        } catch (e) {
            path = [];
        }
    }
    path = path || [];
    const isExpanded = rowElem.dataset.expanded === 'true';
    const arrow = rowElem.querySelector('.toggle-arrow');
    const depth = path.length;

    if (isExpanded) {
        let next = rowElem.nextElementSibling;
        while (next && next.classList.contains('child-row')) {
            const nextDepth = parseInt(next.dataset.depth || '0', 10);
            if (nextDepth <= depth) break;
            const toRemove = next;
            next = next.nextElementSibling;
            toRemove.remove();
        }
        rowElem.dataset.expanded = 'false';
        if (arrow) {
            arrow.textContent = '▶';
            arrow.style.transform = 'rotate(0deg)';
        }
        return;
    }

    if (arrow) arrow.textContent = '⏳';
    const progressBar = document.getElementById('purchase-plan-report-progress');
    if (progressBar) progressBar.classList.remove('hidden');

    try {
        const params = new URLSearchParams(appliedPurchasePlanParams);
        params.set('path', JSON.stringify(path));

        const headers = await getPurchasePlanAuthHeaders();
        const response = await fetch(`/partial/sales-stock-composition-analysis-for-purchase-plan/branch?${params.toString()}`, { headers });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const childHtml = await response.text();
        rowElem.insertAdjacentHTML('afterend', childHtml);

        rowElem.dataset.expanded = 'true';
        if (arrow) {
            arrow.textContent = '▼';
            arrow.style.transform = 'rotate(0deg)';
        }
    } catch (err) {
        console.error('Failed to load child purchase plan rows:', err);
        if (arrow) arrow.textContent = '▶';
    } finally {
        if (progressBar) progressBar.classList.add('hidden');
    }
}

function collapseAllPurchasePlanBranches() {
    loadPurchasePlanReportData();
}

function applyPurchasePlanFilters() {
    loadPurchasePlanReportData();
}

function sortPurchasePlan(column) {
    if (!purchasePlanSortKeys.includes(column)) return;
    purchasePlanSortOrder = purchasePlanSortBy === column && purchasePlanSortOrder === 'asc' ? 'desc' : 'asc';
    purchasePlanSortBy = column;
    const params = new URLSearchParams(appliedPurchasePlanParams);
    params.set('sort_by', purchasePlanSortBy);
    params.set('sort_order', purchasePlanSortOrder);
    loadPurchasePlanReportData(params);
}

function resetPurchasePlanFilters() {
    const dateSelect = document.getElementById('purchase-plan-filter-max-date');
    if (dateSelect) dateSelect.value = latestPurchasePlanSalesDate;

    const divisionSelect = document.getElementById('purchase-plan-filter-division');
    if (divisionSelect) {
        const goldOpt = Array.from(divisionSelect.options).find(o => o.value.toLowerCase() === 'gold');
        divisionSelect.value = goldOpt ? goldOpt.value : 'Gold';
        purchasePlanFilterValues.division = divisionSelect.value;
    }

    if (purchasePlanLocationSelect) purchasePlanLocationSelect.reset();
    if (purchasePlanSectionSelect) purchasePlanSectionSelect.reset();
    if (purchasePlanClassificationSelect) purchasePlanClassificationSelect.reset();
    if (purchasePlanMakeSelect) purchasePlanMakeSelect.reset();
    if (purchasePlanPuritySelect) purchasePlanPuritySelect.reset();

    const searchInput = document.getElementById('purchase-plan-report-search');
    if (searchInput) searchInput.value = '';
    purchasePlanSearch = '';
    purchasePlanSortBy = 'label';
    purchasePlanSortOrder = 'asc';

    loadPurchasePlanReportData();
}

async function exportPurchasePlanToExcel() {
    const exportBtn = document.getElementById('btn-export-purchase-plan-excel');
    const label = document.getElementById('purchase-plan-export-btn-label');
    const icon = document.getElementById('purchase-plan-export-btn-icon');

    if (exportBtn) exportBtn.disabled = true;
    if (label) label.textContent = 'Exporting...';
    if (icon) icon.textContent = 'hourglass_empty';

    try {
        collectPurchasePlanFilterValues();
        const payload = {
            filters: purchasePlanFilterValues,
            socket_id: window.socket ? window.socket.id : null
        };

        const headers = await getPurchasePlanAuthHeaders();
        const response = await fetch('/api/sales-stock-composition-analysis-for-purchase-plan/export', {
            method: 'POST',
            headers,
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        if (result.status === 'success' || result.task_id) {
            if (window.showToast) {
                window.showToast('Export job queued. Download will begin shortly.', 'success');
            }
        } else {
            throw new Error(result.message || 'Export failed');
        }
    } catch (err) {
        console.error('Export failed:', err);
        if (window.showToast) {
            window.showToast(`Export error: ${err.message}`, 'error');
        }
    } finally {
        if (exportBtn) exportBtn.disabled = false;
        if (label) label.textContent = 'Export';
        if (icon) icon.textContent = 'download';
    }
}

let purchasePlanSalesChart = null;
let purchasePlanStockChart = null;
let purchasePlanChartRequest = null;
let currentPurchasePlanModalTab = 'compare';
let cachedContributorData = null;

const CHART_COLORS = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
    '#06b6d4', '#ec4899', '#64748b', '#84cc16', '#f97316', '#a855f7'
];

function switchPurchasePlanModalTab(tab) {
    currentPurchasePlanModalTab = 'compare';
    const salesPanel = document.getElementById('purchase-plan-sales-panel');
    const stockPanel = document.getElementById('purchase-plan-stock-panel');
    if (salesPanel) salesPanel.hidden = false;
    if (stockPanel) stockPanel.hidden = false;

    setTimeout(() => {
        purchasePlanSalesChart?.resize();
        purchasePlanStockChart?.resize();
    }, 60);
}

function renderContributorPanel(type, dataSection, canvasId, frameId, emptyMsgId, listId, subtitleId) {
    const frame = document.getElementById(frameId);
    const canvas = document.getElementById(canvasId);
    const emptyMsg = document.getElementById(emptyMsgId);
    const list = document.getElementById(listId);
    const subtitle = document.getElementById(subtitleId);

    if (list) list.replaceChildren();

    const items = dataSection?.items || [];
    const totalPositive = dataSection?.total_positive_weight ?? items.reduce((sum, item) => sum + item.weight, 0);

    if (subtitle) {
        const totalKg = Number(totalPositive) / 1000;
        subtitle.textContent = `Total: ${totalKg.toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 })} kg`;
        if (dataSection?.negative_weight < 0) {
            const negKg = Number(dataSection.negative_weight) / 1000;
            subtitle.textContent += ` · Excl. neg: ${negKg.toFixed(3)} kg`;
        }
    }

    if (!items.length || totalPositive <= 0) {
        if (frame) frame.hidden = true;
        if (emptyMsg) emptyMsg.classList.remove('hidden');
        return null;
    }

    if (emptyMsg) emptyMsg.classList.add('hidden');
    if (frame) frame.hidden = false;

    items.forEach((item, index) => {
        const li = document.createElement('li');
        li.style.display = 'flex';
        li.style.gap = '6px';
        li.style.alignItems = 'flex-start';

        const swatch = document.createElement('span');
        Object.assign(swatch.style, {
            background: CHART_COLORS[index % CHART_COLORS.length],
            width: '9px',
            height: '9px',
            borderRadius: '50%',
            flexShrink: '0',
            marginTop: '3px'
        });

        const pct = totalPositive > 0 ? (item.weight / totalPositive * 100).toFixed(2) : '0.00';
        const label = document.createElement('span');
        label.style.overflowWrap = 'anywhere';
        label.className = 'text-gray-700 dark:text-gray-300';
        label.textContent = `${item.label}: ${Number(item.weight).toFixed(3)} g (${pct}%)`;

        li.append(swatch, label);
        list.append(li);
    });

    if (typeof Chart === 'undefined' || !canvas) return null;

    return new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: items.map(i => i.label),
            datasets: [{
                data: items.map(i => i.weight),
                backgroundColor: CHART_COLORS.slice(0, items.length),
                borderWidth: 2,
                borderColor: '#ffffff',
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '52%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const val = Number(ctx.raw);
                            const p = totalPositive > 0 ? (val / totalPositive * 100).toFixed(2) : '0.00';
                            return ` ${val.toFixed(3)} g (${p}%)`;
                        }
                    }
                }
            }
        }
    });
}

async function openPurchasePlanChart(button) {
    const dialog = document.getElementById('purchase-plan-sales-chart-modal');
    const status = document.getElementById('purchase-plan-sales-chart-status');
    const path = JSON.parse(button.dataset.chartPath || '[]');

    purchasePlanChartRequest?.abort();
    const controller = new AbortController();
    purchasePlanChartRequest = controller;

    purchasePlanSalesChart?.destroy();
    purchasePlanSalesChart = null;
    purchasePlanStockChart?.destroy();
    purchasePlanStockChart = null;

    const salesFrame = document.getElementById('purchase-plan-sales-frame');
    const stockFrame = document.getElementById('purchase-plan-stock-frame');
    if (salesFrame) salesFrame.hidden = true;
    if (stockFrame) stockFrame.hidden = true;

    document.getElementById('purchase-plan-sales-values')?.replaceChildren();
    document.getElementById('purchase-plan-stock-values')?.replaceChildren();

    const titleTarget = path.join(' / ') || 'All Sections';
    document.getElementById('purchase-plan-sales-chart-title').textContent = `Top 10 Contributors: ${titleTarget}`;
    if (status) status.textContent = 'Loading sales & stock contributors...';

    const salesPanel = document.getElementById('purchase-plan-sales-panel');
    const stockPanel = document.getElementById('purchase-plan-stock-panel');
    if (salesPanel) salesPanel.hidden = false;
    if (stockPanel) stockPanel.hidden = false;

    if (!dialog.open) dialog.showModal();

    try {
        const params = new URLSearchParams(appliedPurchasePlanParams);
        params.set('path', JSON.stringify(path));

        const response = await fetch(`/api/sales-stock-composition-analysis-for-purchase-plan/contributors?${params}`, {
            headers: await getPurchasePlanAuthHeaders(),
            signal: controller.signal
        });
        if (!response.ok) throw new Error('Unable to load contributors. Please try again.');

        const data = await response.json();
        if (controller.signal.aborted || !dialog.open) return;
        cachedContributorData = data;

        const levelDisplay = (data.level || '').replaceAll('_', ' ');
        if (status) {
            status.textContent = `${levelDisplay} · Cutoff: ${data.cutoff || 'Current'} · Top contributors by weight`;
        }

        const salesSection = data.sales || { items: data.items || [], negative_weight: data.negative_weight, total_positive_weight: data.net_weight };
        const stockSection = data.stock || { items: [], negative_weight: 0, total_positive_weight: 0 };

        purchasePlanSalesChart = renderContributorPanel(
            'sales',
            salesSection,
            'purchase-plan-sales-contributors-chart',
            'purchase-plan-sales-frame',
            'sales-empty-msg',
            'purchase-plan-sales-values',
            'sales-panel-subtitle'
        );

        purchasePlanStockChart = renderContributorPanel(
            'stock',
            stockSection,
            'purchase-plan-stock-contributors-chart',
            'purchase-plan-stock-frame',
            'stock-empty-msg',
            'purchase-plan-stock-values',
            'stock-panel-subtitle'
        );

        requestAnimationFrame(() => {
            purchasePlanSalesChart?.resize();
            purchasePlanStockChart?.resize();
        });
    } catch (err) {
        if (err.name !== 'AbortError' && status) status.textContent = err.message;
    }
}

function openPurchasePlanSalesChart(button) {
    return openPurchasePlanChart(button);
}

document.addEventListener('DOMContentLoaded', () => {
    const dialog = document.getElementById('purchase-plan-sales-chart-modal');
    if (dialog) {
        dialog.addEventListener('close', () => {
            purchasePlanChartRequest?.abort();
            purchasePlanSalesChart?.destroy();
            purchasePlanSalesChart = null;
            purchasePlanStockChart?.destroy();
            purchasePlanStockChart = null;
        });
    }
});

// Window exposures
window.togglePurchasePlanFilters = togglePurchasePlanFilters;
window.adjustPurchasePlanZoom = adjustPurchasePlanZoom;
window.onPurchasePlanSearchInput = onPurchasePlanSearchInput;
window.applyPurchasePlanFilters = applyPurchasePlanFilters;
window.resetPurchasePlanFilters = resetPurchasePlanFilters;
window.collapseAllPurchasePlanBranches = collapseAllPurchasePlanBranches;
window.togglePurchasePlanBranch = togglePurchasePlanBranch;
window.exportPurchasePlanToExcel = exportPurchasePlanToExcel;
window.sortPurchasePlan = sortPurchasePlan;
window.openPurchasePlanChart = openPurchasePlanChart;
window.openPurchasePlanSalesChart = openPurchasePlanSalesChart;
window.switchPurchasePlanModalTab = switchPurchasePlanModalTab;
