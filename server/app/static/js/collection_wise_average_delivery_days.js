document.addEventListener('DOMContentLoaded', () => {
    initDeliveryTimelineModal();
    initCollectionGrouping();
    initCollectionSummaryModal();
    initFilters();
    loadReportData();
});

let filterValues = {
    search: '',
    location: '',
    group: '',
    purity: '',
    classification: '',
    make: '',
    master_collection: '',
    collection: '',
    section: '',
    branch_type: '',
    sort_by: '',
    sort_order: 'none',
    page: 1,
    per_page: 50
};

let locationMultiSelect = null;
let searchTimeout = null;
let currentZoom = 1.0;
let deliveryModalPreviousOverflow = '';
let collectionSummaryPreviousOverflow = '';
let collectionSupplierDeliveryController = null;
const collectionDetailControllers = new Map();

function abortCollectionDetailRequests() {
    collectionDetailControllers.forEach(controller => controller.abort());
    collectionDetailControllers.clear();
}

function buildCollectionDetailParams(toggle, page) {
    collectFilterValues();
    const params = new URLSearchParams();

    Object.entries(filterValues).forEach(([key, value]) => {
        if (!['page', 'per_page', 'sort_by', 'sort_order'].includes(key) && value !== '' && value !== null) {
            params.set(key, value);
        }
    });

    params.set('group_collection', toggle.dataset.collectionName || '');
    params.set('detail_page', String(page));
    params.set('detail_per_page', '25');
    return params;
}

async function loadCollectionDetails(toggle, page = 1) {
    const groupId = toggle.dataset.groupId;
    const detailRow = document.querySelector(`[data-collection-detail-row="${groupId}"]`);
    const content = detailRow?.querySelector('[data-collection-detail-content]');
    if (!groupId || !content) return;

    collectionDetailControllers.get(groupId)?.abort();
    const controller = new AbortController();
    collectionDetailControllers.set(groupId, controller);
    toggle.disabled = true;
    content.innerHTML = `
        <div class="flex min-h-16 items-center justify-center gap-2 text-[10px] text-gray-400">
            <span class="size-4 rounded-full border-2 border-primary/20 border-t-primary animate-spin"></span>
            Loading barcode records...
        </div>
    `;

    try {
        const response = await fetch(
            `/partial/collection-wise-average-delivery-days/collection-rows?${buildCollectionDetailParams(toggle, page)}`,
            {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
                signal: controller.signal
            }
        );
        const html = await response.text();
        if (!response.ok) throw new Error(`Request failed with status ${response.status}`);

        content.innerHTML = html;
        content.dataset.loaded = 'true';
        content.dataset.page = String(page);
    } catch (error) {
        if (error.name !== 'AbortError') {
            console.error('Unable to load collection barcode rows:', error);
            content.innerHTML = `
                <div class="flex min-h-16 items-center justify-center gap-2 text-[10px] text-red-500">
                    <span class="material-symbols-outlined text-base">error</span>
                    Unable to load barcode records.
                </div>
            `;
        }
    } finally {
        if (collectionDetailControllers.get(groupId) === controller) {
            collectionDetailControllers.delete(groupId);
            toggle.disabled = false;
        }
    }
}

function initCollectionGrouping() {
    document.addEventListener('click', event => {
        const pageButton = event.target.closest('[data-collection-detail-page]');
        if (pageButton) {
            if (pageButton.disabled) return;
            const detailRow = pageButton.closest('[data-collection-detail-row]');
            const groupId = detailRow?.dataset.collectionDetailRow;
            const toggle = groupId
                ? document.querySelector(`[data-collection-toggle][data-group-id="${groupId}"]`)
                : null;
            const page = Number.parseInt(pageButton.dataset.collectionDetailPage || '1', 10);
            if (toggle && page > 0) loadCollectionDetails(toggle, page);
            return;
        }

        const toggle = event.target.closest('[data-collection-toggle]');
        if (!toggle) return;

        const groupId = toggle.dataset.groupId;
        const detailRow = document.querySelector(`[data-collection-detail-row="${groupId}"]`);
        const content = detailRow?.querySelector('[data-collection-detail-content]');
        const icon = toggle.querySelector('[data-collection-toggle-icon]');
        if (!detailRow || !content) return;

        const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', String(!isExpanded));
        detailRow.classList.toggle('hidden', isExpanded);
        icon?.classList.toggle('rotate-90', !isExpanded);

        if (!isExpanded && content.dataset.loaded !== 'true') {
            loadCollectionDetails(toggle, 1);
        }
    });
}

function setCollectionSummaryText(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) element.textContent = value ?? '-';
}

function formatCollectionSummaryNumber(value, fractionDigits = 0) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
    return Number(value).toLocaleString('en-IN', {
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits
    });
}

function buildSupplierDeliveryParams(collection) {
    collectFilterValues();
    const params = new URLSearchParams();

    Object.entries(filterValues).forEach(([key, value]) => {
        if (!['page', 'per_page', 'sort_by', 'sort_order'].includes(key) && value !== '' && value !== null) {
            params.set(key, value);
        }
    });

    params.set('group_collection', collection || '');
    return params;
}

function showSupplierDeliveryState(state) {
    const loading = document.getElementById('collection-summary-supplier-loading');
    const empty = document.getElementById('collection-summary-supplier-empty');
    const error = document.getElementById('collection-summary-supplier-error');
    const list = document.getElementById('collection-summary-supplier-list');
    const maxBadge = document.getElementById('collection-summary-supplier-max');

    [
        [loading, state === 'loading'],
        [empty, state === 'empty'],
        [error, state === 'error']
    ].forEach(([element, visible]) => {
        if (!element) return;
        element.classList.toggle('hidden', !visible);
        element.classList.toggle('flex', visible);
    });

    list?.classList.toggle('hidden', state !== 'ready');
    maxBadge?.classList.toggle('hidden', state !== 'ready');
}

function renderSupplierDeliveryTimes(data) {
    const list = document.getElementById('collection-summary-supplier-list');
    const maxBadge = document.getElementById('collection-summary-supplier-max');
    const suppliers = Array.isArray(data.suppliers) ? data.suppliers : [];
    if (!list) return;

    list.replaceChildren();
    if (!suppliers.length) {
        showSupplierDeliveryState('empty');
        return;
    }

    if (maxBadge) {
        const maximum = Number(data.max_delivery_days || 0);
        maxBadge.textContent = `Max: ${formatCollectionSummaryNumber(maximum)} day${maximum === 1 ? '' : 's'}`;
    }

    suppliers.forEach(supplier => {
        const row = document.createElement('div');
        row.className = 'grid grid-cols-[minmax(0,180px)_minmax(120px,1fr)_58px] items-center gap-3';

        const identity = document.createElement('div');
        identity.className = 'min-w-0';

        const name = document.createElement('p');
        name.className = 'truncate text-[10px] font-bold text-gray-800 dark:text-gray-200';
        name.textContent = supplier.supplier_name || '-';
        name.title = supplier.supplier_name || '-';

        const records = document.createElement('p');
        records.className = 'mt-0.5 text-[8px] text-gray-400 tabular-nums';
        records.textContent = `${formatCollectionSummaryNumber(supplier.record_count)} record${
            Number(supplier.record_count) === 1 ? '' : 's'
        }`;
        identity.append(name, records);

        const track = document.createElement('div');
        track.className = 'h-2 overflow-hidden rounded bg-gray-100 dark:bg-gray-800';
        track.title = `${supplier.delivery_days || 0} days`;

        const bar = document.createElement('div');
        bar.className = 'h-full rounded bg-primary transition-[width] duration-300';
        bar.style.width = `${Math.min(Math.max(Number(supplier.progress_percent || 0), 0), 100)}%`;
        track.appendChild(bar);

        const days = document.createElement('p');
        days.className = 'text-right text-[10px] font-bold text-gray-900 dark:text-white tabular-nums whitespace-nowrap';
        const deliveryDays = Number(supplier.delivery_days || 0);
        days.textContent = `${formatCollectionSummaryNumber(deliveryDays)}d`;

        row.append(identity, track, days);
        list.appendChild(row);
    });

    showSupplierDeliveryState('ready');
}

async function loadCollectionSupplierDeliveryTimes(collection) {
    collectionSupplierDeliveryController?.abort();
    collectionSupplierDeliveryController = new AbortController();
    const controller = collectionSupplierDeliveryController;
    showSupplierDeliveryState('loading');

    try {
        const response = await fetch(
            `/api/collection-wise-average-delivery-days/supplier-delivery-times?${buildSupplierDeliveryParams(collection)}`,
            {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
                signal: controller.signal
            }
        );
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || data.message || `Request failed with status ${response.status}`);
        renderSupplierDeliveryTimes(data);
    } catch (error) {
        if (error.name !== 'AbortError') {
            console.error('Unable to load supplier delivery times:', error);
            showSupplierDeliveryState('error');
        }
    } finally {
        if (collectionSupplierDeliveryController === controller) {
            collectionSupplierDeliveryController = null;
        }
    }
}

function openCollectionSummaryModal(detail) {
    const modal = document.getElementById('collection-summary-modal');
    if (!modal) return;

    setCollectionSummaryText('collection-summary-title', detail.collection || '-');
    setCollectionSummaryText('collection-summary-subtitle', detail.master_collection || '-');
    setCollectionSummaryText('collection-summary-barcodes', formatCollectionSummaryNumber(detail.barcode_count));
    setCollectionSummaryText('collection-summary-branches', formatCollectionSummaryNumber(detail.branch_count));
    setCollectionSummaryText('collection-summary-sections', formatCollectionSummaryNumber(detail.section_count));
    setCollectionSummaryText('collection-summary-types', formatCollectionSummaryNumber(detail.type_count));
    setCollectionSummaryText('collection-summary-median', `${formatCollectionSummaryNumber(detail.median_tat_days, 1)} days`);
    setCollectionSummaryText('collection-summary-p90', `${formatCollectionSummaryNumber(detail.p90_tat_days, 1)} days`);
    setCollectionSummaryText('collection-summary-maximum', `${formatCollectionSummaryNumber(detail.max_tat_days)} days`);
    setCollectionSummaryText('collection-summary-delayed', formatCollectionSummaryNumber(detail.delayed_count));
    setCollectionSummaryText('collection-summary-received', formatCollectionSummaryNumber(detail.received_inshop_count));
    setCollectionSummaryText('collection-summary-awaiting', formatCollectionSummaryNumber(detail.awaiting_inshop_count));
    setCollectionSummaryText(
        'collection-summary-pending-age',
        detail.avg_pending_age_days === null || detail.avg_pending_age_days === undefined
            ? '-'
            : `${formatCollectionSummaryNumber(detail.avg_pending_age_days, 1)} days`
    );
    setCollectionSummaryText('collection-summary-first-order', formatDeliveryModalDate(detail.first_ordered_date));
    setCollectionSummaryText('collection-summary-last-order', formatDeliveryModalDate(detail.last_ordered_date));
    setCollectionSummaryText('collection-summary-last-morr', formatDeliveryModalDate(detail.last_morr_received_date));

    const average = document.getElementById('collection-summary-average');
    if (average) {
        average.textContent = detail.avg_tat_days === null || detail.avg_tat_days === undefined
            ? '-'
            : `${formatCollectionSummaryNumber(detail.avg_tat_days, 1)} days`;
        average.className = `mt-1 text-sm font-bold tabular-nums ${
            Number(detail.avg_tat_days) > 10
                ? 'text-red-500 dark:text-red-400'
                : 'text-emerald-600 dark:text-emerald-400'
        }`;
    }

    const compliance = Number(detail.compliance_pct || 0);
    const complianceBadge = document.getElementById('collection-summary-compliance-badge');
    if (complianceBadge) {
        complianceBadge.textContent = `${formatCollectionSummaryNumber(compliance, 1)}% compliant`;
        let colorClass = 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400';
        if (compliance >= 80) {
            colorClass = 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400';
        } else if (compliance >= 50) {
            colorClass = 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400';
        }
        complianceBadge.className = `inline-flex rounded px-2 py-1 text-[9px] font-bold uppercase tracking-wider ${colorClass}`;
    }

    const complianceBar = document.getElementById('collection-summary-compliance-bar');
    if (complianceBar) {
        complianceBar.style.width = `${Math.min(Math.max(compliance, 0), 100)}%`;
    }

    collectionSummaryPreviousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    modal.setAttribute('aria-hidden', 'false');
    modal.querySelector('[data-collection-summary-close]:not(.absolute)')?.focus();
    loadCollectionSupplierDeliveryTimes(detail.collection || '');
}

function closeCollectionSummaryModal() {
    const modal = document.getElementById('collection-summary-modal');
    if (!modal || modal.classList.contains('hidden')) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = collectionSummaryPreviousOverflow;
    collectionSupplierDeliveryController?.abort();
    collectionSupplierDeliveryController = null;
}

function initCollectionSummaryModal() {
    const modal = document.getElementById('collection-summary-modal');
    if (!modal) return;

    modal.querySelectorAll('[data-collection-summary-close]').forEach(button => {
        button.addEventListener('click', closeCollectionSummaryModal);
    });

    document.addEventListener('click', event => {
        if (event.target.closest('[data-collection-toggle]')) return;
        const row = event.target.closest('.collection-summary-row');
        if (!row) return;
        try {
            openCollectionSummaryModal(JSON.parse(row.dataset.collectionSummary || '{}'));
        } catch (error) {
            console.error('Unable to open collection summary:', error);
        }
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            closeCollectionSummaryModal();
            return;
        }
        if (event.target.closest('[data-collection-toggle]')) return;

        const row = event.target.closest('.collection-summary-row');
        if (row && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            try {
                openCollectionSummaryModal(JSON.parse(row.dataset.collectionSummary || '{}'));
            } catch (error) {
                console.error('Unable to open collection summary:', error);
            }
        }
    });
}

function setDeliveryModalText(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) element.textContent = value ?? '-';
}

function formatDeliveryModalDate(isoDate) {
    if (!isoDate) return '-';
    const [year, month, day] = isoDate.split('-').map(Number);
    if (!year || !month || !day) return '-';
    return new Date(year, month - 1, day).toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    }).replace(/ /g, '-');
}

function renderDeliveryTimeline(stages) {
    const list = document.getElementById('delivery-timeline-list');
    if (!list) return;
    list.innerHTML = '';

    (stages || []).forEach((stage, index) => {
        const status = stage.status || (stage.completed ? 'completed' : 'pending');
        const isCompleted = status === 'completed';
        const isSkipped = status === 'skipped';

        const item = document.createElement('div');
        let cardBgClass = 'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800/40';
        if (isCompleted) {
            cardBgClass = 'border-blue-100 bg-blue-50/40 dark:border-blue-900/50 dark:bg-blue-900/10';
        } else if (isSkipped) {
            cardBgClass = 'border-dashed border-gray-300 bg-gray-50/60 dark:border-gray-700 dark:bg-gray-800/20 opacity-80';
        }
        item.className = `relative min-w-0 min-h-[112px] rounded-md border p-3 pt-9 shadow-sm transition-colors ${cardBgClass}`;

        const marker = document.createElement('span');
        let markerClass = 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-300';
        if (isCompleted) {
            markerClass = 'bg-primary text-white shadow-sm';
        } else if (isSkipped) {
            markerClass = 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 font-bold';
        }
        marker.className = `absolute left-3 top-3 flex size-4 items-center justify-center rounded-full text-[8px] font-bold ${markerClass}`;
        marker.textContent = String(index + 1);
        item.appendChild(marker);

        const state = document.createElement('span');
        let stateClass = 'text-gray-400';
        let stateText = 'Pending';
        if (isCompleted) {
            stateClass = 'text-primary';
            stateText = 'Completed';
        } else if (isSkipped) {
            stateClass = 'text-amber-600 dark:text-amber-400';
            stateText = 'Skipped / N/A';
        }
        state.className = `absolute right-3 top-3 text-[8px] font-bold uppercase tracking-wider ${stateClass}`;
        state.textContent = stateText;
        item.appendChild(state);

        if (index < stages.length - 1 && index % 4 !== 3) {
            const connector = document.createElement('span');
            connector.className = `material-symbols-outlined absolute -right-[30px] top-1/2 z-10 hidden md:flex size-6 -translate-y-1/2 items-center justify-center rounded-full border bg-white dark:bg-gray-900 text-[16px] shadow-sm ${
                isCompleted && (stages[index + 1]?.completed || stages[index + 1]?.status === 'completed')
                    ? 'border-blue-100 text-primary dark:border-blue-900'
                    : 'border-gray-200 text-gray-300 dark:border-gray-700 dark:text-gray-600'
            }`;
            connector.textContent = 'arrow_forward';
            connector.setAttribute('aria-hidden', 'true');
            item.appendChild(connector);
        }

        const label = document.createElement('p');
        label.className = 'text-[11px] font-bold text-gray-900 dark:text-white truncate';
        label.textContent = stage.label || '-';
        item.appendChild(label);

        const date = document.createElement('p');
        date.className = 'mt-1 text-[10px] font-medium text-gray-500 dark:text-gray-400';
        if (isSkipped) {
            date.textContent = 'N/A';
        } else {
            date.textContent = formatDeliveryModalDate(stage.date);
        }
        item.appendChild(date);

        const stageMetrics = document.createElement('div');
        stageMetrics.className = 'mt-2 flex items-center justify-between gap-2';

        const duration = document.createElement('p');
        duration.className = `text-[9px] font-semibold ${
            isCompleted ? 'text-primary' : (isSkipped ? 'text-amber-600 dark:text-amber-400' : 'text-gray-400')
        }`;
        if (isSkipped) {
            duration.textContent = 'Skipped';
        } else if (!isCompleted) {
            duration.textContent = 'Pending';
        } else if (stage.days_to_next !== null && stage.days_to_next !== undefined) {
            duration.textContent = `${stage.days_to_next} day${stage.days_to_next === 1 ? '' : 's'} to next stage`;
        } else if (index === stages.length - 1) {
            duration.textContent = 'Process complete';
        } else {
            duration.textContent = 'Awaiting next stage';
        }
        stageMetrics.appendChild(duration);

        const cumulative = document.createElement('span');
        cumulative.className = `inline-flex shrink-0 rounded px-1.5 py-0.5 text-[8px] font-bold ${
            stage.cumulative_days !== null && stage.cumulative_days !== undefined
                ? 'bg-blue-100/70 text-primary dark:bg-blue-900/30'
                : 'bg-gray-100 text-gray-400 dark:bg-gray-700'
        }`;
        cumulative.title = 'Cumulative days';
        cumulative.textContent = stage.cumulative_days !== null && stage.cumulative_days !== undefined
            ? `${stage.cumulative_days}d`
            : '-';
        stageMetrics.appendChild(cumulative);
        item.appendChild(stageMetrics);

        list.appendChild(item);
    });
}

function openDeliveryTimelineModal(detail) {
    const modal = document.getElementById('delivery-timeline-modal');
    if (!modal) return;

    setDeliveryModalText('delivery-timeline-title', detail.collection);
    setDeliveryModalText(
        'delivery-timeline-subtitle',
        `${detail.barcode || '-'} · ${detail.branch || '-'}`
    );
    setDeliveryModalText('delivery-modal-product', detail.product);
    setDeliveryModalText(
        'delivery-modal-weight',
        detail.weight === null || detail.weight === undefined
            ? '-'
            : `${Number(detail.weight).toLocaleString('en-IN', {
                minimumFractionDigits: 3,
                maximumFractionDigits: 3
            })} g`
    );
    setDeliveryModalText(
        'delivery-modal-tat',
        detail.tat_days === null || detail.tat_days === undefined ? '-' : `${detail.tat_days} days`
    );

    const variance = document.getElementById('delivery-modal-variance');
    if (variance) {
        variance.className = 'mt-1 text-sm font-bold';
        if (detail.variance_days === null || detail.variance_days === undefined) {
            variance.textContent = '-';
            variance.classList.add('text-gray-400');
        } else if (detail.variance_days > 0) {
            variance.textContent = `+${detail.variance_days} days`;
            variance.classList.add('text-red-500', 'dark:text-red-400');
        } else {
            variance.textContent = `${detail.variance_days} days`;
            variance.classList.add('text-emerald-600', 'dark:text-emerald-400');
        }
    }

    setDeliveryModalText('delivery-modal-status', detail.status);
    setDeliveryModalText('delivery-modal-inshop', formatDeliveryModalDate(detail.inshop_date));
    setDeliveryModalText('delivery-modal-order-type', detail.order_type);
    setDeliveryModalText('delivery-modal-branch-type', detail.branch_type);

    // Requirement A: Extended Product & Taxonomy
    setDeliveryModalText('delivery-modal-purity', detail.purity || '-');
    setDeliveryModalText('delivery-modal-make', detail.make || '-');
    setDeliveryModalText('delivery-modal-classification', detail.classification || '-');
    setDeliveryModalText('delivery-modal-sub-classification', detail.sub_classification || '-');
    setDeliveryModalText('delivery-modal-master-collection', detail.master_collection || '-');
    const sizeScrew = [detail.size, detail.screw_type].filter(Boolean).join(' · ');
    setDeliveryModalText('delivery-modal-size-screw', sizeScrew || '-');
    setDeliveryModalText('delivery-modal-design-no', detail.design_no || '-');
    setDeliveryModalText('delivery-modal-barcode-no', detail.barcode || '-');

    // Location & Branch Details
    setDeliveryModalText('delivery-modal-order-location', detail.branch || '-');
    setDeliveryModalText('delivery-modal-loc-branch-type', detail.branch_type || '-');
    setDeliveryModalText('delivery-modal-received-location', detail.received_location || '-');
    setDeliveryModalText('delivery-modal-current-location', detail.current_location || '-');

    renderDeliveryTimeline(detail.timeline);
    renderStageDurationsTable(detail.stage_durations);

    deliveryModalPreviousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    modal.setAttribute('aria-hidden', 'false');
    modal.querySelector('[data-delivery-modal-close]:not(.absolute)')?.focus();
}

function renderStageDurationsTable(durations) {
    const tbody = document.getElementById('delivery-modal-stage-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!durations || durations.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" class="px-3 py-3 text-center text-gray-400 italic">No completed stage transitions available yet.</td>
            </tr>
        `;
        return;
    }

    durations.forEach(item => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-gray-50 dark:hover:bg-gray-800/50';
        tr.innerHTML = `
            <td class="px-3 py-2 font-semibold text-gray-900 dark:text-white">
                ${item.from_stage} <span class="text-gray-400 mx-1">→</span> ${item.to_stage}
            </td>
            <td class="px-3 py-2 text-gray-600 dark:text-gray-400">${formatDeliveryModalDate(item.start_date)}</td>
            <td class="px-3 py-2 text-gray-600 dark:text-gray-400">${formatDeliveryModalDate(item.end_date)}</td>
            <td class="px-3 py-2 text-right font-mono font-bold text-primary">${item.duration_days} days</td>
        `;
        tbody.appendChild(tr);
    });
}

function closeDeliveryTimelineModal() {
    const modal = document.getElementById('delivery-timeline-modal');
    if (!modal || modal.classList.contains('hidden')) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = deliveryModalPreviousOverflow;
}

function initDeliveryTimelineModal() {
    const modal = document.getElementById('delivery-timeline-modal');
    if (!modal) return;

    modal.querySelectorAll('[data-delivery-modal-close]').forEach(button => {
        button.addEventListener('click', closeDeliveryTimelineModal);
    });

    document.addEventListener('click', event => {
        const row = event.target.closest('.delivery-report-row');
        if (!row) return;
        try {
            openDeliveryTimelineModal(JSON.parse(row.dataset.detail || '{}'));
        } catch (error) {
            console.error('Unable to open delivery timeline:', error);
        }
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            closeDeliveryTimelineModal();
            return;
        }

        const row = event.target.closest('.delivery-report-row');
        if (row && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            try {
                openDeliveryTimelineModal(JSON.parse(row.dataset.detail || '{}'));
            } catch (error) {
                console.error('Unable to open delivery timeline:', error);
            }
        }
    });
}

async function initFilters() {
    try {
        const headers = {};
        const token = localStorage.getItem('access_token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch('/api/collection-wise-average-delivery-days/options', { headers });
        if (!response.ok) {
            console.error('Failed to fetch filter options:', response.status);
            return;
        }
        const options = await response.json();

        // Location multi-select
        const locContainer = document.getElementById('filter-location-container');
        if (locContainer && typeof CustomMultiSelect !== 'undefined') {
            locationMultiSelect = new CustomMultiSelect({
                containerId: 'filter-location-container',
                label: 'Location',
                defaultText: 'All Locations',
                options: (options.locations || []).map(loc => ({ value: loc, label: loc })),
                onChange: (selected) => {
                    filterValues.location = selected.join(',');
                }
            });
        }

        populateSelect('filter-group', options.groups || []);
        populateSelect('filter-purity', options.purities || []);
        populateSelect('filter-classification', options.classifications || []);
        populateSelect('filter-make', options.makes || []);
        populateSelect('filter-master-collection', options.master_collections || []);
        populateSelect('filter-collection', options.collections || []);
        populateSelect('filter-section', options.sections || []);
        populateSelect('filter-branch-type', options.branch_types || []);
    } catch (err) {
        console.error('Error initializing filters:', err);
    }
}

function populateSelect(elementId, items) {
    const select = document.getElementById(elementId);
    if (!select) return;
    items.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item;
        opt.textContent = item;
        select.appendChild(opt);
    });
}

function collectFilterValues() {
    filterValues.group = document.getElementById('filter-group')?.value || '';
    filterValues.purity = document.getElementById('filter-purity')?.value || '';
    filterValues.classification = document.getElementById('filter-classification')?.value || '';
    filterValues.make = document.getElementById('filter-make')?.value || '';
    filterValues.master_collection = document.getElementById('filter-master-collection')?.value || '';
    filterValues.collection = document.getElementById('filter-collection')?.value || '';
    filterValues.section = document.getElementById('filter-section')?.value || '';
    filterValues.branch_type = document.getElementById('filter-branch-type')?.value || '';
    if (locationMultiSelect && typeof locationMultiSelect.getValues === 'function') {
        filterValues.location = locationMultiSelect.getValues().join(',');
    }
}

function applyFilters() {
    collectFilterValues();
    filterValues.page = 1;
    loadReportData();
}

function resetFilters() {
    filterValues = {
        search: '',
        location: '',
        group: '',
        purity: '',
        classification: '',
        make: '',
        master_collection: '',
        collection: '',
        section: '',
        branch_type: '',
        sort_by: '',
        sort_order: 'none',
        page: 1,
        per_page: filterValues.per_page || 50
    };

    const searchInput = document.getElementById('report-search');
    if (searchInput) searchInput.value = '';

    if (locationMultiSelect && typeof locationMultiSelect.reset === 'function') {
        locationMultiSelect.reset();
    }

    ['filter-group', 'filter-purity', 'filter-classification', 'filter-make', 'filter-master-collection', 'filter-collection', 'filter-section', 'filter-branch-type'].forEach(id => {
        const select = document.getElementById(id);
        if (select) select.value = '';
    });

    loadReportData();
}

function onSearchInput(val) {
    clearTimeout(searchTimeout);
    filterValues.search = val.trim();
    filterValues.page = 1;
    searchTimeout = setTimeout(() => {
        loadReportData();
    }, 400);
}

function goToPage(page) {
    filterValues.page = page;
    loadReportData();
}

function updateHeaderPagination() {
    const root = document.getElementById('partial-root');
    const infoSpan = document.getElementById('pagination-info');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const selectPerPage = document.getElementById('per-page-select');

    if (!root) return;

    const page = parseInt(root.dataset.page || '1', 10);
    const perPage = parseInt(root.dataset.perPage || '50', 10);
    const totalPages = parseInt(root.dataset.totalPages || '1', 10);
    const totalRecords = parseInt(root.dataset.totalRecords || '0', 10);

    filterValues.page = page;
    filterValues.per_page = perPage;

    if (selectPerPage) selectPerPage.value = String(perPage);

    if (totalRecords === 0) {
        if (infoSpan) infoSpan.textContent = '0-0 of 0';
        if (btnPrev) btnPrev.disabled = true;
        if (btnNext) btnNext.disabled = true;
        return;
    }

    const startRecord = (page - 1) * perPage + 1;
    const endRecord = Math.min(page * perPage, totalRecords);

    if (infoSpan) infoSpan.textContent = `${startRecord.toLocaleString('en-IN')}-${endRecord.toLocaleString('en-IN')} of ${totalRecords.toLocaleString('en-IN')}`;
    if (btnPrev) btnPrev.disabled = (page <= 1);
    if (btnNext) btnNext.disabled = (page >= totalPages);
}

function changePerPage(newPerPage) {
    filterValues.per_page = parseInt(newPerPage, 10) || 50;
    filterValues.page = 1;
    loadReportData();
}

function goToPrevPage() {
    if (filterValues.page > 1) {
        filterValues.page--;
        loadReportData();
    }
}

function goToNextPage() {
    filterValues.page++;
    loadReportData();
}

async function loadReportData() {
    const container = document.getElementById('view-collection-wise-average-delivery-days');
    const progressBar = document.getElementById('report-progress');

    abortCollectionDetailRequests();
    if (progressBar) progressBar.classList.remove('hidden');

    try {
        const params = new URLSearchParams();
        Object.keys(filterValues).forEach(key => {
            if (filterValues[key] !== '' && filterValues[key] !== null) {
                params.set(key, filterValues[key]);
            }
        });

        const response = await fetch(`/partial/collection-wise-average-delivery-days?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });

        const html = await response.text();
        if (container) {
            container.innerHTML = html;
            updateHeaderPagination();
        }
    } catch (err) {
        console.error('Error loading report data:', err);
        if (container) {
            container.innerHTML = `
                <div class="h-full flex flex-col items-center justify-center p-8 text-center text-red-500">
                    <span class="material-symbols-outlined text-3xl mb-2">error</span>
                    <p class="text-xs font-bold">Failed to load report data.</p>
                </div>
            `;
        }
    } finally {
        if (progressBar) progressBar.classList.add('hidden');
    }
}

function adjustZoom(delta, reset = false) {
    const container = document.getElementById('table-area');
    const label = document.getElementById('zoom-level');
    if (!container) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(0.7, currentZoom + delta), 1.3);
    }

    container.style.transform = `scale(${currentZoom})`;
    container.style.transformOrigin = 'top left';
    if (label) label.textContent = `${Math.round(currentZoom * 100)}%`;
}

async function exportToExcel() {
    const icon = document.getElementById('export-btn-icon');
    const label = document.getElementById('export-btn-label');
    const btn = document.getElementById('btn-export-excel');

    if (btn) btn.disabled = true;
    if (label) label.textContent = 'Queuing...';

    try {
        collectFilterValues();
        const response = await fetch('/api/collection-wise-average-delivery-days/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({ filters: filterValues })
        });

        const res = await response.json();
        if (response.ok && res.status === 'success') {
            if (label) label.textContent = 'Exporting...';
        } else {
            alert('Export failed: ' + (res.message || 'Unknown error'));
            if (label) label.textContent = 'Export';
            if (btn) btn.disabled = false;
        }
    } catch (err) {
        console.error('Export error:', err);
        alert('Failed to initiate export.');
        if (label) label.textContent = 'Export';
        if (btn) btn.disabled = false;
    }
}

function toggleSort(column) {
    if (filterValues.sort_by === column) {
        if (filterValues.sort_order === 'asc') {
            filterValues.sort_order = 'desc';
        } else if (filterValues.sort_order === 'desc') {
            filterValues.sort_by = '';
            filterValues.sort_order = 'none';
        } else {
            filterValues.sort_order = 'asc';
        }
    } else {
        filterValues.sort_by = column;
        filterValues.sort_order = 'asc';
    }
    filterValues.page = 1;
    loadReportData();
}

window.applyFilters = applyFilters;
window.resetFilters = resetFilters;
window.onSearchInput = onSearchInput;
window.goToPage = goToPage;
window.changePerPage = changePerPage;
window.goToPrevPage = goToPrevPage;
window.goToNextPage = goToNextPage;
window.toggleSort = toggleSort;
window.adjustZoom = adjustZoom;
window.exportToExcel = exportToExcel;
