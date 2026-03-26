let currentStatusFilter = 'pending_to_accept';

async function loadViewData() {
    const activeView = document.getElementById('view-pending-acceptance');
    const loader = document.getElementById('loader-overlay');
    if (!activeView) return;

    if (loader) loader.classList.remove('hidden');

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
    } finally {
        if (loader) {
            // Small delay for smooth transition if data loads too fast
            setTimeout(() => {
                loader.classList.add('hidden');
            }, 300);
        }
    }
}

function setStatusFilter(filter) {
    currentStatusFilter = filter;
    
    // Update button UI
    document.querySelectorAll('.status-filter-btn').forEach(btn => btn.classList.remove('active'));
    if (filter === 'pending_to_accept') {
        const btn = document.getElementById('btn-status-accept');
        if (btn) btn.classList.add('active');
    } else if (filter === 'pending_to_deliver') {
        const btn = document.getElementById('btn-status-deliver');
        if (btn) btn.classList.add('active');
    } else if (filter === 'pending_to_deliver_not_barcoded') {
        const btn = document.getElementById('btn-status-not-barcoded');
        if (btn) btn.classList.add('active');
    }
    
    // Apply filters. If status is pending_to_deliver_not_barcoded, ensure delay is enabled.
    if (filter === 'pending_to_deliver_not_barcoded') {
        const delayEnable = document.getElementById('filter-delay-enable');
        if (delayEnable && !delayEnable.checked) {
            delayEnable.checked = true;
            const delayInput = document.getElementById('filter-delay');
            if (delayInput && (delayInput.value === '' || delayInput.value === '0')) {
                delayInput.value = '5';
            }
        }
    }
    
    applyGlobalFilters();
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

    if (currentStatusFilter) urlParams.set('status_filter', currentStatusFilter);
    else urlParams.delete('status_filter');

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

    currentStatusFilter = 'pending_to_accept';
    document.querySelectorAll('.status-filter-btn').forEach(btn => btn.classList.remove('active'));
    const btnAccept = document.getElementById('btn-status-accept');
    if (btnAccept) btnAccept.classList.add('active');

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
    const statusFilterArg = urlParams.get('status_filter') || 'pending_to_accept';
    if (urlParams.get('delay')) {
        const sel = document.getElementById('filter-delay');
        if (sel) sel.value = urlParams.get('delay');
        const enable = document.getElementById('filter-delay-enable');
        if (enable) enable.checked = true;
    } else if (statusFilterArg === 'pending_to_deliver_not_barcoded') {
        // Default to enabled with 5 days for this status if not in URL
        const enable = document.getElementById('filter-delay-enable');
        if (enable) enable.checked = true;
        const sel = document.getElementById('filter-delay');
        if (sel) sel.value = '5';
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

    if (urlParams.get('status_filter')) {
        currentStatusFilter = urlParams.get('status_filter');
        document.querySelectorAll('.status-filter-btn').forEach(btn => btn.classList.remove('active'));
        if (currentStatusFilter === 'pending_to_accept') {
            const btn = document.getElementById('btn-status-accept');
            if (btn) btn.classList.add('active');
        } else if (currentStatusFilter === 'pending_to_deliver') {
            const btn = document.getElementById('btn-status-deliver');
            if (btn) btn.classList.add('active');
        } else if (currentStatusFilter === 'pending_to_deliver_not_barcoded') {
            const btn = document.getElementById('btn-status-not-barcoded');
            if (btn) btn.classList.add('active');
        }
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
    const withFeedback = parseInt(stats.withFeedback || 0);
    
    const urlParams = new URLSearchParams(window.location.search);
    const statusFilter = urlParams.get('status_filter') || 'pending_to_accept';

    const fmt = (v) => new Intl.NumberFormat('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(v);

    document.getElementById('stat-order-wt').textContent = fmt(orderWt);
    document.getElementById('stat-accepted-wt').textContent = fmt(acceptedWt);
    document.getElementById('stat-with-feedback').textContent = withFeedback.toLocaleString();

    const card3 = document.getElementById('stat-pending-wt').parentElement;
    const card4 = document.getElementById('stat-contextual-metric').parentElement;

    if (statusFilter === 'pending_to_deliver') {
        const wt = parseFloat(stats.totalPendingToDeliverWt || 0);
        const pcs = parseInt(stats.totalPendingToDeliverPcs || 0);
        
        card3.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-indigo-600">local_shipping</span>Pending Deliver Wt`;
        document.getElementById('stat-pending-wt').textContent = fmt(wt);
        document.getElementById('stat-pending-wt').className = 'stat-val text-orange-600';
        
        card4.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-blue-600">inventory_2</span>Pending Deliver Pcs`;
        document.getElementById('stat-contextual-metric').textContent = pcs.toLocaleString();
        document.getElementById('stat-contextual-metric').className = 'stat-val';
    } else if (statusFilter === 'pending_to_deliver_not_barcoded') {
        const wt = parseFloat(stats.totalNotBarcodedWt || 0);
        const pcs = parseInt(stats.totalNotBarcodedPcs || 0);
        
        card3.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-orange-600">barcode_scanner</span>Not Barcoded Wt`;
        document.getElementById('stat-pending-wt').textContent = fmt(wt);
        document.getElementById('stat-pending-wt').className = 'stat-val text-orange-600';
        
        card4.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-cyan-600">pin</span>Not Barcoded Pcs`;
        document.getElementById('stat-contextual-metric').textContent = pcs.toLocaleString();
        document.getElementById('stat-contextual-metric').className = 'stat-val';
    } else {
        const pendingWt = parseFloat(stats.totalPendingToAcceptedWt || 0);
        const withoutFeedback = parseInt(stats.withoutFeedback || 0);
        
        card3.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-orange-premium">pending_actions</span>Pending Wt`;
        document.getElementById('stat-pending-wt').textContent = fmt(pendingWt);
        document.getElementById('stat-pending-wt').className = 'stat-val text-orange-premium';
        
        card4.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-red-600">chat_error</span>Without Feedback`;
        document.getElementById('stat-contextual-metric').textContent = withoutFeedback.toLocaleString();
        document.getElementById('stat-contextual-metric').className = 'stat-val';
    }
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
        feedback_category: document.getElementById('feedbackCategory').value,
        status_filter: currentStatusFilter
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
async function showPODetailsModal(collectionOwner, makeOwner, supplier, collection, statusFilter) {
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
    if (statusFilter) urlParams.set('status_filter', statusFilter);

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

function toggleDrilldown(id) {
    const rows = document.querySelectorAll(`tr[data-parent="${id}"]`);
    const btn = document.getElementById(`btn-${id}`);
    const icon = btn ? btn.querySelector('span') : null;
    
    // Check if we are opening or closing
    const isOpening = rows.length > 0 && rows[0].classList.contains('hidden');
    
    if (isOpening) {
        // Open immediate children
        rows.forEach(row => {
            row.classList.remove('hidden');
        });
        if (icon) icon.style.transform = 'rotate(90deg)';
    } else {
        // Close all descendants recursively
        closeDescendants(id);
        if (icon) icon.style.transform = 'rotate(0deg)';
    }
}

function closeDescendants(parentId) {
    const children = document.querySelectorAll(`tr[data-parent="${parentId}"]`);
    children.forEach(child => {
        child.classList.add('hidden');
        const childId = child.getAttribute('data-id');
        const btn = document.getElementById(`btn-${childId}`);
        const icon = btn ? btn.querySelector('span') : null;
        if (icon) icon.style.transform = 'rotate(0deg)';
        closeDescendants(childId);
    });
}

// Expired Order Wizard Logic
let wizardData = null;
let currentWizardStep = 1;
let currentContext = null;
let existingWizardAction = null;

async function openExpiredOrderWizard(co, mo, s, c, sf) {
    const loader = document.getElementById('loader-overlay');
    if (loader) loader.classList.remove('hidden');

    try {
        currentContext = {
            collection_owner: co,
            make_owner: mo,
            supplier: s,
            collection: c,
            status_filter: sf || 'pending_to_deliver_not_barcoded'
        };

        const urlParams = new URLSearchParams(window.location.search);
        urlParams.set('collection_owner', co);
        urlParams.set('make_owner', mo);
        urlParams.set('supplier', s);
        urlParams.set('collection', c);
        urlParams.set('status_filter', sf || 'pending_to_deliver_not_barcoded');
        
        const response = await fetch(`/api/pending-acceptance-feedback/po-details?${urlParams.toString()}`, {
            headers: { 
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) throw new Error('Failed to fetch PO details');
        const result = await response.json();
        
        wizardData = result.details || [];
        existingWizardAction = result.existing_actions || {};
        
        // Reset and show wizard
        currentWizardStep = 1;
        renderWizardData();
        goToWizardStep(1);
        document.getElementById('expiredOrderWizard').classList.remove('hidden');
        
    } catch (e) {
        console.error('Wizard initialization failed:', e);
        showToast('Could not load expired order details.', 'error');
        closeExpiredOrderWizard();
    } finally {
        if (loader) loader.classList.add('hidden');
    }
}

function closeExpiredOrderWizard() {
    document.getElementById('expiredOrderWizard').classList.add('hidden');
    wizardData = null;
    currentWizardStep = 1;
}

function goToWizardStep(step) {
    currentWizardStep = step;
    
    // Hide all steps
    document.getElementById('wizard-step-1').classList.add('hidden');
    document.getElementById('wizard-step-2').classList.add('hidden');
    document.getElementById('wizard-step-3').classList.add('hidden');
    
    // Header updates
    const title = document.getElementById('wizard-title');
    const subtitle = document.getElementById('wizard-subtitle');
    
    // Footer updates
    const backBtn = document.getElementById('wizard-back-btn');
    const subBtn = document.getElementById('wizard-sub-btn');
    const cancelBtn = document.getElementById('wizard-cancel-btn');
    
    backBtn.classList.add('hidden');
    subBtn.classList.add('hidden');
    subBtn.disabled = false;
    subBtn.textContent = 'Proceed with Fulfillment';
    cancelBtn.classList.add('hidden');
    cancelBtn.disabled = false;
    cancelBtn.textContent = 'Cancel Order';

    if (step === 1) {
        document.getElementById('wizard-step-1').classList.remove('hidden');
        title.textContent = 'Expired Order Management';
        subtitle.textContent = 'Address orders that have passed their scheduled delivery date.';
    } else if (step === 2) {
        document.getElementById('wizard-step-2').classList.remove('hidden');
        title.textContent = 'Review & Action';
        subtitle.textContent = 'Step 2 of 2: Finalize management action for expired items.';
        backBtn.classList.remove('hidden');
        subBtn.classList.remove('hidden');
        subBtn.textContent = 'Proceed with Fulfillment';
    } else if (step === 3) {
        document.getElementById('wizard-step-3').classList.remove('hidden');
        title.textContent = 'Expired Order';
        subtitle.textContent = 'Step 3 of 3: Confirm cancellation operation';
        backBtn.classList.remove('hidden');
        cancelBtn.classList.remove('hidden');
    }
}

function goBackWizard() {
    goToWizardStep(1);
}

function renderWizardData() {
    if (!wizardData) return;
    
    // Step 2: Continue Items - Now 4 Blank Rows for Manual Entry
    const continueBody = document.getElementById('wizard-continue-items');
    
    let prefillContinue = null;
    let prefillCancel = null;
    
    if (existingWizardAction['CONTINUE']) {
        prefillContinue = existingWizardAction['CONTINUE'].action_data || [];
        const rCont = document.getElementById('continue-reason');
        if(rCont) rCont.value = existingWizardAction['CONTINUE'].reason || '';
    } else {
        const rCont = document.getElementById('continue-reason');
        if(rCont) rCont.value = '';
    }
    if (existingWizardAction['CANCEL']) {
        prefillCancel = existingWizardAction['CANCEL'].action_data || [];
        const rCanc = document.getElementById('cancel-reason');
        if(rCanc) rCanc.value = existingWizardAction['CANCEL'].reason || '';
    } else {
        const rCanc = document.getElementById('cancel-reason');
        if(rCanc) rCanc.value = '';
    }

    const masterCb = document.querySelector('input[onclick="toggleAllWizardPOs(this)"]');
    if (masterCb) masterCb.checked = false;

    const blankRows = [1, 2, 3, 4];
    continueBody.innerHTML = blankRows.map((num, i) => {
        let wVal = '';
        let dVal = '';
        if (prefillContinue && prefillContinue[i]) {
            wVal = prefillContinue[i].weight || '';
            dVal = prefillContinue[i].delivery_date || '';
            if (dVal && !dVal.match(/^\d{4}-\d{2}-\d{2}$/)) {
                const parsedDate = new Date(dVal);
                if (!isNaN(parsedDate.getTime())) {
                    const y = parsedDate.getFullYear();
                    const m = String(parsedDate.getMonth() + 1).padStart(2, '0');
                    const d = String(parsedDate.getDate()).padStart(2, '0');
                    dVal = `${y}-${m}-${d}`;
                }
            }
        }
        return `
        <tr class="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
            <td class="px-4 py-2 font-bold text-gray-400">${num.toString().padStart(2, '0')}</td>
            <td class="px-4 py-2">
                <input type="number" step="0.001" value="${wVal}" placeholder="0.000"
                    oninput="updateContinueTotal()" class="wizard-edit-weight w-full bg-transparent border-b border-gray-100 dark:border-gray-700 focus:border-blue-500 focus:ring-0 text-right font-black text-blue-900 dark:text-blue-100 p-0 transition-all">
            </td>
            <td class="px-4 py-2">
                <input type="date" value="${dVal}" 
                    class="wizard-edit-date w-full bg-transparent border-b border-gray-100 dark:border-gray-700 focus:border-blue-500 focus:ring-0 font-bold text-gray-700 dark:text-gray-300 p-0 transition-all text-xs">
            </td>
            <td class="px-4 py-2 text-center text-[10px] font-black text-amber-500 uppercase tracking-tighter">
                Pending
            </td>
        </tr>
    `}).join('');

    // Step 3: Cancel Items
    const cancelBody = document.getElementById('wizard-cancel-items');
    cancelBody.innerHTML = wizardData.map((item, idx) => {
        let isChecked = false;
        if (prefillCancel) {
            isChecked = prefillCancel.some(pc => pc.po_number === item.po_number);
        }
        return `
        <tr class="hover:bg-red-50 dark:hover:bg-red-900/10 transition-colors cursor-pointer" onclick="const cb = this.querySelector('.wizard-po-checkbox'); cb.checked = !cb.checked; updateCancelTotal();">
            <td class="px-4 py-3" onclick="event.stopPropagation()">
                <input type="checkbox" class="wizard-po-checkbox w-4 h-4 text-red-600 bg-gray-100 border-gray-300 rounded focus:ring-red-500" data-idx="${idx}" onchange="updateCancelTotal()" ${isChecked ? 'checked' : ''}>
            </td>
            <td class="px-4 py-2 font-black text-gray-800 dark:text-gray-200 tracking-tighter">${item.po_number || 'N/A'}</td>
            <td class="px-4 py-2 font-bold text-gray-500 uppercase">${item.po_date || 'N/A'}</td>
            <td class="px-4 py-2 text-right font-bold text-gray-700 dark:text-gray-300">${parseFloat(item.order_piece || 0).toLocaleString()}</td>
            <td class="px-4 py-3 font-medium text-gray-900 dark:text-white" onclick="event.stopPropagation()">${parseFloat(item.total_weight || 0).toFixed(3)}</td>
        </tr>
    `}).join('');
    
    updateContinueTotal();
    updateCancelTotal();
}

function updateContinueTotal() {
    const inputs = document.querySelectorAll('.wizard-edit-weight');
    let total = 0;
    inputs.forEach(input => {
        total += parseFloat(input.value || 0);
    });
    const totalEl = document.getElementById('wizard-continue-total');
    if (totalEl) totalEl.textContent = total.toFixed(3);
}

function updateCancelTotal() {
    const checkboxes = document.querySelectorAll('.wizard-po-checkbox');
    let totalWeight = 0;
    let count = 0;
    let overallWeight = 0;
    
    if (wizardData) {
        wizardData.forEach(item => {
            overallWeight += parseFloat(item.total_weight || 0);
        });
    }
    
    checkboxes.forEach(cb => {
        if (cb.checked) {
            const idx = parseInt(cb.dataset.idx);
            totalWeight += parseFloat(wizardData[idx].total_weight || 0);
            count++;
        }
    });
    
    const balanceWeight = Math.max(0, overallWeight - totalWeight);
    
    document.getElementById('wizard-cancel-total').textContent = totalWeight.toFixed(3);
    
    const balanceEl = document.getElementById('wizard-cancel-balance');
    if (balanceEl) balanceEl.textContent = balanceWeight.toFixed(3);
    
    const countEl = document.getElementById('wizard-cancel-po-count');
    if (countEl) countEl.textContent = `Selected Purchase Orders (${count})`;
}

function toggleAllWizardPOs(master) {
    document.querySelectorAll('.wizard-po-checkbox').forEach(cb => cb.checked = master.checked);
    updateCancelTotal();
}

async function submitWizardAction(clickedType) {
    const continueReasonEl = document.getElementById('continue-reason');
    const cancelReasonEl = document.getElementById('cancel-reason');
    
    const continueReason = continueReasonEl ? continueReasonEl.value.trim() : '';
    const cancelReason = cancelReasonEl ? cancelReasonEl.value.trim() : '';
    
    let continueData = [];
    let cancelData = [];
    
    // Parse Continue forms
    let proposedContinueTotal = 0;
    document.querySelectorAll('.wizard-edit-weight').forEach((el, index) => {
        const weightValue = parseFloat(el.value);
        const dateEl = document.querySelectorAll('.wizard-edit-date')[index];
        const dateValue = dateEl ? dateEl.value : '';
        
        if (!isNaN(weightValue) && weightValue > 0) {
            proposedContinueTotal += weightValue;
            continueData.push({
                weight: weightValue,
                delivery_date: dateValue
            });
        }
    });

    // Parse Cancel forms
    let cancelTotal = 0;
    document.querySelectorAll('.wizard-po-checkbox').forEach(cb => {
        if (cb.checked) {
            const idx = parseInt(cb.dataset.idx);
            cancelData.push(wizardData[idx]);
            cancelTotal += parseFloat(wizardData[idx].total_weight || 0);
        }
    });

    if (continueData.length === 0 && cancelData.length === 0) {
        showToast('Please enter weight details or select POs to cancel.', 'warning');
        return;
    }

    if (continueData.length > 0 && !continueReason) {
        showToast('Please provide a reason for the rescheduled order before proceeding.', 'warning');
        return;
    }
    
    if (cancelData.length > 0 && !cancelReason) {
        showToast('Please provide a reason for the cancelled order before proceeding.', 'warning');
        return;
    }
    
    // Validation: Total Continue <= Overall - Total Cancel
    let overallWeight = 0;
    if (wizardData) {
        wizardData.forEach(item => {
            overallWeight += parseFloat(item.total_weight || 0);
        });
    }
    let maxAllowed = overallWeight - cancelTotal;
    if (proposedContinueTotal > maxAllowed + 0.001) {
        showToast(`Total rescheduled weight (${proposedContinueTotal.toFixed(3)}) cannot exceed the balance weight (${maxAllowed.toFixed(3)}).`, 'error');
        return;
    }
    
    // Disable buttons
    const submitBtn = clickedType === 'continue' ? document.getElementById('wizard-sub-btn') : document.getElementById('wizard-cancel-btn');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<span class="material-symbols-outlined text-sm align-middle animate-spin">refresh</span> Processing...';
    submitBtn.disabled = true;

    try {
        let promises = [];
        const token = localStorage.getItem('access_token');
        
        if (continueData.length > 0 || (existingWizardAction && existingWizardAction['CONTINUE'])) {
            const payload = {
                ...currentContext,
                action_type: 'CONTINUE',
                reason: continueReason || 'Cleared',
                action_data: continueData
            };
            promises.push(
                fetch('/api/pending-acceptance-feedback/wizard-action', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(payload)
                }).then(async r => { if (!r.ok) throw new Error(await r.text()); })
            );
        }
        
        if (cancelData.length > 0 || (existingWizardAction && existingWizardAction['CANCEL'])) {
            const payload = {
                ...currentContext,
                action_type: 'CANCEL',
                reason: cancelReason || 'Cleared',
                action_data: cancelData
            };
            promises.push(
                fetch('/api/pending-acceptance-feedback/wizard-action', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(payload)
                }).then(async r => { if (!r.ok) throw new Error(await r.text()); })
            );
        }
        
        await Promise.all(promises);

        showToast('Action(s) saved successfully!', 'success');
        closeExpiredOrderWizard();
        loadViewData(currentStatusFilter); // Refresh data
        
    } catch (error) {
        console.error('Wizard save error:', error);
        showToast('An error occurred while saving. Please try again.', 'error');
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}
