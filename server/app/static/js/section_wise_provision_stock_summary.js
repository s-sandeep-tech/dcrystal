let currentSearch = '';
let filterValues = {
    division: 'Gold',
    location: '',
    purity: '',
    classification: '',
    make: '',
    collection: '',
    section: '',
    prov_type: '',
    provision_mode: '',
    branch_type: '',
    branch_status: '',
    business_head: '',
    state: '',
    sort_by: '',
    sort_order: 'none'
};

let locationMultiSelect;
let stateMultiSelect;
let branchTypeMultiSelect;
let branchStatusMultiSelect;
let makeMultiSelect;
let collectionMultiSelect;
let sectionMultiSelect;
let currentZoom = 1.0;

function toggleSectionFilters() {
    const sidebar = document.getElementById('section-filter-sidebar');
    const button = document.getElementById('section-filter-toggle');
    if (!sidebar || !button) return;
    const hidden = sidebar.style.display !== 'none';
    sidebar.style.display = hidden ? 'none' : '';
    button.setAttribute('aria-expanded', String(!hidden));
    const label = hidden ? 'Show filters' : 'Hide filters';
    button.setAttribute('aria-label', label);
    button.title = label;
}
window.toggleSectionFilters = toggleSectionFilters;

document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('division')) {
        filterValues.division = urlParams.get('division');
        const divSelect = document.getElementById('filter-division');
        if (divSelect) divSelect.value = filterValues.division;
    }

    locationMultiSelect = new CustomMultiSelect({
        containerId: 'filter-location-container',
        label: 'Location',
        defaultText: 'All Locations',
        options: []
    });

    branchStatusMultiSelect = new CustomMultiSelect({
        containerId: 'filter-branch-status-container',
        label: 'Branch Status',
        defaultText: 'All Branch Statuses',
        options: []
    });

    branchTypeMultiSelect = new CustomMultiSelect({
        containerId: 'filter-branch-type-container',
        label: 'Branch Type',
        defaultText: 'All Branch Types',
        options: []
    });

    stateMultiSelect = new CustomMultiSelect({
        containerId: 'filter-state-container',
        label: 'State',
        defaultText: 'All States',
        options: []
    });

    sectionMultiSelect = new CustomMultiSelect({
        containerId: 'filter-section-container',
        label: 'Section',
        defaultText: 'All Sections',
        options: []
    });

    makeMultiSelect = new CustomMultiSelect({
        containerId: 'filter-make-container',
        label: 'Make',
        defaultText: 'All Makes',
        options: [],
        onSearch: async (query, callback) => {
            try {
                const divParam = encodeURIComponent(filterValues.division || '');
                const response = await fetch(`/api/section-wise-provision-stock-summary/makes/search?q=${encodeURIComponent(query)}&division=${divParam}`, {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
                });
                const data = await response.json();
                callback(data);
            } catch (err) {
                console.error('Make search failed:', err);
                callback([]);
            }
        }
    });

    collectionMultiSelect = new CustomMultiSelect({
        containerId: 'filter-collection-container',
        label: 'Collection',
        defaultText: 'All Collections',
        options: [],
        onSearch: async (query, callback) => {
            try {
                const divParam = encodeURIComponent(filterValues.division || '');
                const response = await fetch(`/api/section-wise-provision-stock-summary/collections/search?q=${encodeURIComponent(query)}&division=${divParam}`, {
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
                });
                const data = await response.json();
                callback(data);
            } catch (err) {
                console.error('Collection search failed:', err);
                callback([]);
            }
        }
    });

    loadOptions();
    loadReport();

    // Reset export cooldown flag when export completes
    if (window.socket) {
        window.socket.on('new_notification', function (data) {
            if (data.title && data.title.includes('Section-wise Provision and Stock Summary')) {
                localStorage.removeItem('last_section_wise_provision_stock_export_time');
            }
        });
    }
});

async function loadOptions() {
    try {
        const response = await fetch('/api/section-wise-provision-stock-summary/options', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const data = await response.json();

        const config = [
            { id: 'filter-purity', data: data.purities },
            { id: 'filter-classification', data: data.classifications },
            { id: 'filter-prov-type', data: data.prov_types },
            { id: 'filter-provision-mode', data: data.provision_modes },
            { id: 'filter-business-head', data: data.business_heads }
        ];

        if (locationMultiSelect) locationMultiSelect.populateOptions(data.locations);
        if (branchStatusMultiSelect) branchStatusMultiSelect.populateOptions(data.branch_statuses);
        if (branchTypeMultiSelect) branchTypeMultiSelect.populateOptions(data.branch_types);
        if (stateMultiSelect) stateMultiSelect.populateOptions(data.states);
        if (sectionMultiSelect) sectionMultiSelect.populateOptions(data.sections);

        config.forEach(item => {
            const select = document.getElementById(item.id);
            if (select && item.data) {
                // Clear existing except first
                while (select.options.length > 1) {
                    select.remove(1);
                }
                item.data.forEach(opt => {
                    const el = document.createElement('option');
                    el.value = opt;
                    el.textContent = opt;
                    select.appendChild(el);
                });
            }
        });

        if (data.divisions) {
            const divSelect = document.getElementById('filter-division');
            if (divSelect) {
                const currentVal = divSelect.value || filterValues.division || 'Gold';
                divSelect.innerHTML = '<option value="">All Divisions</option>';
                data.divisions.forEach(opt => {
                    const el = document.createElement('option');
                    el.value = opt;
                    el.textContent = opt;
                    if (opt.toLowerCase() === currentVal.toLowerCase()) {
                        el.selected = true;
                    }
                    divSelect.appendChild(el);
                });
                if (divSelect.value) {
                    filterValues.division = divSelect.value;
                }
            }
        }
    } catch (err) {
        console.error('Failed to load filter options:', err);
    }
}

async function loadReport() {
    const tableArea = document.getElementById('view-section-wise-provision-stock-summary');
    const mainContainer = document.getElementById('table-area');
    const reportLoader = document.getElementById('report-loader');
    const applyBtn = document.getElementById('btn-apply-filters');
    if (!tableArea) return;

    mainContainer.classList.add('opacity-75', 'pointer-events-none');
    if (reportLoader) reportLoader.classList.remove('hidden');
    if (applyBtn) applyBtn.disabled = true;

    try {
        const params = new URLSearchParams({
            ...filterValues
        });

        const response = await fetch(`/partial/section-wise-provision-stock-summary?${params}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const html = await response.text();
        tableArea.innerHTML = html;

        // Apply search filter if active
        if (currentSearch) {
            applyClientSearch(currentSearch);
        }
    } catch (err) {
        console.error('Failed to load report:', err);
        tableArea.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Failed to load data: ${err.message}</div>`;
    } finally {
        mainContainer.classList.remove('opacity-75', 'pointer-events-none');
        if (reportLoader) reportLoader.classList.add('hidden');
        if (applyBtn) applyBtn.disabled = false;
    }
}

function applyFilters() {
    filterValues.division = document.getElementById('filter-division')?.value || '';
    filterValues.business_head = document.getElementById('filter-business-head')?.value || '';
    filterValues.purity = document.getElementById('filter-purity')?.value || '';
    filterValues.classification = document.getElementById('filter-classification')?.value || '';
    filterValues.prov_type = document.getElementById('filter-prov-type')?.value || '';
    filterValues.provision_mode = document.getElementById('filter-provision-mode')?.value || '';

    if (locationMultiSelect) filterValues.location = locationMultiSelect.getValues().join(',');
    if (branchStatusMultiSelect) filterValues.branch_status = branchStatusMultiSelect.getValues().join(',');
    if (branchTypeMultiSelect) filterValues.branch_type = branchTypeMultiSelect.getValues().join(',');
    if (stateMultiSelect) filterValues.state = stateMultiSelect.getValues().join(',');
    if (sectionMultiSelect) filterValues.section = sectionMultiSelect.getValues().join(',');
    if (makeMultiSelect) filterValues.make = makeMultiSelect.getValues().join(',');
    if (collectionMultiSelect) filterValues.collection = collectionMultiSelect.getValues().join(',');

    loadReport();
}

function resetFilters() {
    const divSelect = document.getElementById('filter-division');
    if (divSelect) divSelect.value = 'Gold';
    filterValues.division = 'Gold';

    ['filter-business-head', 'filter-purity', 'filter-classification', 'filter-prov-type', 'filter-provision-mode'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    if (locationMultiSelect) locationMultiSelect.clear();
    if (branchStatusMultiSelect) branchStatusMultiSelect.clear();
    if (branchTypeMultiSelect) branchTypeMultiSelect.clear();
    if (stateMultiSelect) stateMultiSelect.clear();
    if (sectionMultiSelect) sectionMultiSelect.clear();
    if (makeMultiSelect) makeMultiSelect.clear();
    if (collectionMultiSelect) collectionMultiSelect.clear();

    const searchInput = document.getElementById('report-search');
    if (searchInput) searchInput.value = '';
    currentSearch = '';

    applyFilters();
}

/* ==========================================================================
   Tree Hierarchical Expand / Collapse Logic
   ========================================================================== */

function toggleSectionTreeNode(buttonEl, event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    const currentRow = buttonEl.closest('tr[data-tree-row]');
    if (!currentRow) return;

    const nodeId = currentRow.dataset.nodeId;
    if (!nodeId) return;

    const iconSpan = buttonEl.querySelector('.material-symbols-outlined');
    const isExpanded = iconSpan ? iconSpan.textContent.trim() === 'arrow_drop_down' : false;

    if (isExpanded) {
        // Collapse
        if (iconSpan) iconSpan.textContent = 'arrow_right';
        collapseSectionChildren(currentRow.parentElement, nodeId);
    } else {
        // Expand direct children
        if (iconSpan) iconSpan.textContent = 'arrow_drop_down';
        expandSectionDirectChildren(currentRow.parentElement, nodeId);
    }
}
window.toggleSectionTreeNode = toggleSectionTreeNode;

function expandSectionDirectChildren(tbody, parentId) {
    if (!tbody || !parentId) return;
    const directChildren = tbody.querySelectorAll(`tr[data-tree-row][data-parent-id="${parentId}"]`);
    directChildren.forEach(row => {
        row.classList.remove('hidden');
    });
}

function collapseSectionChildren(tbody, parentId) {
    if (!tbody || !parentId) return;
    const directChildren = tbody.querySelectorAll(`tr[data-tree-row][data-parent-id="${parentId}"]`);
    directChildren.forEach(row => {
        row.classList.add('hidden');
        const childNodeId = row.dataset.nodeId;
        const iconSpan = row.querySelector('[data-tree-toggle] .material-symbols-outlined');
        if (iconSpan) iconSpan.textContent = 'arrow_right';
        if (childNodeId) {
            collapseSectionChildren(tbody, childNodeId);
        }
    });
}

function toggleAllSectionTree(buttonEl, event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const table = document.getElementById('sectionWiseProvisionStockTable');
    if (!table) return;

    const isExpanded = buttonEl.dataset.expanded === 'true';
    const newExpanded = !isExpanded;
    buttonEl.dataset.expanded = String(newExpanded);

    const rows = table.querySelectorAll('tbody tr[data-tree-row]');
    rows.forEach(row => {
        const level = Number(row.dataset.level || 1);
        if (newExpanded) {
            row.classList.remove('hidden');
        } else {
            row.classList.toggle('hidden', level > 1);
        }
    });

    const icons = table.querySelectorAll('[data-tree-toggle] .material-symbols-outlined');
    icons.forEach(icon => {
        icon.textContent = newExpanded ? 'arrow_drop_down' : 'arrow_right';
    });

    const btnIcon = buttonEl.querySelector('.material-symbols-outlined');
    if (btnIcon) {
        btnIcon.textContent = newExpanded ? 'unfold_less' : 'unfold_more';
    }
    buttonEl.title = newExpanded ? 'Collapse all hierarchy levels' : 'Expand all hierarchy levels';
}
window.toggleAllSectionTree = toggleAllSectionTree;

/* ==========================================================================
   Client-side Search / Filter
   ========================================================================== */

function onSearchInput(val) {
    currentSearch = (val || '').trim().toLowerCase();
    clearTimeout(window.sectionSearchTimeout);
    window.sectionSearchTimeout = setTimeout(() => {
        applyClientSearch(currentSearch);
    }, 250);
}
window.onSearchInput = onSearchInput;

function applyClientSearch(searchStr) {
    const table = document.getElementById('sectionWiseProvisionStockTable');
    if (!table) return;

    const rows = Array.from(table.querySelectorAll('tbody tr[data-tree-row]'));
    if (!searchStr) {
        // Reset to initial collapsed state (level 1 visible, others hidden)
        rows.forEach(row => {
            const level = Number(row.dataset.level || 1);
            row.classList.toggle('hidden', level > 1);
            const icon = row.querySelector('[data-tree-toggle] .material-symbols-outlined');
            if (icon) icon.textContent = 'arrow_right';
        });
        const toggleAllBtn = document.getElementById('btn-toggle-all-tree');
        if (toggleAllBtn) {
            toggleAllBtn.dataset.expanded = 'false';
            const btnIcon = toggleAllBtn.querySelector('.material-symbols-outlined');
            if (btnIcon) btnIcon.textContent = 'unfold_more';
        }
        return;
    }

    // Match rows and propagate visibility upwards to parents
    const matchingNodeIds = new Set();
    const rowsByNodeId = new Map();
    const parentMap = new Map();

    rows.forEach(row => {
        const nodeId = row.dataset.nodeId;
        const parentId = row.dataset.parentId;
        rowsByNodeId.set(nodeId, row);
        if (parentId) parentMap.set(nodeId, parentId);

        const textContent = (row.querySelector('td:first-child')?.textContent || '').toLowerCase();
        if (textContent.includes(searchStr)) {
            matchingNodeIds.add(nodeId);
        }
    });

    // Expand all ancestor nodes of matching rows
    const visibleNodeIds = new Set(matchingNodeIds);
    matchingNodeIds.forEach(nodeId => {
        let curr = nodeId;
        while (parentMap.has(curr)) {
            const p = parentMap.get(curr);
            if (p) {
                visibleNodeIds.add(p);
                curr = p;
            } else {
                break;
            }
        }
    });

    rows.forEach(row => {
        const nodeId = row.dataset.nodeId;
        const isVisible = visibleNodeIds.has(nodeId);
        row.classList.toggle('hidden', !isVisible);

        const icon = row.querySelector('[data-tree-toggle] .material-symbols-outlined');
        if (icon && isVisible) {
            icon.textContent = 'arrow_drop_down';
        }
    });
}

/* ==========================================================================
   Zoom Controls
   ========================================================================== */

function adjustZoom(delta, reset = false) {
    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.6), 1.5);
    }
    const table = document.getElementById('sectionWiseProvisionStockTable');
    if (table) {
        table.style.transform = `scale(${currentZoom})`;
        table.style.transformOrigin = 'top left';
    }
    const zoomLabel = document.getElementById('zoom-level');
    if (zoomLabel) {
        zoomLabel.textContent = `${Math.round(currentZoom * 100)}%`;
    }
}
window.adjustZoom = adjustZoom;

/* ==========================================================================
   Export to Excel
   ========================================================================== */

async function exportToExcel() {
    const btn = document.getElementById('btn-export-excel');
    const label = document.getElementById('export-btn-label');
    const icon = document.getElementById('export-btn-icon');

    if (btn) btn.disabled = true;
    if (label) label.textContent = 'Queuing...';
    if (icon) icon.textContent = 'hourglass_top';

    try {
        const response = await fetch('/api/section-wise-provision-stock-summary/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({
                filters: filterValues,
                socket_id: window.socket ? window.socket.id : null
            })
        });

        const data = await response.json();
        if (response.ok && data.status === 'success') {
            if (window.showToast) {
                window.showToast('Export job queued! You will receive a notification when ready.', 'success');
            } else {
                alert('Export job queued! You will receive a notification when ready.');
            }
        } else {
            throw new Error(data.message || 'Export failed to enqueue.');
        }
    } catch (err) {
        console.error('Export error:', err);
        alert(`Failed to queue export: ${err.message}`);
    } finally {
        if (btn) btn.disabled = false;
        if (label) label.textContent = 'Export';
        if (icon) icon.textContent = 'download';
    }
}
window.exportToExcel = exportToExcel;

