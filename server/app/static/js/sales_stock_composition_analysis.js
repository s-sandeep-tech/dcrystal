document.addEventListener('DOMContentLoaded', () => {
    initFilters();
    loadReportData();
});

let currentSearch = '';
let currentZoom = 1.0;
let searchTimeout = null;

let filterValues = {
    date: '',
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
    const dateSelect = document.getElementById('filter-date');
    filterValues.date = dateSelect ? dateSelect.value : '';

    filterValues.location = locationMultiSelect ? locationMultiSelect.getValues().join(',') : '';
    filterValues.section = sectionMultiSelect ? sectionMultiSelect.getValues().join(',') : '';
    filterValues.classification = classificationMultiSelect ? classificationMultiSelect.getValues().join(',') : '';
    filterValues.search = currentSearch;
}

function buildRequestParams() {
    collectFilterValues();
    const params = new URLSearchParams();

    if (filterValues.date) params.set('date', filterValues.date);
    if (filterValues.location) params.set('branch_id', filterValues.location);
    if (filterValues.section) params.set('section', filterValues.section);
    if (filterValues.classification) params.set('classification', filterValues.classification);
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

        // 1. Source Date
        const dateSelect = document.getElementById('filter-date');
        if (dateSelect && Array.isArray(data.dates)) {
            dateSelect.innerHTML = '';
            data.dates.forEach(d => dateSelect.add(new Option(d, d)));
            if (dateSelect.options.length > 0) {
                dateSelect.options[0].defaultSelected = true;
                filterValues.date = dateSelect.options[0].value;
            }
        }

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
    const dateDisplay = document.getElementById('selected-source-date-display');
    const fyFactorLabel = document.getElementById('fy-factor-label');

    if (!container) return;

    if (tableArea) tableArea.classList.add('opacity-50', 'pointer-events-none');
    if (progressBar) progressBar.classList.remove('hidden');

    try {
        const params = buildRequestParams();
        const headers = await requestHeaders();

        const response = await fetch(`/partial/sales-stock-composition-analysis?${params.toString()}`, { headers });
        const html = await response.text();
        container.innerHTML = html;

        // Parse and update top stat values from metadata
        const statsScript = document.getElementById('partial-stats-data');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent || '{}');
                updateTopStats(stats);
            } catch (parseErr) {
                console.warn('Could not parse partial stats metadata:', parseErr);
            }
        }

        const dateSelect = document.getElementById('filter-date');
        if (dateDisplay && dateSelect) {
            dateDisplay.textContent = dateSelect.value || 'SNAPSHOT';
        }

        // Re-apply search filter if user already typed
        const searchInput = document.getElementById('report-search');
        if (searchInput && searchInput.value) {
            onSearchInput(searchInput.value);
        }
    } catch (err) {
        console.error('Failed to load report data:', err);
        container.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Failed to load data: ${err.message}</div>`;
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

    if (salesWeightEl) {
        salesWeightEl.textContent = (Number(stats.sales_weight || 0)).toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 });
    }
    if (provisionWeightEl) {
        provisionWeightEl.textContent = (Number(stats.provision_weight || 0)).toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 });
    }
    if (turnWeightEl) {
        turnWeightEl.textContent = (Number(stats.turn_weight || 0)).toFixed(2);
    }
    if (turnoverEl) {
        turnoverEl.textContent = (Number(stats.turnover || 0)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (tskPctEl) {
        tskPctEl.textContent = `${(Number(stats.tsk_pct || 0)).toFixed(2)}%`;
    }
    if (fyFactorLabel && stats.factor) {
        fyFactorLabel.textContent = `${stats.fy_label || 'FY'} · Factor: ${Number(stats.factor).toFixed(2)}`;
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
        const params = buildRequestParams();
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

    const dateSelect = document.getElementById('filter-date');
    if (dateSelect && dateSelect.options.length > 0) {
        dateSelect.selectedIndex = 0;
    }

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
