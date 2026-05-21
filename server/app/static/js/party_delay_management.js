let currentZoom = parseFloat(localStorage.getItem('party-delay-report-zoom')) || 1.0;
let allModalRows = [];
let currentModalSegmentId = null;
let makeMultiSelect;

let currentSortCol = null;
let currentSortDir = 'desc';

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

    // Initialize Make multiselect dropdown
    makeMultiSelect = new CustomMultiSelect({
        containerId: 'filter-make-container',
        label: 'Make',
        defaultText: 'All Makes',
        options: window.availableMakes || []
    });

    // Auto-fill Make multiselect from query parameter
    const makeVal = urlParams.get('make');
    if (makeVal && makeMultiSelect) {
        const selectedMakes = makeVal.split(',').map(m => m.trim());
        document.querySelectorAll(`.filter-make-container-checkbox`).forEach(cb => {
            if (selectedMakes.includes(cb.value)) {
                cb.checked = true;
            }
        });
        makeMultiSelect.updateTriggerText();
    }

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
        if (currentSortCol !== null) {
            applyCurrentSort();
        }
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

    const makeVal = makeMultiSelect ? makeMultiSelect.getValues().join(',') : '';
    if (makeVal) urlParams.set('make', makeVal); else urlParams.delete('make');

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
    
    if (makeMultiSelect) {
        makeMultiSelect.reset();
    }
    
    loadReport();
}

function showAddressModal(party, address) {
    const titleEl = document.getElementById('addressModalTitle');
    const contentEl = document.getElementById('addressModalContent');
    if (titleEl) titleEl.textContent = party;
    if (contentEl) contentEl.textContent = address || 'No address details found.';
    
    const modalEl = document.getElementById('addressModal');
    if (modalEl) modalEl.classList.remove('hidden');
}

function closeAddressModal() {
    const modalEl = document.getElementById('addressModal');
    if (modalEl) modalEl.classList.add('hidden');
}

function openFeedbackModal(party, segment_id) {
    document.getElementById('fb_party').value = party;
    document.getElementById('fb_segment_id').value = segment_id;
    
    const segmentNames = {
        1: "Accept Pending",
        2: "Process Pending",
        3: "Barcode Pending",
        4: "Barcode Completed - BIS Request Pending",
        5: "BIS Request Completed - HM Issue Pending",
        6: "HM Receipt Return Completed - QC Issue Pending",
        7: "Invoice Generated - Invoice Approve Pending",
        8: "Invoice Approve Completed - Not Synched to Muziris"
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
        4: "Barcode Completed - BIS Request Pending Details",
        5: "BIS Request Completed - HM Issue Pending Details",
        6: "HM Receipt Return Completed - QC Issue Pending Details",
        7: "Invoice Generated - Invoice Approve Pending Details",
        8: "Invoice Approve Completed - Not Synched to Muziris Details"
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
    if (segment_id === 1 || segment_id === 2 || segment_id === 3) {
        headers = `
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">PO Info</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">Party Info</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">Design / Set</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-center">Status</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-right">Weights</th>
        `;
    } else if (segment_id === 4 || segment_id === 5 || segment_id === 7 || segment_id === 8) {
        headers = `
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">PO Info</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">Party / BH</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">Design / Set</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-center">${segment_id === 4 || segment_id === 5 ? 'Barcode Date' : 'Invoice Info'}</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-center">Delay</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-right">Metrics (Pcs/Wt)</th>
        `;
    } else if (segment_id === 6) {
        headers = `
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">PO Info</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">Party Info</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-center">Hallmark Info</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase">Design / Set</th>
            <th class="px-4 py-3 text-[10px] font-bold text-gray-400 uppercase text-right">Weight</th>
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

    const groupedData = {};
    data.forEach(row => {
        const po = row.po_number || 'UNKNOWN_PO';
        if (!groupedData[po]) {
            groupedData[po] = {
                ...row,
                _designs: new Set(),
                _collections: new Set(),
                _targets: new Set(),
                _statuses: new Set(),
                _orders: new Set(),
                _hm_reqs: new Set(),
                _inv_reqs: new Set(),
                _hm_receipts: new Set(),
                _inv_receipts: new Set(),
                _hm_agents: new Set(),
                _hm_agent_emails: new Set(),
                _hm_agent_phones: new Set(),
                _hm_ros: new Set(),
                _final_qc_receipts: new Set(),
                piece_count: 0,
                required_weight: 0,
                barcoded_weight: 0,
                stone_weight: 0,
                net_weight: 0,
                pending_to_hallmark_issue_piece: 0,
                pending_to_hallmark_issue_wt: 0,
                pending_to_final_qc_issue_pcs: 0,
                pending_to_final_qc_issue_weight: 0,
                
                // Segments 4, 5, 7, 8:
                order_pieces: 0,
                order_wt: 0,
                pending_piece: 0,
                pending_weight: 0
            };
        }
        
        const g = groupedData[po];
        g.piece_count += 1;
        g.required_weight += parseFloat(row.required_weight || 0);
        g.barcoded_weight += parseFloat(row.barcoded_weight || 0);
        g.stone_weight += parseFloat(row.stone_weight || 0);
        g.net_weight += parseFloat(row.net_weight || 0);
        
        g.pending_to_hallmark_issue_piece += parseInt(row.pending_to_hallmark_issue_piece || 0);
        g.pending_to_hallmark_issue_wt += parseFloat(row.pending_to_hallmark_issue_wt || 0);
        
        g.pending_to_final_qc_issue_pcs += parseInt(row.pending_to_final_qc_issue_pcs || 0);
        g.pending_to_final_qc_issue_weight += parseFloat(row.pending_to_final_qc_issue_weight || 0);

        g.order_pieces += parseInt(row.order_pieces || 0);
        g.order_wt += parseFloat(row.order_wt || 0);
        g.pending_piece += parseInt(row.pending_piece || 0);
        g.pending_weight += parseFloat(row.pending_weight || 0);

        if (row.set_design_no) g._designs.add(row.set_design_no);
        else if (row.design_no) g._designs.add(row.design_no);

        if (row.collection) g._collections.add(row.collection);
        if (row.target_date) g._targets.add(row.target_date.split('T')[0]);
        if (row.order_status) g._statuses.add(row.order_status);
        if (row.order_no) g._orders.add(row.order_no);
        if (row.hm_req_id) g._hm_reqs.add(row.hm_req_id);
        if (row.invoice_request_number) g._inv_reqs.add(row.invoice_request_number);
        if (row.hm_issue_receipt_no) g._hm_receipts.add(row.hm_issue_receipt_no);
        if (row.hm_agent_invoice_receipt_no) g._inv_receipts.add(row.hm_agent_invoice_receipt_no);
        if (row.hallmark_agent) g._hm_agents.add(row.hallmark_agent);
        if (row.hm_agent_email) g._hm_agent_emails.add(row.hm_agent_email);
        if (row.hm_agent_pnone_no) g._hm_agent_phones.add(row.hm_agent_pnone_no);
        if (row.hm_ro) g._hm_ros.add(row.hm_ro);
        if (row.final_qc_receipt_no) g._final_qc_receipts.add(row.final_qc_receipt_no);
    });

    const processedData = Object.values(groupedData).map(g => {
        const formatArr = (set, limit=3) => {
            const arr = Array.from(set).filter(Boolean);
            if (!arr.length) return { full: '-', display: '-' };
            return {
                full: arr.join(', '),
                display: arr.length > limit ? arr.slice(0, limit).join(', ') + ` ... (+${arr.length - limit})` : arr.join(', ')
            };
        };

        return {
            ...g,
            set_design_no: formatArr(g._designs, 3),
            collection: formatArr(g._collections, 3),
            target_date: formatArr(g._targets, 3),
            order_status: formatArr(g._statuses, 3),
            order_no: formatArr(g._orders, 3),
            hm_req_id: formatArr(g._hm_reqs, 3),
            invoice_request_number: formatArr(g._inv_reqs, 3),
            hm_issue_receipt_no: formatArr(g._hm_receipts, 3),
            hm_agent_invoice_receipt_no: formatArr(g._inv_receipts, 3),
            hallmark_agent: formatArr(g._hm_agents, 3),
            hm_agent_email: formatArr(g._hm_agent_emails, 3),
            hm_agent_pnone_no: formatArr(g._hm_agent_phones, 3),
            hm_ro: formatArr(g._hm_ros, 3),
            final_qc_receipt_no: formatArr(g._final_qc_receipts, 3)
        };
    });

    processedData.forEach(row => {
        if (segment_id === 1 || segment_id === 2 || segment_id === 3) {
            const poDate = row.po_date ? row.po_date.split('T')[0] : '-';
            
            html += `
                <tr class="hover:bg-indigo-50/30 dark:hover:bg-indigo-900/10 transition-colors">
                    <td class="px-4 py-4">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.po_number || '-'}</span>
                            <span class="text-[10px] text-gray-500 flex items-center gap-1">
                                <span class="material-symbols-outlined text-[12px]">calendar_today</span> ${poDate}
                            </span>
                            <span class="text-[10px] text-indigo-600 dark:text-indigo-400 font-medium">${row.order_branch || '-'}</span>
                            <span class="text-[9px] text-gray-400 cursor-help" title="${row.order_no.full}">Ord: ${row.order_no.display}</span>
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
                            <span class="text-[9px] text-gray-400 mt-1">Owner: ${row.make_owner || '-'} / ${row.collection_owner || '-'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4">
                        <div class="flex flex-col gap-0.5">
                            <div class="flex items-center gap-2">
                                <span class="text-xs font-bold text-gray-900 dark:text-gray-100 break-words max-w-[150px] cursor-help" title="${row.set_design_no.full}">${row.set_design_no.display}</span>
                            </div>
                            <span class="text-[10px] text-gray-500 flex items-center gap-1 mt-1 cursor-help" title="${row.target_date.full}">
                                <span class="material-symbols-outlined text-[12px] text-rose-500">event</span> Target: ${row.target_date.display}
                            </span>
                            <span class="text-[9px] text-gray-400 italic break-words max-w-[150px] cursor-help" title="${row.collection.full}">${row.collection.display}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4 text-center">
                        <span class="px-2.5 py-1 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-[10px] font-bold border border-amber-200 dark:border-amber-800/50 italic break-words max-w-[100px] cursor-help" title="${row.order_status.full}">
                            ${row.order_status.display}
                        </span>
                    </td>
                    <td class="px-4 py-4 text-right">
                        <div class="flex flex-col">
                            <span class="text-xs font-black text-rose-600 mb-0.5">${row.piece_count || 0} Pcs</span>
                            <span class="text-xs font-black text-gray-900 dark:text-gray-100">${formatWeight(row.required_weight || row.barcoded_weight)} <span class="text-[9px] font-normal text-gray-400">Gms</span></span>
                            <div class="flex flex-col mt-1">
                                <span class="text-[9px] text-gray-500">Stone: ${formatWeight(row.stone_weight)}</span>
                                <span class="text-[9px] text-gray-500">Net: ${formatWeight(row.net_weight)}</span>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        } else if (segment_id === 4 || segment_id === 5 || segment_id === 7 || segment_id === 8) {
            const poDate = row.po_date ? row.po_date.split('T')[0] : '-';
            
            let eventCol = "";
            if (segment_id === 4 || segment_id === 5) {
                const barcodeDate = row.barcode_completion_date ? row.barcode_completion_date.split('T')[0] : '-';
                eventCol = `
                    <div class="flex flex-col text-center">
                        <span class="text-xs font-bold text-gray-700 dark:text-gray-300">${barcodeDate}</span>
                    </div>
                `;
            } else {
                const invDate = row.invoice_generated_date ? row.invoice_generated_date.split('T')[0] : 
                                (row.invoice_approved_date ? row.invoice_approved_date.split('T')[0] : '-');
                eventCol = `
                    <div class="flex flex-col text-center gap-0.5">
                        <span class="text-[10px] text-indigo-600 dark:text-indigo-400 font-bold">${row.invoice_no || '-'}</span>
                        <span class="text-[9px] text-gray-400">${segment_id === 7 ? 'Generated' : 'Approved'}</span>
                        <span class="text-xs font-bold text-gray-700 dark:text-gray-300">${invDate}</span>
                    </div>
                `;
            }

            html += `
                <tr class="hover:bg-indigo-50/30 dark:hover:bg-indigo-900/10 transition-colors">
                    <td class="px-4 py-4">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.po_number || '-'}</span>
                            <span class="text-[10px] text-gray-500 flex items-center gap-1">
                                <span class="material-symbols-outlined text-[12px]">calendar_today</span> ${poDate}
                            </span>
                            <span class="text-[10px] text-indigo-600 dark:text-indigo-400 font-medium">${row.order_branch || '-'}</span>
                            <span class="text-[9px] text-gray-400">${row.order_type || '-'} (${row.order_request_type || '-'})</span>
                        </div>
                    </td>
                    <td class="px-4 py-4">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.party || '-'}</span>
                            <span class="text-[10px] text-gray-500">${row.party_mobile_no || '-'}</span>
                            <span class="text-[9px] text-gray-400 mt-1 leading-tight">BH: ${row.business_head_name || '-'}</span>
                            <span class="text-[8px] text-gray-400">Owner: ${row.make_owner || '-'} / ${row.collection_owner || '-'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100 break-words max-w-[150px] cursor-help" title="${row.set_design_no.full}">${row.set_design_no.display}</span>
                            <span class="text-[9px] text-gray-400 italic break-words max-w-[150px] cursor-help" title="${row.collection.full}">${row.collection.display}</span>
                            <span class="text-[10px] text-gray-500 flex items-center gap-1 mt-1 cursor-help" title="${row.target_date.full}">
                                <span class="material-symbols-outlined text-[12px] text-rose-500">event</span> Target: ${row.target_date.display}
                            </span>
                        </div>
                    </td>
                    <td class="px-4 py-4 text-center">
                        ${eventCol}
                    </td>
                    <td class="px-4 py-4 text-center">
                        <span class="px-2.5 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-[11px] font-bold border border-red-200 dark:border-red-800/50">
                            ${row.delay_days || 0} Days
                        </span>
                    </td>
                    <td class="px-4 py-4 text-right">
                        <div class="flex flex-col">
                            <span class="text-xs font-black text-rose-600 mb-0.5">${row.pending_piece || 0} Pcs <span class="text-[9px] font-normal text-gray-400">/ ${row.order_pieces || 0}</span></span>
                            <span class="text-xs font-black text-gray-900 dark:text-gray-100">${formatWeight(row.pending_weight)} <span class="text-[9px] font-normal text-gray-400">Gms</span></span>
                            <span class="text-[9px] text-gray-400 mt-1">Order Wt: ${formatWeight(row.order_wt)}</span>
                        </div>
                    </td>
                </tr>
            `;
        } else if (segment_id === 6) {
            const poDate = row.po_date ? row.po_date.split('T')[0] : '-';
            const hmReceiptDate = row.hm_agent_invoice_receipt_date ? row.hm_agent_invoice_receipt_date.split('T')[0] : '-';
            const hmCompletedAt = row.hm_completed_at ? row.hm_completed_at.split('T')[0] : '-';
            
            html += `
                <tr class="hover:bg-orange-50/30 dark:hover:bg-orange-900/10 transition-colors">
                    <td class="px-4 py-4 align-top">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.po_number || '-'}</span>
                            <span class="text-[10px] text-gray-500 flex items-center gap-1">
                                <span class="material-symbols-outlined text-[12px]">calendar_today</span> ${poDate}
                            </span>
                            <span class="text-[10px] text-indigo-600 dark:text-indigo-400 font-medium">${row.order_branch || '-'}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4 align-top">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-xs font-bold text-gray-900 dark:text-gray-100">${row.party || '-'}</span>
                            <span class="text-[10px] text-gray-500">${row.party_mobile_no || '-'}</span>
                            <div class="flex flex-col mt-1">
                                <span class="text-[10px] text-gray-400 leading-tight">BH: ${row.business_head_name || '-'}</span>
                                <span class="text-[10px] text-gray-400 leading-tight">${row.business_head_phone_number || '-'}</span>
                            </div>
                        </div>
                    </td>
                    <td class="px-4 py-4 align-top">
                        <div class="flex flex-col gap-0.5">
                            <span class="text-[10px] font-bold text-gray-700 dark:text-gray-300 cursor-help" title="${row.hm_agent_invoice_receipt_no.full}">Inv/Rect: ${row.hm_agent_invoice_receipt_no.display}</span>
                            <span class="text-[10px] text-gray-500">Dt: ${hmReceiptDate}</span>
                            <div class="flex flex-col mt-1">
                                <span class="text-[9px] text-gray-400 leading-tight break-words max-w-[150px] cursor-help" title="${row.hm_agent_email.full}">Email: ${row.hm_agent_email.display}</span>
                                <span class="text-[9px] text-gray-400 leading-tight break-words max-w-[150px] cursor-help" title="${row.hm_agent_pnone_no.full}">Ph: ${row.hm_agent_pnone_no.display}</span>
                            </div>
                            <span class="text-[9px] text-gray-400 mt-1">Comp: ${hmCompletedAt}</span>
                            <span class="text-[9px] text-gray-400 break-words max-w-[150px] cursor-help" title="${row.hm_ro.full}">RO: ${row.hm_ro.display}</span>
                        </div>
                    </td>
                    <td class="px-4 py-4 align-top">
                        <div class="flex flex-col gap-0.5">
                            <div class="flex items-center gap-2">
                                <span class="text-xs font-bold text-gray-900 dark:text-gray-100 break-words max-w-[150px] cursor-help" title="${row.set_design_no.full}">${row.set_design_no.display}</span>
                            </div>
                            <span class="text-[10px] text-gray-500 flex items-center gap-1 mt-1 cursor-help" title="${row.target_date.full}">
                                <span class="material-symbols-outlined text-[12px] text-rose-500">event</span> Target: ${row.target_date.display}
                            </span>
                        </div>
                    </td>
                    <td class="px-4 py-4 text-right align-top">
                        <div class="flex flex-col">
                            <span class="text-xs font-black text-orange-600">${row.pending_to_final_qc_issue_pcs || 0} Pcs</span>
                            <span class="text-[10px] text-gray-400 font-bold">${formatWeight(row.pending_to_final_qc_issue_weight)} Gms</span>
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

function sortPartyDelayTable(headerEl, colIndex) {
    if (currentSortCol === colIndex) {
        currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortCol = colIndex;
        currentSortDir = 'desc'; // default to desc for weight
    }
    applyCurrentSort();
}

function applyCurrentSort() {
    if (currentSortCol === null) return;
    
    const table = document.querySelector('#view-container table');
    if (!table) return;
    
    const tbody = table.querySelector('tbody');
    if (!tbody) return;
    
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Check if it's the empty state row
    if (rows.length === 1 && rows[0].querySelector('td') && rows[0].querySelector('td').colSpan > 1) {
        return;
    }

    // Update icons
    const allIcons = table.querySelectorAll('.sort-icon');
    allIcons.forEach(icon => {
        icon.textContent = 'unfold_more';
        icon.classList.remove('opacity-100', 'text-primary');
        icon.classList.add('opacity-30');
    });

    const activeHeader = table.querySelector(`th[data-col-index="${currentSortCol}"]`);
    if (activeHeader) {
        const activeIcon = activeHeader.querySelector('.sort-icon');
        if (activeIcon) {
            activeIcon.textContent = currentSortDir === 'asc' ? 'arrow_upward' : 'arrow_downward';
            activeIcon.classList.add('opacity-100', 'text-primary');
            activeIcon.classList.remove('opacity-30');
        }
    }

    // Sort rows
    rows.sort((a, b) => {
        const tdsA = a.querySelectorAll('td');
        const tdsB = b.querySelectorAll('td');
        
        const tdA = tdsA[currentSortCol];
        const tdB = tdsB[currentSortCol];
        
        let valA = tdA ? parseFloat(tdA.textContent.trim().replace(/,/g, '')) || 0 : 0;
        let valB = tdB ? parseFloat(tdB.textContent.trim().replace(/,/g, '')) || 0 : 0;

        return currentSortDir === 'asc' ? (valA - valB) : (valB - valA);
    });

    // Re-append
    rows.forEach(row => tbody.appendChild(row));
}
