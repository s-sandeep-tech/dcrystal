let currentZoom = parseFloat(localStorage.getItem('party-location-zoom')) || 1.0;
let currentPage = parseInt(new URLSearchParams(window.location.search).get('page'), 10) || 1;
let totalPages = 1;
let currentSortBy = new URLSearchParams(window.location.search).get('sort_by') || 'hierarchy';
let currentSortDir = new URLSearchParams(window.location.search).get('sort_dir') || 'asc';

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('party-location-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

function toggleFilterDrawer() {
    const drawer = document.getElementById('filter-drawer');
    const overlay = document.getElementById('filter-drawer-overlay');
    if (drawer && overlay) {
        drawer.classList.toggle('translate-x-full');
        overlay.classList.toggle('hidden');
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-party-location');
    if (!activeView) return;

    const searchParams = buildQueryParams();

    try {
        const response = await fetch(`/partial/party-design-location-allocation?${searchParams}`, {
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
        activeView.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Error loading data. ${error.message}</div>`;
    }
}

function updateHeaderStats(stats) {
    if (!stats) return;
    const deliveredWeightEl = document.getElementById('stat-delivered-weight');
    if (deliveredWeightEl) deliveredWeightEl.textContent = stats.delivered_weight || '0.000';
}

function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge && level) {
        badge.textContent = level.replace(/_/g, ' ');
    }
}

function updatePaginationControls(meta) {
    if (!meta) return;
    currentPage = parseInt(meta.page) || 1;
    totalPages = parseInt(meta.pages) || 1;
    const total = parseInt(meta.total) || 0;
    const perPage = parseInt(meta.perPage) || 50;
    currentSortBy = meta.sortBy || 'hierarchy';
    currentSortDir = meta.sortDir || 'asc';

    const start = total === 0 ? 0 : (currentPage - 1) * perPage + 1;
    const end = Math.min(currentPage * perPage, total);

    const info = document.getElementById('pagination-info');
    if (info) info.textContent = `${start}-${end} of ${total}`;

    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    if (btnPrev) btnPrev.disabled = currentPage <= 1;
    if (btnNext) btnNext.disabled = currentPage >= totalPages;
}

function handleSort(column) {
    currentSortDir = currentSortBy === column && currentSortDir === 'asc' ? 'desc' : 'asc';
    currentSortBy = column;
    currentPage = 1;
    loadViewData();
}

function buildQueryParams() {
    const params = new URLSearchParams();
    params.set('page', currentPage);
    params.set('sort_by', currentSortBy);
    params.set('sort_dir', currentSortDir);

    const perPageSelect = document.getElementById('per-page-select');
    if (perPageSelect) params.set('per_page', perPageSelect.value);

    const searchInput = document.getElementById('hierarchy-search');
    if (searchInput && searchInput.value.trim()) params.set('search', searchInput.value.trim());

    const filterIds = [
        ['filter-party', 'party'],
        ['filter-make', 'make'],
        ['filter-zone', 'zone'],
        ['filter-order-type', 'order_type'],
        ['filter-provision-type', 'provision_type']
    ];

    for (const [id, param] of filterIds) {
        const el = document.getElementById(id);
        if (el && el.value) {
            params.set(param, el.value);
        }
    }
    return params.toString();
}

function applyFilters() {
    currentPage = 1;
    loadViewData();
}


function resetAllFilters() {
    const filterIds = ['filter-party', 'filter-make', 'filter-zone', 'filter-order-type', 'filter-provision-type'];
    for (const id of filterIds) {
        const el = document.getElementById(id);
        if (el) el.value = '';
    }
    const searchInput = document.getElementById('hierarchy-search');
    if (searchInput) searchInput.value = '';

    currentPage = 1;
    loadViewData();
}

function navigatePage(delta) {
    const newPage = currentPage + delta;
    if (newPage >= 1 && newPage <= totalPages) {
        currentPage = newPage;
        loadViewData();
    }
}

function changePerPage(value) {
    currentPage = 1;
    loadViewData();
}

let searchTimeout;
function onSearchInput(val) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        currentPage = 1;
        loadViewData();
    }, 400);
}

const hierarchyDepth = {
    party: 0,
    zone: 1,
    make: 2
};

function removeDescendantRows(row) {
    const currentDepth = hierarchyDepth[row.dataset.level];
    if (currentDepth === undefined) return;

    let nextRow = row.nextElementSibling;
    while (nextRow) {
        const nextDepth = hierarchyDepth[nextRow.dataset.level];
        if (nextDepth === undefined || nextDepth <= currentDepth) break;
        const rowToRemove = nextRow;
        nextRow = nextRow.nextElementSibling;
        rowToRemove.remove();
    }
}

async function togglePartyLocationRow(btn, level, party, zone) {
    const icon = btn.querySelector('.material-symbols-outlined');
    const tr = btn.closest('tr');
    const tableBody = tr.parentNode;

    if (tr.classList.contains('expanded')) {
        tr.classList.remove('expanded');
        if (icon) icon.textContent = 'add_circle';

        removeDescendantRows(tr);
        return;
    }

    tr.classList.add('expanded');
    if (icon) icon.textContent = 'remove_circle';

    const params = new URLSearchParams(buildQueryParams());
    params.set('is_child_rows', 'true');
    params.set('parent_party', party || '');
    params.set('parent_zone', zone || '');

    if (level === 'party') {
        params.set('target_level', 'zone');
    } else if (level === 'zone') {
        params.set('target_level', 'make');
    }

    try {
        const response = await fetch(`/partial/party-design-location-allocation?${params.toString()}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to load child rows');
        const html = await response.text();

        const tempDiv = document.createElement('tbody');
        tempDiv.innerHTML = html;

        const childRows = Array.from(tempDiv.querySelectorAll('tr'));
        let insertAfter = tr;
        childRows.forEach(row => {
            row.classList.add('child-row', 'bg-gray-50/50');
            insertAfter.parentNode.insertBefore(row, insertAfter.nextSibling);
            insertAfter = row;
        });

    } catch (e) {
        console.error('Error fetching child rows:', e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    adjustZoom(0);
    const activeView = document.getElementById('view-party-location');
    if (activeView) {
        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
            updateLevelBadge(metaDiv.dataset.level);
        }
    }
});
