document.addEventListener('DOMContentLoaded', async () => {
    resetTopStats();
    await initFilters();
    loadReportData();
});

function resetTopStats() {
    const ids = ['stat-sales-weight', 'stat-provision-weight', 'stat-turn-weight', 'stat-turnover', 'stat-tsk-pct'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '-';
    });
    const fyFactorLabel = document.getElementById('fy-factor-label');
    if (fyFactorLabel) fyFactorLabel.textContent = 'Loading factor...';
}

let currentSearch = '';
let currentZoom = 1.0;
let searchTimeout = null;
let appliedCompositionParams = new URLSearchParams();

let filterValues = {
    location: '',
    section: '',
    classification: '',
    search: ''
};

let locationMultiSelect = null;
let sectionMultiSelect = null;
let classificationMultiSelect = null;

function toggleCompositionFilters() {
    const sidebar = document.getElementById('composition-filter-sidebar');
    const button = document.getElementById('composition-filter-toggle');
    if (!sidebar || !button) return;
    const hidden = sidebar.style.display !== 'none';
    sidebar.style.display = hidden ? 'none' : '';
    button.setAttribute('aria-expanded', String(!hidden));
    const label = hidden ? 'Show filters' : 'Hide filters';
    button.setAttribute('aria-label', label);
    button.title = label;
}

function adjustZoom(delta, reset = false) {
    const main = document.getElementById('sales-stock-composition-analysis-main');
    if (!main) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom += delta;
    }

    currentZoom = Math.max(0.7, Math.min(1.5, currentZoom));
    main.style.zoom = currentZoom;

    const zoomText = document.getElementById('zoom-level');
    if (zoomText) zoomText.textContent = `${Math.round(currentZoom * 100)}%`;
}

function onSearchInput(val) {
    currentSearch = (val || '').trim();
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        const query = currentSearch.toLowerCase();
        const rows = document.querySelectorAll('#composition-analysis-table tbody tr');
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

function collectFilterValues() {
    filterValues.location = locationMultiSelect ? locationMultiSelect.getValues().join(',') : '';
    filterValues.section = sectionMultiSelect ? sectionMultiSelect.getValues().join(',') : '';
    filterValues.classification = classificationMultiSelect ? classificationMultiSelect.getValues().join(',') : '';
    filterValues.search = currentSearch;
}

function buildRequestParams() {
    collectFilterValues();
    const params = new URLSearchParams();

    for (const [key, control] of [['branch_id', locationMultiSelect], ['section', sectionMultiSelect], ['classification', classificationMultiSelect]]) {
        for (const value of control?.getValues() || []) params.append(key, value);
    }
    if (filterValues.search) params.set('search', filterValues.search);

    return params;
}

async function requestHeaders() {
    const token = localStorage.getItem('access_token');
    return {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    };
}

async function initFilters() {
    try {
        const headers = await requestHeaders();
        const response = await fetch('/api/sales-stock-composition-analysis/options', { headers });
        if (!response.ok) return;

        const data = await response.json();

        // 2. Location MultiSelect
        locationMultiSelect = new CustomMultiSelect({
            containerId: 'filter-location-container',
            label: 'Location',
            defaultText: 'All Locations',
            options: data.locations || []
        });

        // 3. Section MultiSelect
        sectionMultiSelect = new CustomMultiSelect({
            containerId: 'filter-section-container',
            label: 'Section',
            defaultText: 'All Sections',
            options: data.sections || []
        });

        // 4. Classification MultiSelect
        classificationMultiSelect = new CustomMultiSelect({
            containerId: 'filter-classification-container',
            label: 'Classification',
            defaultText: 'All Classifications',
            options: data.classifications || []
        });

    } catch (err) {
        console.error('Failed to initialize filters:', err);
    }
}

async function loadReportData() {
    const container = document.getElementById('view-sales-stock-composition-analysis');
    const tableArea = document.getElementById('table-area');
    const progressBar = document.getElementById('report-progress');
    const fyFactorLabel = document.getElementById('fy-factor-label');

    if (!container) return;

    resetTopStats();
    if (tableArea) tableArea.classList.add('opacity-50', 'pointer-events-none');
    if (progressBar) progressBar.classList.remove('hidden');

    // Show initial loading placeholder in container if table not rendered
    if (!container.querySelector('table')) {
        container.innerHTML = `
            <div class="h-full flex flex-col items-center justify-center p-12 text-center text-gray-500">
                <span class="material-symbols-outlined text-4xl text-primary animate-spin mb-3">progress_activity</span>
                <p class="text-sm font-bold text-gray-700 dark:text-gray-200">Loading Sales &amp; Stock Composition Analysis...</p>
                <p class="mt-1 text-xs text-gray-400">Fetching report data via AJAX...</p>
            </div>
        `;
    }

    try {
        const params = buildRequestParams();
        const headers = await requestHeaders();

        const response = await fetch(`/partial/sales-stock-composition-analysis?${params.toString()}`, { headers });
        if (!response.ok) throw new Error('Unable to load report');
        const html = await response.text();
        container.innerHTML = html;
        appliedCompositionParams = new URLSearchParams(params);

        // Parse and update top stat values from metadata
        const statsScript = document.getElementById('partial-stats-data');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent || '{}');
                updateTopStats(stats);
            } catch (parseErr) {
                console.warn('Could not parse partial stats metadata:', parseErr);
                resetTopStats();
            }
        } else {
            resetTopStats();
        }


        // Re-apply search filter if user already typed
        const searchInput = document.getElementById('report-search');
        if (searchInput && searchInput.value) {
            onSearchInput(searchInput.value);
        }
    } catch (err) {
        console.error('Failed to load report data:', err);
        container.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Failed to load data: ${err.message}</div>`;
        resetTopStats();
    } finally {
        if (tableArea) tableArea.classList.remove('opacity-50', 'pointer-events-none');
        if (progressBar) progressBar.classList.add('hidden');
    }
}

function updateTopStats(stats) {
    const salesWeightEl = document.getElementById('stat-sales-weight');
    const provisionWeightEl = document.getElementById('stat-provision-weight');
    const turnWeightEl = document.getElementById('stat-turn-weight');
    const turnoverEl = document.getElementById('stat-turnover');
    const tskPctEl = document.getElementById('stat-tsk-pct');
    const fyFactorLabel = document.getElementById('fy-factor-label');

    if (!stats || Object.keys(stats).length === 0) {
        resetTopStats();
        return;
    }

    if (salesWeightEl) {
        salesWeightEl.textContent = stats.sales_weight != null
            ? (Number(stats.sales_weight)).toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 })
            : '-';
    }
    if (provisionWeightEl) {
        provisionWeightEl.textContent = stats.provision_weight != null
            ? (Number(stats.provision_weight)).toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 })
            : '-';
    }
    if (turnWeightEl) {
        turnWeightEl.textContent = stats.turn_weight != null
            ? Number(stats.turn_weight).toFixed(2)
            : (stats.turn_weight === null ? 'N/A' : '-');
    }
    if (turnoverEl) {
        turnoverEl.textContent = stats.turnover != null
            ? (Number(stats.turnover)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
            : '-';
    }
    if (tskPctEl) {
        tskPctEl.textContent = stats.tsk_pct != null
            ? `${(Number(stats.tsk_pct)).toFixed(2)}%`
            : '-';
    }
    if (fyFactorLabel && stats.factor) {
        fyFactorLabel.textContent = stats.cutoff_date
            ? `${stats.fy_label} · As on ${stats.cutoff_date} · ${stats.inclusive_fy_days}/${stats.inclusive_elapsed_days} = ${Number(stats.factor).toFixed(4)}`
            : `${stats.fy_label || 'FY'} · Factor: ${Number(stats.factor).toFixed(2)}`;
    }
}

async function toggleHierarchyBranch(rowElem, path) {
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
        // Collapse all descendant child rows
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

    // Expand via AJAX
    if (arrow) arrow.textContent = '⏳';
    const progressBar = document.getElementById('report-progress');
    if (progressBar) progressBar.classList.remove('hidden');

    try {
        const params = new URLSearchParams(appliedCompositionParams);
        params.set('path', JSON.stringify(path));

        const headers = await requestHeaders();
        const response = await fetch(`/partial/sales-stock-composition-analysis/branch?${params.toString()}`, { headers });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const childHtml = await response.text();
        rowElem.insertAdjacentHTML('afterend', childHtml);

        rowElem.dataset.expanded = 'true';
        if (arrow) {
            arrow.textContent = '▼';
            arrow.style.transform = 'rotate(0deg)';
        }
    } catch (err) {
        console.error('Failed to load child hierarchy rows:', err);
        if (arrow) arrow.textContent = '▶';
    } finally {
        if (progressBar) progressBar.classList.add('hidden');
    }
}

function collapseAllBranches() {
    loadReportData();
}

function applyFilters() {
    loadReportData();
}

function resetFilters() {
    if (locationMultiSelect) locationMultiSelect.reset();
    if (sectionMultiSelect) sectionMultiSelect.reset();
    if (classificationMultiSelect) classificationMultiSelect.reset();

    const searchInput = document.getElementById('report-search');
    if (searchInput) searchInput.value = '';
    currentSearch = '';

    loadReportData();
}

async function exportToExcel() {
    const exportBtn = document.getElementById('btn-export-excel');
    const label = document.getElementById('export-btn-label');
    const icon = document.getElementById('export-btn-icon');

    if (exportBtn) exportBtn.disabled = true;
    if (label) label.textContent = 'Exporting...';
    if (icon) icon.textContent = 'hourglass_empty';

    try {
        collectFilterValues();
        const payload = {
            filters: filterValues,
            socket_id: window.socket ? window.socket.id : null
        };

        const headers = await requestHeaders();
        const response = await fetch('/api/sales-stock-composition-analysis/export', {
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

// Global exposures
window.toggleCompositionFilters = toggleCompositionFilters;
window.adjustZoom = adjustZoom;
window.onSearchInput = onSearchInput;
window.applyFilters = applyFilters;
window.resetFilters = resetFilters;
window.collapseAllBranches = collapseAllBranches;
window.toggleHierarchyBranch = toggleHierarchyBranch;
window.exportToExcel = exportToExcel;

let salesContributorsChart = null;
let salesChartRequest = null;

async function openSalesChart(button) {
    const dialog = document.getElementById('sales-chart-modal');
    const status = document.getElementById('sales-chart-status');
    const frame = document.getElementById('sales-chart-frame');
    const list = document.getElementById('sales-chart-values');
    const path = JSON.parse(button.dataset.chartPath || '[]');
    salesChartRequest?.abort();
    const controller = new AbortController();
    salesChartRequest = controller;
    salesContributorsChart?.destroy();
    salesContributorsChart = null;
    frame.hidden = true;
    list.replaceChildren();
    document.getElementById('sales-chart-title').textContent = `Top 10 Sales Contributors: ${path.join(' / ') || 'All Sections'}`;
    status.textContent = 'Loading contributors...';
    if (!dialog.open) dialog.showModal();
    try {
        const params = new URLSearchParams(appliedCompositionParams);
        params.set('path', JSON.stringify(path));
        const response = await fetch(`/api/sales-stock-composition-analysis/contributors?${params}`, {
            headers: await requestHeaders(), signal: controller.signal
        });
        if (!response.ok) throw new Error('Unable to load contributors. Please try again.');
        const data = await response.json();
        if (controller.signal.aborted || !dialog.open) return;
        if (!data.items.length) {
            status.textContent = 'No positive net sales contributors for this selection.';
            return;
        }
        const total = data.items.reduce((sum, item) => sum + item.weight, 0);
        status.textContent = `${data.level.replaceAll('_', ' ')} · As on ${data.cutoff} · Share of positive net sales weight`;
        if (data.negative_weight < 0) status.textContent += ` · Negative contributors excluded from chart: ${data.negative_weight.toFixed(3)} g`;
        const colors = ['#3b82f6', '#16a34a', '#eab308', '#ea580c', '#8b5cf6', '#06b6d4', '#ec4899', '#64748b', '#84cc16', '#b45309', '#9ca3af'];
        data.items.forEach((item, index) => {
            const li = document.createElement('li');
            li.style.display = 'flex';
            li.style.gap = '8px';
            const swatch = document.createElement('span');
            Object.assign(swatch.style, { background: colors[index], width: '10px', height: '10px', borderRadius: '50%', flexShrink: '0', marginTop: '3px' });
            const label = document.createElement('span');
            label.style.overflowWrap = 'anywhere';
            label.textContent = `${item.label}: ${item.weight.toFixed(3)} g (${(item.weight / total * 100).toFixed(2)}%)`;
            li.append(swatch, label);
            list.append(li);
        });
        if (typeof Chart === 'undefined') throw new Error('Chart library unavailable. Contributor values are listed below.');
        frame.hidden = false;
        salesContributorsChart = new Chart(document.getElementById('sales-contributors-chart'), {
            type: 'doughnut',
            data: { labels: data.items.map(i => i.label), datasets: [{ data: data.items.map(i => i.weight), backgroundColor: colors, borderWidth: 2, hoverOffset: 6 }] },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '52%',
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: ctx => ` ${Number(ctx.raw).toFixed(3)} g · ${(ctx.raw / total * 100).toFixed(2)}%` } }
                }
            }
        });
    } catch (error) {
        if (error.name !== 'AbortError') status.textContent = error.message;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const dialog = document.getElementById('sales-chart-modal');
    dialog.addEventListener('close', () => {
        salesChartRequest?.abort();
        salesContributorsChart?.destroy();
        salesContributorsChart = null;
    });
});
window.openSalesChart = openSalesChart;
