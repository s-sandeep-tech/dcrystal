let currentPage = 1;
let perPage = 2000;
let currentSearch = '';
let currentLocation = '';

document.addEventListener('DOMContentLoaded', () => {
    loadOptions();
    loadReport();

    // Pagination Listeners
    document.getElementById('btn-prev').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadReport();
        }
    });

    document.getElementById('btn-next').addEventListener('click', () => {
        currentPage++;
        loadReport();
    });
});

async function loadOptions() {
    try {
        const response = await fetch('/api/provision-allocation/options', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const data = await response.json();

        const locationSelect = document.getElementById('filter-location');
        data.locations.forEach(loc => {
            const opt = document.createElement('option');
            opt.value = loc;
            opt.textContent = loc;
            locationSelect.appendChild(opt);
        });
    } catch (err) {
        console.error('Failed to load filter options:', err);
    }
}

async function loadReport() {
    const tableArea = document.getElementById('view-provision-allocation');
    tableArea.classList.add('opacity-50', 'pointer-events-none');

    try {
        const params = new URLSearchParams({
            page: currentPage,
            per_page: perPage,
            search: currentSearch,
            location: currentLocation
        });

        const response = await fetch(`/partial/provision-allocation?${params}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const html = await response.text();
        tableArea.innerHTML = html;

        // Re-execute scripts in the partial
        const scripts = tableArea.getElementsByTagName('script');
        for (let i = 0; i < scripts.length; i++) {
            eval(scripts[i].innerText);
        }
    } catch (err) {
        console.error('Failed to load report:', err);
        tableArea.innerHTML = `<div class="p-8 text-center text-red-500 font-bold">Failed to load data.</div>`;
    } finally {
        tableArea.classList.remove('opacity-50', 'pointer-events-none');
    }
}

function onSearchInput(val) {
    currentSearch = val;
    currentPage = 1;
    // Debounce search?
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => loadReport(), 300);
}

function applyFilters() {
    currentLocation = document.getElementById('filter-location').value;
    currentPage = 1;
    loadReport();
}

function resetFilters() {
    document.getElementById('filter-location').value = '';
    document.getElementById('report-search').value = '';
    currentLocation = '';
    currentSearch = '';
    currentPage = 1;
    loadReport();
}

function changePerPage(val) {
    perPage = parseInt(val);
    currentPage = 1;
    loadReport();
}

function adjustZoom(delta, reset = false) {
    const main = document.getElementById('provision-allocation-main');
    let currentZoom = parseFloat(main.getAttribute('data-zoom') || '1');

    if (reset) currentZoom = 1;
    else currentZoom += delta;

    currentZoom = Math.max(0.7, Math.min(1.5, currentZoom));
    main.style.zoom = currentZoom;
    main.setAttribute('data-zoom', currentZoom);
    document.getElementById('zoom-level').textContent = `${Math.round(currentZoom * 100)}%`;
}
