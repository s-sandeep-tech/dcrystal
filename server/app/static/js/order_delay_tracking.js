let currentZoom = parseFloat(localStorage.getItem('order-delay-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('order-delay-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

async function loadViewData() {
    const activeView = document.getElementById('view-order-delay');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    const searchParams = urlParams.toString();

    try {
        const response = await fetch(`/partial/orderdelaytracking?${searchParams}`, {
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

        // Update pagination info if meta exists
        const paginationInfo = activeView.querySelector('#pagination-metadata');
        if (paginationInfo) {
            updatePaginationControls(paginationInfo.dataset);
        }

    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    }
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

function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

async function loadFilterOptions() {
    try {
        const response = await fetch(`/api/orderdelaytracking/options`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const options = await response.json();

        populateSelect('filter-classification-owner', options.classification_owners, 'All Owners');
        populateSelect('filter-make-owner', options.make_owners, 'All Owners');
        populateSelect('filter-collection-owner', options.collection_owners, 'All Owners');

        // Restore values from URL
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('classification_owner')) document.getElementById('filter-classification-owner').value = urlParams.get('classification_owner');
        if (urlParams.get('make_owner')) document.getElementById('filter-make-owner').value = urlParams.get('make_owner');
        if (urlParams.get('collection_owner')) document.getElementById('filter-collection-owner').value = urlParams.get('collection_owner');

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

function applyGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);

    const co = document.getElementById('filter-classification-owner').value;
    const mo = document.getElementById('filter-make-owner').value;
    const coll = document.getElementById('filter-collection-owner').value;

    if (co) urlParams.set('classification_owner', co); else urlParams.delete('classification_owner');
    if (mo) urlParams.set('make_owner', mo); else urlParams.delete('make_owner');
    if (coll) urlParams.set('collection_owner', coll); else urlParams.delete('collection_owner');

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.delete('classification_owner');
    urlParams.delete('make_owner');
    urlParams.delete('collection_owner');
    urlParams.set('page', 1);

    document.getElementById('filter-classification-owner').value = '';
    document.getElementById('filter-make-owner').value = '';
    document.getElementById('filter-collection-owner').value = '';

    updateUrlAndLoad(urlParams);
}

async function showDetails(co, mo, colo, bucket) {
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

    try {
        const response = await fetch(`/api/orderdelaytracking/details?classification_owner=${encodeURIComponent(co)}&make_owner=${encodeURIComponent(mo)}&collection_owner=${encodeURIComponent(colo)}&delay_bucket=${encodeURIComponent(bucket)}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch details');
        const html = await response.text();
        content.innerHTML = html;
    } catch (error) {
        console.error('Error fetching details:', error);
        content.innerHTML = `<div class="p-12 text-center text-red-500">Failed to load details.</div>`;
    }
}

function closeDetailsModal() {
    const modal = document.getElementById('detailsModal');
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

async function triggerSync(type) {
    if (!confirm('Are you sure you want to trigger a fresh data synchronization? This may take a few minutes.')) return;

    try {
        const response = await fetch(`/api/sync/trigger?type=${type}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        const result = await response.json();
        if (result.status === 'success') {
            alert('Sync task queued! You will receive a notification when it completes.');
        } else {
            alert('Failed to queue sync task: ' + result.message);
        }
    } catch (e) {
        console.error('Sync trigger error:', e);
        alert('Error triggering sync.');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;

    loadViewData();
    loadFilterOptions();
});
