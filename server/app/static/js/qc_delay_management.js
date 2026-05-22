let currentZoom = parseFloat(localStorage.getItem('qc-delay-report-zoom')) || 1.0;
let allModalRows = [];
let selectedModalParties = new Set();
let currentModalSegmentId = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('QC Delay Management JS Initialized');
    adjustZoom(0);

    const urlParams = new URLSearchParams(window.location.search);
    
    // Auto-fill search
    if (urlParams.get('search')) {
        const s = document.getElementById('hierarchy-search');
        if (s) s.value = urlParams.get('search');
    }

    // Auto-fill simple select filters
    ['office', 'status'].forEach(f => {
        const val = urlParams.get(f);
        if (val) {
            const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
            if (el) el.value = val;
        }
    });

    // Auto-fill multiselect checkbox filters
    ['party', 'make'].forEach(f => {
        const val = urlParams.get(f);
        if (val) {
            const selectedVals = val.split(',').map(s => s.trim()).filter(s => s);
            const optionsDiv = document.getElementById(`options-${f}`);
            if (optionsDiv) {
                selectedVals.forEach(v => {
                    const cb = optionsDiv.querySelector(`input[value="${v}"]`);
                    if (cb) cb.checked = true;
                });
                onCheckboxChange(f);
            }
        }
    });

    // Set default values of 1 if no delay parameter is specified in the URL at all
    let hasDelayParams = false;
    ['delay_s1', 'delay_s2', 'delay_s3'].forEach(d => {
        if (urlParams.has(d)) hasDelayParams = true;
    });

    if (!hasDelayParams) {
        urlParams.set('delay_s1', '1');
        urlParams.set('delay_s2', '1');
        urlParams.set('delay_s3', '1');
        const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
        window.history.replaceState({path: newUrl}, '', newUrl);
    }

    ['delay_s1', 'delay_s2', 'delay_s3'].forEach(d => {
        const val = urlParams.get(d);
        if (val) {
            const el = document.getElementById(`filter-${d.replace(/_/g, '-')}`);
            if (el) el.value = val;
        }
    });

    setupDynamicTooltips();
    loadReport();
});

// Generic custom dropdown controls
function toggleDropdown(type) {
    const dropdown = document.getElementById(`dropdown-${type}`);
    const arrow = document.getElementById(`arrow-${type}`);
    if (!dropdown || !arrow) return;
    
    // Close other dropdowns first
    ['party', 'make'].forEach(t => {
        if (t !== type) {
            const d = document.getElementById(`dropdown-${t}`);
            const a = document.getElementById(`arrow-${t}`);
            if (d) d.classList.add('hidden');
            if (a) a.classList.remove('rotate-180');
        }
    });

    const isHidden = dropdown.classList.contains('hidden');
    if (isHidden) {
        dropdown.classList.remove('hidden');
        arrow.classList.add('rotate-180');
        
        // Add click-away handler to document
        setTimeout(() => {
            const closeHandler = (e) => {
                const wrapper = document.getElementById(`filter-${type}-wrapper`);
                if (wrapper && !wrapper.contains(e.target)) {
                    dropdown.classList.add('hidden');
                    arrow.classList.remove('rotate-180');
                    document.removeEventListener('click', closeHandler);
                }
            };
            document.addEventListener('click', closeHandler);
        }, 50);
    } else {
        dropdown.classList.add('hidden');
        arrow.classList.remove('rotate-180');
    }
}

function filterDropdownOptions(type, query) {
    const optionsDiv = document.getElementById(`options-${type}`);
    if (!optionsDiv) return;
    
    const labels = optionsDiv.getElementsByTagName('label');
    const cleanQuery = query.toLowerCase().trim();
    
    for (let i = 0; i < labels.length; i++) {
        const text = labels[i].textContent || labels[i].innerText;
        if (text.toLowerCase().includes(cleanQuery)) {
            labels[i].style.display = '';
        } else {
            labels[i].style.display = 'none';
        }
    }
}

function clearDropdown(type) {
    const optionsDiv = document.getElementById(`options-${type}`);
    if (!optionsDiv) return;
    
    const checkboxes = optionsDiv.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
    
    // Clear search input
    const wrapper = document.getElementById(`filter-${type}-wrapper`);
    if (wrapper) {
        const searchInput = wrapper.querySelector('input[type="text"]');
        if (searchInput) {
            searchInput.value = '';
            filterDropdownOptions(type, '');
        }
    }
    
    onCheckboxChange(type);
}

function onCheckboxChange(type) {
    const optionsDiv = document.getElementById(`options-${type}`);
    if (!optionsDiv) return;
    
    const checkedBoxes = optionsDiv.querySelectorAll('input[type="checkbox"]:checked');
    const selectCountSpan = document.getElementById(`${type}-select-count`);
    const selectedLabelSpan = document.getElementById(`${type}-selected-label`);
    
    if (checkedBoxes.length > 0) {
        if (selectCountSpan) {
            selectCountSpan.textContent = `${checkedBoxes.length} selected`;
            selectCountSpan.classList.remove('hidden');
        }
        
        const names = Array.from(checkedBoxes).map(cb => cb.value);
        if (selectedLabelSpan) {
            selectedLabelSpan.textContent = names.join(', ');
            selectedLabelSpan.classList.remove('text-gray-500', 'dark:text-gray-400');
            selectedLabelSpan.classList.add('text-gray-900', 'dark:text-white', 'font-semibold');
        }
    } else {
        if (selectCountSpan) {
            selectCountSpan.classList.add('hidden');
        }
        if (selectedLabelSpan) {
            selectedLabelSpan.textContent = type === 'party' ? 'All Parties' : 'All Makes';
            selectedLabelSpan.classList.remove('text-gray-900', 'dark:text-white', 'font-semibold');
            selectedLabelSpan.classList.add('text-gray-500', 'dark:text-gray-400');
        }
    }
}

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

    // Office & Status (simple select)
    ['office', 'status'].forEach(f => {
        const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
        if (el && el.value) urlParams.set(f, el.value); else if (f !== 'status') urlParams.delete(f);
    });

    // Party & Make (multiselect checkboxes)
    ['party', 'make'].forEach(f => {
        const optionsDiv = document.getElementById(`options-${f}`);
        if (optionsDiv) {
            const checked = optionsDiv.querySelectorAll('input[type="checkbox"]:checked');
            if (checked.length > 0) {
                const vals = Array.from(checked).map(cb => cb.value);
                urlParams.set(f, vals.join(','));
            } else {
                urlParams.delete(f);
            }
        }
    });

    const delays = ['delay_s1', 'delay_s2', 'delay_s3'];
    delays.forEach(d => {
        const el = document.getElementById(`filter-${d.replace(/_/g, '-')}`);
        if (el && el.value) urlParams.set(d, el.value); else urlParams.delete(d);
    });

    urlParams.set('page', 1);
    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.pushState({path: newUrl}, '', newUrl);
    loadReport();
}

function resetFilters() {
    const newUrl = window.location.pathname + '?status=segment_1&page=1&delay_s1=1&delay_s2=1&delay_s3=1';
    window.history.pushState({path: newUrl}, '', newUrl);
    
    // Reset DOM elements
    const s = document.getElementById('hierarchy-search');
    if (s) s.value = '';
    
    ['office', 'status'].forEach(f => {
        const el = document.getElementById(`filter-${f.replace(/_/g, '-')}`);
        if (el) el.value = (f === 'status' ? 'segment_1' : '');
    });

    ['party', 'make'].forEach(f => {
        clearDropdown(f);
    });
    
    ['delay_s1', 'delay_s2', 'delay_s3'].forEach(d => {
        const el = document.getElementById(`filter-${d.replace(/_/g, '-')}`);
        if (el) el.value = '1';
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

function openDetailsModal(party, qc_ro, segment_id) {
    const modal = document.getElementById('detailsModal');
    const content = document.getElementById('modalContent');
    const title = document.getElementById('modalTitle');
    const subtitle = document.getElementById('modalSubtitle');
    
    let segmentName = "";
    if (segment_id === 1) segmentName = "QC Issue Completed - Receipt Pending";
    else if (segment_id === 2) segmentName = "QC Receipt Completed - QC Pending";
    else if (segment_id === 3) segmentName = "QC Completed - Invoice Request Pending";
    
    const displayIdentifier = party || qc_ro;
    title.textContent = `Purchase Order Details - ${displayIdentifier}`;
    subtitle.textContent = segmentName;
    content.innerHTML = '<div class="flex justify-center p-12"><div class="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div></div>';
    
    currentModalSegmentId = segment_id;
    selectedModalParties.clear();
    document.getElementById('modalFilterBar').classList.add('hidden');
    document.getElementById('modalPartyFilterContainer').innerHTML = '';
    document.getElementById('clearModalFilterBtn').classList.add('hidden');
    
    modal.classList.remove('hidden');

    let queryParams = `segment_id=${segment_id}`;
    if (qc_ro) queryParams += `&qc_ro=${encodeURIComponent(qc_ro)}`;

    const urlParams = new URLSearchParams(window.location.search);
    let selectedParty = party;
    if (!selectedParty) {
        selectedParty = urlParams.get('party');
        if (!selectedParty) {
            const checkedBoxes = document.querySelectorAll('#options-party input[type="checkbox"]:checked');
            if (checkedBoxes.length > 0) {
                selectedParty = Array.from(checkedBoxes).map(cb => cb.value).join(',');
            }
        }
    }
    if (selectedParty) queryParams += `&party=${encodeURIComponent(selectedParty)}`;

    let selectedMake = urlParams.get('make');
    if (!selectedMake) {
        const checkedBoxes = document.querySelectorAll('#options-make input[type="checkbox"]:checked');
        if (checkedBoxes.length > 0) {
            selectedMake = Array.from(checkedBoxes).map(cb => cb.value).join(',');
        }
    }
    if (selectedMake) queryParams += `&make=${encodeURIComponent(selectedMake)}`;

    const delayS1 = document.getElementById('filter-delay-s1')?.value;
    const delayS2 = document.getElementById('filter-delay-s2')?.value;
    const delayS3 = document.getElementById('filter-delay-s3')?.value;

    if (segment_id === 1 && delayS1) {
        queryParams += `&delay=${encodeURIComponent(delayS1)}`;
    } else if (segment_id === 2 && delayS2) {
        queryParams += `&delay=${encodeURIComponent(delayS2)}`;
    } else if (segment_id === 3 && delayS3) {
        queryParams += `&delay=${encodeURIComponent(delayS3)}`;
    }

    fetch(`/api/qc-delay-management/details/${segment_id}?${queryParams}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.length === 0) {
                content.innerHTML = '<div class="p-12 text-center text-gray-500">No detailed records found for this office/party and segment.</div>';
                return;
            }
            allModalRows = data;
            initModalPartyFilter(data);
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
    selectedModalParties.clear();
    currentModalSegmentId = null;
}

function initModalPartyFilter(data) {
    const container = document.getElementById('modalPartyFilterContainer');
    const filterBar = document.getElementById('modalFilterBar');
    
    // Extract unique parties
    const parties = [...new Set(data.map(row => row.party).filter(p => p))].sort();
    
    if (parties.length <= 1) {
        filterBar.classList.add('hidden');
        return;
    }

    filterBar.classList.remove('hidden');
    container.innerHTML = parties.map(party => `
        <button onclick="toggleModalPartyTag(this, '${party.replace(/'/g, "\\'")}')" 
                class="modal-party-tag px-2.5 py-1 rounded-full border border-gray-200 dark:border-gray-700 text-[10px] font-bold transition-all hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400">
            ${party}
        </button>
    `).join('');
}

function toggleModalPartyTag(btn, party) {
    if (selectedModalParties.has(party)) {
        selectedModalParties.delete(party);
        btn.classList.remove('bg-primary', 'text-white', 'border-primary', 'shadow-sm');
        btn.classList.add('text-gray-500', 'dark:text-gray-400', 'border-gray-200', 'dark:border-gray-700');
    } else {
        selectedModalParties.add(party);
        btn.classList.add('bg-primary', 'text-white', 'border-primary', 'shadow-sm');
        btn.classList.remove('text-gray-500', 'dark:text-gray-400', 'border-gray-200', 'dark:border-gray-700');
    }

    const clearBtn = document.getElementById('clearModalFilterBtn');
    if (selectedModalParties.size > 0) clearBtn.classList.remove('hidden');
    else clearBtn.classList.add('hidden');

    applyModalFiltering();
}

function applyModalFiltering() {
    let filteredData = allModalRows;
    if (selectedModalParties.size > 0) {
        filteredData = allModalRows.filter(row => selectedModalParties.has(row.party));
    }
    renderRichModalContent(filteredData, currentModalSegmentId);
}

function clearModalPartyFilter() {
    selectedModalParties.clear();
    document.querySelectorAll('.modal-party-tag').forEach(btn => {
        btn.classList.remove('bg-primary', 'text-white', 'border-primary', 'shadow-sm');
        btn.classList.add('text-gray-500', 'dark:text-gray-400', 'border-gray-200', 'dark:border-gray-700');
    });
    document.getElementById('clearModalFilterBtn').classList.add('hidden');
    renderRichModalContent(allModalRows, currentModalSegmentId);
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

    // Group data by PO Number
    const groupedData = {};
    data.forEach(row => {
        const po = row.po_number || 'UNKNOWN_PO';
        if (!groupedData[po]) {
            groupedData[po] = {
                ...row,
                _qc_numbers: new Set(),
                _qc_dates: new Set(),
                _snapshot_dates: new Set(),
                _qc_ros: new Set(),
                _qc_ro_incharges: new Set(),
                
                _po_dates: new Set(),
                _order_nos: new Set(),
                _party_mobile_nos: new Set(),
                _business_head_names: new Set(),
                
                _designs: new Set(),
                _set_identifiers: new Set(),
                _set_designs: new Set(),
                _barcode_dates: new Set(),
                _target_dates: new Set(),
                
                _final_qc_receipts: new Set(),
                _order_ros: new Set(),
                
                piece_count: 0,
                gross_weight: 0,
                net_weight: 0,
                stone_weight: 0,
                barcoded_weight: 0
            };
        }
        
        const g = groupedData[po];
        g.piece_count += 1;
        g.gross_weight += parseFloat(row.gross_weight || 0);
        g.net_weight += parseFloat(row.net_weight || row.weight || 0);
        g.stone_weight += parseFloat(row.stone_weight || 0);
        g.barcoded_weight += parseFloat(row.barcoded_weight || 0);
        
        // Col 1
        const qcNo = segment_id === 3 ? (row.qc_number || 'N/A') : (row.qc_req_no || row.id || 'N/A');
        g._qc_numbers.add(qcNo);
        
        const qcDt = row.qc_completed_date ? row.qc_completed_date.split('T')[0] : (row.qc_date ? row.qc_date.split('T')[0] : 'N/A');
        g._qc_dates.add(qcDt);
        
        if (row.snapshot_date) g._snapshot_dates.add(row.snapshot_date.split('T')[0]);
        if (row.qc_ro) g._qc_ros.add(row.qc_ro);
        if (row.qc_ro_incharge) g._qc_ro_incharges.add(row.qc_ro_incharge);
        
        // Col 2
        if (row.po_date) g._po_dates.add(row.po_date.split('T')[0]);
        if (row.order_no) g._order_nos.add(row.order_no);
        if (row.party_mobile_no) g._party_mobile_nos.add(row.party_mobile_no);
        if (row.business_head_name) g._business_head_names.add(row.business_head_name);
        
        // Col 3
        if (row.design_no) g._designs.add(row.design_no);
        if (row.set_identifier) g._set_identifiers.add(row.set_identifier);
        if (row.set_design_no) g._set_designs.add(row.set_design_no);
        
        const bcDt = row.barcode_date ? row.barcode_date.split('T')[0] : (row.barcode_completion_date ? row.barcode_completion_date.split('T')[0] : 'N/A');
        g._barcode_dates.add(bcDt);
        
        const targetDt = row.delivery_target_date ? row.delivery_target_date.split('T')[0] : (row.target_date ? row.target_date.split('T')[0] : 'N/A');
        g._target_dates.add(targetDt);
        
        // Col 4
        if (row.final_qc_receipt_no) g._final_qc_receipts.add(row.final_qc_receipt_no);
        if (row.order_ro) g._order_ros.add(row.order_ro);
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
            qc_number_fmt: formatArr(g._qc_numbers, 3),
            qc_date_fmt: formatArr(g._qc_dates, 3),
            snapshot_date_fmt: formatArr(g._snapshot_dates, 3),
            qc_ro_fmt: formatArr(g._qc_ros, 3),
            qc_ro_incharge_fmt: formatArr(g._qc_ro_incharges, 3),
            
            po_date_fmt: formatArr(g._po_dates, 3),
            order_no_fmt: formatArr(g._order_nos, 3),
            party_mobile_no_fmt: formatArr(g._party_mobile_nos, 3),
            business_head_name_fmt: formatArr(g._business_head_names, 3),
            
            design_no_fmt: formatArr(g._designs, 3),
            set_identifier_fmt: formatArr(g._set_identifiers, 3),
            set_design_no_fmt: formatArr(g._set_designs, 3),
            barcode_date_fmt: formatArr(g._barcode_dates, 3),
            target_date_fmt: formatArr(g._target_dates, 3),
            
            final_qc_receipt_no_fmt: formatArr(g._final_qc_receipts, 3),
            order_ro_fmt: formatArr(g._order_ros, 3)
        };
    });

    processedData.forEach(row => {
        const isSegment3 = segment_id === 3;
        html += `
            <tr class="hover:bg-gray-50/50 dark:hover:bg-gray-800/50 transition-colors">
                <!-- QC INFO -->
                <td class="px-4 py-4 align-top">
                    <div class="flex flex-col gap-0.5">
                        <span class="text-xs font-bold text-orange-600 cursor-help" title="${row.qc_number_fmt.full}">No: ${row.qc_number_fmt.display}</span>
                        <span class="text-[10px] text-gray-400 cursor-help" title="${row.qc_date_fmt.full}">QC Date: ${row.qc_date_fmt.display}</span>
                        <span class="text-[10px] font-bold text-emerald-600 cursor-help" title="${row.snapshot_date_fmt.full}">Comp: ${row.snapshot_date_fmt.display}</span>
                        <span class="text-[10px] text-gray-500 cursor-help" title="${row.qc_ro_fmt.full}">RO: ${row.qc_ro_fmt.display}</span>
                        ${isSegment3 ? `<span class="text-[10px] text-indigo-600 font-bold cursor-help" title="${row.qc_ro_incharge_fmt.full}">RO Incharge: ${row.qc_ro_incharge_fmt.display}</span>` : ''}
                    </div>
                </td>

                <!-- PO INFO -->
                <td class="px-4 py-4 align-top">
                    <div class="flex flex-col gap-0.5">
                        <span class="text-xs font-bold text-blue-600">${row.po_number || 'N/A'}</span>
                        <span class="text-[10px] text-gray-400 cursor-help" title="${row.po_date_fmt.full}">${row.po_date_fmt.display}</span>
                        <span class="text-[10px] text-gray-500 font-bold cursor-help" title="${row.order_no_fmt.full}">Order No: ${row.order_no_fmt.display}</span>
                        <span class="text-[10px] text-gray-400 flex items-center gap-1 cursor-help" title="${row.party_mobile_no_fmt.full}">
                            <span class="material-symbols-outlined text-[12px]">phone</span> ${row.party_mobile_no_fmt.display}
                        </span>
                        <span class="text-[10px] font-bold text-blue-700 cursor-help" title="${row.business_head_name_fmt.full}">BH: ${row.business_head_name_fmt.display}</span>
                    </div>
                </td>

                <!-- DESIGN / SET -->
                <td class="px-4 py-4 align-top">
                    <div class="flex flex-col gap-0.5">
                        <span class="text-xs font-bold text-gray-700 dark:text-gray-300 cursor-help" title="${row.design_no_fmt.full}">Design: ${row.design_no_fmt.display}</span>
                        <span class="text-[10px] text-gray-400 cursor-help" title="Set ID: ${row.set_identifier_fmt.full} / Set Design: ${row.set_design_no_fmt.full}">Set: ${row.set_identifier_fmt.display} (${row.set_design_no_fmt.display})</span>
                        <span class="text-[10px] font-bold text-blue-600 cursor-help" title="${row.barcode_date_fmt.full}">BC Date: ${row.barcode_date_fmt.display}</span>
                        <span class="text-[10px] font-bold text-red-500 cursor-help" title="${row.target_date_fmt.full}">Target: ${row.target_date_fmt.display}</span>
                    </div>
                </td>

                <!-- STATUS / INVOICE -->
                <td class="px-4 py-4 align-top">
                    <div class="flex flex-col gap-1.5 mt-1">
                        <div class="flex items-center gap-2">
                            <span class="size-1.5 rounded-full bg-emerald-500"></span>
                            <span class="text-[10px] font-bold text-gray-600 dark:text-gray-400">QC COMP</span>
                        </div>
                        <div class="flex items-center gap-2 ${isSegment3 ? '' : 'opacity-40'}">
                            <span class="size-1.5 rounded-full ${isSegment3 ? 'bg-orange-500' : 'bg-gray-400'}"></span>
                            <span class="text-[10px] font-bold text-gray-600 dark:text-gray-400">${isSegment3 ? 'HM COMP' : 'RATE REQ'}</span>
                        </div>
                        <div class="flex items-center gap-2 opacity-40">
                            <span class="size-1.5 rounded-full bg-gray-400"></span>
                            <span class="text-[10px] font-bold text-gray-600 dark:text-gray-400">INVOICED</span>
                        </div>
                        <div class="mt-1 flex flex-col gap-0.5">
                            <span class="text-[10px] font-bold text-blue-600 cursor-help" title="${row.final_qc_receipt_no_fmt.full}">Receipt: ${row.final_qc_receipt_no_fmt.display}</span>
                            <span class="text-[10px] text-gray-400 cursor-help" title="${row.order_ro_fmt.full}">Order RO: ${row.order_ro_fmt.display}</span>
                        </div>
                    </div>
                </td>

                <!-- WEIGHTS -->
                <td class="px-4 py-4 align-top text-right">
                    <div class="flex flex-col gap-0.5 font-mono">
                        <span class="text-[11px] text-gray-600 dark:text-gray-400"><span class="font-bold">G:</span> ${formatWeight(row.gross_weight)}</span>
                        <span class="text-[11px] text-gray-600 dark:text-gray-400"><span class="font-bold">N:</span> ${formatWeight(row.net_weight)}</span>
                        <span class="text-[11px] text-gray-600 dark:text-gray-400"><span class="font-bold">S:</span> ${formatWeight(row.stone_weight)}</span>
                        <span class="text-[11px] text-blue-600 font-bold"><span class="font-bold">BC:</span> ${formatWeight(row.barcoded_weight)}</span>
                    </div>
                </td>

                <!-- SUMMARY -->
                <td class="px-4 py-4 align-top text-right">
                    <div class="flex flex-col items-end">
                        <span class="text-lg font-black text-emerald-600 leading-tight">${formatWeight(row.net_weight)}</span>
                        <span class="text-[10px] font-bold text-gray-400">${row.piece_count} PCS</span>
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

function openContactModal(row) {
    const modal = document.getElementById('contactModal');
    if (!modal) return;

    // Populate data
    document.getElementById('contactModalTitle').textContent = row.qc_ro || 'N/A';
    document.getElementById('contact-incharge').textContent = row.qc_ro_incharge || 'N/A';
    
    const emailEl = document.getElementById('contact-email');
    emailEl.textContent = row.qc_ro_incharge_email || 'N/A';
    emailEl.href = row.qc_ro_incharge_email ? `mailto:${row.qc_ro_incharge_email}` : '#';
    
    document.getElementById('contact-phone').textContent = row.qc_ro_incharge_phone_number || 'N/A';
    document.getElementById('contact-address').textContent = row.qc_ro_address || 'Address not available';

    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        modal.querySelector('.relative').classList.remove('scale-95');
    }, 10);
}

function closeContactModal() {
    const modal = document.getElementById('contactModal');
    if (!modal) return;
    
    modal.classList.add('opacity-0');
    modal.querySelector('.relative').classList.add('scale-95');
    setTimeout(() => {
        modal.classList.add('hidden');
    }, 300);
}
