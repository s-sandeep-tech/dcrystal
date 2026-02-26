let currentZoom = parseFloat(localStorage.getItem('outstanding-orders-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('outstanding-orders-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-outstanding-orders');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/outstanding_orders?${searchParams}`, {
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
        badge.textContent = level || 'classification_owner';
    }
}

function updateDashboardStats(stats) {
    if (!stats) return;

    const mappings = {
        'stat-order-pieces': stats.order_pieces,
        'stat-order-weight': stats.order_weight,
        'stat-accepted-pieces': stats.accepted_pieces,
        'stat-accepted-weight': stats.accepted_weight,
    };

    for (const [id, value] of Object.entries(mappings)) {
        const el = document.getElementById(id);
        if (el) {
            if (id.includes('pieces')) el.textContent = new Intl.NumberFormat().format(value) + ' pcs';
            else el.textContent = value !== undefined ? new Intl.NumberFormat(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(value) : '0.000';
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

            const response = await fetch(`/partial/outstanding_orders?${params.toString()}`, {
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



function onClassificationOwnerChange(val) {
    const urlParams = new URLSearchParams(window.location.search);
    if (val) urlParams.set('classification_owner', val);
    else urlParams.delete('classification_owner');

    urlParams.delete('make_owner');
    urlParams.delete('collection_owner');
    urlParams.set('page', 1);

    updateUrlAndLoad(urlParams);
    loadFilterOptions();
}

function onMakeOwnerChange(val) {
    const urlParams = new URLSearchParams(window.location.search);
    if (val) urlParams.set('make_owner', val);
    else urlParams.delete('make_owner');

    urlParams.delete('collection_owner');
    urlParams.set('page', 1);

    updateUrlAndLoad(urlParams);
    loadFilterOptions();
}

function onCollectionOwnerChange(val) {
    const urlParams = new URLSearchParams(window.location.search);
    if (val) urlParams.set('collection_owner', val);
    else urlParams.delete('collection_owner');
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetDrillDown() {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.delete('classification_owner');
    urlParams.delete('make_owner');
    urlParams.delete('collection_owner');
    urlParams.set('page', 1);

    document.getElementById('filter-classification-owner').value = '';
    document.getElementById('filter-make-owner').value = '';
    document.getElementById('filter-collection-owner').value = '';

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
    const searchVal = document.getElementById('hierarchy-search')?.value;
    if (searchVal) urlParams.set('search', searchVal);
    else urlParams.delete('search');

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.delete('search');
    urlParams.delete('classification_owner');
    urlParams.delete('make_owner');
    urlParams.delete('collection_owner');

    const search = document.getElementById('hierarchy-search');
    if (search) search.value = '';

    document.getElementById('filter-classification-owner').value = '';
    document.getElementById('filter-make-owner').value = '';
    document.getElementById('filter-collection-owner').value = '';

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
    loadFilterOptions();
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
    const classificationOwner = urlParams.get('classification_owner') || '';
    const makeOwner = urlParams.get('make_owner') || '';

    try {
        const response = await fetch(`/api/outstanding_orders/options?classification_owner=${classificationOwner}&make_owner=${makeOwner}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const options = await response.json();

        populateSelect('filter-classification-owner', options.classification_owners, 'All Classification Owners', urlParams.get('classification_owner'));
        populateSelect('filter-make-owner', options.make_owners, 'All Make Owners', urlParams.get('make_owner'));
        populateSelect('filter-collection-owner', options.collection_owners, 'All Collection Owners', urlParams.get('collection_owner'));

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

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('search')) document.getElementById('hierarchy-search').value = urlParams.get('search');

    loadViewData();
    loadFilterOptions();
});

function showOrderDetails(classificationOwner, makeOwner, collectionOwner) {
    const modal = document.getElementById('detailsModal');
    const content = document.getElementById('detailsModalContent');

    if (!modal || !content) return;

    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    content.innerHTML = `
        <div class="flex flex-col items-center justify-center h-full py-24 text-gray-400">
            <div class="size-8 border-2 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-[10px] font-medium uppercase tracking-widest">Fetching details...</p>
        </div>
    `;

    fetch(`/api/outstanding_orders/details?classification_owner=${encodeURIComponent(classificationOwner)}&make_owner=${encodeURIComponent(makeOwner)}&collection_owner=${encodeURIComponent(collectionOwner)}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch details');
            return response.text();
        })
        .then(html => {
            content.innerHTML = html;
        })
        .catch(error => {
            console.error('Error fetching details:', error);
            content.innerHTML = `
            <div class="p-12 text-center text-red-500">
                <span class="material-symbols-outlined text-4xl mb-2">error</span>
                <p class="text-xs font-bold">Failed to load order details.</p>
                <p class="text-[10px] mt-1 text-gray-400">${error.message}</p>
            </div>
        `;
        });
}

function closeDetailsModal() {
    const modal = document.getElementById('detailsModal');
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }
}
