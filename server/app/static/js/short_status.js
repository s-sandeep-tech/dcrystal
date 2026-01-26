let currentZoom = parseFloat(localStorage.getItem('shortstatus-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('shortstatus-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadReportData() {
    const mainMain = document.getElementById('shortstatus-main');
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (mainMain) mainMain.classList.add('loading');

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/shortstatus/partial?${searchParams}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch report');
        const html = await response.text();

        tableArea.innerHTML = html;

        // Parse stats metadata
        const statsScript = tableArea.querySelector('#stats-metadata');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent);
                updateHeaderStats(stats);
            } catch (e) {
                console.error('Error parsing stats metadata:', e);
            }
        }

    } catch (error) {
        console.error('Error loading report:', error);
        tableArea.innerHTML = `
            <div class="flex flex-col items-center justify-center h-64 text-red-500">
                <span class="material-symbols-outlined text-4xl">error</span>
                <p class="text-[11px] mt-2 font-bold uppercase">Error loading report. Please try again.</p>
            </div>
        `;
    } finally {
        if (mainMain) mainMain.classList.remove('loading');
    }
}

function updateHeaderStats(stats) {
    if (!stats) return;
    const mappings = {
        'stat-total-items': stats.total_items,
        'stat-total-weight': stats.total_weight,
        'stat-unique-products': stats.unique_products,
        'stat-avg-weight': stats.avg_weight
    };
    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) el.textContent = value || '0';
    }
}

function applyFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const filters = {
        'division': 'filter-division',
        'group': 'filter-group',
        'purity': 'filter-purity',
        'classification': 'filter-classification',
        'section': 'filter-section',
        'product_type': 'filter-product-type'
    };

    for (const [key, id] of Object.entries(filters)) {
        const val = document.getElementById(id)?.value;
        if (val) urlParams.set(key, val);
        else urlParams.delete(key);
    }

    const searchVal = document.getElementById('shortstatus-search')?.value;
    if (searchVal) urlParams.set('search', searchVal);
    else urlParams.delete('search');

    const perPage = document.getElementById('per-page-select')?.value;
    if (perPage) urlParams.set('per_page', perPage);

    urlParams.set('page', 1);

    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    loadReportData();
}

function resetFilters() {
    const filters = [
        'filter-division', 'filter-group', 'filter-purity',
        'filter-classification', 'filter-section', 'filter-product-type',
        'shortstatus-search'
    ];
    filters.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = "";
    });

    const newUrl = window.location.pathname;
    window.history.pushState({ path: newUrl }, '', newUrl);

    loadReportData();
}

function changePage(page) {
    if (!page) return;
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    loadReportData();
}

let searchTimeout;
function onSearchInput(value) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        applyFilters();
    }, 500);
}

document.addEventListener('DOMContentLoaded', () => {
    // Sync UI from URL
    const urlParams = new URLSearchParams(window.location.search);
    const filters = {
        'division': 'filter-division',
        'group': 'filter-group',
        'purity': 'filter-purity',
        'classification': 'filter-classification',
        'section': 'filter-section',
        'product_type': 'filter-product-type',
        'search': 'shortstatus-search'
    };
    for (const [key, id] of Object.entries(filters)) {
        const val = urlParams.get(key);
        if (val) {
            const el = document.getElementById(id);
            if (el) el.value = val;
        }
    }

    loadReportData();
});
