let currentStatusFilter = 'pending_to_accept';
let currentZoom = parseFloat(localStorage.getItem('pending-acceptance-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('pending-acceptance-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

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
    // Perform reset filter while switching status filters
    clearFilterInputs();
    
    currentStatusFilter = filter;
    
    // Update button UI
    document.querySelectorAll('.status-filter-btn').forEach(btn => btn.classList.remove('active'));
    if (filter === 'pending_to_accept') {
        const btn = document.getElementById('btn-status-accept');
        if (btn) btn.classList.add('active');
    } else if (filter === 'pending_to_deliver') {
        const btn = document.getElementById('btn-status-deliver');
        if (btn) btn.classList.add('active');
    } else if (filter === 'hallmarking_delayed') {
        const btn = document.getElementById('btn-status-hallmarking-delayed');
        if (btn) btn.classList.add('active');
    }
    
    // Apply filters. 
    const delayEnable = document.getElementById('filter-delay-enable');
    const delayInput = document.getElementById('filter-delay');

    if (filter === 'pending_to_deliver_not_barcoded') {
        if (delayEnable) {
            delayEnable.checked = true;
            delayEnable.disabled = false;
            if (delayInput) {
                if (delayInput.value === '' || delayInput.value === '0') {
                    delayInput.value = '5';
                }
                delayInput.disabled = false;
            }
        }
    } else if (filter === 'hallmarking_delayed') {
        if (delayEnable) {
            delayEnable.checked = true;
            delayEnable.disabled = true;
        }
        if (delayInput) {
            delayInput.value = '2';
            delayInput.disabled = true;
        }
    } else {
        if (delayEnable) delayEnable.disabled = false;
        if (delayInput) delayInput.disabled = false;
    }
    
    // Toggle new filter visibility
    const officeContainer = document.getElementById('filter-container-office');
    const hmAgentContainer = document.getElementById('filter-container-hm-agent');
    if (filter === 'hallmarking_delayed') {
        if (officeContainer) officeContainer.style.display = 'block';
        if (hmAgentContainer) hmAgentContainer.style.display = 'block';
    } else {
        if (officeContainer) officeContainer.style.display = 'none';
        if (hmAgentContainer) hmAgentContainer.style.display = 'none';
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

    const branchType = document.getElementById('filter-branch-type')?.value;
    if (branchType) urlParams.set('branch_type', branchType);
    else urlParams.delete('branch_type');

    const collection = document.getElementById('filter-collection')?.value;
    if (collection) urlParams.set('collection', collection);
    else urlParams.delete('collection');

    const office = document.getElementById('filter-office')?.value;
    if (office) urlParams.set('office', office);
    else urlParams.delete('office');

    const hmAgent = document.getElementById('filter-hm-agent')?.value;
    if (hmAgent) urlParams.set('hm_agent', hmAgent);
    else urlParams.delete('hm_agent');

    const delayEnable = document.getElementById('filter-delay-enable')?.checked;
    const delay = document.getElementById('filter-delay')?.value;
    if (delayEnable) {
        urlParams.set('delay_enabled', 'true');
        if (delay !== '') urlParams.set('delay', delay);
        else urlParams.delete('delay');
    } else {
        urlParams.set('delay_enabled', 'false');
        urlParams.delete('delay');
    }

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

function clearFilterInputs() {
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

    const branchType = document.getElementById('filter-branch-type');
    if (branchType) branchType.value = '';

    const collection = document.getElementById('filter-collection');
    if (collection) collection.value = '';

    const office = document.getElementById('filter-office');
    if (office) office.value = '';

    const hmAgent = document.getElementById('filter-hm-agent');
    if (hmAgent) hmAgent.value = '';

    const delay = document.getElementById('filter-delay');
    if (delay) {
        delay.value = '5';
        delay.disabled = false;
    }
    const delayEnable = document.getElementById('filter-delay-enable');
    if (delayEnable) {
        delayEnable.checked = false;
        delayEnable.disabled = false;
    }

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
}

function resetGlobalFilters() {
    const urlParams = new URLSearchParams();
    clearFilterInputs();

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
    const tableArea = document.getElementById('table-area');
    if (tableArea) tableArea.style.zoom = currentZoom;
    
    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }

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
    if (urlParams.get('branch_type')) {
        const sel = document.getElementById('filter-branch-type');
        if (sel) sel.value = urlParams.get('branch_type');
    }
    if (urlParams.get('collection')) {
        const sel = document.getElementById('filter-collection');
        if (sel) sel.value = urlParams.get('collection');
    }
    if (urlParams.get('office')) {
        const sel = document.getElementById('filter-office');
        if (sel) sel.value = urlParams.get('office');
    }
    if (urlParams.get('hm_agent')) {
        const sel = document.getElementById('filter-hm-agent');
        if (sel) sel.value = urlParams.get('hm_agent');
    }
    const statusFilter = urlParams.get('status_filter') || 'pending_to_accept';
    currentStatusFilter = statusFilter;

    // Update button UI
    document.querySelectorAll('.status-filter-btn').forEach(btn => btn.classList.remove('active'));
    const btnMap = {
        'pending_to_accept': 'btn-status-accept',
        'pending_to_deliver': 'btn-status-deliver',
        'pending_to_deliver_not_barcoded': 'btn-status-not-barcoded',
        'hallmarking_delayed': 'btn-status-hallmarking-delayed'
    };
    const activeBtn = document.getElementById(btnMap[statusFilter]);
    if (activeBtn) activeBtn.classList.add('active');

    // Handle Delay Filter state
    const delayEnable = document.getElementById('filter-delay-enable');
    const delayInput = document.getElementById('filter-delay');
    const delayEnabledArg = urlParams.get('delay_enabled');
    const delayArg = urlParams.get('delay');

    if (statusFilter === 'hallmarking_delayed') {
        if (delayEnable) {
            delayEnable.checked = true;
            delayEnable.disabled = true;
        }
        if (delayInput) {
            delayInput.value = '2';
            delayInput.disabled = true;
        }
        // Visibility for HD specific filters
        const officeContainer = document.getElementById('filter-container-office');
        const hmAgentContainer = document.getElementById('filter-container-hm-agent');
        if (officeContainer) officeContainer.style.display = 'block';
        if (hmAgentContainer) hmAgentContainer.style.display = 'block';
    } else {
        if (delayEnable) {
            delayEnable.disabled = false;
            if (delayArg) {
                delayEnable.checked = (delayEnabledArg !== 'false');
            } else if (statusFilter === 'pending_to_deliver_not_barcoded' && delayEnabledArg !== 'false') {
                delayEnable.checked = true;
            } else {
                delayEnable.checked = (delayEnabledArg === 'true');
            }
        }
        if (delayInput) {
            delayInput.disabled = false;
            delayInput.value = delayArg || (statusFilter === 'pending_to_deliver_not_barcoded' ? '5' : '5');
        }
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
    const withFeedback = parseInt(stats.withFeedback || 0);
    
    const urlParams = new URLSearchParams(window.location.search);
    const statusFilter = urlParams.get('status_filter') || 'pending_to_accept';

    const fmt = (v) => new Intl.NumberFormat('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(v);

    const card1 = document.getElementById('stat-order-wt').parentElement;
    const card2 = document.getElementById('stat-accepted-wt').parentElement;
    const card3 = document.getElementById('stat-pending-wt').parentElement;
    const card4 = document.getElementById('stat-contextual-metric').parentElement;
    const card5 = document.getElementById('card-with-feedback');

    if (statusFilter === 'pending_to_deliver') {
        const wt = parseFloat(stats.totalPendingToDeliverWt || 0);
        const pcs = parseInt(stats.totalPendingToDeliverPcs || 0);
        
        card1.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-blue-premium">leaderboard</span>Total Order Wt`;
        document.getElementById('stat-order-wt').textContent = fmt(orderWt);
        
        card2.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-emerald-premium">check_circle</span>Accepted Wt`;
        document.getElementById('stat-accepted-wt').textContent = fmt(acceptedWt);

        card3.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-indigo-600">local_shipping</span>Pending Deliver Wt`;
        document.getElementById('stat-pending-wt').textContent = fmt(wt);
        document.getElementById('stat-pending-wt').className = 'stat-val text-orange-600';
        
        card4.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-blue-600">inventory_2</span>Pending Deliver Pcs`;
        document.getElementById('stat-contextual-metric').textContent = pcs.toLocaleString();
        document.getElementById('stat-contextual-metric').className = 'stat-val';

        if (card5) {
            card5.classList.remove('hidden');
            const fbElem = document.getElementById('stat-with-feedback');
            if (fbElem) fbElem.textContent = withFeedback.toLocaleString();
        }
    } else if (statusFilter === 'pending_to_deliver_not_barcoded') {
        const wt = parseFloat(stats.totalNotBarcodedWt || 0);
        const pcs = parseInt(stats.totalNotBarcodedPcs || 0);
        
        card1.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-blue-premium">leaderboard</span>Total Order Wt`;
        document.getElementById('stat-order-wt').textContent = fmt(orderWt);
        
        card2.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-emerald-premium">check_circle</span>Accepted Wt`;
        document.getElementById('stat-accepted-wt').textContent = fmt(acceptedWt);

        card3.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-orange-600">barcode_scanner</span>Not Barcoded Wt`;
        document.getElementById('stat-pending-wt').textContent = fmt(wt);
        document.getElementById('stat-pending-wt').className = 'stat-val text-orange-600';
        
        card4.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-cyan-600">pin</span>Not Barcoded Pcs`;
        document.getElementById('stat-contextual-metric').textContent = pcs.toLocaleString();
        document.getElementById('stat-contextual-metric').className = 'stat-val';

        if (card5) {
            card5.classList.remove('hidden');
            const fbElem = document.getElementById('stat-with-feedback');
            if (fbElem) fbElem.textContent = withFeedback.toLocaleString();
        }
    } else if (statusFilter === 'hallmarking_delayed') {
        const pcs = parseInt(stats.totalPieces || 0);
        const wt = parseFloat(stats.totalWeight || 0);
        const withoutFeedback = parseInt(stats.withoutFeedback || 0);

        card1.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-indigo-600">inventory_2</span>Total Pieces`;
        document.getElementById('stat-order-wt').textContent = pcs.toLocaleString();

        card2.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-emerald-premium">check_circle</span>Total Weight`;
        document.getElementById('stat-accepted-wt').textContent = fmt(wt);

        card3.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-red-600">chat_error</span>Without Feedback`;
        document.getElementById('stat-pending-wt').textContent = withoutFeedback.toLocaleString();
        document.getElementById('stat-pending-wt').className = 'stat-val';

        card4.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-emerald-premium">chat_bubble</span>With Feedback`;
        document.getElementById('stat-contextual-metric').textContent = withFeedback.toLocaleString();
        document.getElementById('stat-contextual-metric').className = 'stat-val text-emerald-premium';

        if (card5) card5.classList.add('hidden');
    } else {
        const pendingWt = parseFloat(stats.totalPendingToAcceptedWt || 0);
        const withoutFeedback = parseInt(stats.withoutFeedback || 0);

        card1.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-blue-premium">leaderboard</span>Total Order Wt`;
        document.getElementById('stat-order-wt').textContent = fmt(orderWt);

        card2.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-emerald-premium">check_circle</span>Accepted Wt`;
        document.getElementById('stat-accepted-wt').textContent = fmt(acceptedWt);

        card3.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-orange-premium">pending_actions</span>Pending Wt`;
        document.getElementById('stat-pending-wt').textContent = fmt(pendingWt);
        document.getElementById('stat-pending-wt').className = 'stat-val text-orange-premium';
        
        card4.querySelector('.stat-label').innerHTML = `<span class="material-symbols-outlined text-red-600">chat_error</span>Without Feedback`;
        document.getElementById('stat-contextual-metric').textContent = withoutFeedback.toLocaleString();
        document.getElementById('stat-contextual-metric').className = 'stat-val';

        if (card5) {
            card5.classList.remove('hidden');
            const fbElem = document.getElementById('stat-with-feedback');
            if (fbElem) fbElem.textContent = withFeedback.toLocaleString();
        }
    }
}

// Modal stuff
function openFeedbackModal(collectionOwner, makeOwner, supplier, collection, currFeedback, currCategory) {
    document.getElementById('fb_collection_owner').value = collectionOwner;
    document.getElementById('fb_make_owner').value = makeOwner;
    document.getElementById('fb_supplier').value = supplier;
    document.getElementById('fb_collection').value = collection;
    
    // Hidden HD fields
    if (!document.getElementById('fb_office')) {
        const form = document.querySelector('#feedbackModal form') || document.getElementById('feedbackModal');
        const h1 = document.createElement('input'); h1.type = 'hidden'; h1.id = 'fb_office'; h1.name = 'office';
        const h2 = document.createElement('input'); h2.type = 'hidden'; h2.id = 'fb_hm_agent'; h2.name = 'hm_agent';
        form.appendChild(h1);
        form.appendChild(h2);
    }
    
    const btn = event.currentTarget || {};
    document.getElementById('fb_office').value = btn.dataset?.office || '';
    document.getElementById('fb_hm_agent').value = btn.dataset?.hmAgent || '';

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
        status_filter: currentStatusFilter,
        office: document.getElementById('fb_office')?.value || '',
        hm_agent: document.getElementById('fb_hm_agent')?.value || ''
    };

    if (!payload.feedback_text.trim()) {
        showToast('Required', "Feedback cannot be empty", 'warning');
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
        showToast('Error', err.message || "Failed to save feedback", 'error');
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
    
    // Add HD context if applicable
    if (statusFilter === 'hallmarking_delayed') {
        const btn = event.currentTarget; // Should be row or button
        if (btn) {
            urlParams.set('office', btn.dataset.office || '');
            urlParams.set('hm_agent', btn.dataset.hmAgent || '');
        }
    }
    
    const delayEnable = document.getElementById('filter-delay-enable')?.checked;
    const delay = document.getElementById('filter-delay')?.value;
    if (delayEnable) {
        urlParams.set('delay_enabled', 'true');
        if (delay !== '') urlParams.set('delay', delay);
    } else {
        urlParams.set('delay_enabled', 'false');
    }

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
        showToast('Error', 'Could not load expired order details.', 'error');
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
        const actionData = existingWizardAction['CONTINUE'].action_data;
        if (actionData && !Array.isArray(actionData) && actionData.schedules) {
            prefillContinue = actionData.schedules;
        } else {
            prefillContinue = actionData || [];
        }
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
    let continueTotal = 0;
    inputs.forEach(input => {
        continueTotal += parseFloat(input.value || 0);
    });
    const totalEl = document.getElementById('wizard-continue-total');
    if (totalEl) totalEl.textContent = continueTotal.toFixed(3);
    
    // Determine overall and cancel components for balance
    let overallWeight = 0;
    if (wizardData) {
        wizardData.forEach(item => {
            overallWeight += parseFloat(item.total_weight || 0);
        });
    }
    
    let cancelTotal = 0;
    document.querySelectorAll('.wizard-po-checkbox').forEach(cb => {
        if (cb.checked) {
            const idx = parseInt(cb.dataset.idx);
            cancelTotal += parseFloat(wizardData[idx].total_weight || 0);
        }
    });
    
    const balanceWeight = Math.max(0, overallWeight - cancelTotal - continueTotal);
    const balanceElFiltered = document.getElementById('wizard-continue-balance');
    if (balanceElFiltered) balanceElFiltered.textContent = balanceWeight.toFixed(3);
}

function updateCancelTotal() {
    const checkboxes = document.querySelectorAll('.wizard-po-checkbox');
    let totalWeight = 0; // Current selection in this tab
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

    // Also factor in current Continue inputs for balance
    let continueTotal = 0;
    document.querySelectorAll('.wizard-edit-weight').forEach(input => {
        continueTotal += parseFloat(input.value || 0);
    });
    
    const balanceWeight = Math.max(0, overallWeight - totalWeight - continueTotal);
    
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
    let unselectedData = [];
    document.querySelectorAll('.wizard-po-checkbox').forEach(cb => {
        const idx = parseInt(cb.dataset.idx);
        if (cb.checked) {
            cancelData.push(wizardData[idx]);
            cancelTotal += parseFloat(wizardData[idx].total_weight || 0);
        } else {
            unselectedData.push(wizardData[idx]);
        }
    });

    if (continueData.length === 0 && cancelData.length === 0) {
        showToast('Warning', 'Please enter weight details or select POs to cancel.', 'warning');
        return;
    }

    if (continueData.length > 0 && !continueReason) {
        showToast('Warning', 'Please provide a reason for the rescheduled order before proceeding.', 'warning');
        return;
    }
    
    if (cancelData.length > 0 && !cancelReason) {
        showToast('Warning', 'Please provide a reason for the cancelled order before proceeding.', 'warning');
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
        showToast('Error', `Total rescheduled weight (${proposedContinueTotal.toFixed(3)}) cannot exceed the balance weight (${maxAllowed.toFixed(3)}).`, 'error');
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
        
        if (clickedType === 'continue' && (continueData.length > 0 || (existingWizardAction && existingWizardAction['CONTINUE']))) {
            const payload = {
                ...currentContext,
                action_type: 'CONTINUE',
                reason: continueReason || 'Cleared',
                action_data: {
                    schedules: continueData,
                    unselected_pos: unselectedData
                }
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
        
        if (clickedType === 'cancel' && (cancelData.length > 0 || (existingWizardAction && existingWizardAction['CANCEL']))) {
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

        showToast('Success', 'Action(s) saved successfully!', 'success');
        closeExpiredOrderWizard();
        loadViewData(currentStatusFilter); // Refresh data
        
    } catch (error) {
        console.error('Wizard save error:', error);
        let errorMsg = 'An error occurred while saving. Please try again.';
        try {
            const parsed = JSON.parse(error.message);
            if (parsed && parsed.message) {
                errorMsg = parsed.message;
            }
        } catch (e) {
            // Fallback: If not JSON, use the raw error message if it's brief
            if (error.message && error.message.length < 200) {
                errorMsg = error.message;
            }
        }
        showToast('Save Error', errorMsg, 'error');
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

async function exportToExcel() {
    const btn = document.getElementById('btn-export-excel');
    const icon = document.getElementById('export-btn-icon');
    const label = document.getElementById('export-btn-label');
    const originalIcon = icon.innerText;
    const originalLabel = label.innerText;

    try {
        // Disable button and show loading state
        btn.disabled = true;
        icon.innerText = 'sync';
        icon.classList.add('animate-spin');
        label.innerText = 'Queuing...';

        const filters = {
            search: document.getElementById('hierarchy-search')?.value || '',
            status_filter: currentStatusFilter,
            feedback_status: document.getElementById('filter-feedback-status')?.value || '',
            collection_owner: document.getElementById('filter-collection-owner')?.value || '',
            make_owner: document.getElementById('filter-make-owner')?.value || '',
            supplier: document.getElementById('filter-supplier')?.value || '',
            collection: document.getElementById('filter-collection')?.value || '',
            classification: document.getElementById('filter-classification')?.value || '',
            order_type: document.getElementById('filter-order-type')?.value || '',
            order_request_type: document.getElementById('filter-order-request-type')?.value || '',
            branch_type: document.getElementById('filter-branch-type')?.value || '',
            delay: document.getElementById('filter-delay')?.value || '',
            delay_enabled: document.getElementById('filter-delay-enable')?.checked || false,
            from_date: document.getElementById('filter-from-date')?.value || '',
            to_date: document.getElementById('filter-to-date')?.value || '',
            enable_date_filter: document.getElementById('filter-date-enable')?.checked || false,
            feedback_from_date: document.getElementById('filter-feedback-from-date')?.value || '',
            feedback_to_date: document.getElementById('filter-feedback-to-date')?.value || '',
            enable_feedback_date_filter: document.getElementById('filter-feedback-date-enable')?.checked || false,
            office: document.getElementById('filter-office')?.value || '',
            hm_agent: document.getElementById('filter-hm-agent')?.value || ''
        };

        const response = await fetch('/api/pending-acceptance-feedback/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({
                filters: filters,
                socket_id: window.socket?.id
            })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.message || 'Failed to queue export');
        }

        showToast('Success', 'Export job enqueued. You will be notified when the file is ready.', 'success');

    } catch (error) {
        console.error('Export error:', error);
        showToast('Error', error.message || 'Failed to trigger export', 'error');
    } finally {
        // Restore button state
        btn.disabled = false;
        icon.innerText = originalIcon;
        icon.classList.remove('animate-spin');
        label.innerText = originalLabel;
    }
}
