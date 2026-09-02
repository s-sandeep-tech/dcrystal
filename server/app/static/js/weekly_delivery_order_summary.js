let currentZoom = parseFloat(localStorage.getItem('weekly-delivery-zoom')) || 1.0;
let searchTimeout;

const hierarchyRanks = {
    classification: 1,
    make: 2,
    collection: 3,
    purity: 4,
    party: 5
};

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    currentZoom = reset ? 1.0 : Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    tableArea.style.zoom = currentZoom;
    localStorage.setItem('weekly-delivery-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) zoomLevel.textContent = `${Math.round(currentZoom * 100)}%`;
}

async function loadViewData() {
    const activeView = document.getElementById('view-weekly-delivery');
    if (!activeView) return;

    activeView.innerHTML = `
        <div class="flex flex-col items-center justify-center min-h-[350px] text-gray-400 gap-3">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
            <span class="text-xs font-semibold text-gray-500">Loading report data...</span>
        </div>`;

    try {
        const params = new URLSearchParams(window.location.search);
        const response = await fetch(`/partial/weekly-delivery-order-summary?${params.toString()}`, {
            headers: {
                Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`
            }
        });
        if (!response.ok) throw new Error(await response.text());

        activeView.innerHTML = await response.text();
        const metadata = activeView.querySelector('.pagination-meta');
        if (metadata) {
            updatePaginationControls(metadata.dataset);
            updateLevelBadge(metadata.dataset.level);
        }

        const statsElement = activeView.querySelector('#stats-metadata');
        if (statsElement) updateHeaderStats(JSON.parse(statsElement.textContent));
    } catch (error) {
        console.error('Unable to load weekly delivery summary:', error);
        activeView.innerHTML = '<div class="p-8 text-center text-red-500 font-bold">Error loading report data.</div>';
    }
}

function updateHeaderStats(stats) {
    const values = {
        'stat-total-weight': stats.total_weight,
        'stat-hallmark-weight': stats.hallmark_weight,
        'stat-qc-weight': stats.qc_weight,
        'stat-current-week-weight': stats.current_week_weight,
        'stat-party-count': stats.party_count,
        'stat-week-total': stats.week_total
    };
    Object.entries(values).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) element.textContent = value || '0';
    });

    const bars = {
        'stat-total-weight-bar': 100,
        'stat-hallmark-weight-bar': stats.hallmark_percentage,
        'stat-qc-weight-bar': stats.qc_percentage,
        'stat-current-week-weight-bar': stats.current_week_percentage
    };
    Object.entries(bars).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) element.style.width = `${value || 0}%`;
    });
}

function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge) badge.textContent = (level || 'classification').replaceAll('_', ' ').toUpperCase();
}

function updatePaginationControls(metadata) {
    const page = parseInt(metadata.page || '1', 10);
    const perPage = parseInt(metadata.perPage || '50', 10);
    const total = parseInt(metadata.total || '0', 10);
    const start = total ? ((page - 1) * perPage) + 1 : 0;
    const end = Math.min(page * perPage, total);

    const info = document.getElementById('pagination-info');
    if (info) info.textContent = `${start}-${end} of ${total}`;

    const previous = document.getElementById('btn-prev');
    const next = document.getElementById('btn-next');
    if (previous) {
        previous.disabled = metadata.hasPrev !== 'true';
        previous.onclick = previous.disabled ? null : () => changePage(metadata.prevNum);
    }
    if (next) {
        next.disabled = metadata.hasNext !== 'true';
        next.onclick = next.disabled ? null : () => changePage(metadata.nextNum);
    }
}

async function toggleRow(button) {
    const row = button.closest('tr');
    if (!row) return;

    const icon = button.querySelector('.material-symbols-outlined');
    const level = row.dataset.level;
    const isExpanded = icon.textContent.trim() === 'remove_circle';

    if (isExpanded) {
        const parentRank = hierarchyRanks[level] || 0;
        let nextRow = row.nextElementSibling;
        while (nextRow && nextRow.classList.contains('child-row')) {
            const nextRank = hierarchyRanks[nextRow.dataset.level] || 0;
            if (nextRank <= parentRank) break;
            const rowToRemove = nextRow;
            nextRow = nextRow.nextElementSibling;
            rowToRemove.remove();
        }
        icon.textContent = 'add_circle';
        row.classList.remove('bg-blue-50/50');
        return;
    }

    icon.textContent = 'hourglass_empty';
    try {
        const path = JSON.parse(row.dataset.path || '{}');
        const params = new URLSearchParams(window.location.search);
        params.set('parent_level', level);
        params.set('parent_value', path[level] || '');
        params.set('path', JSON.stringify(path));

        const response = await fetch(`/partial/weekly-delivery-order-summary?${params.toString()}`, {
            headers: {
                Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`
            }
        });
        if (!response.ok) throw new Error(await response.text());

        const template = document.createElement('template');
        template.innerHTML = `<table><tbody>${await response.text()}</tbody></table>`;
        let reference = row;
        template.content.querySelectorAll('tr').forEach(child => {
            child.classList.add('child-row', 'animate-fade-in');
            reference.parentNode.insertBefore(child, reference.nextSibling);
            reference = child;
        });
        icon.textContent = 'remove_circle';
        row.classList.add('bg-blue-50/50');
    } catch (error) {
        console.error('Unable to load hierarchy children:', error);
        icon.textContent = 'error';
    }
}

function applyGlobalFilters() {
    const params = new URLSearchParams(window.location.search);
    const filters = {
        classification: 'filter-classification',
        make: 'filter-make',
        collection: 'filter-collection',
        purity: 'filter-purity',
        party: 'filter-party',
        order_type: 'filter-order-type',
        order_request_type: 'filter-order-request-type',
        search: 'hierarchy-search'
    };

    Object.entries(filters).forEach(([parameter, id]) => {
        const value = document.getElementById(id)?.value.trim() || '';
        if (value) params.set(parameter, value);
        else params.delete(parameter);
    });
    params.set('page', '1');
    updateUrlAndLoad(params);
}

function resetGlobalFilters() {
    [
        'filter-classification', 'filter-make', 'filter-collection', 'filter-purity',
        'filter-party', 'filter-order-type', 'filter-order-request-type', 'hierarchy-search'
    ].forEach(id => {
        const element = document.getElementById(id);
        if (element) element.value = '';
    });
    const params = new URLSearchParams();
    params.set('page', '1');
    updateUrlAndLoad(params);
}

function onSearchInput() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(applyGlobalFilters, 400);
}

function changePage(page) {
    const params = new URLSearchParams(window.location.search);
    params.set('page', String(page || 1));
    updateUrlAndLoad(params);
}

function changePerPage(perPage) {
    const params = new URLSearchParams(window.location.search);
    params.set('per_page', perPage);
    params.set('page', '1');
    updateUrlAndLoad(params);
}

function updateUrlAndLoad(params) {
    const url = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({}, '', url);
    loadViewData();
}

window.addEventListener('DOMContentLoaded', () => {
    adjustZoom(0);
    loadViewData();
});
