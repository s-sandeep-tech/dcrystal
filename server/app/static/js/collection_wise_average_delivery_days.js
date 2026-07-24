document.addEventListener('DOMContentLoaded', () => {
    initDeliveryTimelineModal();
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
    page: 1
};

let locationMultiSelect = null;
let searchTimeout = null;
let currentZoom = 1.0;
let deliveryModalPreviousOverflow = '';

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
        const item = document.createElement('div');
        item.className = `relative min-w-0 min-h-[112px] rounded-md border p-3 pt-9 shadow-sm transition-colors ${
            stage.completed
                ? 'border-blue-100 bg-blue-50/40 dark:border-blue-900/50 dark:bg-blue-900/10'
                : 'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800/40'
        }`;

        const marker = document.createElement('span');
        marker.className = `absolute left-3 top-3 flex size-4 items-center justify-center rounded-full text-[8px] font-bold ${
            stage.completed
                ? 'bg-primary text-white shadow-sm'
                : 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-300'
        }`;
        marker.textContent = String(index + 1);
        item.appendChild(marker);

        const state = document.createElement('span');
        state.className = `absolute right-3 top-3 text-[8px] font-bold uppercase tracking-wider ${
            stage.completed ? 'text-primary' : 'text-gray-400'
        }`;
        state.textContent = stage.completed ? 'Completed' : 'Pending';
        item.appendChild(state);

        if (index < stages.length - 1 && index % 4 !== 3) {
            const connector = document.createElement('span');
            connector.className = `material-symbols-outlined absolute -right-[30px] top-1/2 z-10 hidden md:flex size-6 -translate-y-1/2 items-center justify-center rounded-full border bg-white dark:bg-gray-900 text-[16px] shadow-sm ${
                stage.completed && stages[index + 1]?.completed
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
        date.textContent = formatDeliveryModalDate(stage.date);
        item.appendChild(date);

        const stageMetrics = document.createElement('div');
        stageMetrics.className = 'mt-2 flex items-center justify-between gap-2';

        const duration = document.createElement('p');
        duration.className = `mt-2 text-[9px] font-semibold ${
            stage.completed ? 'text-primary' : 'text-gray-400'
        }`;
        if (!stage.completed) {
            duration.textContent = 'Pending';
        } else if (stage.days_to_next !== null && stage.days_to_next !== undefined) {
            duration.textContent = `${stage.days_to_next} day${stage.days_to_next === 1 ? '' : 's'} to next stage`;
        } else if (index === stages.length - 1) {
            duration.textContent = 'Process complete';
        } else {
            duration.textContent = 'Awaiting next stage';
        }
        duration.classList.remove('mt-2');
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
    renderDeliveryTimeline(detail.timeline);

    deliveryModalPreviousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    modal.setAttribute('aria-hidden', 'false');
    modal.querySelector('[data-delivery-modal-close]:not(.absolute)')?.focus();
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
        const response = await fetch('/api/collection-wise-average-delivery-days/options', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!response.ok) return;
        const options = await response.json();

        // Location multi-select
        const locContainer = document.getElementById('filter-location-container');
        if (locContainer && typeof CustomMultiSelect !== 'undefined') {
            locationMultiSelect = new CustomMultiSelect({
                containerId: 'filter-location-container',
                placeholder: 'All Locations',
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
        page: 1
    };

    const searchInput = document.getElementById('report-search');
    if (searchInput) searchInput.value = '';

    if (locationMultiSelect) locationMultiSelect.setSelected([]);

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

async function loadReportData() {
    const container = document.getElementById('view-collection-wise-average-delivery-days');
    const progressBar = document.getElementById('report-progress');

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
        if (container) container.innerHTML = html;
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

window.applyFilters = applyFilters;
window.resetFilters = resetFilters;
window.onSearchInput = onSearchInput;
window.goToPage = goToPage;
window.adjustZoom = adjustZoom;
window.exportToExcel = exportToExcel;
