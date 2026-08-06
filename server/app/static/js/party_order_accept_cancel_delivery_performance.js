let currentZoom = parseFloat(localStorage.getItem('party-order-zoom')) || 1.0;
let currentPage = parseInt(new URLSearchParams(window.location.search).get('page'), 10) || 1;
let totalPages = 1;
let currentSortBy = new URLSearchParams(window.location.search).get('sort_by') || 'party';
let currentSortDir = new URLSearchParams(window.location.search).get('sort_dir') || 'asc';

const reportFilters = {
    party: 'filter-party',
    make: 'filter-make',
    month: 'filter-month',
    order_type: 'filter-order-type',
    provision_type: 'filter-provision-type'
};

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;
    currentZoom = reset ? 1.0 : Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    tableArea.style.zoom = currentZoom;
    localStorage.setItem('party-order-zoom', currentZoom);
    const label = document.getElementById('zoom-level');
    if (label) label.textContent = `${Math.round(currentZoom * 100)}%`;
}

function updateUrlAndLoad(params) {
    const query = params.toString();
    window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
    currentPage = parseInt(params.get('page'), 10) || 1;
    loadViewData();
}

async function loadViewData() {
    const container = document.getElementById('view-party-order');
    if (!container) return;
    const params = new URLSearchParams(window.location.search);
    params.set('page', currentPage.toString());

    try {
        const response = await fetch(`/partial/party-order-accept-cancel-delivery-performance?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) throw new Error(await response.text());
        container.innerHTML = await response.text();
        hydrateReportMetadata(container);
    } catch (error) {
        console.error('Error loading party order report:', error);
        container.innerHTML = '<div class="p-8 text-center text-red-500">Error loading data.</div>';
    }
}

function hydrateReportMetadata(container) {
    const meta = container.querySelector('.pagination-meta');
    if (meta) {
        updatePaginationControls(meta.dataset);
        const badge = document.getElementById('current-level-badge');
        if (badge) badge.textContent = (meta.dataset.level || 'party').toUpperCase();
    }
    const statsNode = container.querySelector('#stats-metadata');
    if (statsNode) {
        try {
            updateHeaderStats(JSON.parse(statsNode.textContent));
        } catch (error) {
            console.error('Unable to parse report statistics:', error);
        }
    }
}

function updateHeaderStats(stats) {
    ['ordered', 'accepted', 'cancelled', 'delivered'].forEach(metric => {
        const weight = document.getElementById(`stat-${metric}-wt`);
        const pieces = document.getElementById(`stat-${metric}-pcs`);
        const bar = document.getElementById(`stat-${metric}-bar`);
        if (weight) weight.textContent = stats[`${metric}_wt`] || '0.000';
        if (pieces) pieces.textContent = `${stats[`${metric}_pcs`] || '0'} Pcs`;
        if (bar) bar.style.width = `${metric === 'ordered' ? 100 : (stats[`${metric}_perc`] || 0)}%`;
    });
}

function updatePaginationControls(meta) {
    currentPage = parseInt(meta.page, 10) || 1;
    totalPages = parseInt(meta.pages, 10) || 1;
    const total = parseInt(meta.total, 10) || 0;
    const perPage = parseInt(meta.perPage, 10) || 50;
    currentSortBy = meta.sortBy || 'party';
    currentSortDir = meta.sortDir || 'asc';
    const start = total ? ((currentPage - 1) * perPage) + 1 : 0;
    const end = Math.min(currentPage * perPage, total);
    const info = document.getElementById('pagination-info');
    const previous = document.getElementById('btn-prev');
    const next = document.getElementById('btn-next');
    if (info) info.textContent = `${start}-${end} of ${total}`;
    if (previous) previous.disabled = currentPage <= 1;
    if (next) next.disabled = currentPage >= totalPages;
}

function handleSort(column) {
    currentSortDir = currentSortBy === column && currentSortDir === 'asc' ? 'desc' : 'asc';
    currentSortBy = column;

    const params = new URLSearchParams(window.location.search);
    params.set('sort_by', currentSortBy);
    params.set('sort_dir', currentSortDir);
    params.set('page', '1');
    updateUrlAndLoad(params);
}

function applyGlobalFilters() {
    const params = new URLSearchParams(window.location.search);
    Object.entries(reportFilters).forEach(([name, id]) => {
        const value = document.getElementById(id)?.value || '';
        if (value) params.set(name, value);
        else params.delete(name);
    });
    const search = document.getElementById('hierarchy-search')?.value.trim() || '';
    if (search) params.set('search', search);
    else params.delete('search');
    params.set('page', '1');
    updateUrlAndLoad(params);
}

function resetGlobalFilters() {
    const params = new URLSearchParams(window.location.search);
    Object.entries(reportFilters).forEach(([name, id]) => {
        const element = document.getElementById(id);
        if (element) element.value = '';
        params.delete(name);
    });
    const search = document.getElementById('hierarchy-search');
    if (search) search.value = '';
    params.delete('search');
    params.set('page', '1');
    updateUrlAndLoad(params);
}

function navigatePage(delta) {
    const target = currentPage + delta;
    if (target < 1 || target > totalPages) return;
    const params = new URLSearchParams(window.location.search);
    params.set('page', target.toString());
    updateUrlAndLoad(params);
}

function changePerPage(value) {
    const params = new URLSearchParams(window.location.search);
    params.set('per_page', value);
    params.set('page', '1');
    updateUrlAndLoad(params);
}

let searchTimeout;
function onSearchInput() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(applyGlobalFilters, 400);
}

function lastGroupRow(firstRow) {
    const groupId = firstRow.dataset.matrixGroup;
    let lastRow = firstRow;
    while (lastRow.nextElementSibling?.dataset.matrixGroup === groupId) {
        lastRow = lastRow.nextElementSibling;
    }
    return lastRow;
}

async function togglePartyOrderRow(button, party) {
    const firstRow = button.closest('tr');
    const icon = button.querySelector('.material-symbols-outlined');
    if (!firstRow || !icon) return;
    const endRow = lastGroupRow(firstRow);

    if (firstRow.classList.contains('expanded')) {
        firstRow.classList.remove('expanded', 'bg-blue-50/50');
        icon.textContent = 'add_circle';
        let sibling = endRow.nextElementSibling;
        while (sibling?.classList.contains('child-row')) {
            const next = sibling.nextElementSibling;
            sibling.remove();
            sibling = next;
        }
        return;
    }

    icon.textContent = 'hourglass_empty';
    const params = new URLSearchParams(window.location.search);
    params.set('is_child_rows', 'true');
    params.set('parent_party', party || '');

    try {
        const response = await fetch(`/partial/party-order-accept-cancel-delivery-performance?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) throw new Error('Failed to load make rows');

        const template = document.createElement('template');
        template.innerHTML = await response.text();
        let insertionPoint = endRow;
        template.content.querySelectorAll('tr').forEach(child => {
            child.classList.add('child-row');
            insertionPoint.parentNode.insertBefore(child, insertionPoint.nextSibling);
            insertionPoint = child;
        });
        firstRow.classList.add('expanded', 'bg-blue-50/50');
        icon.textContent = 'remove_circle';
    } catch (error) {
        console.error('Error fetching make rows:', error);
        icon.textContent = 'error';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    adjustZoom(0);
    const container = document.getElementById('view-party-order');
    if (container) hydrateReportMetadata(container);
});
