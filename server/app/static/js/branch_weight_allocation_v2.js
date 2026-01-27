let currentZoom = parseFloat(localStorage.getItem('branchweightv2-zoom')) || 1.0;
let chartInstance = null;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('branchweightv2-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-branch');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/branchv2?${searchParams}`, {
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

        // Parse pagination & Level
        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
            updateLevelBadge(metaDiv.dataset.level);
        }

        // Parse chart data
        const chartScript = activeView.querySelector('#chart-data');
        if (chartScript) {
            try {
                const chartData = JSON.parse(chartScript.textContent);
                updateChart(chartData);
            } catch (e) {
                console.error('Error parsing chart data:', e);
            }
        }

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    }
}

function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge) {
        badge.textContent = level || 'ZONE';
    }
}

function updateDashboardStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-stock-weight': stats.stock_weight,
        'stat-stock-pieces': stats.stock_pieces,
        'stat-provision-weight': stats.provision_weight,
        'stat-provision-pieces': stats.provision_pieces,
        'stat-short-weight': stats.short_weight,
        'stat-short-pieces': stats.short_pieces,
        'stat-max-allocate': stats.max_allocate,
        'stat-max-refill': stats.max_refill
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            if (id.includes('pieces')) el.textContent = value + ' pcs';
            else el.textContent = value !== undefined ? parseFloat(value).toFixed(3) : '0.000';
        }
    }
}

// Tree-Grid Toggle Action
async function toggleRow(btn, level, value, grandparentValue = null) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        // Collapse: Hide all children
        // We find all rows that are children of this row based on hierarchy
        // A simple way is to look for next siblings until we hit a row of the same level or higher

        let nextTr = tr.nextElementSibling;
        while (nextTr) {
            // If we encounter a row that is NOT a child (same level or higher up), stop
            // But how do we know? We can mark rows with 'data-level'.
            // Zone > State > Location.
            const nextLevel = nextTr.dataset.level;

            // If we are expanding Zone (level=zone), stop if next is Zone.
            // If we are expanding State (level=state), stop if next is State or Zone.

            if (level === 'zone' && nextLevel === 'zone') break;
            if (level === 'state' && (nextLevel === 'state' || nextLevel === 'zone')) break;

            // Remove or Hide? Re-fetching is safer for data consistency but hiding is faster.
            // For now, let's remove them to keep state simple.
            const toRemove = nextTr;
            nextTr = nextTr.nextElementSibling;
            toRemove.remove();
        }
        icon.textContent = 'add_circle';
        tr.classList.remove('bg-blue-50/50');
    } else {
        // Expand: Fetch children
        icon.textContent = 'hourglass_empty'; // Loading state

        try {
            const urlParams = new URLSearchParams(window.location.search);
            // Keep search params but add parent info
            const params = new URLSearchParams(urlParams);
            params.set('parent_level', level);
            params.set('parent_value', value);
            if (grandparentValue) params.set('grandparent_value', grandparentValue);

            const response = await fetch(`/partial/branchv2?${params.toString()}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });

            if (!response.ok) throw new Error("Failed to load children");
            const html = await response.text();

            // Insert HTML after current row
            // The HTML returns TRs.
            const template = document.createElement('template');
            template.innerHTML = html;
            const newRows = template.content.querySelectorAll('tr');

            // We need to reverse insert so order is preserved when inserting after
            let referenceNode = tr;
            newRows.forEach(newRow => {
                // Mark as child for styling if needed
                newRow.classList.add('child-row');
                newRow.classList.add('animate-fade-in'); // Add animation class if exists
                referenceNode.parentNode.insertBefore(newRow, referenceNode.nextSibling);
                referenceNode = newRow;
            });

            icon.textContent = 'remove_circle';
            tr.classList.add('bg-blue-50/50');

        } catch (e) {
            console.error(e);
            icon.textContent = 'error';
        }
    }
}



function onZoneChange(val) {
    const urlParams = new URLSearchParams(window.location.search);
    if (val) urlParams.set('zone', val);
    else urlParams.delete('zone');

    urlParams.delete('state');
    urlParams.delete('location');
    urlParams.set('page', 1);

    updateUrlAndLoad(urlParams);
    loadFilterOptions(); // Refresh dependent options
}

function onStateChange(val) {
    const urlParams = new URLSearchParams(window.location.search);
    if (val) urlParams.set('state', val);
    else urlParams.delete('state');

    urlParams.delete('location');
    urlParams.set('page', 1);

    updateUrlAndLoad(urlParams);
    loadFilterOptions(); // Refresh dependent options
}

function onLocationChange(val) {
    const urlParams = new URLSearchParams(window.location.search);
    if (val) urlParams.set('location', val);
    else urlParams.delete('location');
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetDrillDown() {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.delete('zone');
    urlParams.delete('state');
    urlParams.delete('location');
    urlParams.set('page', 1);

    document.getElementById('filter-zone').value = '';
    document.getElementById('filter-state').value = '';
    document.getElementById('filter-location').value = '';

    updateUrlAndLoad(urlParams);
    loadFilterOptions();
}

function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    const bh = document.getElementById('filter-business-head')?.value;
    if (bh) urlParams.set('business_head', bh);
    else urlParams.delete('business_head');

    const searchVal = document.getElementById('hierarchy-search')?.value;
    if (searchVal) urlParams.set('search', searchVal);
    else urlParams.delete('search');

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.delete('business_head');
    urlParams.delete('search');
    urlParams.delete('zone');
    urlParams.delete('state');
    urlParams.delete('location');

    const bh = document.getElementById('filter-business-head');
    if (bh) bh.value = '';
    const search = document.getElementById('hierarchy-search');
    if (search) search.value = '';

    document.getElementById('filter-zone').value = '';
    document.getElementById('filter-state').value = '';
    document.getElementById('filter-location').value = '';

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
    loadFilterOptions(); // Reload options after reset to ensure all options are available
}

function onSearchInput(value) {
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
        applyGlobalFilters();
    }, 500);
}

function updatePaginationControls(meta) {
    const page = parseInt(meta.page);
    const perPage = parseInt(meta.perPage);
    const total = parseInt(meta.total);
    const hasPrev = meta.hasPrev === 'true';
    const hasNext = meta.hasNext === 'true';

    const start = (page - 1) * perPage + 1;
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

async function loadFilterOptions() {
    const urlParams = new URLSearchParams(window.location.search);
    const zone = urlParams.get('zone') || '';
    const state = urlParams.get('state') || '';

    try {
        const response = await fetch(`/api/branchweightv2/options?zone=${zone}&state=${state}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const options = await response.json();

        populateSelect('filter-zone', options.zones, 'All Zones', urlParams.get('zone'));
        populateSelect('filter-state', options.states, 'All States', urlParams.get('state'));
        populateSelect('filter-location', options.locations, 'All Locations', urlParams.get('location'));
        populateSelect('filter-business-head', options.business_heads, 'All Business Heads', urlParams.get('business_head'));

    } catch (e) {
        console.error('Error loading options:', e);
    }
}

function populateSelect(id, list, placeholder, selectedValue) {
    const el = document.getElementById(id);
    if (!el) return;
    let html = `<option value="">${placeholder}</option>`;
    list.forEach(item => {
        html += `<option value="${item}" ${item === selectedValue ? 'selected' : ''}>${item}</option>`;
    });
    el.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    // Sync UI from URL
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('search')) document.getElementById('hierarchy-search').value = urlParams.get('search');

    // Initial Load only if not already loaded (though browser might cache)
    // We call loadViewData anyway to ensure fresh data
    loadViewData();
    loadFilterOptions();
});

function initChart() {
    const ctx = document.getElementById('weightVsRefillChart');
    if (!ctx) return;

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Max Alloc Wt',
                    data: [],
                    backgroundColor: 'rgba(16, 185, 129, 0.8)', // emerald-500
                    borderColor: 'rgba(16, 185, 129, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Max Refill Weight',
                    data: [],
                    backgroundColor: 'rgba(79, 70, 229, 0.8)', // indigo-600
                    borderColor: 'rgba(79, 70, 229, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        boxWidth: 8
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        autoSkip: true,
                        maxRotation: 0,
                        maxTicksLimit: 20
                    }
                }
            }
        }
    });
}

function updateChart(data) {
    if (!chartInstance) initChart();
    if (!chartInstance) return;

    if (!data || data.length === 0) {
        chartInstance.data.labels = [];
        chartInstance.data.datasets[0].data = [];
        chartInstance.data.datasets[1].data = [];
        chartInstance.update();
        return;
    }

    // Limit to top 20 or so to avoid clutter, or show all if reasonable
    const displayData = data.slice(0, 30);

    const labels = displayData.map(r => {
        if (r.level === 'zone') return r.zone;
        if (r.level === 'state') return r.state;
        return r.location;
    });

    const allocData = displayData.map(r => r.max_allocate || 0);
    const refillData = displayData.map(r => r.max_refill || 0);

    chartInstance.data.labels = labels;
    chartInstance.data.datasets[0].data = allocData;
    chartInstance.data.datasets[1].data = refillData;
    chartInstance.update();
}
