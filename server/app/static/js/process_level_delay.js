let currentZoom = parseFloat(localStorage.getItem('processleveldelay-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('processleveldelay-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-process-delay');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/processleveldelay?${searchParams}`, {
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

        // Parse stats
        const statsScript = activeView.querySelector('#stats-metadata');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent);
                updateDashboardStats(stats);
            } catch (e) {
                console.error('Error parsing stats metadata:', e);
            }
        }

        // Parse pagination
        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
        }

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    }
}

function updateDashboardStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-total-qty': stats.total_qty,
        'stat-1-2-days': stats.total_1_2,
        'stat-2-4-days': stats.total_2_4,
        'stat-5-10-days': stats.total_5_10,
        'stat-more-10-days': stats.total_more_10
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value !== undefined ? value.toLocaleString() : '0';
        }
    }
}

function updatePaginationControls(meta) {
    const page = parseInt(meta.page);
    const perPage = parseInt(meta.perPage);
    const total = parseInt(meta.total);
    const hasPrev = meta.hasPrev === 'true';
    const hasNext = meta.hasNext === 'true';

    const start = total > 0 ? (page - 1) * perPage + 1 : 0;
    const end = Math.min(page * perPage, total);
    const infoSpan = document.getElementById('pagination-info');
    if (infoSpan) {
        infoSpan.textContent = total > 0 ? `${start}-${end} of ${total}` : '0-0 of 0';
    }

    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    if (btnPrev) {
        btnPrev.disabled = !hasPrev;
        btnPrev.onclick = hasPrev ? () => changePage(parseInt(meta.prevNum)) : null;
    }
    if (btnNext) {
        btnNext.disabled = !hasNext;
        btnNext.onclick = hasNext ? () => changePage(parseInt(meta.nextNum)) : null;
    }

    const perPageSelect = document.getElementById('per-page-select');
    if (perPageSelect) {
        perPageSelect.value = perPage;
    }
}

function changePage(page) {
    if (!page) return;
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    updateUrlAndLoad(urlParams);
}

function changePerPage(perPage) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

async function loadFilterOptions() {
    try {
        const response = await fetch('/api/processleveldelay/options', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const options = await response.json();

        populateSelect('filter-party', options.party_names, 'All Parties');
        populateSelect('filter-completed', options.completed_processes, 'All Processes');
        populateSelect('filter-next', options.next_processes, 'All Processes');

        // Restore filter values from URL
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('party_name')) document.getElementById('filter-party').value = urlParams.get('party_name');
        if (urlParams.get('completed_process')) document.getElementById('filter-completed').value = urlParams.get('completed_process');
        if (urlParams.get('next_process')) document.getElementById('filter-next').value = urlParams.get('next_process');

    } catch (e) {
        console.error('Error loading options:', e);
    }
}

function populateSelect(id, list, placeholder) {
    const el = document.getElementById(id);
    if (!el) return;
    let html = `<option value="">${placeholder}</option>`;
    list.forEach(item => {
        html += `<option value="${item}">${item}</option>`;
    });
    el.innerHTML = html;
}

function applyFilters() {
    const party = document.getElementById('filter-party').value;
    const completed = document.getElementById('filter-completed').value;
    const next = document.getElementById('filter-next').value;
    const searchVal = document.getElementById('hierarchy-search')?.value;

    const urlParams = new URLSearchParams(window.location.search);
    if (party) urlParams.set('party_name', party); else urlParams.delete('party_name');
    if (completed) urlParams.set('completed_process', completed); else urlParams.delete('completed_process');
    if (next) urlParams.set('next_process', next); else urlParams.delete('next_process');
    if (searchVal) urlParams.set('party_name', searchVal); // Using party_name for search as well for now

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetFilters() {
    const urlParams = new URLSearchParams();
    updateUrlAndLoad(urlParams);

    document.getElementById('filter-party').value = '';
    document.getElementById('filter-completed').value = '';
    document.getElementById('filter-next').value = '';
    if (document.getElementById('hierarchy-search')) document.getElementById('hierarchy-search').value = '';
}

function onSearchInput(value) {
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
        applyFilters();
    }, 500);
}

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }

    // Sync UI from URL
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('party_name')) {
        const hSearch = document.getElementById('hierarchy-search');
        if (hSearch) hSearch.value = urlParams.get('party_name');
    }

    loadViewData();
    loadFilterOptions();
});
