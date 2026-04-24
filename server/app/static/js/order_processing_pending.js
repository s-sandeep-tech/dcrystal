/**
 * Order Processing Pending Status and Feedback Report JS
 */

let currentZoom = parseFloat(localStorage.getItem('opp-report-zoom')) || 1.0;

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;
    if (reset) currentZoom = 1.0;
    else currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    tableArea.style.zoom = currentZoom;
    localStorage.setItem('opp-report-zoom', currentZoom);
    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
}

async function loadViewData() {
    const viewContainer = document.getElementById('view-container');
    const loader = document.getElementById('loader-overlay');
    if (!viewContainer) return;
    if (loader) loader.classList.remove('hidden');

    const urlParams = new URLSearchParams(window.location.search);
    
    // Sync active button state
    document.querySelectorAll('.status-filter-btn').forEach(btn => btn.classList.remove('active'));
    let btnId = 'btn-status-barcode';
    const statusVal = urlParams.get('status');
    if (statusVal === 'hm_issue') btnId = 'btn-status-hm-issue';
    else if (statusVal === 'hm_return') btnId = 'btn-status-hm-return';
    else if (statusVal === 'hm_qc_issue') btnId = 'btn-status-hm-qc-issue';
    else if (statusVal === 'qc_issue_receipt') btnId = 'btn-status-qc-issue-receipt';
    else if (statusVal === 'qc_completed_invoice') btnId = 'btn-status-qc-completed-invoice';
    else if (statusVal === 'invoice_completed_deliver') btnId = 'btn-status-invoice-completed-deliver';
    const activeBtn = document.getElementById(btnId);
    if (activeBtn) activeBtn.classList.add('active');

    try {
        const response = await fetch(`/partial/order-processing-pending-status?${urlParams.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const html = await response.text();
        
        if (!html.trim()) {
            viewContainer.innerHTML = `
                <div class="flex flex-col items-center justify-center p-12 text-gray-400 h-full">
                    <span class="material-symbols-outlined text-4xl mb-4">search_off</span>
                    <span class="text-xs font-bold uppercase tracking-widest">No matching records found for this status</span>
                </div>
            `;
            // Reset stats and pagination
            updatePaginationControls({ page: 1, perPage: 50, total: 0, hasPrev: 'false', hasNext: 'false' });
            updateStatsCards({ totalPieces: 0, totalWeight: '0.000', withFeedback: 0, withoutFeedback: 0 });
        } else {
            viewContainer.innerHTML = html;
            const metaDiv = viewContainer.querySelector('.pagination-meta');
            if (metaDiv) updatePaginationControls(metaDiv.dataset);
            const statsDiv = viewContainer.querySelector('.stats-meta');
            if (statsDiv) updateStatsCards(statsDiv.dataset);
        }
        
    } catch (error) {
        console.error('Error loading view:', error);
        viewContainer.innerHTML = `<div class="p-8 text-center text-red-500">Error loading data: ${error.message}</div>`;
    } finally {
        if (loader) loader.classList.add('hidden');
        // Fallback: search for any internal loader in viewContainer and hide it
        const innerLoader = viewContainer.querySelector('.animate-spin');
        if (innerLoader && innerLoader.parentElement.textContent.includes('Loading')) {
             innerLoader.parentElement.classList.add('hidden');
        }
    }
}

function setStatus(status) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('status', status);
    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function updateUrlAndLoad(params) {
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    loadViewData();
}

function applyFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    
    const searchVal = document.getElementById('hierarchy-search')?.value;
    if (searchVal) urlParams.set('search', searchVal); else urlParams.delete('search');

    const fields = [
        'collection_owner', 'collection', 'branch', 'supplier', 
        'make_owner', 'order_type', 'order_request_type', 'feedback_status', 'status',
        'business_head_name', 'make'
    ];
    fields.forEach(f => {
        const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
        if (el && el.value) urlParams.set(f, el.value); else if (f !== 'status') urlParams.delete(f);
    });

    // Checkboxes
    ['is_qc_completed', 'is_rate_requisition_completed', 'is_invoiced'].forEach(f => {
        const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
        if (el && el.checked) urlParams.set(f, 'true'); else urlParams.delete(f);
    });

    urlParams.set('page', 1);
    updateUrlAndLoad(urlParams);
}

function resetFilters() {
    const cleanUrl = window.location.pathname;
    window.location.href = cleanUrl;
}

function onSearchInput(value) {
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => applyFilters(), 500);
}

function updatePaginationControls(meta) {
    const page = parseInt(meta.page);
    const perPage = parseInt(meta.perPage);
    const total = parseInt(meta.total);
    const hasPrev = meta.hasPrev === 'true';
    const hasNext = meta.hasNext === 'true';

    const start = total > 0 ? (page - 1) * perPage + 1 : 0;
    const end = Math.min(page * perPage, total);
    
    const infoSpan = document.getElementById('pagination-info');
    if (infoSpan) infoSpan.textContent = `${start}-${end} of ${total}`;
    
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    if (btnPrev) {
        btnPrev.disabled = !hasPrev;
        btnPrev.onclick = () => changePage(page - 1);
    }
    if (btnNext) {
        btnNext.disabled = !hasNext;
        btnNext.onclick = () => changePage(page + 1);
    }
}

function changePage(page) {
    if (page < 1) return;
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

function updateStatsCards(stats) {
    if (!stats) return;
    const p = document.getElementById('stat-total-pieces');
    const w = document.getElementById('stat-total-weight');
    const wf = document.getElementById('stat-with-feedback');
    const wof = document.getElementById('stat-without-feedback');
    
    if (p) p.textContent = stats.totalPieces || '0';
    if (w) w.textContent = stats.totalWeight || '0.000';
    if (wf) wf.textContent = stats.withFeedback || '0';
    if (wof) wof.textContent = stats.withoutFeedback || '0';

    // Update dynamic titles
    const urlParams = new URLSearchParams(window.location.search);
    const status = urlParams.get('status') || 'pending';
    
    let piecesLabel = 'Total Pieces';
    let weightLabel = 'Total Weight';
    
    if (status === 'pending') {
        piecesLabel = 'Barcoded Pieces';
        weightLabel = 'Barcoded Weight';
    } else if (status === 'hm_issue') {
        piecesLabel = 'HM Issue Pieces';
        weightLabel = 'HM Issue Weight';
    } else if (status === 'hm_return') {
        piecesLabel = 'HM Return Pieces';
        weightLabel = 'HM Return Weight';
    } else if (status === 'hm_qc_issue') {
        piecesLabel = 'QC Issue Pieces';
        weightLabel = 'QC Issue Weight';
    } else if (status === 'qc_issue_receipt') {
        piecesLabel = 'QC Pending Pieces';
        weightLabel = 'QC Pending Weight';
    } else if (status === 'qc_completed_invoice') {
        piecesLabel = 'Invoice Pending Pieces';
        weightLabel = 'Invoice Pending Weight';
    } else if (status === 'invoice_completed_deliver') {
        piecesLabel = 'Delivery Pending Pieces';
        weightLabel = 'Delivery Pending Weight';
    }

    const lp = document.getElementById('label-total-pieces');
    const lw = document.getElementById('label-total-weight');
    
    if (lp) lp.textContent = piecesLabel;
    if (lw) lw.textContent = weightLabel;
}

/**
 * Hierarchical Toggle Logic
 */
function toggleRow(id) {
    const row = document.querySelector(`tr[data-id="${id}"]`);
    if (!row) return;

    const icon = row.querySelector('.toggle-icon');
    if (!icon) return; // If there's no toggle icon, it's a leaf node.

    const isExpanded = row.dataset.expanded === "true";
    row.dataset.expanded = !isExpanded;

    if (icon) {
        icon.style.transform = isExpanded ? 'rotate(0deg)' : 'rotate(90deg)';
    }

    if (isExpanded) {
        collapseDescendants(id);
    } else {
        // Expand direct children only
        const children = document.querySelectorAll(`tr[data-parent="${id}"]`);
        children.forEach(child => child.classList.remove('hidden'));
    }
}

function collapseDescendants(parentId) {
    const children = document.querySelectorAll(`tr[data-parent="${parentId}"]`);
    children.forEach(child => {
        child.classList.add('hidden');
        child.dataset.expanded = "false";
        const icon = child.querySelector('.toggle-icon');
        if (icon) icon.style.transform = 'rotate(0deg)';
        collapseDescendants(child.dataset.id);
    });
}

/**
 * Modal Interactions
 */
function openFeedbackModal(owner, coll, branch, supplier, text, cat) {
    document.getElementById('fb_collection_owner').value = owner;
    document.getElementById('fb_collection').value = coll;
    document.getElementById('fb_branch').value = branch;
    document.getElementById('fb_supplier').value = supplier;
    
    document.getElementById('feedbackModalContext').textContent = `${owner} | ${coll} | ${branch} | ${supplier}`;
    
    const ta = document.getElementById('feedbackText');
    const tc = document.getElementById('feedbackCategory');
    if (ta) ta.value = text || '';
    if (tc) tc.value = cat || '';
    
    document.getElementById('feedbackModal').classList.remove('hidden');
}

function closeFeedbackModal() {
    document.getElementById('feedbackModal').classList.add('hidden');
    document.getElementById('feedbackText').value = '';
    document.getElementById('feedbackCategory').value = '';
    
    const saveBtn = document.querySelector('#feedbackModal button[onclick*="save"]');
    if (saveBtn) saveBtn.setAttribute('onclick', 'saveFeedback()');
    
    // Clear all hidden inputs
    ['fb_hm_ro', 'fb_make_owner', 'fb_hallmark_agent', 'fb_collection_owner', 'fb_collection', 'fb_branch', 'fb_supplier', 'fb_order_branch', 'fb_party', 'fb_qc_ro'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
}

async function saveFeedback() {
    const payload = {
        collection_owner: document.getElementById('fb_collection_owner').value,
        collection: document.getElementById('fb_collection').value,
        branch: document.getElementById('fb_branch').value,
        supplier: document.getElementById('fb_supplier').value,
        feedback_text: document.getElementById('feedbackText').value,
        feedback_category: document.getElementById('feedbackCategory').value
    };

    if (!payload.feedback_text.trim()) {
        alert("Please enter feedback text.");
        return;
    }

    try {
        const response = await fetch('/api/order-processing-pending-status/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error('Failed to save feedback');
        closeFeedbackModal();
        loadViewData();
    } catch (error) {
        alert("Error saving feedback: " + error.message);
    }
}

async function showPODetailsModal(owner, coll, branch, supplier) {
    const modal = document.getElementById('poDetailsModal');
    const content = document.getElementById('poDetailsContent');
    if (!modal || !content) return;
    
    modal.classList.remove('hidden');
    content.innerHTML = `
        <div class="flex flex-col items-center justify-center p-12 text-gray-400">
            <span class="material-symbols-outlined text-4xl animate-spin mb-4 text-primary">sync</span>
            <span class="text-xs font-bold uppercase tracking-widest">Loading PO Details...</span>
        </div>
    `;

    try {
        const params = new URLSearchParams({ 
            collection_owner: owner, 
            collection: coll, 
            branch: branch, 
            supplier: supplier 
        });
        const response = await fetch(`/api/order-processing-pending-status/po-details?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) throw new Error("Failed to load PO details");
        content.innerHTML = await response.text();
    } catch (error) {
        content.innerHTML = `<div class="p-8 text-center text-red-500">Error: ${error.message}</div>`;
    }
}

function closePODetailsModal() {
    document.getElementById('poDetailsModal').classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
    adjustZoom(0);
    const urlParams = new URLSearchParams(window.location.search);
    
    // Auto-fill filters from URL
    if (urlParams.get('search')) {
        const s = document.getElementById('hierarchy-search');
        if (s) s.value = urlParams.get('search');
    }
    
    const fields = [
        'collection_owner', 'collection', 'branch', 'supplier', 
        'make_owner', 'order_type', 'order_request_type', 'feedback_status', 'status',
        'business_head_name'
    ];
    fields.forEach(f => {
        const val = urlParams.get(f);
        if (val) {
            const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
            if (el) el.value = val;
            
            if (f === 'status') {
                const statusVal = val;
                document.querySelectorAll('.status-filter-btn').forEach(btn => btn.classList.remove('active'));
                let btnId = 'btn-status-barcode';
                if (statusVal === 'hm_issue') btnId = 'btn-status-hm-issue';
                else if (statusVal === 'hm_return') btnId = 'btn-status-hm-return';
                else if (statusVal === 'hm_qc_issue') btnId = 'btn-status-hm-qc-issue';
                else if (statusVal === 'qc_issue_receipt') btnId = 'btn-status-qc-issue-receipt';
                else if (statusVal === 'qc_completed_invoice') btnId = 'btn-status-qc-completed-invoice';
                else if (statusVal === 'invoice_completed_deliver') btnId = 'btn-status-invoice-completed-deliver';
                const activeBtn = document.getElementById(btnId);
                if (activeBtn) activeBtn.classList.add('active');
            }
        }
    });

    // Sync Checkboxes
    ['is_qc_completed', 'is_rate_requisition_completed', 'is_invoiced'].forEach(f => {
        const val = urlParams.get(f);
        const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
        if (el) el.checked = (val === 'true');
    });

    loadViewData();
});

function openHMFeedbackModal(hm_ro, make_owner, collection_owner, collection, hallmark_agent, supplier, currentFeedback, currentCategory) {
    document.getElementById('fb_hm_ro').value = hm_ro;
    document.getElementById('fb_make_owner').value = make_owner;
    document.getElementById('fb_collection_owner').value = collection_owner;
    document.getElementById('fb_collection').value = collection;
    document.getElementById('fb_hallmark_agent').value = hallmark_agent;
    document.getElementById('fb_supplier').value = supplier;
    
    document.getElementById('feedbackText').value = currentFeedback || '';
    document.getElementById('feedbackCategory').value = currentCategory || '';
    document.getElementById('feedbackModalContext').textContent = `${hm_ro} > ${supplier}`;
    
    // Change save button to HM specific one
    const saveBtn = document.querySelector('#feedbackModal button[onclick="saveFeedback()"]');
    if (saveBtn) saveBtn.setAttribute('onclick', 'saveHMFeedback()');

    document.getElementById('feedbackModal').classList.remove('hidden');
}

async function saveHMFeedback() {
    const data = {
        hm_ro: document.getElementById('fb_hm_ro').value,
        make_owner: document.getElementById('fb_make_owner').value,
        collection_owner: document.getElementById('fb_collection_owner').value,
        collection: document.getElementById('fb_collection').value,
        hallmark_agent: document.getElementById('fb_hallmark_agent').value,
        supplier: document.getElementById('fb_supplier').value,
        feedback_text: document.getElementById('feedbackText').value,
        feedback_category: document.getElementById('feedbackCategory').value
    };

    if (!data.feedback_text || !data.feedback_category) {
        alert("Please enter both category and feedback");
        return;
    }

    try {
        const response = await fetch('/api/supplier-hm-issue/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            closeFeedbackModal();
            loadViewData();
            showToast("Feedback saved successfully!", "success");
        }
    } catch (err) {
        console.error("Error saving HM feedback:", err);
        showToast("Error saving feedback", "error");
    }
}

async function showHMIssueDetailsModal(hm_ro, make_owner, collection_owner, collection, hallmark_agent, supplier) {
    const content = document.getElementById('poDetailsContent');
    content.innerHTML = `
        <div class="flex flex-col items-center justify-center p-8 text-gray-400">
            <span class="material-symbols-outlined text-3xl animate-spin mb-4 text-primary">sync</span>
            <span class="text-xs font-bold uppercase tracking-widest">Loading details...</span>
        </div>
    `;
    document.getElementById('poDetailsModal').classList.remove('hidden');

    try {
        const params = new URLSearchParams({ hm_ro, make_owner, collection_owner, collection, hallmark_agent, supplier });
        const response = await fetch(`/api/supplier-hm-issue/details?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const html = await response.text();
        content.innerHTML = html;
    } catch (err) {
        console.error("Error fetching HM details:", err);
        content.innerHTML = '<p class="text-center p-8 text-red-500">Error loading details</p>';
    }
}

// Intercept closeFeedbackModal to reset save button
const originalCloseFeedbackModal = window.closeFeedbackModal;
window.closeFeedbackModal = function() {
    if (originalCloseFeedbackModal) originalCloseFeedbackModal();
    const saveBtn = document.querySelector('#feedbackModal button[onclick="saveHMFeedback()"]');
    if (saveBtn) saveBtn.setAttribute('onclick', 'saveFeedback()');
    
    // Clear all hidden inputs
    ['fb_hm_ro', 'fb_make_owner', 'fb_hallmark_agent', 'fb_collection_owner', 'fb_collection', 'fb_branch', 'fb_supplier', 'fb_order_branch', 'fb_party', 'fb_qc_ro'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
};

function openHMReturnFeedbackModal(hm_ro, make_owner, collection_owner, collection, hallmark_agent, supplier, currentFeedback, currentCategory) {
    document.getElementById('fb_hm_ro').value = hm_ro;
    document.getElementById('fb_make_owner').value = make_owner;
    document.getElementById('fb_collection_owner').value = collection_owner;
    document.getElementById('fb_collection').value = collection;
    document.getElementById('fb_hallmark_agent').value = hallmark_agent;
    document.getElementById('fb_supplier').value = supplier;
    
    document.getElementById('feedbackText').value = currentFeedback || '';
    document.getElementById('feedbackCategory').value = currentCategory || '';
    document.getElementById('feedbackModalContext').textContent = `${hm_ro} > ${supplier} (Return)`;
    
    const saveBtn = document.querySelector('#feedbackModal button[onclick*="save"]');
    if (saveBtn) saveBtn.setAttribute('onclick', 'saveHMReturnFeedback()');

    document.getElementById('feedbackModal').classList.remove('hidden');
}

async function saveHMReturnFeedback() {
    const data = {
        hm_ro: document.getElementById('fb_hm_ro').value,
        make_owner: document.getElementById('fb_make_owner').value,
        collection_owner: document.getElementById('fb_collection_owner').value,
        collection: document.getElementById('fb_collection').value,
        hallmark_agent: document.getElementById('fb_hallmark_agent').value,
        supplier: document.getElementById('fb_supplier').value,
        feedback_text: document.getElementById('feedbackText').value,
        feedback_category: document.getElementById('feedbackCategory').value
    };

    try {
        const response = await fetch('/api/hm-return/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
            body: JSON.stringify(data)
        });
        if (response.ok) { closeFeedbackModal(); loadViewData(); showToast("Feedback saved!", "success"); }
    } catch (err) { console.error(err); showToast("Error", "error"); }
}

async function showHMReturnDetailsModal(hm_ro, make_owner, collection_owner, collection, hallmark_agent, supplier) {
    const content = document.getElementById('poDetailsContent');
    content.innerHTML = '<div class="p-8 text-center">Loading...</div>';
    document.getElementById('poDetailsModal').classList.remove('hidden');
    try {
        const params = new URLSearchParams({ hm_ro, make_owner, collection_owner, collection, hallmark_agent, supplier });
        const response = await fetch(`/api/hm-return/details?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        content.innerHTML = await response.text();
    } catch (err) { content.innerHTML = 'Error'; }
}

async function showHMReturnLogisticModal(hm_ro, make_owner, collection_owner, collection, hallmark_agent, supplier) {
    const content = document.getElementById('poDetailsContent'); // Reusing modal content
    content.innerHTML = '<div class="p-8 text-center">Loading Logistics...</div>';
    document.getElementById('poDetailsModal').classList.remove('hidden');
    try {
        const params = new URLSearchParams({ hm_ro, make_owner, collection_owner, collection, hallmark_agent, supplier });
        const response = await fetch(`/api/hm-return/logistic-details?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        content.innerHTML = await response.text();
    } catch (err) { content.innerHTML = 'Error'; }
}

function openHMQCIssueFeedbackModal(order_branch, make_owner, collection_owner, collection, hallmark_agent, party, currentFeedback, currentCategory) {
    document.getElementById('fb_order_branch').value = order_branch;
    document.getElementById('fb_make_owner').value = make_owner;
    document.getElementById('fb_collection_owner').value = collection_owner;
    document.getElementById('fb_collection').value = collection;
    document.getElementById('fb_hallmark_agent').value = hallmark_agent;
    document.getElementById('fb_party').value = party;
    
    document.getElementById('feedbackText').value = currentFeedback || '';
    document.getElementById('feedbackCategory').value = currentCategory || '';
    document.getElementById('feedbackModalContext').textContent = `${order_branch} > ${party} (QC Issue)`;
    
    const saveBtn = document.querySelector('#feedbackModal button[onclick*="save"]');
    if (saveBtn) saveBtn.setAttribute('onclick', 'saveHMQCIssueFeedback()');

    document.getElementById('feedbackModal').classList.remove('hidden');
}

async function saveHMQCIssueFeedback() {
    const data = {
        order_branch: document.getElementById('fb_order_branch').value,
        make_owner: document.getElementById('fb_make_owner').value,
        collection_owner: document.getElementById('fb_collection_owner').value,
        collection: document.getElementById('fb_collection').value,
        hallmark_agent: document.getElementById('fb_hallmark_agent').value,
        party: document.getElementById('fb_party').value,
        feedback_text: document.getElementById('feedbackText').value,
        feedback_category: document.getElementById('feedbackCategory').value
    };

    try {
        const response = await fetch('/api/hm-qc-issue/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
            body: JSON.stringify(data)
        });
        if (response.ok) { closeFeedbackModal(); loadViewData(); showToast("Feedback saved!", "success"); }
    } catch (err) { console.error(err); showToast("Error", "error"); }
}

async function showHMQCIssueDetailsModal(order_branch, make_owner, collection_owner, collection, hallmark_agent, party) {
    const content = document.getElementById('poDetailsContent');
    content.innerHTML = '<div class="p-8 text-center">Loading Details...</div>';
    document.getElementById('poDetailsModal').classList.remove('hidden');
    try {
        const params = new URLSearchParams({ order_branch, make_owner, collection_owner, collection, hallmark_agent, party });
        const response = await fetch(`/api/hm-qc-issue/details?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        content.innerHTML = await response.text();
    } catch (err) { content.innerHTML = 'Error'; }
}

function openQCIssueReceiptFeedbackModal(qc_ro, make_owner, collection_owner, collection, party, currentFeedback, currentCategory) {
    document.getElementById('fb_qc_ro').value = qc_ro;
    document.getElementById('fb_make_owner').value = make_owner;
    document.getElementById('fb_collection_owner').value = collection_owner;
    document.getElementById('fb_collection').value = collection;
    document.getElementById('fb_party').value = party;
    
    document.getElementById('feedbackText').value = currentFeedback || '';
    document.getElementById('feedbackCategory').value = currentCategory || '';
    document.getElementById('feedbackModalContext').textContent = `${qc_ro} > ${party} (QC Receipt)`;
    
    const saveBtn = document.querySelector('#feedbackModal button[onclick*="save"]');
    if (saveBtn) saveBtn.setAttribute('onclick', 'saveQCIssueReceiptFeedback()');

    document.getElementById('feedbackModal').classList.remove('hidden');
}

async function saveQCIssueReceiptFeedback() {
    const data = {
        qc_ro: document.getElementById('fb_qc_ro').value,
        make_owner: document.getElementById('fb_make_owner').value,
        collection_owner: document.getElementById('fb_collection_owner').value,
        collection: document.getElementById('fb_collection').value,
        party: document.getElementById('fb_party').value,
        feedback_text: document.getElementById('feedbackText').value,
        feedback_category: document.getElementById('feedbackCategory').value
    };

    try {
        const response = await fetch('/api/qc-issue-receipt/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
            body: JSON.stringify(data)
        });
        if (response.ok) { closeFeedbackModal(); loadViewData(); showToast("Feedback saved!", "success"); }
    } catch (err) { console.error(err); showToast("Error", "error"); }
}

async function showQCIssueReceiptDetailsModal(qc_ro, make_owner, collection_owner, collection, party) {
    const content = document.getElementById('poDetailsContent');
    content.innerHTML = '<div class="p-8 text-center">Loading Details...</div>';
    document.getElementById('poDetailsModal').classList.remove('hidden');
    try {
        const params = new URLSearchParams({ qc_ro, make_owner, collection_owner, collection, party });
        const response = await fetch(`/api/qc-issue-receipt/details?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        content.innerHTML = await response.text();
    } catch (err) { content.innerHTML = 'Error'; }
}

function openQCCompletedInvoiceFeedbackModal(order_branch, make_owner, collection_owner, collection, party, currentFeedback, currentCategory) {
    document.getElementById('fb_order_branch').value = order_branch;
    document.getElementById('fb_make_owner').value = make_owner;
    document.getElementById('fb_collection_owner').value = collection_owner;
    document.getElementById('fb_collection').value = collection;
    document.getElementById('fb_party').value = party;
    
    document.getElementById('feedbackText').value = currentFeedback || '';
    document.getElementById('feedbackCategory').value = currentCategory || '';
    document.getElementById('feedbackModalContext').textContent = `${order_branch} > ${party} (Invoice)`;
    
    const saveBtn = document.querySelector('#feedbackModal button[onclick*="save"]');
    if (saveBtn) saveBtn.setAttribute('onclick', 'saveQCCompletedInvoiceFeedback()');

    document.getElementById('feedbackModal').classList.remove('hidden');
}

async function saveQCCompletedInvoiceFeedback() {
    const data = {
        order_branch: document.getElementById('fb_order_branch').value,
        make_owner: document.getElementById('fb_make_owner').value,
        collection_owner: document.getElementById('fb_collection_owner').value,
        collection: document.getElementById('fb_collection').value,
        party: document.getElementById('fb_party').value,
        feedback_text: document.getElementById('feedbackText').value,
        feedback_category: document.getElementById('feedbackCategory').value
    };

    try {
        const response = await fetch('/api/qc-completed-invoice/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
            body: JSON.stringify(data)
        });
        if (response.ok) { closeFeedbackModal(); loadViewData(); showToast("Feedback saved!", "success"); }
    } catch (err) { console.error(err); showToast("Error", "error"); }
}

async function showQCCompletedInvoiceDetailsModal(order_branch, make_owner, collection_owner, collection, party) {
    const content = document.getElementById('poDetailsContent');
    content.innerHTML = '<div class="p-8 text-center">Loading Details...</div>';
    document.getElementById('poDetailsModal').classList.remove('hidden');
    try {
        const params = new URLSearchParams({ order_branch, make_owner, collection_owner, collection, party });
        const response = await fetch(`/api/qc-completed-invoice/details?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        content.innerHTML = await response.text();
    } catch (err) { content.innerHTML = 'Error'; }
}

function openInvoiceDeliverFeedbackModal(order_branch, make_owner, collection_owner, collection, party, currentFeedback, currentCategory) {
    document.getElementById('fb_order_branch').value = order_branch;
    document.getElementById('fb_make_owner').value = make_owner;
    document.getElementById('fb_collection_owner').value = collection_owner;
    document.getElementById('fb_collection').value = collection;
    document.getElementById('fb_party').value = party;
    
    document.getElementById('feedbackText').value = currentFeedback || '';
    document.getElementById('feedbackCategory').value = currentCategory || '';
    document.getElementById('feedbackModalContext').textContent = `${order_branch} > ${party} (Delivery)`;
    
    const saveBtn = document.querySelector('#feedbackModal button[onclick*="save"]');
    if (saveBtn) saveBtn.setAttribute('onclick', 'saveInvoiceDeliverFeedback()');

    document.getElementById('feedbackModal').classList.remove('hidden');
}

async function saveInvoiceDeliverFeedback() {
    const data = {
        order_branch: document.getElementById('fb_order_branch').value,
        make_owner: document.getElementById('fb_make_owner').value,
        collection_owner: document.getElementById('fb_collection_owner').value,
        collection: document.getElementById('fb_collection').value,
        party: document.getElementById('fb_party').value,
        feedback_text: document.getElementById('feedbackText').value,
        feedback_category: document.getElementById('feedbackCategory').value
    };

    try {
        const response = await fetch('/api/invoice-completed-deliver/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
            body: JSON.stringify(data)
        });
        if (response.ok) { closeFeedbackModal(); loadViewData(); showToast("Feedback saved!", "success"); }
    } catch (err) { console.error(err); showToast("Error", "error"); }
}

async function showInvoiceDeliverDetailsModal(order_branch, make_owner, collection_owner, collection, party) {
    const content = document.getElementById('poDetailsContent');
    content.innerHTML = '<div class="p-8 text-center">Loading Details...</div>';
    document.getElementById('poDetailsModal').classList.remove('hidden');
    try {
        const params = new URLSearchParams({ order_branch, make_owner, collection_owner, collection, party });
        const response = await fetch(`/api/invoice-completed-deliver/details?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        content.innerHTML = await response.text();
    } catch (err) { content.innerHTML = 'Error'; }
}
