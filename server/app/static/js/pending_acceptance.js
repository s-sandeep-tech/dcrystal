async function loadViewData() {
    const activeView = document.getElementById('view-pending-acceptance');
    if (!activeView) return;

    const urlParams = new URLSearchParams(window.location.search);
    try {
        const response = await fetch(`/partial/pending-acceptance-feedback?${urlParams.toString()}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });
        if (!response.ok) throw new Error('Failed to fetch view');
        const html = await response.text();
        activeView.innerHTML = html;

        const metaDiv = activeView.querySelector('.pagination-meta');
        if (metaDiv) updatePaginationControls(metaDiv.dataset);

        const statsDiv = activeView.querySelector('.stats-meta');
        if (statsDiv) updateStatsCards(statsDiv.dataset);
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

    const classification = document.getElementById('filter-classification')?.value;
    if (classification) urlParams.set('classification', classification);
    else urlParams.delete('classification');

    const collection = document.getElementById('filter-collection')?.value;
    if (collection) urlParams.set('collection', collection);
    else urlParams.delete('collection');

    const delayEnable = document.getElementById('filter-delay-enable')?.checked;
    const delay = document.getElementById('filter-delay')?.value;
    if (delayEnable && delay !== '') urlParams.set('delay', delay);
    else urlParams.delete('delay');

    const dateEnable = document.getElementById('enable-date-filter')?.checked;
    const fromDate = document.getElementById('filter-from-date')?.value;
    const toDate = document.getElementById('filter-to-date')?.value;
    if (dateEnable && fromDate && toDate) {
        urlParams.set('enable_date_filter', 'true');
        urlParams.set('from_date', fromDate);
        urlParams.set('to_date', toDate);
    } else {
        urlParams.delete('enable_date_filter');
        urlParams.delete('from_date');
        urlParams.delete('to_date');
    }

    const enableFeedbackDateFilter = document.getElementById('enable-feedback-date-filter')?.checked;
    const feedbackFromDate = document.getElementById('filter-feedback-from-date')?.value;
    const feedbackToDate = document.getElementById('filter-feedback-to-date')?.value;
    if (enableFeedbackDateFilter && feedbackFromDate && feedbackToDate) {
        urlParams.set('enable_feedback_date_filter', 'true');
        urlParams.set('feedback_from_date', feedbackFromDate);
        urlParams.set('feedback_to_date', feedbackToDate);
    } else {
        urlParams.delete('enable_feedback_date_filter');
        urlParams.delete('feedback_from_date');
        urlParams.delete('feedback_to_date');
    }

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

    const classification = document.getElementById('filter-classification');
    if (classification) classification.value = '';

    const collection = document.getElementById('filter-collection');
    if (collection) collection.value = '';

    const delay = document.getElementById('filter-delay');
    if (delay) delay.value = '5';
    const delayEnable = document.getElementById('filter-delay-enable');
    if (delayEnable) delayEnable.checked = false;

    const dateEnable = document.getElementById('enable-date-filter');
    if (dateEnable) dateEnable.checked = false;
    const fromDate = document.getElementById('filter-from-date');
    if (fromDate) fromDate.value = '';
    const toDate = document.getElementById('filter-to-date');
    if (toDate) toDate.value = '';
    toggleDateInputs();

    const feedbackDateEnable = document.getElementById('enable-feedback-date-filter');
    if (feedbackDateEnable) feedbackDateEnable.checked = false;
    const feedbackFromDate = document.getElementById('filter-feedback-from-date');
    if (feedbackFromDate) feedbackFromDate.value = '';
    const feedbackToDate = document.getElementById('filter-feedback-to-date');
    if (feedbackToDate) feedbackToDate.value = '';
    toggleFeedbackDateInputs();

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

document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('search')) {
        const input = document.getElementById('hierarchy-search');
        if (input) input.value = urlParams.get('search');
    }

    if (urlParams.get('feedback_status')) {
        const sel = document.getElementById('filter-feedback-status');
        if (sel) sel.value = urlParams.get('feedback_status');
    }
    if (urlParams.get('collection_owner')) {
        const sel = document.getElementById('filter-collection-owner');
        if (sel) sel.value = urlParams.get('collection_owner');
    }
    if (urlParams.get('make_owner')) {
        const sel = document.getElementById('filter-make-owner');
        if (sel) sel.value = urlParams.get('make_owner');
    }
    if (urlParams.get('supplier')) {
        const sel = document.getElementById('filter-supplier');
        if (sel) sel.value = urlParams.get('supplier');
    }
    if (urlParams.get('order_type')) {
        const sel = document.getElementById('filter-order-type');
        if (sel) sel.value = urlParams.get('order_type');
    }
    if (urlParams.get('order_request_type')) {
        const sel = document.getElementById('filter-order-request-type');
        if (sel) sel.value = urlParams.get('order_request_type');
    }
    if (urlParams.get('classification')) {
        const sel = document.getElementById('filter-classification');
        if (sel) sel.value = urlParams.get('classification');
    }
    if (urlParams.get('collection')) {
        const sel = document.getElementById('filter-collection');
        if (sel) sel.value = urlParams.get('collection');
    }
    if (urlParams.get('delay')) {
        const sel = document.getElementById('filter-delay');
        if (sel) sel.value = urlParams.get('delay');
        const enable = document.getElementById('filter-delay-enable');
        if (enable) enable.checked = true;
    } else {
        const enable = document.getElementById('filter-delay-enable');
        if (enable) enable.checked = false;
        const sel = document.getElementById('filter-delay');
        if (sel) sel.value = '5';
    }

    if (urlParams.get('enable_date_filter') === 'true') {
        const enable = document.getElementById('enable-date-filter');
        if (enable) enable.checked = true;
        const from = document.getElementById('filter-from-date');
        if (from) from.value = urlParams.get('from_date') || '';
        const to = document.getElementById('filter-to-date');
        if (to) to.value = urlParams.get('to_date') || '';
        toggleDateInputs();
    }

    if (urlParams.get('enable_feedback_date_filter') === 'true') {
        const enable = document.getElementById('enable-feedback-date-filter');
        if (enable) enable.checked = true;
        const from = document.getElementById('filter-feedback-from-date');
        if (from) from.value = urlParams.get('feedback_from_date') || '';
        const to = document.getElementById('filter-feedback-to-date');
        if (to) to.value = urlParams.get('feedback_to_date') || '';
        toggleFeedbackDateInputs();
    }

    const metaDiv = document.querySelector('.pagination-meta');
    if (metaDiv) {
        updatePaginationControls(metaDiv.dataset);
    } else {
        // No metadata means initial shell, load data via AJAX
        loadViewData();
    }

    const statsDiv = document.querySelector('.stats-meta');
    if (statsDiv) updateStatsCards(statsDiv.dataset);
});

function updateStatsCards(stats) {
    const orderWt = parseFloat(stats.totalOrderWt || 0);
    const acceptedWt = parseFloat(stats.totalAcceptedWt || 0);
    const pendingWt = parseFloat(stats.totalPendingWt || 0);
    const withFeedback = parseInt(stats.withFeedback || 0);
    const withoutFeedback = parseInt(stats.withoutFeedback || 0);

    const fmt = (v) => new Intl.NumberFormat('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(v);

    const elOrder = document.getElementById('stat-order-wt');
    if (elOrder) elOrder.textContent = fmt(orderWt);

    const elAccepted = document.getElementById('stat-accepted-wt');
    if (elAccepted) elAccepted.textContent = fmt(acceptedWt);

    const elPending = document.getElementById('stat-pending-wt');
    if (elPending) elPending.textContent = fmt(pendingWt);

    const elWith = document.getElementById('stat-with-feedback');
    if (elWith) elWith.textContent = withFeedback.toLocaleString();

    const elWithout = document.getElementById('stat-without-feedback');
    if (elWithout) elWithout.textContent = withoutFeedback.toLocaleString();
}

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
    document.getElementById('feedbackText').value = '';
    const cat = document.getElementById('feedbackCategory');
    if (cat) cat.value = '';
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

        const res = await fetch('/api/pending-acceptance-feedback/feedback', {
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

// PO Details Modal
async function showPODetailsModal(collectionOwner, makeOwner, supplier, collection) {
    console.log('Opening PO Details for:', { collectionOwner, makeOwner, supplier, collection });
    document.getElementById('poOwnerText').textContent = collectionOwner || 'N/A';
    document.getElementById('poMakeText').textContent = makeOwner || 'N/A';
    document.getElementById('poSupplierText').textContent = supplier || 'N/A';
    document.getElementById('poCollectionText').textContent = collection || 'N/A';

    const contentDiv = document.getElementById('poDetailsContent');
    contentDiv.innerHTML = `
        <div class="flex flex-col items-center justify-center p-8 text-gray-400">
            <span class="material-symbols-outlined text-3xl animate-spin mb-2 text-primary">sync</span>
            <span class="text-xs font-medium uppercase tracking-widest">Loading Details...</span>
        </div>
    `;

    document.getElementById('poDetailsModal').classList.remove('hidden');

    // Pass same filters mapping to main API
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('collection_owner', collectionOwner);
    urlParams.set('make_owner', makeOwner);
    urlParams.set('supplier', supplier);
    urlParams.set('collection', collection);

    try {
        const response = await fetch(`/api/pending-acceptance-feedback/po-details?${urlParams.toString()}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });

        if (!response.ok) throw new Error('Failed to load details');

        const html = await response.text();
        contentDiv.innerHTML = html;

    } catch (error) {
        console.error('Error fetching PO Details:', error);
        contentDiv.innerHTML = `
            <div class="p-8 text-center text-red-500 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-100 dark:border-red-900/30">
                <span class="material-symbols-outlined text-2xl mb-2">error</span>
                <p class="font-bold">Error loading details</p>
                <p class="text-xs mt-1 opacity-80">${error.message}</p>
            </div>
        `;
    }
}

function closePODetailsModal() {
    document.getElementById('poDetailsModal').classList.add('hidden');
    document.getElementById('poDetailsContent').innerHTML = '';
}

function toggleDateInputs() {
    const isChecked = document.getElementById('enable-date-filter')?.checked;
    const container = document.getElementById('date-inputs');
    if (container) {
        if (isChecked) {
            container.classList.remove('opacity-40', 'pointer-events-none');
        } else {
            container.classList.add('opacity-40', 'pointer-events-none');
        }
    }
}

function toggleFeedbackDateInputs() {
    const isChecked = document.getElementById('enable-feedback-date-filter')?.checked;
    const container = document.getElementById('feedback-date-inputs');
    if (container) {
        if (isChecked) {
            container.classList.remove('opacity-40', 'pointer-events-none');
        } else {
            container.classList.add('opacity-40', 'pointer-events-none');
        }
    }
}
