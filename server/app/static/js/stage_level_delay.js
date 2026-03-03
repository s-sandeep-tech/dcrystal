let currentZoom = parseFloat(localStorage.getItem('stageleveldelay-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('stageleveldelay-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-delay');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/stageleveldelay?${searchParams}`, {
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

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    }
}

function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge) {
        badge.textContent = (level || 'classification_owner').replace(/_/g, ' ').toUpperCase();
    }
}

function updateDashboardStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-tw1': stats.tw1,
        'stat-tw2': stats.tw2,
        'stat-tw3': stats.tw3,
        'stat-tw4': stats.tw4
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value || 0;
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
        let nextTr = tr.nextElementSibling;
        while (nextTr) {
            const nextLevel = nextTr.dataset.level;

            if (level === 'classification_owner' && nextLevel === 'classification_owner') break;
            if (level === 'make_owner' && (nextLevel === 'make_owner' || nextLevel === 'classification_owner')) break;

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
            const params = new URLSearchParams(urlParams);
            params.set('parent_level', level);
            params.set('parent_value', value);
            if (grandparentValue) params.set('grandparent_value', grandparentValue);

            const response = await fetch(`/partial/stageleveldelay?${params.toString()}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });

            if (!response.ok) throw new Error("Failed to load children");
            const html = await response.text();

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

function onSearchInput(value) {
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
        applyFilters();
    }, 500);
}

function applyFilters() {
    const params = new URLSearchParams(window.location.search);
    const party = document.getElementById('filter-party')?.value;
    const completed = document.getElementById('filter-completed')?.value;
    const next = document.getElementById('filter-next')?.value;
    const search = document.getElementById('hierarchy-search')?.value;

    if (party) params.set('party', party); else params.delete('party');
    if (completed) params.set('completed_process', completed); else params.delete('completed_process');
    if (next) params.set('next_process', next); else params.delete('next_process');
    if (search) params.set('search', search); else params.delete('search');

    params.set('page', 1);
    updateUrlAndLoad(params);
}

function resetFilters() {
    const params = new URLSearchParams(window.location.search);
    params.delete('party');
    params.delete('completed_process');
    params.delete('next_process');
    params.delete('search');
    params.delete('page');

    document.getElementById('filter-party').value = '';
    document.getElementById('filter-completed').value = '';
    document.getElementById('filter-next').value = '';
    document.getElementById('hierarchy-search').value = '';

    updateUrlAndLoad(params);
    loadOptions();
}

function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
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

function changePage(p) {
    if (!p) return;
    const params = new URLSearchParams(window.location.search);
    params.set('page', p);
    updateUrlAndLoad(params);
}

function changePerPage(perPage) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

async function loadOptions() {
    try {
        const response = await fetch('/api/stageleveldelay/options', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const options = await response.json();

        populateSelect('filter-party', options.parties, 'party');
        populateSelect('filter-completed', options.completed_processes, 'completed_process');
        populateSelect('filter-next', options.next_processes, 'next_process');
    } catch (e) {
        console.error(e);
    }
}

function populateSelect(id, list, paramName) {
    const el = document.getElementById(id);
    if (!el) return;
    const currentVal = new URLSearchParams(window.location.search).get(paramName);
    let html = `<option value="">All</option>`;
    list.forEach(v => {
        html += `<option value="${v}" ${v === currentVal ? 'selected' : ''}>${v}</option>`;
    });
    el.innerHTML = html;
}

async function showDetails(classOwner, makeOwner, collOwner) {
    const modal = document.getElementById('detailsModal');
    const tableBody = document.getElementById('modalTableBody');
    const title = document.getElementById('modalTitle');
    const subtitle = document.getElementById('modalSubtitle');

    modal.classList.remove('hidden');
    tableBody.innerHTML = '<tr><td colspan="12" class="text-center py-8">Loading...</td></tr>';
    title.textContent = `Details: ${collOwner}`;
    subtitle.textContent = `${classOwner} > ${makeOwner}`;

    try {
        const response = await fetch(`/api/stageleveldelay/details?classification_owner=${encodeURIComponent(classOwner)}&make_owner=${encodeURIComponent(makeOwner)}&collection_owner=${encodeURIComponent(collOwner)}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const details = await response.json();

        let html = '';
        details.forEach(d => {
            html += `
                <tr class="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                    <td class="px-3 py-2">${d.division || '-'}</td>
                    <td class="px-3 py-2">${d.group || '-'}</td>
                    <td class="px-3 py-2">${d.purity || '-'}</td>
                    <td class="px-3 py-2">${d.purchase_ro || '-'}</td>
                    <td class="px-3 py-2 font-medium">${d.order_number || '-'}</td>
                    <td class="px-3 py-2 text-gray-500">${d.order_date || '-'}</td>
                    <td class="px-3 py-2">${d.barcode_number || '-'}</td>
                    <td class="px-3 py-2 text-gray-500">${d.barcode_last_step_date || '-'}</td>
                    <td class="px-3 py-2 text-center ${d.time_window_1_2_days > 0 ? 'bg-blue-50 text-blue-600 font-bold' : 'text-gray-300'}">${d.time_window_1_2_days || ''}</td>
                    <td class="px-3 py-2 text-center ${d.time_window_3_4_days > 0 ? 'bg-orange-50 text-orange-600 font-bold' : 'text-gray-300'}">${d.time_window_3_4_days || ''}</td>
                    <td class="px-3 py-2 text-center ${d.time_window_5_10_days > 0 ? 'bg-pink-50 text-pink-600 font-bold' : 'text-gray-300'}">${d.time_window_5_10_days || ''}</td>
                    <td class="px-3 py-2 text-center ${d.time_window_more_than_10_days > 0 ? 'bg-red-50 text-red-600 font-bold' : 'text-gray-300'}">${d.time_window_more_than_10_days || ''}</td>
                </tr>
            `;
        });
        tableBody.innerHTML = html || '<tr><td colspan="12" class="text-center py-8">No specific details found.</td></tr>';
    } catch (e) {
        console.error(e);
        tableBody.innerHTML = '<tr><td colspan="12" class="text-center py-8 text-red-500">Error loading details.</td></tr>';
    }
}

function closeDetails() {
    document.getElementById('detailsModal').classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
    adjustZoom(0);
    loadViewData();
    loadOptions();
});
