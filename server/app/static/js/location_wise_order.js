function toggleRow(id) {
    const children = document.querySelectorAll('.child-' + id);
    const icon = document.getElementById('icon-' + id);
    if (children.length > 0) {
        const isHidden = children[0].classList.contains('hidden');
        children.forEach(row => {
            if (isHidden) row.classList.remove('hidden');
            else row.classList.add('hidden');
        });
        if (icon) icon.textContent = isHidden ? 'expand_more' : 'chevron_right';
    }
}

let currentZoom = parseFloat(localStorage.getItem('locationstatus-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;
    if (reset) currentZoom = 1.0;
    else currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    tableArea.style.zoom = currentZoom;
    localStorage.setItem('locationstatus-zoom', currentZoom);
    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
}

async function loadViewData() {
    const activeView = document.getElementById('view-location-wise');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/locationwiseorderstatus/partial?${searchParams}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) throw new Error('Failed to fetch view');
        const html = await response.text();
        activeView.innerHTML = html;

        const statsScript = activeView.querySelector('#stats-metadata');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent);
                updateDashboardStats(stats);
            } catch (e) { console.error('Error parsing stats:', e); }
        }

        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) updatePaginationControls(metaDiv.dataset);

        activeView.querySelectorAll('tr[class*="child-"]').forEach(row => row.classList.add('hidden'));
    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="flex flex-col items-center justify-center h-64 text-red-500">
            <span class="material-symbols-outlined text-4xl">error</span>
            <p class="text-[11px] mt-2 font-bold uppercase">Error loading view. Please try again.</p>
        </div>`;
    }
}

function updateDashboardStats(stats) {
    if (!stats) return;
    const mappings = {
        'stat-total-orders': stats.total_orders,
        'stat-dispatched': stats.dispatched,
        'stat-in-process': stats.in_process,
        'stat-delayed': stats.delayed,
        'stat-sla-index': stats.sla_index,
        'stat-fulfillment-text': stats.fulfillment
    };
    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) el.textContent = value || '0';
    }
    const bar = document.getElementById('stat-fulfillment-bar');
    if (bar) bar.style.width = stats.fulfillment || '0%';
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    const filters = {
        'location': 'filter-location',
        'division': 'filter-division', 'group': 'filter-group', 'purity': 'filter-purity',
        'classification': 'filter-classification', 'make': 'filter-make', 'collection': 'filter-collection',
        'make_owner': 'filter-make-owner', 'collection_owner': 'filter-collection-owner',
        'classification_owner': 'filter-classification-owner', 'business_head': 'filter-business-head'
    };
    for (const [key, id] of Object.entries(filters)) {
        const val = document.getElementById(id)?.value;
        if (val) urlParams.set(key, val);
        else urlParams.delete(key);
    }
    const searchVal = document.getElementById('hierarchy-search')?.value;
    if (searchVal) urlParams.set('search', searchVal);
    else urlParams.delete('search');

    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

function resetGlobalFilters() {
    const selects = [
        'filter-location',
        'filter-division', 'filter-group', 'filter-purity', 'filter-classification',
        'filter-make', 'filter-collection', 'filter-make-owner', 'filter-collection-owner',
        'filter-classification-owner', 'filter-business-head'
    ];
    selects.forEach(id => { const el = document.getElementById(id); if (el) el.value = ""; });
    const search = document.getElementById('hierarchy-search');
    if (search) search.value = "";

    const urlParams = new URL(window.location.href).searchParams;
    const keys = ['location', 'division', 'group', 'purity', 'classification', 'make', 'collection', 'search', 'make_owner', 'collection_owner', 'classification_owner', 'business_head'];
    keys.forEach(k => urlParams.delete(k));
    urlParams.set('page', 1);

    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

let searchTimeout;
function onSearchInput(value) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => applyGlobalFilters(), 500);
}

function updatePaginationControls(meta) {
    const page = parseInt(meta.page);
    const perPage = parseInt(meta.perPage);
    const total = parseInt(meta.total);
    const hasPrev = meta.hasPrev === 'true';
    const hasNext = meta.hasNext === 'true';
    const prevNum = meta.prevNum;
    const nextNum = meta.nextNum;

    const start = (page - 1) * perPage + 1;
    const end = Math.min(page * perPage, total);
    const infoSpan = document.getElementById('pagination-info');
    if (infoSpan) infoSpan.textContent = total > 0 ? `${start}-${end} of ${total}` : '0-0 of 0';

    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    if (btnPrev) {
        btnPrev.disabled = !hasPrev;
        btnPrev.onclick = hasPrev ? () => changePage(prevNum) : null;
        btnPrev.classList.toggle('opacity-50', !hasPrev);
        btnPrev.classList.toggle('cursor-not-allowed', !hasPrev);
    }
    if (btnNext) {
        btnNext.disabled = !hasNext;
        btnNext.onclick = hasNext ? () => changePage(nextNum) : null;
        btnNext.classList.toggle('opacity-50', !hasNext);
        btnNext.classList.toggle('cursor-not-allowed', !hasNext);
    }
    const select = document.getElementById('per-page-select');
    if (select) select.value = perPage;
}

function changePage(page) {
    if (!page) return;
    const urlParams = new URL(window.location.href).searchParams;
    urlParams.set('page', page);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

function changePerPage(perPage) {
    if (!perPage) return;
    const urlParams = new URL(window.location.href).searchParams;
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

let filterOptionsLoaded = false;
async function loadFilterOptions() {
    if (filterOptionsLoaded) return;
    const filters = {
        'locations': 'filter-location',
        'divisions': 'filter-division', 'groups': 'filter-group', 'purities': 'filter-purity',
        'classifications': 'filter-classification', 'makes': 'filter-make', 'collections': 'filter-collection',
        'make_owners': 'filter-make-owner', 'collection_owners': 'filter-collection-owner',
        'classification_owners': 'filter-classification-owner', 'business_heads': 'filter-business-head'
    };
    Object.values(filters).forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.dataset.pendingValue = el.value; el.innerHTML = `<option value="">Loading...</option>`; el.disabled = true; }
    });

    try {
        const response = await fetch('/api/locationwiseorderstatus/options', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) throw new Error('Failed to fetch options');
        const options = await response.json();
        const mapping = {
            'locations': 'All Locations',
            'divisions': 'All Divisions', 'groups': 'All Groups', 'purities': 'All Purities',
            'classifications': 'All Classifications', 'makes': 'All Makes', 'collections': 'All Collections',
            'make_owners': 'All Make Owners', 'collection_owners': 'All Collection Owners',
            'classification_owners': 'All Class-Owners', 'business_heads': 'All Business Heads'
        };
        for (const [key, id] of Object.entries(filters)) {
            const el = document.getElementById(id);
            if (el && options[key]) {
                const pendingValue = el.dataset.pendingValue;
                let html = `<option value="">${mapping[key]}</option>`;
                options[key].forEach(opt => { html += `<option value="${opt}" ${opt === pendingValue ? 'selected' : ''}>${opt}</option>`; });
                el.innerHTML = html;
                el.disabled = false;
            }
        }
        filterOptionsLoaded = true;
    } catch (error) { console.error('Error loading filters:', error); Object.values(filters).forEach(id => { const el = document.getElementById(id); if (el) el.disabled = false; }); }
}

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;
    loadViewData();

    // Lazy load filters on focus
    const filterIds = [
        'filter-location',
        'filter-division', 'filter-group', 'filter-purity', 'filter-classification',
        'filter-make', 'filter-collection', 'filter-make-owner', 'filter-collection-owner',
        'filter-classification-owner', 'filter-business-head'
    ];
    filterIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('focus', () => loadFilterOptions(), { once: true });
    });
});
