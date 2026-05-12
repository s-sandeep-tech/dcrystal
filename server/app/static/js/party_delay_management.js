let currentZoom = parseFloat(localStorage.getItem('party-delay-report-zoom')) || 1.0;
let allModalRows = [];
let currentModalSegmentId = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('Party Delay Management JS Initialized');
    adjustZoom(0);

    const urlParams = new URLSearchParams(window.location.search);
    
    // Auto-fill search
    if (urlParams.get('search')) {
        const s = document.getElementById('hierarchy-search');
        if (s) s.value = urlParams.get('search');
    }

    // Auto-fill filters
    ['party'].forEach(f => {
        const val = urlParams.get(f);
        if (val) {
            const el = document.getElementById(`filter-${f}`);
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
    
    fetch(`/partial/party-delay-management-report?${urlParams.toString()}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
    .then(res => res.text())
    .then(html => {
        container.innerHTML = html;
        setupDynamicTooltips();
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
    localStorage.setItem('party-delay-report-zoom', currentZoom);
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

    const partyVal = document.getElementById('filter-party')?.value;
    if (partyVal) urlParams.set('party', partyVal); else urlParams.delete('party');

    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({path: newUrl}, '', newUrl);
    loadReport();
}

function resetFilters() {
    const newUrl = window.location.pathname;
    window.history.pushState({path: newUrl}, '', newUrl);
    
    const s = document.getElementById('hierarchy-search');
    if (s) s.value = '';
    const p = document.getElementById('filter-party');
    if (p) p.value = '';
    
    loadReport();
}

function openFeedbackModal(party, segment_id) {
    document.getElementById('fb_party').value = party;
    document.getElementById('fb_segment_id').value = segment_id;
    
    const segmentNames = {
        1: "Accept Pending",
        2: "Process Pending",
        3: "Barcode Pending",
        4: "HM Issue Pending",
        5: "QC Issue Pending",
        6: "Invoice Pending"
    };
    
    document.getElementById('fb_display_info').textContent = `${party} | ${segmentNames[segment_id]}`;
    document.getElementById('feedbackModal').classList.remove('hidden');
}

function closeFeedbackModal() {
    document.getElementById('feedbackModal').classList.add('hidden');
    document.getElementById('feedbackForm').reset();
    document.getElementById('feedbackCategory').value = '';
    document.querySelectorAll('.category-tag').forEach(t => t.classList.remove('selected'));
}

function selectCategoryTag(el, value) {
    document.getElementById('feedbackCategory').value = value;
    document.querySelectorAll('.category-tag').forEach(t => t.classList.remove('selected'));
    el.classList.add('selected');
}

document.getElementById('feedbackForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    const data = {
        party: formData.get('party'),
        segment_id: parseInt(formData.get('segment_id')),
        feedback_text: formData.get('feedback_text'),
        category: formData.get('category')
    };

    fetch('/api/party-delay-management/feedback', {
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
            setTimeout(() => loadReport(), 500);
        } else {
            if (window.showToast) window.showToast('Error', data.message || 'Error saving feedback', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        if (window.showToast) window.showToast('Network Error', 'Error saving feedback', 'error');
    });
});

function openDetailsModal(party, segment_id) {
    const modal = document.getElementById('detailsModal');
    const content = document.getElementById('modalContent');
    const title = document.getElementById('modalTitle');
    const subtitle = document.getElementById('modalSubtitle');
    
    const segmentNames = {
        1: "Accept Pending Details",
        2: "Process Pending Details",
        3: "Barcode Pending Details",
        4: "HM Issue Pending Details",
        5: "QC Issue Pending Details",
        6: "Invoice Pending Details"
    };
    
    title.textContent = `${party}`;
    subtitle.textContent = segmentNames[segment_id];
    content.innerHTML = '<div class="flex justify-center p-12"><div class="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div></div>';
    
    currentModalSegmentId = segment_id;
    modal.classList.remove('hidden');

    fetch(`/api/party-delay-management/details/${segment_id}?party=${encodeURIComponent(party)}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.length === 0) {
            content.innerHTML = '<div class="p-12 text-center text-gray-500">No detailed records found for this party and segment.</div>';
            return;
        }
        allModalRows = data;
        renderRichModalContent(data, segment_id);
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

function renderRichModalContent(data, segment_id) {
    const content = document.getElementById('modalContent');
    
    let headers = "";
    if (segment_id <= 4) {
        headers = `
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">PO Info</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">Party Info</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">Design / Set</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-center">Status</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-right">Weights</th>
        `;
    } else if (segment_id === 5) {
        headers = `
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">PO / HM Info</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">Party Info</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-center">HM Completed</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-right">Pending QC Issue</th>
        `;
    } else {
        headers = `
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">PO / Invoice Req</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">Party / RO</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-center">QC Receipt</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-right">Net / Stone</th>
        `;
    }

    let html = `
        <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-gray-50/50 dark:bg-gray-800/50 border-y border-gray-200 dark:border-gray-700">
                        ${headers}
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
    `;

    data.forEach(row => {
        if (segment_id <= 4) {
            const poDate = row.po_date ? row.po_date.split('T')[0] : '-';
            const targetDate = (row.target_date || row.delivery_target_date) ? (row.target_date || row.delivery_target_date).split('T')[0] : '-';
            
            html += `
                <tr class="hover:bg-indigo-50/30 dark:hover:bg-indigo-900/10 transition-colors">
                    <td class="px-4 py-4">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.po_number || '-'}</span>
                            <span class="text-[10px] text-gray-500 flex items-center gap-1">
                                <span class="material-symbols-outlined text-[12px]">calendar_today</span> ${poDate}
                            </span>
                            <span class="text-[10px] text-indigo-600 dark:text-indigo-400 font-medium">${row.order_branch || '-'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.party || '-'}</span>
                            <span class="text-[10px] text-gray-500">${row.party_mobile_no || '-'}</span>
                            <div class="flex flex-col mt-1">
                                <span class="text-[10px] text-gray-400 leading-tight">BH: ${row.business_head_name || '-'}</span>
                                <span class="text-[10px] text-gray-400 leading-tight">${row.business_head_phone_number || '-'}</span>
                            </div>
                        </div>
                    </td>
                    <td class="px-4 py-4">
                        <div class="flex flex-col gap-0.5">
                            <div class="flex items-center gap-2">
                                <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.set_design_no || row.design_no || '-'}</span>
                                ${row.set_identifier ? `<span class="px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 text-[9px] font-bold">${row.set_identifier}</span>` : ''}
                            </div>
                            <span class="text-[10px] text-gray-500 flex items-center gap-1">
                                <span class="material-symbols-outlined text-[12px] text-rose-500">event</span> Target: ${targetDate}
                            </span>
                        </div>
                    </td>
                    <td class="px-4 py-4 text-center">
                        <span class="px-2.5 py-1 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-[10px] font-bold border border-amber-200 dark:border-amber-800/50 italic">
                            ${row.order_status || '-'}
                        </span>
                    </td>
                    <td class="px-4 py-4 text-right">
                        <div class="flex flex-col">
                            <span class="text-xs font-black text-gray-900 dark:text-gray-100">${formatWeight(row.barcoded_weight || row.required_weight)} <span class="text-[9px] font-normal text-gray-400">Gms</span></span>
                            <div class="flex flex-col mt-1">
                                <span class="text-[9px] text-gray-500">Stone: ${formatWeight(row.stone_weight)}</span>
                                <span class="text-[9px] text-gray-500">Net: ${formatWeight(row.net_weight)}</span>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        } else if (segment_id === 5) {
            html += `
                <tr class="hover:bg-orange-50/30 dark:hover:bg-orange-900/10 transition-colors">
                    <td class="px-4 py-4">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.po_number || '-'}</span>
                            <span class="text-[10px] text-orange-600 dark:text-orange-400 font-bold">${row.hm_request_no || '-'}</span>
                            <span class="text-[10px] text-gray-400 font-medium">${row.hallmark_agent || '-'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4">
                        <div class="flex flex-col">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.party || '-'}</span>
                            <span class="text-[10px] text-gray-500">${row.party_mobile_no || '-'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4 text-center">
                        <div class="flex flex-col">
                            <span class="text-[10px] text-gray-400 uppercase font-black tracking-tighter">HM Comp At</span>
                            <span class="text-xs font-bold text-gray-700 dark:text-gray-300">${row.hm_completed_at ? row.hm_completed_at.split('T')[0] : '-'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4 text-right">
                        <div class="flex flex-col">
                            <span class="text-xs font-black text-rose-600">${row.pending_to_final_qc_issue_pcs || 0} Pcs</span>
                            <span class="text-[10px] text-gray-400 font-bold">${formatWeight(row.pending_to_final_qc_issue_weight)} Gms</span>
                        </div>
                    </td>
                </tr>
            `;
        } else {
            html += `
                <tr class="hover:bg-emerald-50/30 dark:hover:bg-emerald-900/10 transition-colors">
                    <td class="px-4 py-4">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.po_number || '-'}</span>
                            <span class="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold">${row.invoice_request_number || '-'}</span>
                            <span class="text-[10px] text-gray-400">Req: ${row.invoice_request_date ? row.invoice_request_date.split('T')[0] : '-'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4">
                        <div class="flex flex-col">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.party || '-'}</span>
                            <span class="text-[10px] text-gray-500">RO: ${row.qc_ro || '-'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4 text-center">
                        <div class="flex flex-col">
                            <span class="text-[10px] text-gray-400 uppercase font-black tracking-tighter">QC Receipt</span>
                            <span class="text-xs font-bold text-gray-700 dark:text-gray-300">${row.final_qc_receipt_date ? row.final_qc_receipt_date.split('T')[0] : '-'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4 text-right">
                        <div class="flex flex-col">
                            <span class="text-xs font-black text-gray-900 dark:text-gray-100">${formatWeight(row.net_weight)} <span class="text-[9px] font-normal text-gray-400">Net</span></span>
                            <span class="text-[10px] text-gray-400 font-bold">Stone: ${formatWeight(row.stone_weight)}</span>
                        </div>
                    </td>
                </tr>
            `;
        }
    });

    html += `</tbody></table></div>`;
    content.innerHTML = html;
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
            const party = this.getAttribute('data-party');
            const segment_id = this.getAttribute('data-segment-id');
            
            tooltip.classList.remove('hidden');
            tooltip.classList.add('opacity-100');
            updateTooltipPosition(e, tooltip);
            
            fetch(`/api/party-delay-management/feedback-info?party=${encodeURIComponent(party)}&segment_id=${segment_id}`, {
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
