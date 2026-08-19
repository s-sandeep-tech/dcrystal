let currentZoom = parseFloat(localStorage.getItem('oldgold-zoom')) || 1.0;
let searchTimeout;
const oldGoldMultiSelects = {};

function initializeMultiSelectFilters() {
    if (typeof CustomMultiSelect === 'undefined') return;

    const options = window.OLD_GOLD_FILTER_OPTIONS || {};
    const definitions = {
        office: ['Office', 'All Offices', options.offices || []],
        location: ['Location', 'All Locations', options.locations || []],
        division: ['Division', 'All Divisions', options.divisions || []],
        purity: ['Purity', 'All Purities', options.purities || []]
    };
    const urlParams = new URLSearchParams(window.location.search);

    Object.entries(definitions).forEach(([key, [label, defaultText, values]]) => {
        const containerId = `filter-${key}-container`;
        if (!document.getElementById(containerId)) return;

        const instance = new CustomMultiSelect({
            containerId,
            label,
            defaultText,
            options: values.map(value => ({ value: String(value), label: String(value) }))
        });
        oldGoldMultiSelects[key] = instance;

        const selectedValues = new Set(
            (urlParams.get(key) || '').split(',').map(value => value.trim()).filter(Boolean)
        );
        document.querySelectorAll(`.${containerId}-checkbox`).forEach(checkbox => {
            checkbox.checked = selectedValues.has(checkbox.value);
        });
        instance.updateTriggerText();
    });
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
    localStorage.setItem('oldgold-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-oldgold');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/location-wise-old-gold-settlement-transfer?${searchParams}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`
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
    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Error loading data: ${error.message}</div>`;
    }
}

function updateHeaderStats(stats) {
    if (!stats) return;
    const textMappings = {
        'stat-total-grwt': stats.total_grwt,
        'stat-grwt-2-5': stats.grwt_2_5,
        'stat-grwt-6-10': stats.grwt_6_10,
        'stat-grwt-11-15': stats.grwt_11_15,
        'stat-grwt-gt-15': stats.grwt_gt_15,
        'stat-transfer-grwt': stats.transfer_grwt,
    };

    for (const [id, value] of Object.entries(textMappings)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value || '0.000';
        }
    }

    function formatSubNetSt(net, st) {
        const hasSt = st && parseFloat(st) > 0;
        return hasSt ? `Net: ${net || '0.000'} | St: ${st}` : `Net: ${net || '0.000'}`;
    }

    const subTextMappings = {
        'stat-total-netwt': formatSubNetSt(stats.total_netwt, stats.total_stwt),
        'stat-netwt-2-5': formatSubNetSt(stats.netwt_2_5, stats.stwt_2_5),
        'stat-netwt-6-10': formatSubNetSt(stats.netwt_6_10, stats.stwt_6_10),
        'stat-netwt-11-15': formatSubNetSt(stats.netwt_11_15, stats.stwt_11_15),
        'stat-netwt-gt-15': formatSubNetSt(stats.netwt_gt_15, stats.stwt_gt_15),
        'stat-transfer-netwt': formatSubNetSt(stats.transfer_netwt, stats.transfer_stwt),
    };

    for (const [id, value] of Object.entries(subTextMappings)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
        }
    }

    const transSubMappings = {
        'stat-trans-2-5': stats.transfer_grwt_2_5,
        'stat-trans-6-10': stats.transfer_grwt_6_10,
        'stat-trans-11-15': stats.transfer_grwt_11_15,
        'stat-trans-gt-15': stats.transfer_grwt_gt_15,
    };

    for (const [id, transVal] of Object.entries(transSubMappings)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = `Tr: ${transVal || '0.000'}`;
        }
    }

    const barMappings = {
        'stat-bar-2-5': stats.perc_2_5,
        'stat-bar-6-10': stats.perc_6_10,
        'stat-bar-11-15': stats.perc_11_15,
        'stat-bar-gt-15': stats.perc_gt_15,
        'stat-transfer-bar': stats.transfer_perc,
    };

    for (const [id, perc] of Object.entries(barMappings)) {
        const el = document.getElementById(id);
        if (el) el.style.width = (perc || 0) + '%';
    }
}

function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge) {
        badge.textContent = level ? level.replace('_', ' ').toUpperCase() : 'OFFICE';
    }
}

function updatePaginationControls(meta) {
    const info = document.getElementById('pagination-info');
    const prevBtn = document.getElementById('btn-prev');
    const nextBtn = document.getElementById('btn-next');

    if (!meta || !info) return;

    const page = parseInt(meta.page) || 1;
    const perPage = parseInt(meta.perPage) || 50;
    const total = parseInt(meta.total) || 0;
    const pages = parseInt(meta.pages) || 1;

    const start = total === 0 ? 0 : (page - 1) * perPage + 1;
    const end = Math.min(page * perPage, total);

    info.textContent = `${start}-${end} of ${total}`;

    if (prevBtn) prevBtn.disabled = page <= 1;
    if (nextBtn) nextBtn.disabled = page >= pages;
}

function navigatePage(direction) {
    const urlParams = new URLSearchParams(window.location.search);
    const currentPage = parseInt(urlParams.get('page') || '1');
    const targetPage = Math.max(1, currentPage + direction);
    urlParams.set('page', targetPage);
    updateUrlAndLoad(urlParams);
}

function changePerPage(perPage) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

// Tree-Grid Toggle Action for Multi-Level Hierarchy
async function toggleRow(btn, level, value, officeVal = '', locationVal = '', divisionVal = '') {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        // Collapse all descendents
        const currentLevelRank = getLevelRank(level);
        let nextTr = tr.nextElementSibling;
        while (nextTr && nextTr.classList.contains('child-row')) {
            const nextLevel = nextTr.dataset.level;
            const nextRank = getLevelRank(nextLevel);
            if (nextRank <= currentLevelRank) break;

            const toRemove = nextTr;
            nextTr = nextTr.nextElementSibling;
            toRemove.remove();
        }
        icon.textContent = 'add_circle';
        tr.classList.remove('bg-blue-50/50', 'dark:bg-blue-900/20');
    } else {
        icon.textContent = 'hourglass_empty';

        try {
            const urlParams = new URLSearchParams(window.location.search);
            urlParams.set('parent_level', level);
            urlParams.set('parent_value', value);
            if (officeVal) urlParams.set('office_val', officeVal);
            if (locationVal) urlParams.set('location_val', locationVal);
            if (divisionVal) urlParams.set('division_val', divisionVal);

            const response = await fetch(`/partial/location-wise-old-gold-settlement-transfer?${urlParams.toString()}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`
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
            tr.classList.add('bg-blue-50/50', 'dark:bg-blue-900/20');
        } catch (e) {
            console.error(e);
            icon.textContent = 'error';
        }
    }
}

function getLevelRank(levelName) {
    const ranks = {
        'office': 1,
        'locationname': 2,
        'division': 3,
        'groupname': 4,
        'purity': 5
    };
    return ranks[levelName] || 0;
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const filterMappings = {
        'group': 'filter-group',
        'search': 'hierarchy-search',
        'from_date': 'filter-from-date',
        'to_date': 'filter-to-date',
        'enable_date_filter': 'enable-date-filter'
    };

    for (const [param, id] of Object.entries(filterMappings)) {
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

    ['office', 'location', 'division', 'purity'].forEach(param => {
        const value = oldGoldMultiSelects[param]?.getValues().join(',') || '';
        if (value) {
            urlParams.set(param, value);
        } else {
            urlParams.delete(param);
        }
    });

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const inputs = [
        'filter-group', 'hierarchy-search',
        'filter-from-date', 'filter-to-date'
    ];

    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    Object.values(oldGoldMultiSelects).forEach(instance => instance.reset());

    const dateCheckbox = document.getElementById('enable-date-filter');
    if (dateCheckbox) dateCheckbox.checked = false;
    toggleDateInputs();

    const urlParams = new URLSearchParams();
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function toggleDateInputs() {
    const checkbox = document.getElementById('enable-date-filter');
    const container = document.getElementById('date-inputs');
    if (!checkbox || !container) return;

    if (checkbox.checked) {
        container.classList.remove('opacity-50', 'pointer-events-none');
    } else {
        container.classList.add('opacity-50', 'pointer-events-none');
    }
}

function onSearchInput(val) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        const urlParams = new URLSearchParams(window.location.search);
        if (val.trim()) {
            urlParams.set('search', val.trim());
        } else {
            urlParams.delete('search');
        }
        urlParams.set('page', 1);
        updateUrlAndLoad(urlParams);
    }, 400);
}

function updateUrlAndLoad(urlParams) {
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({}, '', newUrl);
    loadViewData();
}

function handleSort(column) {
    const urlParams = new URLSearchParams(window.location.search);
    const currentSort = urlParams.get('sort_by') || 'hierarchy';
    const currentOrder = urlParams.get('sort_order') || 'asc';

    let newOrder = 'asc';
    if (currentSort === column) {
        newOrder = currentOrder === 'asc' ? 'desc' : 'asc';
    }

    urlParams.set('sort_by', column);
    urlParams.set('sort_order', newOrder);
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function initPaginationFromDOM() {
    const metaDiv = document.querySelector('.pagination-meta');
    if (metaDiv) {
        updatePaginationControls(metaDiv.dataset);
        updateLevelBadge(metaDiv.dataset.level);
    }
}

window.addEventListener('DOMContentLoaded', () => {
    initializeMultiSelectFilters();
    adjustZoom(0, false);
    loadViewData();
});
