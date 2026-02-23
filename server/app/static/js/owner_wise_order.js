let currentZoom = parseFloat(localStorage.getItem('ownerwise-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('ownerwise-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-ownerwise');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/ownerwise?${searchParams}`, {
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

        // Parse pagination & Level & Stats
        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) {
            updatePaginationControls(metaDiv.dataset);
            updateLevelBadge(metaDiv.dataset.level);
        }

        const statsScript = activeView.querySelector('#stats-metadata');
        if (statsScript) {
            try {
                const stats = JSON.parse(statsScript.textContent);
                updateHeaderStats(stats);
            } catch (e) {
                console.error("Error parsing stats metadata:", e);
            }
        }

        updateAllRejectedBtnState();

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    }
}

function updateHeaderStats(stats) {
    if (!stats) return;
    const mappings = {
        'stat-ordered-wt': stats.ordered_wt,
        'stat-ordered-pcs': stats.ordered_pcs,
        'stat-accepted-wt': stats.accepted_wt,
        'stat-accepted-pcs': stats.accepted_pcs,
        'stat-rejected-wt': stats.rejected_wt,
        'stat-rejected-pcs': stats.rejected_pcs,
        'stat-barcoded-wt': stats.barcoded_wt,
        'stat-barcoded-pcs': stats.barcoded_pcs,
        'stat-hallmarked-wt': stats.hallmarked_wt,
        'stat-hallmarked-pcs': stats.hallmarked_pcs,
        'stat-qc-passed-wt': stats.qc_passed_wt,
        'stat-qc-passed-pcs': stats.qc_passed_pcs,
        'stat-invoiced-wt': stats.invoiced_wt,
        'stat-invoiced-pcs': stats.invoiced_pcs,
        'stat-delivered-wt': stats.delivered_wt,
        'stat-delivered-pcs': stats.delivered_pcs
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) el.textContent = value || (id.endsWith('-wt') ? '0.00' : '0');
    }

    const barMappings = {
        'stat-accepted-bar': stats.accepted_perc,
        'stat-rejected-bar': stats.rejected_perc,
        'stat-barcoded-bar': stats.barcoded_perc,
        'stat-hallmarked-bar': stats.hallmarked_perc,
        'stat-qc-passed-bar': stats.qc_passed_perc,
        'stat-invoiced-bar': stats.invoiced_perc,
        'stat-delivered-bar': stats.delivered_perc
    };

    for (const [id, perc] of Object.entries(barMappings)) {
        const el = document.getElementById(id);
        if (el) el.style.width = (perc || 0) + '%';
    }
}



function updateLevelBadge(level) {
    const badge = document.getElementById('current-level-badge');
    if (badge) {
        badge.textContent = level ? level.replace('_', ' ').toUpperCase() : 'CLASSIFICATION OWNER';
    }
}

// Tree-Grid Toggle Action
async function toggleRow(btn, level, value, grandparentValue = null) {
    const tr = btn.closest('tr');
    if (!tr) return;

    const icon = btn.querySelector('.material-symbols-outlined');
    const isExpanded = icon.textContent === 'remove_circle';

    if (isExpanded) {
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
        icon.textContent = 'hourglass_empty';

        try {
            const urlParams = new URLSearchParams(window.location.search);
            const params = new URLSearchParams(urlParams);
            params.set('parent_level', level);
            params.set('parent_value', value);
            if (grandparentValue) params.set('grandparent_value', grandparentValue);

            const response = await fetch(`/partial/ownerwise?${params.toString()}`, {
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

function toggleAllRejected() {
    const urlParams = new URLSearchParams(window.location.search);
    const isAllRejected = urlParams.get('all_rejected') === 'true';

    if (isAllRejected) {
        urlParams.delete('all_rejected');
    } else {
        urlParams.set('all_rejected', 'true');
    }

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function updateAllRejectedBtnState() {
    const urlParams = new URLSearchParams(window.location.search);
    const isAllRejected = urlParams.get('all_rejected') === 'true';
    const btn = document.getElementById('btn-all-rejected');

    if (btn) {
        if (isAllRejected) {
            btn.classList.remove('bg-white', 'dark:bg-gray-800', 'text-gray-500', 'border-gray-200', 'dark:border-gray-700');
            btn.classList.add('bg-red-50', 'dark:bg-red-900/20', 'text-red-600', 'border-red-200', 'dark:border-red-800');
        } else {
            btn.classList.add('bg-white', 'dark:bg-gray-800', 'text-gray-500', 'border-gray-200', 'dark:border-gray-700');
            btn.classList.remove('bg-red-50', 'dark:bg-red-900/20', 'text-red-600', 'border-red-200', 'dark:border-red-800');
        }
    }
}

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const configs = {
        'division': 'filter-division',
        'group': 'filter-group',
        'purity': 'filter-purity',
        'classification': 'filter-classification',
        'order_type': 'filter-order-type',
        'supplier': 'filter-supplier',
        'classification_owner': 'filter-class-owner',
        'collection_owner': 'filter-coll-owner',
        'make_owner': 'filter-make-owner',
        'search': 'hierarchy-search'
    };

    for (const [param, id] of Object.entries(configs)) {
        const val = document.getElementById(id)?.value;
        if (val) urlParams.set(param, val);
        else urlParams.delete(param);
    }

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    const ids = [
        'filter-division', 'filter-group', 'filter-purity', 'filter-classification', 'filter-order-type', 'filter-supplier',
        'filter-class-owner', 'filter-coll-owner', 'filter-make-owner', 'hierarchy-search'
    ];

    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
        const param = id.replace('filter-', '').replace('class-', 'classification_').replace('coll-', 'collection_').replace('hierarchy-', '');
        urlParams.delete(param);
    });
    urlParams.delete('all_rejected');

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}


function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
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
    try {
        const response = await fetch(`/api/orderstatus/options`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const options = await response.json();

        populateSelect('filter-division', options.divisions, 'All Divisions');
        populateSelect('filter-business-head', options.business_heads, 'All Business Heads');

        // Sync from URL
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('division')) document.getElementById('filter-division').value = urlParams.get('division');
        if (urlParams.get('business_head')) document.getElementById('filter-business-head').value = urlParams.get('business_head');

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

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('search')) document.getElementById('hierarchy-search').value = urlParams.get('search');

    loadViewData();
    loadFilterOptions();
    updateAllRejectedBtnState();
});
