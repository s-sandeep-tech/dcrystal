async function loadViewData() {
    const activeView = document.getElementById('view-rejected-weight');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    try {
        const response = await fetch(`/partial/rejected-weight-feedback?${urlParams.toString()}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch view');
        const html = await response.text();
        activeView.innerHTML = html;

        // Synchronize pagination and stats from hidden fields in the partial
        const total = document.getElementById('hidden-total')?.textContent;
        if (total) {
            updatePaginationControls({
                total: total,
                page: document.getElementById('hidden-page').textContent,
                perPage: document.getElementById('hidden-per-page').textContent,
                hasPrev: document.getElementById('hidden-has-prev').textContent,
                hasNext: document.getElementById('hidden-has-next').textContent
            });
        }
    } catch (error) {
        console.error('Error loading view:', error);
        activeView.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data.</div>`;
    }
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

    const feedbackStatus = document.getElementById('filter-feedback-status')?.value;
    if (feedbackStatus) urlParams.set('feedback_status', feedbackStatus);
    else urlParams.delete('feedback_status');

    const collectionOwner = document.getElementById('filter-collection-owner')?.value;
    if (collectionOwner) urlParams.set('collection_owner', collectionOwner);
    else urlParams.delete('collection_owner');

    const makeOwner = document.getElementById('filter-make-owner')?.value;
    if (makeOwner) urlParams.set('make_owner', makeOwner);
    else urlParams.delete('make_owner');

    const supplier = document.getElementById('filter-supplier')?.value;
    if (supplier) urlParams.set('supplier', supplier);
    else urlParams.delete('supplier');

    const orderType = document.getElementById('filter-order-type')?.value;
    if (orderType) urlParams.set('order_type', orderType);
    else urlParams.delete('order_type');

    const orderRequestType = document.getElementById('filter-order-request-type')?.value;
    if (orderRequestType) urlParams.set('order_request_type', orderRequestType);
    else urlParams.delete('order_request_type');

    const collection = document.getElementById('filter-collection')?.value;
    if (collection) urlParams.set('collection', collection);
    else urlParams.delete('collection');

    const delayEnable = document.getElementById('filter-delay-enable')?.checked;
    const delay = document.getElementById('filter-delay')?.value;
    if (delayEnable && delay !== '') urlParams.set('delay', delay);
    else urlParams.delete('delay');

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetGlobalFilters() {
    const urlParams = new URLSearchParams();

    const searchInput = document.getElementById('hierarchy-search');
    if (searchInput) searchInput.value = '';

    const feedbackStatus = document.getElementById('filter-feedback-status');
    if (feedbackStatus) feedbackStatus.value = '';

    const collOwner = document.getElementById('filter-collection-owner');
    if (collOwner) collOwner.value = '';

    const makeOwner = document.getElementById('filter-make-owner');
    if (makeOwner) makeOwner.value = '';

    const supplier = document.getElementById('filter-supplier');
    if (supplier) supplier.value = '';

    const orderType = document.getElementById('filter-order-type');
    if (orderType) orderType.value = '';

    const orderRequestType = document.getElementById('filter-order-request-type');
    if (orderRequestType) orderRequestType.value = '';

    const collection = document.getElementById('filter-collection');
    if (collection) collection.value = '';

    const delay = document.getElementById('filter-delay');
    if (delay) delay.value = '5';
    const delayEnable = document.getElementById('filter-delay-enable');
    if (delayEnable) delayEnable.checked = false;

    updateUrlAndLoad(urlParams);
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
    if (infoSpan) infoSpan.textContent = total > 0 ? `${start}-${end} of ${total}` : '0-0 of 0';

    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    if (btnPrev) {
        btnPrev.disabled = !hasPrev;
        btnPrev.onclick = hasPrev ? () => changePage(page - 1) : null;
    }
    if (btnNext) {
        btnNext.disabled = !hasNext;
        btnNext.onclick = hasNext ? () => changePage(page + 1) : null;
    }
}

function changePage(page) {
    if (!page || page < 1) return;
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

document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    
    // Set filter values from URL on load
    const filters = ['search', 'feedback_status', 'collection_owner', 'make_owner', 'supplier', 'order_type', 'order_request_type', 'collection'];
    filters.forEach(f => {
        const val = urlParams.get(f);
        if (val) {
            const el = document.getElementById(f === 'search' ? 'hierarchy-search' : `filter-${f.replace('_', '-')}`);
            if (el) el.value = val;
        }
    });

    if (urlParams.get('delay')) {
        const sel = document.getElementById('filter-delay');
        if (sel) sel.value = urlParams.get('delay');
        const enable = document.getElementById('filter-delay-enable');
        if (enable) enable.checked = true;
    }

    loadViewData();
});

// Modal stuff
function openFeedbackModal(collectionOwner, makeOwner, supplier, collection, currFeedback, currCategory) {
    document.getElementById('fb_collection_owner').value = collectionOwner;
    document.getElementById('fb_make_owner').value = makeOwner;
    document.getElementById('fb_supplier').value = supplier;
    document.getElementById('fb_collection').value = collection;

    document.getElementById('feedbackModalContext').textContent = `${collectionOwner} | ${makeOwner} | ${collection}`;

    const ta = document.getElementById('feedbackText');
    ta.value = currFeedback || '';

    const cat = document.getElementById('feedbackCategory');
    if (cat) cat.value = currCategory || '';

    document.getElementById('feedbackModal').classList.remove('hidden');
}

function closeFeedbackModal() {
    document.getElementById('feedbackModal').classList.add('hidden');
}

async function saveFeedback() {
    const btnText = document.getElementById('saveBtnText');
    const btnIcon = document.getElementById('saveBtnIcon');
    const payload = {
        collection_owner: document.getElementById('fb_collection_owner').value,
        make_owner: document.getElementById('fb_make_owner').value,
        supplier: document.getElementById('fb_supplier').value,
        collection: document.getElementById('fb_collection').value,
        feedback_text: document.getElementById('feedbackText').value,
        feedback_category: document.getElementById('feedbackCategory').value
    };

    if (!payload.feedback_text.trim()) {
        alert("Feedback cannot be empty");
        return;
    }

    try {
        btnText.textContent = 'Saving...';
        btnIcon.textContent = 'sync';
        btnIcon.classList.add('animate-spin');

        const res = await fetch('/api/rejected-weight-feedback/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error("Failed to save feedback");

        closeFeedbackModal();
        loadViewData();
    } catch (err) {
        alert(err.message);
    } finally {
        btnText.textContent = 'Save';
        btnIcon.textContent = 'save';
        btnIcon.classList.remove('animate-spin');
    }
}

async function viewPODetails(collectionOwner, makeOwner, supplier, collection) {
    document.getElementById('poOwnerText').textContent = collectionOwner || 'N/A';
    document.getElementById('poMakeText').textContent = makeOwner || 'N/A';
    document.getElementById('poSupplierText').textContent = supplier || 'N/A';
    document.getElementById('poCollectionText').textContent = collection || 'N/A';

    const contentDiv = document.getElementById('poDetailsContent');
    contentDiv.innerHTML = `<div class="flex flex-col items-center justify-center p-8 text-gray-400"><span class="material-symbols-outlined text-3xl animate-spin mb-2 text-primary">sync</span><span class="text-xs font-medium tracking-widest uppercase">Loading Details...</span></div>`;

    document.getElementById('poDetailsModal').classList.remove('hidden');

    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('collection_owner', collectionOwner);
    urlParams.set('make_owner', makeOwner);
    urlParams.set('supplier', supplier);
    urlParams.set('collection', collection);

    try {
        const response = await fetch(`/api/rejected-weight-feedback/po-details?${urlParams.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) throw new Error('Failed to load details');
        const html = await response.text();
        contentDiv.innerHTML = html;
    } catch (error) {
        console.error('Error fetching PO Details:', error);
        contentDiv.innerHTML = `<div class="p-8 text-center text-red-500 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-100 dark:border-red-900/30 font-bold">Error loading details: ${error.message}</div>`;
    }
}

function closePODetailsModal() {
    document.getElementById('poDetailsModal').classList.add('hidden');
    document.getElementById('poDetailsContent').innerHTML = '';
}
