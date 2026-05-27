let currentZoom = parseFloat(localStorage.getItem('hm-delay-report-zoom')) || 1.0;
let allModalRows = [];
let currentModalSegmentId = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('HM Delay Management JS Initialized');
    adjustZoom(0);

    const urlParams = new URLSearchParams(window.location.search);
    
    // Auto-fill search
    if (urlParams.get('search')) {
        const s = document.getElementById('hierarchy-search');
        if (s) s.value = urlParams.get('search');
    }

    // Auto-fill filters
    ['center', 'status'].forEach(f => {
        const val = urlParams.get(f);
        if (val) {
            const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
            if (el) el.value = val;
        }
    });

    setupDynamicTooltips();
    loadReport();
});

function loadReport() {
    const loader = document.getElementById('loader-overlay');
    const container = document.getElementById('view-container');
    if (loader) loader.classList.remove('hidden');

    const urlParams = new URLSearchParams(window.location.search);
    
    fetch(`/partial/hm-delay-management-report?${urlParams.toString()}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
    .then(res => res.text())
    .then(html => {
        container.innerHTML = html;
        setupDynamicTooltips(); // Re-init tooltips for new rows
    })
    .catch(err => {
        console.error('Error loading report:', err);
        container.innerHTML = '<div class="p-20 text-center text-red-500 font-bold">Error loading report. Please refresh.</div>';
    })
    .finally(() => {
        if (loader) loader.classList.add('hidden');
    });
}

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;
    if (reset) currentZoom = 1.0;
    else currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    tableArea.style.zoom = currentZoom;
    localStorage.setItem('hm-delay-report-zoom', currentZoom);
    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
}

function onSearchInput(value) {
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => applyFilters(), 500);
}

function applyFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    
    const searchVal = document.getElementById('hierarchy-search')?.value;
    if (searchVal) urlParams.set('search', searchVal); else urlParams.delete('search');

    const fields = ['center', 'status'];
    fields.forEach(f => {
        const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
        if (el && el.value) urlParams.set(f, el.value); else if (f !== 'status') urlParams.delete(f);
    });

    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({path: newUrl}, '', newUrl);
    loadReport();
}

function resetFilters() {
    const newUrl = window.location.pathname + '?status=hm_summary&page=1';
    window.history.pushState({path: newUrl}, '', newUrl);
    
    // Reset DOM elements
    const s = document.getElementById('hierarchy-search');
    if (s) s.value = '';
    ['center', 'status'].forEach(f => {
        const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
        if (el) el.value = (f === 'status' ? 'hm_summary' : '');
    });
    
    loadReport();
}

function setStatus(status) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('status', status);
    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({path: newUrl}, '', newUrl);
    loadReport();
}

function changePerPage(perPage) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', perPage);
    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({path: newUrl}, '', newUrl);
    loadReport();
}

function changePage(page) {
    if (page < 1) return;
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({path: newUrl}, '', newUrl);
    loadReport();
}

function openFeedbackModal(hallmark_center, hallmark_center_id, segment_id) {
    document.getElementById('fb_hallmark_center').value = hallmark_center;
    document.getElementById('fb_hallmark_center_id').value = hallmark_center_id;
    document.getElementById('fb_segment_id').value = segment_id;
    
    let segmentName = "";
    if (segment_id === 1) segmentName = "Hallmark Issue Completed - Receipt Pending";
    else if (segment_id === 2) segmentName = "Hallmark Receipt Completed - Hallmark Pending";
    else if (segment_id === 3) segmentName = "Hallmark Completed - Return Pending";
    
    document.getElementById('fb_display_info').textContent = `${hallmark_center} | ${segmentName}`;
    document.getElementById('feedbackModal').classList.remove('hidden');
}

function closeFeedbackModal() {
    document.getElementById('feedbackModal').classList.add('hidden');
    document.getElementById('feedbackForm').reset();
    
    // Reset category tags
    document.getElementById('feedbackCategory').value = '';
    document.querySelectorAll('.category-tag').forEach(t => t.classList.remove('selected'));
}

function selectCategoryTag(el, value) {
    // Update hidden input
    document.getElementById('feedbackCategory').value = value;
    
    // Update UI
    document.querySelectorAll('.category-tag').forEach(t => t.classList.remove('selected'));
    el.classList.add('selected');
}

document.getElementById('feedbackForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    const data = {
        hallmark_center: formData.get('hallmark_center'),
        hallmarking_center_id: parseInt(formData.get('hallmark_center_id')),
        segment_id: parseInt(formData.get('segment_id')),
        feedback_text: formData.get('feedback_text'),
        category: formData.get('category')
    };

    fetch('/api/hm-delay-management/feedback', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            if (window.showToast) window.showToast('Feedback Saved', 'Feedback saved successfully', 'success');
            closeFeedbackModal();
            setTimeout(() => window.location.reload(), 1000);
        } else {
            if (window.showToast) window.showToast('Error', data.message || 'Error saving feedback', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        if (window.showToast) window.showToast('Network Error', 'Error saving feedback', 'error');
    });
});

function openDetailsModal(hallmark_center, hallmark_center_id, segment_id) {
    const modal = document.getElementById('detailsModal');
    const content = document.getElementById('modalContent');
    const title = document.getElementById('modalTitle');
    const subtitle = document.getElementById('modalSubtitle');
    
    let segmentName = "";
    if (segment_id === 1) segmentName = "Hallmark Issue Completed - Receipt Pending";
    else if (segment_id === 2) segmentName = "Hallmark Receipt Completed - Hallmark Pending";
    else if (segment_id === 3) segmentName = "Hallmark Completed - Return Pending";
    
    title.textContent = `Hallmarking Details - ${hallmark_center}`;
    subtitle.textContent = segmentName;
    content.innerHTML = '<div class="flex justify-center p-12"><div class="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div></div>';
    
    currentModalSegmentId = segment_id;
    modal.classList.remove('hidden');

    fetch(`/api/hm-delay-management/details/${segment_id}?hallmark_center=${encodeURIComponent(hallmark_center)}&hallmark_center_id=${hallmark_center_id}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.length === 0) {
                content.innerHTML = '<div class="p-12 text-center text-gray-500">No detailed records found for this centre and segment.</div>';
                return;
            }
            allModalRows = data;
            renderHMModalContent(data, segment_id);
        })
        .catch(error => {
            console.error('Error:', error);
            content.innerHTML = '<div class="p-12 text-center text-red-500">Error loading details. Please try again.</div>';
        });
}

function closeDetailsModal() {
    document.getElementById('detailsModal').classList.add('hidden');
    allModalRows = [];
    currentModalSegmentId = null;
}

function renderHMModalContent(data, segment_id) {
    const content = document.getElementById('modalContent');
    
    // Group unique parties for the filter
    const parties = [...new Set(data.map(r => r.party))].filter(Boolean).sort();
    
    let html = `
        <div class="modal-filter-bar mb-4">
            <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest flex items-center gap-2">
                <span class="material-symbols-outlined text-sm">filter_list</span> Filter by Party:
            </span>
            <select id="modal-party-filter" onchange="filterModalByParty(this.value)" 
                class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-3 py-1 text-xs font-bold focus:ring-0 outline-none">
                <option value="">All Parties</option>
                ${parties.map(p => `<option value="${p}">${p}</option>`).join('')}
            </select>
        </div>
        <div class="space-y-4" id="rich-modal-list">
    `;

    data.forEach(row => {
        html += `
        <div class="detail-card animate-in fade-in slide-in-from-bottom-4 duration-300" data-party="${row.party || ''}">
            <!-- Left: ID / RO Info -->
            <div class="info-section border-r border-gray-100 dark:border-gray-800 pr-4">
                <span class="info-label">${segment_id === 1 ? 'HM ISSUE' : segment_id === 2 ? 'HM REQUEST' : 'HM COMPLETION'}</span>
                <span class="info-value text-orange-600">${row.hm_issue_receipt_no || row.hm_request_number || row.hm_request_no || 'N/A'}</span>
                <span class="info-subtext">Date: ${row.hm_issue_receipt_date || row.hm_request_date || row.hm_completed_at || '-'}</span>
                <div class="mt-2 pt-2 border-t border-gray-50 dark:border-gray-800">
                    <span class="info-label">Hallmark RO</span>
                    <span class="info-subtext block font-bold">${row.hm_ro || '-'}</span>
                    <span class="info-subtext block text-[9px]">${row.hm_ro_incharge || ''}</span>
                </div>
            </div>

            <!-- Middle Left: PO Info -->
            <div class="info-section border-r border-gray-100 dark:border-gray-800 pr-4">
                <span class="info-label">PO INFO</span>
                <span class="info-value text-blue-600">${row.po_number || '-'}</span>
                <span class="info-subtext block">Date: ${row.po_date || '-'}</span>
                <span class="info-subtext block">Order: ${row.order_no || '-'}</span>
                <div class="mt-2 pt-2 border-t border-gray-50 dark:border-gray-800">
                    <span class="info-label">Party</span>
                    <span class="info-subtext block font-bold truncate max-w-[150px]">${row.party || row.business_head_name || row.make_owner || '-'}</span>
                </div>
            </div>

            <!-- Middle: Design / Set -->
            <div class="info-section border-r border-gray-100 dark:border-gray-800 pr-4">
                <span class="info-label">Design / Set</span>
                <span class="info-value">${row.design_no || row.set_design_no || '-'}</span>
                <span class="info-subtext block text-[9px] text-indigo-500 font-bold">${row.set_identifier || ''}</span>
                <div class="mt-2 pt-2 border-t border-gray-50 dark:border-gray-800">
                    <span class="info-label">Barcode Status</span>
                    <span class="info-subtext block ${row.is_barcoded ? 'text-emerald-500' : 'text-gray-400'} font-bold">
                        ${row.is_barcoded ? 'BARCODED' : 'NOT BARCODED'}
                    </span>
                    <span class="info-subtext block text-[9px]">${row.barcode_completion_date || ''}</span>
                </div>
            </div>

            <!-- Status Section -->
            <div class="info-section border-r border-gray-100 dark:border-gray-800 pr-4">
                <span class="info-label">Status / Stage</span>
                <div class="flex flex-col gap-2 mt-1">
                    <div class="flex items-center gap-2">
                        <span class="status-dot ${row.is_hm_agent_received ? 'bg-emerald-500' : 'bg-gray-300'}"></span>
                        <span class="text-[10px] font-bold text-gray-500 uppercase">Received by Agent</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="status-dot ${row.is_hallmark_completed ? 'bg-emerald-500' : 'bg-gray-300'}"></span>
                        <span class="text-[10px] font-bold text-gray-500 uppercase">HM Completed</span>
                    </div>
                </div>
                <div class="mt-2 pt-2 border-t border-gray-50 dark:border-gray-800">
                    <span class="info-label">Current Stage</span>
                    <span class="info-subtext block font-black text-blue-500">${row.current_stage || row.order_status || '-'}</span>
                </div>
            </div>

            <!-- Right: Weights -->
            <div class="info-section min-w-[140px]">
                <span class="info-label">Weights (G/N/S)</span>
                <div class="weight-grid mt-1">
                    <span class="weight-label">G:</span> <span class="weight-val">${formatWeight(row.gross_weight)}</span>
                    <span class="weight-label">N:</span> <span class="weight-val">${formatWeight(row.net_weight)}</span>
                    <span class="weight-label">S:</span> <span class="weight-val">${formatWeight(row.stone_weight)}</span>
                </div>
                <div class="mt-2 pt-2 border-t border-gray-50 dark:border-gray-800">
                    <span class="info-label">BC Weight</span>
                    <span class="weight-val block text-indigo-600 font-black">${formatWeight(row.barcoded_weight)}</span>
                </div>
            </div>

            <!-- Far Right: Pending -->
            <div class="flex flex-col justify-center items-end">
                <div class="pending-badge">
                    <span class="info-label block text-[8px] mb-1">PENDING</span>
                    <span class="text-lg font-black text-emerald-600 leading-none">
                        ${formatWeight(row.hm_receipt_pending_wt || row.pending_weight || row.weight)}
                    </span>
                    <span class="block text-[9px] font-bold text-gray-400 mt-1">${row.hm_receipt_pending_pcs || row.pending_piece || row.piece || 1} PCS</span>
                </div>
            </div>
        </div>
        `;
    });

    html += `</div>`;
    modalContent.innerHTML = html;
}

function filterModalByParty(party) {
    const cards = document.querySelectorAll('#rich-modal-list .detail-card');
    cards.forEach(card => {
        if (!party || card.dataset.party === party) {
            card.classList.remove('hidden');
        } else {
            card.classList.add('hidden');
        }
    });
}

function formatWeight(val) {
    if (val === undefined || val === null) return "0.000";
    return parseFloat(val).toFixed(3);
}

function setupDynamicTooltips() {
    const triggers = document.querySelectorAll('.feedback-trigger');
    const tooltip = document.getElementById('feedbackTooltip');
    if (!tooltip) return;

    triggers.forEach(trigger => {
        trigger.addEventListener('mouseenter', function(e) {
            const hallmark_center = this.getAttribute('data-hallmark-center');
            const hallmark_center_id = this.getAttribute('data-hallmark-center-id');
            const segment_id = this.getAttribute('data-segment-id');
            
            // Show loading state
            document.getElementById('tt-username').textContent = 'Loading...';
            document.getElementById('tt-date').textContent = '';
            document.getElementById('tt-category').textContent = '...';
            document.getElementById('tt-text').textContent = 'Fetching latest feedback...';
            
            tooltip.classList.remove('hidden');
            tooltip.classList.add('opacity-100');
            updateTooltipPosition(e, tooltip);
            
            fetch(`/api/hm-delay-management/feedback-info?hallmarking_center_id=${hallmark_center_id}&segment_id=${segment_id}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    const fb = data.data;
                    document.getElementById('tt-username').textContent = fb.username || 'System';
                    document.getElementById('tt-date').textContent = fb.date;
                    document.getElementById('tt-category').textContent = fb.category || 'N/A';
                    document.getElementById('tt-text').textContent = fb.text;
                } else {
                    document.getElementById('tt-text').textContent = 'No feedback found.';
                }
            })
            .catch(err => {
                console.error('Tooltip Fetch Error:', err);
                document.getElementById('tt-text').textContent = 'Error loading feedback.';
            });
        });
        
        trigger.addEventListener('mousemove', function(e) {
            updateTooltipPosition(e, tooltip);
        });
        
        trigger.addEventListener('mouseleave', function() {
            tooltip.classList.remove('opacity-100');
            tooltip.classList.add('hidden');
        });
    });
}

function updateTooltipPosition(e, tooltip) {
    const offset = 15;
    let x = e.clientX + offset;
    let y = e.clientY + offset;
    
    const ttRect = tooltip.getBoundingClientRect();
    if (x + ttRect.width > window.innerWidth) x = e.clientX - ttRect.width - offset;
    if (y + ttRect.height > window.innerHeight) y = e.clientY - ttRect.height - offset;
    
    tooltip.style.left = x + 'px';
    tooltip.style.top = y + 'px';
}

function toggleSort(column) {
    const urlParams = new URLSearchParams(window.location.search);
    const currentSort = urlParams.get('sort_by');
    const currentDir = urlParams.get('sort_dir') || 'desc';
    
    if (currentSort === column) {
        urlParams.set('sort_dir', currentDir === 'desc' ? 'asc' : 'desc');
    } else {
        urlParams.set('sort_by', column);
        urlParams.set('sort_dir', 'desc');
    }
    
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({path: newUrl}, '', newUrl);
    loadReport();
}
