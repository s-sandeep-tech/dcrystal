let currentZoom = parseFloat(localStorage.getItem('crystalissues-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('crystalissues-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadReportData() {
    const activeView = document.getElementById('view-crystal-issues');
    if (!activeView) return;

    activeView.innerHTML = `
        <div class="flex flex-col items-center justify-center h-64">
            <div class="inline-block size-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
            <p class="text-[11px] text-gray-400 mt-4 font-bold tracking-widest uppercase">Loading Report...</p>
        </div>
    `;

    const urlParams = new URL(window.location.href).searchParams;
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/crystal_issues?${searchParams}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch view');
        const html = await response.text();

        activeView.innerHTML = html;

        // Update Stats
        const statsScript = activeView.querySelector('#stats-metadata');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent);
                updateDashboardStats(stats);
            } catch (e) {
                console.error('Error parsing stats metadata:', e);
            }
        }

        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
        }

    } catch (error) {
        console.error('Error loading report:', error);
        activeView.innerHTML = `
            <div class="flex flex-col items-center justify-center h-64 text-red-500">
                <span class="material-symbols-outlined text-4xl">error</span>
                <p class="text-[11px] mt-2 font-bold uppercase">Error loading report. Please try again.</p>
            </div>
        `;
    }
}

function updateDashboardStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-total': stats.total,
        'stat-pending': stats.pending,
        'stat-completed': stats.completed
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value !== undefined ? value : '0';
        }
    }

    // Update Progress Bars
    const total = stats.total || 0;

    const completedProgress = document.getElementById('stat-progress');
    if (completedProgress) {
        const percentage = total > 0 ? (stats.completed / total) * 100 : 0;
        completedProgress.style.width = `${percentage}%`;
    }

    const pendingProgress = document.getElementById('stat-pending-progress');
    if (pendingProgress) {
        const percentage = total > 0 ? (stats.pending / total) * 100 : 0;
        pendingProgress.style.width = `${percentage}%`;
    }
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const filters = {
        'office': 'filter-office',
        'user': 'filter-user',
        'status': 'filter-status',
        'reported_from': 'reported-from',
        'reported_to': 'reported-to',
        'completed_from': 'completed-from',
        'completed_to': 'completed-to'
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

    loadReportData();
}

function resetGlobalFilters() {
    const selects = ['filter-office', 'filter-user', 'filter-status'];
    selects.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = "";
    });

    const dates = ['reported-from', 'reported-to', 'completed-from', 'completed-to'];
    dates.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = "";
    });

    const search = document.getElementById('hierarchy-search');
    if (search) search.value = "";

    const urlParams = new URLSearchParams();
    urlParams.set('page', 1);

    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);

    loadReportData();
}

let searchTimeout;
function onSearchInput(value) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        applyGlobalFilters();
    }, 500);
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
    if (infoSpan) {
        infoSpan.textContent = total > 0 ? `${start}-${end} of ${total}` : '0-0 of 0';
    }

    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');

    if (btnPrev) {
        btnPrev.disabled = !hasPrev;
        if (hasPrev) {
            btnPrev.classList.remove('opacity-50', 'cursor-not-allowed');
            btnPrev.classList.add('cursor-pointer');
            btnPrev.onclick = () => changePage(prevNum);
        } else {
            btnPrev.classList.add('opacity-50', 'cursor-not-allowed');
            btnPrev.classList.remove('cursor-pointer');
            btnPrev.onclick = null;
        }
    }

    if (btnNext) {
        btnNext.disabled = !hasNext;
        if (hasNext) {
            btnNext.classList.remove('opacity-50', 'cursor-not-allowed');
            btnNext.classList.add('cursor-pointer');
            btnNext.onclick = () => changePage(nextNum);
        } else {
            btnNext.classList.add('opacity-50', 'cursor-not-allowed');
            btnNext.classList.remove('cursor-pointer');
            btnNext.onclick = null;
        }
    }

    const select = document.getElementById('per-page-select');
    if (select) select.value = perPage;
}

// Tree-Grid Toggle Action
async function toggleRow(btn, level, value, parentOffice = null) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
        // Collapse: Hide all children
        let nextTr = tr.nextElementSibling;
        while (nextTr) {
            const nextLevel = nextTr.dataset.level;

            // If we are expanding office, stop if next is office
            if (level === 'office' && nextLevel === 'office') break;
            // If we are expanding user, stop if next is office or user
            if (level === 'user' && (nextLevel === 'user' || nextLevel === 'office')) break;

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
            const urlParams = new URL(window.location.href).searchParams;
            const params = new URLSearchParams();

            // Carry over filters
            ['search', 'office', 'user', 'status', 'reported_from', 'reported_to', 'completed_from', 'completed_to'].forEach(k => {
                if (urlParams.get(k)) params.set(k, urlParams.get(k));
            });

            params.set('parent_level', level);
            params.set('parent_value', value);
            if (parentOffice) params.set('parent_office', parentOffice);

            const response = await fetch(`/partial/crystal_issues?${params.toString()}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });

            if (!response.ok) throw new Error("Failed to load children");
            const html = await response.text();

            // Insert HTML after current row
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
            tr.classList.add('bg-blue-50/50');

        } catch (e) {
            console.error(e);
            icon.textContent = 'error';
        }
    }
}

function changePage(page) {
    if (!page) return;
    const urlParams = new URL(window.location.href).searchParams;
    urlParams.set('page', page);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadReportData();
}

function changePerPage(perPage) {
    if (!perPage) return;
    const urlParams = new URL(window.location.href).searchParams;
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadReportData();
}

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    loadReportData();
    loadFilterOptions();

    const perPageSelect = document.getElementById('per-page-select');
    if (perPageSelect) {
        perPageSelect.addEventListener('change', (e) => changePerPage(e.target.value));
    }
});

let globalOptionsLoaded = false;
async function loadFilterOptions() {
    if (globalOptionsLoaded) return;

    try {
        const response = await fetch('/api/crystal_issues/options', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch options');
        const options = await response.json();

        const populateSelect = (id, opts, label) => {
            const el = document.getElementById(id);
            if (!el) return;
            let html = `<option value="">${label}</option>`;
            opts.forEach(opt => {
                html += `<option value="${opt}">${opt}</option>`;
            });
            el.innerHTML = html;
        };

        populateSelect('filter-office', options.offices, 'All Offices');
        populateSelect('filter-user', options.users, 'All Users');
        populateSelect('filter-status', options.statuses, 'All Statuses');

        globalOptionsLoaded = true;
    } catch (error) {
        console.error('Error loading filter options:', error);
    }
}

window.onpopstate = function () {
    loadReportData();
};
