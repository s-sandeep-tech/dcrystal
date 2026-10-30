/**
 * Sales & Stock Composition Analysis for Purchase Plan
 * Standalone JavaScript View
 */

document.addEventListener('DOMContentLoaded', async () => {
    resetPurchasePlanTopStats();
    await initPurchasePlanFilters();
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
    location: '',
    section: '',
    classification: '',
    search: ''
};

let purchasePlanLocationSelect = null;
let purchasePlanSectionSelect = null;
let purchasePlanClassificationSelect = null;

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
    purchasePlanFilterValues.location = purchasePlanLocationSelect ? purchasePlanLocationSelect.getValues().join(',') : '';
    purchasePlanFilterValues.section = purchasePlanSectionSelect ? purchasePlanSectionSelect.getValues().join(',') : '';
    purchasePlanFilterValues.classification = purchasePlanClassificationSelect ? purchasePlanClassificationSelect.getValues().join(',') : '';
    purchasePlanFilterValues.search = purchasePlanSearch;
}

function buildPurchasePlanRequestParams() {
    collectPurchasePlanFilterValues();
    const params = new URLSearchParams();

    for (const [key, ctrl] of [
        ['branch_id', purchasePlanLocationSelect],
        ['section', purchasePlanSectionSelect],
        ['classification', purchasePlanClassificationSelect]
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

async function initPurchasePlanFilters() {
    try {
        const headers = await getPurchasePlanAuthHeaders();
        const response = await fetch('/api/sales-stock-composition-analysis-for-purchase-plan/options', { headers });
        if (!response.ok) return;

        const data = await response.json();
        latestPurchasePlanSalesDate = data.dates?.[0] || '';
        const dateInput = document.getElementById('purchase-plan-filter-max-date');
        if (dateInput && !dateInput.value) dateInput.value = latestPurchasePlanSalesDate;

        purchasePlanLocationSelect = new CustomMultiSelect({
            containerId: 'purchase-plan-filter-location-container',
            label: 'Location',
            defaultText: 'All Locations',
            options: data.locations || []
        });

        purchasePlanSectionSelect = new CustomMultiSelect({
            containerId: 'purchase-plan-filter-section-container',
            label: 'Section',
            defaultText: 'All Sections',
            options: data.sections || []
        });

        purchasePlanClassificationSelect = new CustomMultiSelect({
            containerId: 'purchase-plan-filter-classification-container',
            label: 'Classification',
            defaultText: 'All Classifications',
            options: data.classifications || []
        });
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
    if (purchasePlanLocationSelect) purchasePlanLocationSelect.reset();
    if (purchasePlanSectionSelect) purchasePlanSectionSelect.reset();
    if (purchasePlanClassificationSelect) purchasePlanClassificationSelect.reset();

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

let purchasePlanChartInstance = null;
let purchasePlanChartRequest = null;

async function openPurchasePlanSalesChart(button) {
    const dialog = document.getElementById('purchase-plan-sales-chart-modal');
    const status = document.getElementById('purchase-plan-sales-chart-status');
    const frame = document.getElementById('purchase-plan-chart-frame');
    const list = document.getElementById('purchase-plan-chart-values');
    const path = JSON.parse(button.dataset.chartPath || '[]');

    purchasePlanChartRequest?.abort();
    const controller = new AbortController();
    purchasePlanChartRequest = controller;
    purchasePlanChartInstance?.destroy();
    purchasePlanChartInstance = null;
    frame.hidden = true;
    list.replaceChildren();

    document.getElementById('purchase-plan-sales-chart-title').textContent =
        `Top 10 Sales Contributors: ${path.join(' / ') || 'All Sections'}`;
    status.textContent = 'Loading contributors...';

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

        if (!data.items || !data.items.length) {
            status.textContent = 'No positive net sales contributors for this selection.';
            return;
        }

        const total = data.items.reduce((sum, item) => sum + item.weight, 0);
        status.textContent = `${data.level.replaceAll('_', ' ')} · As on ${data.cutoff} · Share of positive net sales weight`;
        if (data.negative_weight < 0) {
            status.textContent += ` · Negative contributors excluded from chart: ${data.negative_weight.toFixed(3)} g`;
        }

        const colors = ['#3b82f6', '#16a34a', '#eab308', '#ea580c', '#8b5cf6', '#06b6d4', '#ec4899', '#64748b', '#84cc16', '#b45309', '#9ca3af'];
        data.items.forEach((item, index) => {
            const li = document.createElement('li');
            li.style.display = 'flex';
            li.style.gap = '8px';
            const swatch = document.createElement('span');
            Object.assign(swatch.style, {
                background: colors[index % colors.length],
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                flexShrink: '0',
                marginTop: '3px'
            });
            const label = document.createElement('span');
            label.style.overflowWrap = 'anywhere';
            label.textContent = `${item.label}: ${item.weight.toFixed(3)} g (${(item.weight / total * 100).toFixed(2)}%)`;
            li.append(swatch, label);
            list.append(li);
        });

        if (typeof Chart === 'undefined') throw new Error('Chart library unavailable. Contributor values are listed below.');
        frame.hidden = false;
        purchasePlanChartInstance = new Chart(document.getElementById('purchase-plan-sales-contributors-chart'), {
            type: 'doughnut',
            data: {
                labels: data.items.map(i => i.label),
                datasets: [{
                    data: data.items.map(i => i.weight),
                    backgroundColor: colors,
                    borderWidth: 2,
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
                            label: ctx => ` ${Number(ctx.raw).toFixed(3)} g · ${(ctx.raw / total * 100).toFixed(2)}%`
                        }
                    }
                }
            }
        });
    } catch (err) {
        if (err.name !== 'AbortError') status.textContent = err.message;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const dialog = document.getElementById('purchase-plan-sales-chart-modal');
    if (dialog) {
        dialog.addEventListener('close', () => {
            purchasePlanChartRequest?.abort();
            purchasePlanChartInstance?.destroy();
            purchasePlanChartInstance = null;
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
window.openPurchasePlanSalesChart = openPurchasePlanSalesChart;
