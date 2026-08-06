let currentZoom = parseFloat(localStorage.getItem('party-design-zoom')) || 1.0;
let currentPage = parseInt(new URLSearchParams(window.location.search).get('page'), 10) || 1;
let totalPages = 1;
let currentSortBy = new URLSearchParams(window.location.search).get('sort_by') || 'hierarchy';
let currentSortDir = new URLSearchParams(window.location.search).get('sort_dir') || 'asc';

const partyDesignFilters = {
    party: 'filter-party',
    make_owner: 'filter-make-owner',
    make: 'filter-make',
    classification: 'filter-classification',
    sub_classification: 'filter-sub-classification',
    order_type: 'filter-order-type',
    provision_type: 'filter-provision-type'
};

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    currentZoom = reset ? 1.0 : Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    tableArea.style.zoom = currentZoom;
    localStorage.setItem('party-design-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) zoomLevel.textContent = `${Math.round(currentZoom * 100)}%`;
}

function updateUrlAndLoad(params) {
    const query = params.toString();
    window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
    currentPage = parseInt(params.get('page'), 10) || 1;
    loadViewData();
}

async function loadViewData() {
    const activeView = document.getElementById('view-party-design');
    if (!activeView) return;

    const params = new URLSearchParams(window.location.search);
    params.set('page', currentPage);

    try {
        const response = await fetch(`/partial/party-design-delivery-performance?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) throw new Error(await response.text());

        activeView.innerHTML = await response.text();
        hydrateReportMetadata(activeView);
    } catch (error) {
        console.error('Error loading party design report:', error);
        activeView.innerHTML = '<div class="p-8 text-center text-red-500">Error loading data.</div>';
    }
}

function hydrateReportMetadata(container) {
    const meta = container.querySelector('.pagination-meta');
    if (meta) {
        updatePaginationControls(meta.dataset);
        updateLevelBadge(meta.dataset.level);
    }

    const statsScript = container.querySelector('#stats-metadata');
    if (statsScript) {
        try {
            updateHeaderStats(JSON.parse(statsScript.textContent));
        } catch (error) {
            console.error('Unable to parse report statistics:', error);
        }
    }
}

function updateHeaderStats(stats) {
    const totalParties = document.getElementById('stat-total-parties');
    const totalMakes = document.getElementById('stat-total-makes');
    const averageDays = document.getElementById('stat-avg-delivery-days');
    if (totalParties) totalParties.textContent = stats.total_parties || '0';
    if (totalMakes) totalMakes.textContent = stats.total_makes || '0';
    if (averageDays) averageDays.textContent = `${stats.avg_delivery_days || '0.0'} Days`;
}

function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge) badge.textContent = (level || 'party').replace(/_/g, ' ').toUpperCase();
}

function updatePaginationControls(meta) {
    currentPage = parseInt(meta.page, 10) || 1;
    totalPages = parseInt(meta.pages, 10) || 1;
    const total = parseInt(meta.total, 10) || 0;
    const perPage = parseInt(meta.perPage, 10) || 50;
    currentSortBy = meta.sortBy || 'hierarchy';
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

    Object.entries(partyDesignFilters).forEach(([name, id]) => {
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
    Object.entries(partyDesignFilters).forEach(([name, id]) => {
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
    const targetPage = currentPage + delta;
    if (targetPage < 1 || targetPage > totalPages) return;
    const params = new URLSearchParams(window.location.search);
    params.set('page', targetPage.toString());
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

async function togglePartyDesignRow(button, level, party, make, classification) {
    const row = button.closest('tr');
    const icon = button.querySelector('.material-symbols-outlined');
    if (!row || !icon) return;

    if (row.classList.contains('expanded')) {
        row.classList.remove('expanded', 'bg-blue-50/50');
        icon.textContent = 'add_circle';
        let sibling = row.nextElementSibling;
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
    params.set('parent_make', make || '');
    params.set('parent_classification', classification || '');
    params.set('target_level', level === 'party' ? 'make' : (level === 'make' ? 'classification' : 'sub_classification'));

    try {
        const response = await fetch(`/partial/party-design-delivery-performance?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) throw new Error('Failed to load child rows');

        const template = document.createElement('template');
        template.innerHTML = await response.text();
        let insertionPoint = row;
        template.content.querySelectorAll('tr').forEach(child => {
            child.classList.add('child-row', 'animate-fade-in');
            insertionPoint.parentNode.insertBefore(child, insertionPoint.nextSibling);
            insertionPoint = child;
        });

        row.classList.add('expanded', 'bg-blue-50/50');
        icon.textContent = 'remove_circle';
    } catch (error) {
        console.error('Error fetching child rows:', error);
        icon.textContent = 'error';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    adjustZoom(0);
    const view = document.getElementById('view-party-design');
    if (view) hydrateReportMetadata(view);
});
