let currentZoom = parseFloat(localStorage.getItem('qc-delay-report-zoom')) || 1.0;

document.addEventListener('DOMContentLoaded', function() {
    console.log('QC Delay Management JS Initialized');
    adjustZoom(0);

    const urlParams = new URLSearchParams(window.location.search);
    
    // Auto-fill search
    if (urlParams.get('search')) {
        const s = document.getElementById('hierarchy-search');
        if (s) s.value = urlParams.get('search');
    }

    // Auto-fill filters
    ['office', 'status'].forEach(f => {
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
    
    fetch(`/partial/qc-delay-management-report?${urlParams.toString()}`, {
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
    localStorage.setItem('qc-delay-report-zoom', currentZoom);
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

    const fields = ['office', 'status'];
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
    const newUrl = window.location.pathname + '?status=segment_1&page=1';
    window.history.pushState({path: newUrl}, '', newUrl);
    
    // Reset DOM elements
    const s = document.getElementById('hierarchy-search');
    if (s) s.value = '';
    ['office', 'status'].forEach(f => {
        const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
        if (el) el.value = (f === 'status' ? 'segment_1' : '');
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

function openFeedbackModal(qc_ro, segment_id) {
    document.getElementById('fb_qc_ro').value = qc_ro;
    document.getElementById('fb_segment_id').value = segment_id;
    
    let segmentName = "";
    if (segment_id === 1) segmentName = "QC Issue Completed - Receipt Pending";
    else if (segment_id === 2) segmentName = "QC Receipt Completed - QC Pending";
    else if (segment_id === 3) segmentName = "QC Completed - Invoice Request Pending";
    
    document.getElementById('fb_display_info').textContent = `${qc_ro} | ${segmentName}`;
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
        qc_ro: formData.get('qc_ro'),
        segment_id: parseInt(formData.get('segment_id')),
        feedback_text: formData.get('feedback_text'),
        category: formData.get('category')
    };

    fetch('/api/qc-delay-management/feedback', {
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

function openDetailsModal(qc_ro, segment_id) {
    const modal = document.getElementById('detailsModal');
    const content = document.getElementById('modalContent');
    const title = document.getElementById('modalTitle');
    const subtitle = document.getElementById('modalSubtitle');
    
    let segmentName = "";
    if (segment_id === 1) segmentName = "QC Issue Completed - Receipt Pending";
    else if (segment_id === 2) segmentName = "QC Receipt Completed - QC Pending";
    else if (segment_id === 3) segmentName = "QC Completed - Invoice Request Pending";
    
    title.textContent = `Purchase Order Details - ${qc_ro}`;
    subtitle.textContent = segmentName;
    content.innerHTML = '<div class="flex justify-center p-12"><div class="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div></div>';
    
    modal.classList.remove('hidden');

    fetch(`/api/qc-delay-management/details/${segment_id}?qc_ro=${encodeURIComponent(qc_ro)}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.length === 0) {
                content.innerHTML = '<div class="p-12 text-center text-gray-500">No detailed records found for this office and segment.</div>';
                return;
            }
            renderRichModalContent(data, segment_id);
        })
        .catch(error => {
            console.error('Error:', error);
            content.innerHTML = '<div class="p-12 text-center text-red-500">Error loading details. Please try again.</div>';
        });
}

function closeDetailsModal() {
    document.getElementById('detailsModal').classList.add('hidden');
}

function renderRichModalContent(data, segment_id) {
    const content = document.getElementById('modalContent');
    let html = `
        <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-gray-50 dark:bg-gray-800 border-y border-gray-200 dark:border-gray-700">
                        <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">QC INFO</th>
                        <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">PO INFO</th>
                        <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">DESIGN / SET</th>
                        <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">INVOICE / STATUS</th>
                        <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">WEIGHTS (G/N/S)</th>
                        <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-right">${segment_id === 3 ? 'PENDING INV' : 'PENDING QC'}</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
    `;

    data.forEach(row => {
        html += `
            <tr class="hover:bg-gray-50/50 dark:hover:bg-gray-800/50 transition-colors">
                <!-- QC INFO -->
                <td class="px-4 py-4 align-top">
                    <div class="flex flex-col gap-0.5">
                        <span class="text-xs font-bold text-orange-600">No: ${row.qc_req_no || row.id}</span>
                        <span class="text-[10px] text-gray-400">Date: ${row.qc_date ? row.qc_date.split('T')[0] : 'N/A'}</span>
                        <span class="text-[10px] font-bold text-emerald-600">Comp: ${row.snapshot_date ? row.snapshot_date.split('T')[0] : 'N/A'}</span>
                        <span class="text-[10px] text-gray-500">RO: ${row.qc_ro}</span>
                    </div>
                </td>

                <!-- PO INFO -->
                <td class="px-4 py-4 align-top">
                    <div class="flex flex-col gap-0.5">
                        <span class="text-xs font-bold text-blue-600">${row.po_number || 'N/A'}</span>
                        <span class="text-[10px] text-gray-400">${row.po_date || 'N/A'}</span>
                        <span class="text-[10px] text-gray-500">Individual / Refill</span>
                        <span class="text-[10px] text-gray-400 flex items-center gap-1">
                            <span class="material-symbols-outlined text-[12px]">phone</span> ${row.party_mobile_no || 'N/A'}
                        </span>
                        <span class="text-[10px] font-bold text-blue-700">BH: ${row.business_head_name || 'N/A'}</span>
                    </div>
                </td>

                <!-- DESIGN / SET -->
                <td class="px-4 py-4 align-top">
                    <div class="flex flex-col gap-0.5">
                        <span class="text-xs font-bold text-gray-700 dark:text-gray-300">-</span>
                        <span class="text-[10px] text-gray-400">Set: ${row.set_identifier || '-'}</span>
                        <span class="text-[10px] font-bold text-blue-600">BC Date: ${row.barcode_completion_date || 'N/A'}</span>
                        <span class="text-[10px] font-bold text-red-500">Target: ${row.target_date || 'N/A'}</span>
                    </div>
                </td>

                <!-- STATUS / INVOICE -->
                <td class="px-4 py-4 align-top">
                    <div class="flex flex-col gap-1.5 mt-1">
                        <div class="flex items-center gap-2">
                            <span class="size-1.5 rounded-full bg-emerald-500"></span>
                            <span class="text-[10px] font-bold text-gray-600 dark:text-gray-400">QC COMP</span>
                        </div>
                        <div class="flex items-center gap-2 opacity-40">
                            <span class="size-1.5 rounded-full bg-gray-400"></span>
                            <span class="text-[10px] font-bold text-gray-600 dark:text-gray-400">RATE REQ</span>
                        </div>
                        <div class="flex items-center gap-2 opacity-40">
                            <span class="size-1.5 rounded-full bg-gray-400"></span>
                            <span class="text-[10px] font-bold text-gray-600 dark:text-gray-400">INVOICED</span>
                        </div>
                        <div class="mt-1 flex flex-col gap-0.5">
                            <span class="text-[10px] font-bold text-blue-600">Rate Req No: -</span>
                            <span class="text-[10px] text-gray-400">Inv RO: -</span>
                        </div>
                    </div>
                </td>

                <!-- WEIGHTS -->
                <td class="px-4 py-4 align-top text-right">
                    <div class="flex flex-col gap-0.5 font-mono">
                        <span class="text-[11px] text-gray-600 dark:text-gray-400"><span class="font-bold">G:</span> ${formatWeight(row.gross_weight || row.weight)}</span>
                        <span class="text-[11px] text-gray-600 dark:text-gray-400"><span class="font-bold">N:</span> ${formatWeight(row.net_weight || row.weight)}</span>
                        <span class="text-[11px] text-gray-600 dark:text-gray-400"><span class="font-bold">S:</span> ${formatWeight(row.stone_weight)}</span>
                        <span class="text-[11px] text-blue-600 font-bold"><span class="font-bold">BC:</span> ${formatWeight(row.barcoded_weight || row.weight)}</span>
                    </div>
                </td>

                <!-- SUMMARY -->
                <td class="px-4 py-4 align-top text-right">
                    <div class="flex flex-col items-end">
                        <span class="text-lg font-black text-emerald-600 leading-tight">${formatWeight(row.weight)}</span>
                        <span class="text-[10px] font-bold text-gray-400">${row.piece || row.pieces || 0} PCS</span>
                    </div>
                </td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
    `;

    content.innerHTML = html;
}

function formatWeight(val) {
    if (val === undefined || val === null) return "0.000";
    return parseFloat(val).toFixed(3);
}

function triggerSync() {
    const button = event.currentTarget;
    const originalContent = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="animate-spin material-symbols-outlined text-[18px]">sync</span> Syncing...';
    
    fetch('/settings/sync-qc-delay-management', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
    .then(response => response.json())
    .then(data => {
        if (window.showToast) window.showToast('Sync Queued', 'Sync task queued. Check notifications for progress.', 'info');
    })
    .catch(error => {
        console.error('Error:', error);
        if (window.showToast) window.showToast('Sync Failed', 'Failed to trigger sync', 'error');
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = originalContent;
    });
}


// Local showToast removed to use global system from toast.js

function setupDynamicTooltips() {
    const triggers = document.querySelectorAll('.feedback-trigger');
    const tooltip = document.getElementById('feedbackTooltip');
    if (!tooltip) return;

    triggers.forEach(trigger => {
        trigger.addEventListener('mouseenter', function(e) {
            const qc_ro = this.getAttribute('data-qc-ro');
            const segment_id = this.getAttribute('data-segment-id');
            
            // Show loading state immediately
            document.getElementById('tt-username').textContent = 'Loading...';
            document.getElementById('tt-date').textContent = '';
            document.getElementById('tt-category').textContent = '...';
            document.getElementById('tt-text').textContent = 'Fetching latest feedback...';
            
            tooltip.classList.remove('hidden');
            tooltip.classList.add('opacity-100');
            updateTooltipPosition(e, tooltip);
            
            fetch(`/api/qc-delay-management/feedback-info?qc_ro=${encodeURIComponent(qc_ro)}&segment_id=${segment_id}`, {
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
