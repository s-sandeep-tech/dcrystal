const statAnimations = new WeakMap();
const chartSnapshots = new WeakMap();
let activeReportController;
let latestReportRequest = 0;

function animateStatValue(node, target, format, unavailable = 'N/A') {
    if (!node) return;
    const valid = typeof target === 'number' && Number.isFinite(target);
    const old = statAnimations.get(node);
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (valid && old?.target === target && old.frame && !reduced) return;
    if (old?.frame) cancelAnimationFrame(old.frame);
    if (!valid) {
        if (node.textContent !== unavailable) node.textContent = unavailable;
        statAnimations.set(node, { current: null, target: null });
        return;
    }
    const finalText = format(target);
    const from = old?.current ?? (node.textContent.includes('N/A') ? target : 0);
    const state = { current: from, target, frame: null };
    statAnimations.set(node, state);
    if (reduced || from === target) {
        if (node.textContent !== finalText) node.textContent = finalText;
        state.current = target;
        return;
    }
    const start = performance.now();
    function step(now) {
        const progress = Math.max(0, Math.min(1, (now - start) / 700));
        state.current = from + (target - from) * (1 - Math.pow(1 - progress, 3));
        const done = progress === 1 || matchMedia('(prefers-reduced-motion: reduce)').matches;
        const text = done ? finalText : format(state.current);
        if (node.textContent !== text) node.textContent = text;
        if (done) { state.current = target; state.frame = null; }
        else state.frame = requestAnimationFrame(step);
    }
    state.frame = requestAnimationFrame(step);
}

function refreshDashboardChart(chart) {
    const signature = JSON.stringify(chart.data);
    if (chartSnapshots.get(chart) === signature) return;
    chart.options.animation = { duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 650, easing: 'easeOutCubic' };
    chart.update();
    // Chart.js may assign default dataset colors during update.
    chartSnapshots.set(chart, JSON.stringify(chart.data));
}

function reportRefreshMessage(message) {
    let banner = document.getElementById('akt-refresh-message');
    if (!banner) {
        banner = document.createElement('div'); banner.id = 'akt-refresh-message';
        banner.className = 'hidden items-center justify-between gap-3 mb-3 px-3 py-2 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-300 text-xs';
        banner.setAttribute('role', 'status');
        banner.append(document.createElement('span'));
        const retry = document.createElement('button'); retry.type = 'button'; retry.textContent = 'Retry now';
        retry.className = 'font-semibold underline whitespace-nowrap';
        retry.addEventListener('click', () => loadDashboardData(null, false, true)); banner.append(retry);
        const main = document.getElementById('akt-main') || document.body;
        main.insertBefore(banner, main.children[1] || null);
    }
    banner.firstElementChild.textContent = message || '';
    banner.classList.toggle('hidden', !message); banner.classList.toggle('flex', Boolean(message));
}

function waitForReportRetry(ms, signal) {
    return new Promise((resolve, reject) => {
        if (signal.aborted) return reject(new DOMException('Cancelled', 'AbortError'));
        const cancel = () => { clearTimeout(timer); reject(new DOMException('Cancelled', 'AbortError')); };
        const timer = setTimeout(() => { signal.removeEventListener('abort', cancel); resolve(); }, ms);
        signal.addEventListener('abort', cancel, { once: true });
    });
}

let charts = {};
let filtersInitialized = false;
let divisionMultiSelect;

function updateDivisionOptions(options, selected) {
    const select = document.getElementById('filter-division');
    const normalized = new Set(selected.map(value => value.toUpperCase()));
    const available = [...new Set(options.filter(Boolean))];
    // Keep explicit selections when cascading options temporarily have no matches.
    selected.forEach(value => { if (!available.some(item => item.toUpperCase() === value.toUpperCase())) available.push(value); });
    select.replaceChildren();
    available.forEach(value => select.add(new Option(value, value, false, normalized.has(value.toUpperCase()))));
    if (divisionMultiSelect) {
        divisionMultiSelect.populateOptions(available);
        document.querySelectorAll('.akt-division-multi-checkbox').forEach(checkbox => { checkbox.checked = normalized.has(checkbox.value.toUpperCase()); });
        divisionMultiSelect.updateTriggerText();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Set default date to today
    const dateInput = document.getElementById('filter-date');
    if (dateInput) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;
    }

    divisionMultiSelect = new CustomMultiSelect({
        containerId: 'akt-division-multi', defaultText: 'All Divisions', options: ['Gold', 'Diamond'],
        onChange: values => {
            const select = document.getElementById('filter-division');
            [...select.options].forEach(option => { option.selected = values.includes(option.value); });
            loadDashboardData('filter-division');
        }
    });
    updateDivisionOptions(['Gold', 'Diamond'], ['Gold', 'Diamond']);
    initCharts();

    // Set default country if specified
    const countrySelect = document.getElementById('filter-country');
    if (countrySelect) {
        countrySelect.value = 'India';
    }

    loadDashboardData();

    // Setup filter listeners
    const filterIds = ['date', 'country', 'region', 'state', 'location', 'division', 'subledger'];
    filterIds.forEach(f => {
        const el = document.getElementById(`filter-${f}`);
        if (el) el.addEventListener('change', (e) => loadDashboardData(e.target.id));
    });

    // Real-time Sync Listener (Dedicated AKT Relay)
    if (window.socket) {
        // Socket.IO emits connect for initial connection and each reconnection.
        // The page already performs its initial load, so only reload after reconnects.
        let hasConnected = Boolean(window.socket.connected);
        window.socket.on('disconnect', () => { hasConnected = true; });
        window.socket.on('connect', () => {
            const reconnecting = hasConnected;
            hasConnected = true;
            if (reconnecting) loadDashboardData(null, false, true);
        });
        window.socket.on('aktPerformanceRefresh', (data) => {
            console.log('Real-time AKT sync triggered:', data);

            // Show toast if available
            if (window.showToast) {
                window.showToast('Data Synced', data.message || 'Dashboard updated with latest transaction data', 'success');
            }

            // Refresh data (uses current filters) - Silent Background Load
            loadDashboardData(null, false, true);
        });
    }
});

function resetFilters() {
    // 1. Reset Date to Today
    const dateInput = document.getElementById('filter-date');
    if (dateInput) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }

    // 2. Reset Country to default 'India'
    const countrySelect = document.getElementById('filter-country');
    if (countrySelect) {
        countrySelect.value = 'India';
    }

    // 3. Reset All others to empty
    const otherFilters = ['region', 'state', 'location', 'subledger'];
    otherFilters.forEach(f => {
        const el = document.getElementById(`filter-${f}`);
        if (el) el.value = '';
    });

    updateDivisionOptions([...document.getElementById('filter-division').options].map(option => option.value), ['Gold', 'Diamond']);

    // 4. Reset initialization flag to allow full re-population of cascading filters
    filtersInitialized = false;

    // 5. Reload data with is_initial=true
    loadDashboardData(null);
}

function initCharts() {
    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { font: { size: 10, weight: 'bold' }, color: '#94a3b8' }
            }
        },
        scales: {
            x: { grid: { display: false }, ticks: { font: { size: 9 }, color: '#94a3b8' } },
            y: { grid: { color: 'rgba(148, 163, 184, 0.1)' }, ticks: { font: { size: 9 }, color: '#94a3b8' } }
        }
    };

    // --- Section 1: Billing ---
    charts.perMin = new Chart(document.getElementById('chart-per-min-efficiency').getContext('2d'), {
        type: 'line',
        data: { 
            labels: [], 
            datasets: [
                { label: 'Current Total Bills', data: [], borderColor: '#137fec', tension: 0.4, fill: true, backgroundColor: 'rgba(19, 127, 236, 0.1)' },
                { label: '2025 Total Bills', data: [], borderColor: '#fbbf24', tension: 0.4, fill: false }
            ] 
        },
        options: { ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: true } } }
    });
 
    charts.hourly = new Chart(document.getElementById('chart-hourly-count').getContext('2d'), {
        type: 'bar',
        data: { 
            labels: [], 
            datasets: [
                { label: 'Current Count', data: [], backgroundColor: '#137fec', borderRadius: 4 },
                { label: '2025 Count', data: [], backgroundColor: '#fbbf24', borderRadius: 4 }
            ] 
        },
        options: chartDefaults
    });
 
    charts.perMinLoc = new Chart(document.getElementById('chart-per-min-location').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Avg Per Min', data: [], backgroundColor: '#2dd4bf', borderRadius: 4 }] },
        options: chartDefaults
    });
 
    charts.hourlyLoc = new Chart(document.getElementById('chart-hourly-location').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Hourly Count', data: [], backgroundColor: '#6366f1', borderRadius: 4 }] },
        options: chartDefaults
    });
 
    // --- Section 2: Revenue ---
    charts.scatter = new Chart(document.getElementById('chart-revenue-scatter').getContext('2d'), {
        type: 'scatter',
        data: { datasets: [{ label: 'Revenue (₹) vs Bills/Hour', data: [], backgroundColor: '#137fec', pointRadius: 5 }] },
        options: { ...chartDefaults, scales: { x: { title: { display: true, text: 'Efficiency (Bills/Hour)' } }, y: { title: { display: true, text: 'Revenue (₹)' } } } }
    });
 
    charts.revenueHour = new Chart(document.getElementById('chart-revenue-hour').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Revenue (₹)', data: [], backgroundColor: '#137fec', borderRadius: 4 }] },
        options: chartDefaults
    });
 
    charts.daily = new Chart(document.getElementById('chart-daily-trend').getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Sales (₹)', data: [], borderColor: '#137fec', tension: 0.3, yAxisID: 'y' },
                { label: 'Turnover (₹)', data: [], borderColor: '#f59e0b', tension: 0.3, yAxisID: 'y' }
            ]
        },
        options: {
            ...chartDefaults,
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: {
                        font: { size: 9 },
                        color: '#94a3b8',
                        callback: (val) => formatCompactNumber(val)
                    }
                }
            }
        }
    });
 
    // --- Section 3: Performance ---
    charts.salesLoc = new Chart(document.getElementById('chart-sales-location').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Sales (Lakhs ₹)', data: [], backgroundColor: '#feb101', borderRadius: 4 }] },
        options: {
            ...chartDefaults,
            plugins: {
                ...chartDefaults.plugins,
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const val = context.parsed.y;
                            const original = val * 100000;
                            return `Sales: ${val.toFixed(2)} Lakhs (₹${original.toLocaleString('en-IN')})`;
                        }
                    }
                }
            }
        }
    });
 
    charts.salesState = new Chart(document.getElementById('chart-sales-state').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Sales (₹)', data: [], backgroundColor: '#10b981', borderRadius: 4 }] },
        options: {
            ...chartDefaults,
            scales: {
                ...chartDefaults.scales,
                y: {
                    ...chartDefaults.scales.y,
                    ticks: {
                        ...chartDefaults.scales.y.ticks,
                        callback: (val) => formatCompactNumber(val)
                    }
                }
            }
        }
    });
 
    charts.salesDivision = new Chart(document.getElementById('chart-sales-division').getContext('2d'), {
        type: 'doughnut',
        data: { labels: [], datasets: [{ data: [], backgroundColor: ['#137fec', '#2dd4bf', '#6366f1', '#feb101', '#ec4899', '#8b5cf6'] }] },
        options: {
            ...chartDefaults,
            cutout: '70%',
            plugins: {
                ...chartDefaults.plugins,
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const val = context.raw;
                            const original = val * 10000000;
                            return `Sales: ${val.toFixed(2)} Cr (₹${original.toLocaleString('en-IN')})`;
                        }
                    }
                }
            }
        }
    });
 
    charts.avgBillLoc = new Chart(document.getElementById('chart-avg-bill-location').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Avg Bill Value (₹)', data: [], backgroundColor: '#6366f1', borderRadius: 4 }] },
        options: {
            ...chartDefaults,
            scales: {
                ...chartDefaults.scales,
                y: {
                    ...chartDefaults.scales.y,
                    ticks: {
                        ...chartDefaults.scales.y.ticks,
                        callback: (val) => formatCompactNumber(val)
                    }
                }
            }
        }
    });
 
    // --- Section 4: Profitability ---
    charts.composition = new Chart(document.getElementById('chart-revenue-composition').getContext('2d'), {
        type: 'polarArea',
        data: { labels: [], datasets: [{ data: [], backgroundColor: ['#137fec', '#2dd4bf', '#6366f1', '#feb101', '#ec4899'] }] },
        options: { ...chartDefaults, scales: { r: { grid: { color: 'rgba(148, 163, 184, 0.1)' } } } }
    });
 
    // Note: Profit charts hidden as per request (Data unavailable)

    // --- Section 5: Analysis ---
    charts.weightComp = new Chart(document.getElementById('chart-weight-comparison').getContext('2d'), {
        type: 'bar',
        data: {
            labels: ['Weight (Kg)'], datasets: [
                { label: 'Current Gross Weight', data: [], backgroundColor: '#94a3b8' },
                { label: 'Current Net Weight', data: [], backgroundColor: '#137fec' },
                { label: '2025 Gross Weight', data: [], backgroundColor: '#d97706' },
                { label: '2025 Net Weight', data: [], backgroundColor: '#fbbf24' }
            ]
        },
        options: chartDefaults
    });

    charts.stoneAnalysis = new Chart(document.getElementById('chart-stone-analysis').getContext('2d'), {
        type: 'bar',
        data: { labels: ['Diamonds (Carats)', 'Colour Stones (Carats)'], datasets: [{ data: [], backgroundColor: ['#6366f1', '#ec4899'], borderRadius: 4 }] },
        options: { ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: false } } }
    });

    // Heatmap (Simulated with bubble coordinates using Chart.js)
    charts.heatmap = new Chart(document.getElementById('chart-billing-heatmap').getContext('2d'), {
        type: 'bubble',
        data: {
            datasets: [{
                label: 'Bill Count',
                data: [],
                backgroundColor: (ctx) => {
                    const v = ctx.raw ? ctx.raw.v : 0;
                    const alpha = Math.min(Math.max(v / 50, 0.25), 1);
                    return `rgba(19, 127, 236, ${alpha})`;
                },
                borderColor: '#137fec',
                borderWidth: 1
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                x: {
                    title: { display: true, text: 'Hour (0-23)' },
                    min: 0,
                    max: 23,
                    ticks: {
                        stepSize: 1,
                        precision: 0,
                        font: { size: 9 },
                        color: '#94a3b8'
                    }
                },
                y: {
                    title: { display: true, text: 'Date' },
                    type: 'category',
                    labels: [],
                    ticks: {
                        font: { size: 9 },
                        color: '#94a3b8'
                    }
                }
            },
            plugins: {
                ...chartDefaults.plugins,
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            const raw = ctx.raw || {};
                            return `Date: ${raw.y} | Time: ${raw.x}:00 | Bills: ${raw.v}`;
                        }
                    }
                }
            }
        }
    });
}

function formatCompactNumber(val, useGlobal = false) {
    if (val === null || val === undefined || isNaN(val)) return '0';

    const absVal = Math.abs(val);
    const sign = val < 0 ? '-' : '';
    let result = '';
    let suffix = '';

    if (!useGlobal) {
        if (absVal >= 10000000) {
            result = (absVal / 10000000);
            suffix = 'Cr';
        } else if (absVal >= 100000) {
            result = (absVal / 100000);
            suffix = 'L';
        } else if (absVal >= 1000) {
            result = (absVal / 1000);
            suffix = 'K';
        } else {
            return sign + absVal.toString();
        }
    } else {
        if (absVal >= 1000000000) {
            result = (absVal / 1000000000);
            suffix = 'B';
        } else if (absVal >= 1000000) {
            result = (absVal / 1000000);
            suffix = 'M';
        } else if (absVal >= 1000) {
            result = (absVal / 1000);
            suffix = 'K';
        } else {
            return sign + absVal.toString();
        }
    }

    // Remove trailing zeros automatically via parseFloat/toString
    let formatted = parseFloat(result.toFixed(2)).toString();
    return sign + formatted + suffix;
}

// Keep formatCurrency as a wrapper for backward compatibility or specifically for ₹ prefix
function formatCurrency(val) {
    return '₹' + formatCompactNumber(val);
}

async function loadDashboardData(triggerId = null, bypassCache = false, isSilent = false) {
    const requestId = ++latestReportRequest;
    activeReportController?.abort();
    const controller = new AbortController(); activeReportController = controller;
    const params = new URLSearchParams();
    const filterIds = ['date', 'country', 'region', 'state', 'location', 'division', 'subledger'];
    filterIds.forEach(id => {
        const el = document.getElementById(`filter-${id}`);
        if (id === 'division') {
            const values = el ? [...el.selectedOptions].map(option => option.value) : ['Gold', 'Diamond'];
            if (values.length) values.forEach(value => params.append('division', value));
            else params.append('division', '');
            return;
        }
        const val = el ? el.value : '';
        if (val) params.append(id, val);
    });

    if (filtersInitialized === false) {
        params.append('is_initial', 'true');
    }

    if (bypassCache) {
        params.append('bypass_cache', 'true');
    }

    const loader = document.getElementById('loading-overlay');
    if (loader && !isSilent) loader.classList.remove('hidden');
    reportRefreshMessage(null);
    let failures = 0, cacheWaits = 0;
    try {
        while (!controller.signal.aborted) {
            try {
                const token = localStorage.getItem('access_token');
                const response = await fetch(`/api/akt/transaction-data?${params.toString()}`, {
                    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
                    signal: controller.signal
                });
                const data = await response.json();
                if (requestId !== latestReportRequest) return;
                if (response.status === 202 && data.status === 'processing') {
                    if (++cacheWaits > 30) throw new Error('Report preparation is taking longer than expected.');
                    const seconds = Math.min(5, Math.max(1, Number(response.headers.get('Retry-After')) || 2));
                    await waitForReportRetry(seconds * 1000, controller.signal);
                    params.delete('bypass_cache'); continue;
                }
                if (!response.ok || data.status !== 'success') {
                    const error = new Error(data.message || data.msg || `Unable to refresh (${response.status}).`);
                    error.retryable = response.status >= 500 || response.status === 429;
                    throw error;
                }
                if (!data.kpis) throw new Error('The report response was incomplete.');
                updateKPIs(data.kpis);
                updateDashboardCharts(data);
                updateReportStatus(data);
                if (data.filter_options) {
                    if (!isSilent) populateFilters(data.filter_options, triggerId);
                    filtersInitialized = true;
                }
                reportRefreshMessage(null);
                return;
            } catch (error) {
                if (controller.signal.aborted || requestId !== latestReportRequest) return;
                if (loader) loader.classList.add('hidden');
                if (error.retryable === false || ++failures > 3) {
                    reportRefreshMessage(`Could not refresh the report. Displayed values have been kept. ${error.message}`);
                    return;
                }
                const delay = 2000 * Math.pow(2, failures - 1);
                reportRefreshMessage(`Refresh failed; keeping displayed values. Retrying in ${delay / 1000}s…`);
                await waitForReportRetry(delay, controller.signal);
                params.delete('bypass_cache');
            }
        }
    } catch (error) {
        if (!controller.signal.aborted && requestId === latestReportRequest) reportRefreshMessage(`Could not refresh. ${error.message}`);
    } finally {
        if (requestId === latestReportRequest && loader) loader.classList.add('hidden');
    }
}

function updateReportStatus(data) {
    const sync = document.getElementById('akt-last-sync');
    const source = document.getElementById('akt-data-source');
    if (!sync || !source) return;
    const date = data.last_successful_sync_at ? new Date(data.last_successful_sync_at) : null;
    const recorded = date && !Number.isNaN(date.getTime());
    sync.textContent = recorded ? new Intl.DateTimeFormat('en-IN', {
        day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZone: 'Asia/Kolkata'
    }).format(date) + ' IST' : 'Not recorded';
    sync.title = recorded ? `Successful ADF completion notification: ${data.last_successful_sync_at}` : 'No successful data-load completion notification has been recorded for this report version.';
    const cached = data.cached === true;
    document.getElementById('akt-data-source-text').textContent = cached ? 'From cache' : 'Fresh from database';
    document.getElementById('akt-data-source-icon').textContent = cached ? 'cached' : 'database';
    source.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[10px] font-semibold ' +
        (cached ? 'bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800/40' :
            'bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-800/40');
    source.title = cached ? 'This filter combination was served from the 50-minute report cache.' : 'This response was calculated from the database and cached for this filter combination.';
}

function updateComparisonBadge(id, change, detail, comparisonYear, label) {
    const salesBadge = document.getElementById(id);
    const available = typeof change === 'number' && Number.isFinite(change);
    const rounded = available ? Number(change.toFixed(1)) : null;
    let numberLabel = salesBadge.querySelector('[data-growth-number]');
    if (!numberLabel) {
        salesBadge.replaceChildren(); numberLabel = document.createElement('span');
        numberLabel.dataset.growthNumber = ''; salesBadge.append(numberLabel);
    }
    const existingArrow = salesBadge.querySelector('.material-symbols-outlined');
    const desiredArrow = available && rounded !== 0 ? (rounded > 0 ? 'arrow_upward' : 'arrow_downward') : null;
    if (existingArrow && existingArrow.textContent !== desiredArrow) existingArrow.remove();
    salesBadge.className = 'inline-flex items-center gap-0.5 shrink-0 rounded-md px-1.5 py-1 text-[9px] font-bold ' +
        (rounded > 0 ? 'text-emerald-700 bg-emerald-50 dark:text-emerald-400 dark:bg-emerald-900/30' : rounded < 0 ? 'text-red-700 bg-red-50 dark:text-red-400 dark:bg-red-900/30' : 'text-gray-500 bg-gray-100 dark:bg-gray-700 dark:text-gray-400');
    if (desiredArrow && !salesBadge.querySelector('.material-symbols-outlined')) {
        const arrow = document.createElement('span');
        arrow.className = 'material-symbols-outlined text-[12px]';
        arrow.textContent = desiredArrow;
        arrow.setAttribute('aria-hidden', 'true'); salesBadge.prepend(arrow);
    }
    animateStatValue(numberLabel, available ? rounded : null, value => `${value > 0 ? '+' : ''}${Number(value.toFixed(1)).toFixed(1)}%`);
    salesBadge.title = detail;
    salesBadge.setAttribute('aria-label', available ? `${label} change versus ${comparisonYear}: ${rounded > 0 ? '+' : ''}${rounded.toFixed(1)} percent` : `${label} comparison with ${comparisonYear} unavailable`);

}

function updateKPIs(kpis) {
    const growthEl = document.getElementById('kpi-sales-growth');
    const growth = kpis.sales_growth_yoy;
    const available = typeof growth === 'number' && Number.isFinite(growth);
    const rounded = available ? Number(growth.toFixed(1)) : null;
    animateStatValue(growthEl, available ? rounded : null, value => `${value > 0 ? '+' : ''}${Number(value.toFixed(1)).toFixed(1)}%`);
    growthEl.classList.remove('text-gray-900', 'dark:text-white', 'text-emerald-600', 'dark:text-emerald-400', 'text-red-600', 'dark:text-red-400');
    growthEl.classList.add(...(rounded > 0 ? ['text-emerald-600', 'dark:text-emerald-400'] : rounded < 0 ? ['text-red-600', 'dark:text-red-400'] : ['text-gray-900', 'dark:text-white']));
    const comparison = kpis.sales_growth_comparison_date?.split('-').reverse().join('/') || '18/10/2025';
    const cutoff = kpis.sales_growth_cutoff;
    const comparisonYear = kpis.sales_growth_comparison_date?.slice(0, 4) || '2025';
    document.getElementById('kpi-sales-growth-detail').textContent = comparisonYear;
    const fullSalesValue = value => Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 });
    const detail = available
        ? `Current sales: ${fullSalesValue(kpis.sales_growth_current)}; ${comparison} sales: ${fullSalesValue(kpis.sales_growth_previous)}; through ${cutoff}. (Current − comparison) ÷ comparison × 100.`
        : `Comparison with ${comparison} unavailable: ${kpis.sales_growth_status === 'nonpositive_baseline' ? 'comparison sales are zero or negative' : 'matching sales data is missing'}.`;
    growthEl.title = detail;
    document.getElementById('kpi-sales-growth-detail').title = detail;
    updateComparisonBadge('kpi-sales-growth-badge', growth, detail, comparisonYear, 'Sales');

    animateStatValue(document.getElementById('kpi-hourly'), kpis.total_hourly, value => Math.round(value).toLocaleString());
    animateStatValue(document.getElementById('kpi-sales'), kpis.total_sales, formatCurrency);
    const previousSales = kpis.sales_growth_previous;
    const hasPreviousSales = typeof previousSales === 'number' && Number.isFinite(previousSales) && Boolean(cutoff);
    const previousSalesEl = document.getElementById('kpi-sales-previous');
    animateStatValue(previousSalesEl, hasPreviousSales ? previousSales : null, value => `${comparisonYear}: ${formatCurrency(value)}`, `${comparisonYear}: N/A`);
    previousSalesEl.title = hasPreviousSales
        ? `Last-year invoice sales: ${fullSalesValue(previousSales)} on ${comparison}, through ${cutoff}, using the same selected filters as Sales Growth YoY.`
        : `Last-year sales for ${comparison} are unavailable at a matching reporting hour.`;
    animateStatValue(document.getElementById('kpi-bills'), kpis.total_bills, value => Math.round(value).toLocaleString());
    animateStatValue(document.getElementById('kpi-avg-bill'), kpis.avg_bill_value, formatCurrency);
    const profitEl = document.getElementById('kpi-profit');
    if (profitEl) animateStatValue(profitEl, kpis.total_profit, formatCurrency);
    
    const netWeightKg = (kpis.total_net_weight_kg !== undefined)
        ? kpis.total_net_weight_kg
        : (kpis.total_net_weight !== undefined ? kpis.total_net_weight : 0);
    animateStatValue(document.getElementById('kpi-weight'), netWeightKg, value => `${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kg`);
    for (const [metric, label, domMetric = metric] of [['bills', 'Bill count'], ['weight', 'Net weight'], ['avg_bill', 'Average bill value', 'avg-bill'], ['hourly', 'Last hour bills']]) {
        const previous = kpis[`${metric}_growth_previous`];
        const current = kpis[`${metric}_growth_current`];
        const change = kpis[`${metric}_growth_yoy`];
        const hasPrevious = typeof previous === 'number' && Number.isFinite(previous) && Boolean(cutoff);
        const formatValue = value => (metric === 'avg_bill' ? '₹' : '') + Number(value).toLocaleString('en-IN', { maximumFractionDigits: metric === 'weight' ? 3 : metric === 'avg_bill' ? 2 : 0 }) + (metric === 'weight' ? ' kg' : '');
        const comparisonDetail = `${label}: current ${current == null ? 'unavailable' : formatValue(current)}; ${comparison} ${hasPrevious ? formatValue(previous) : 'unavailable'}${cutoff ? `; through ${cutoff}` : ''}. Same selected filters and reporting hour.${metric === 'avg_bill' ? ' Average bill value = invoice sales ÷ bill count.' : ''}${metric === 'hourly' ? ` Hour: ${kpis.hourly_comparison_start || 'unavailable'}–${cutoff || 'unavailable'}. Calculated from consecutive cumulative hour totals; the first recorded hour uses an opening baseline of zero. Missing intermediate hours remain unavailable.` : ''} Percentage requires a positive comparison value.`;
        const previousEl = document.getElementById(`kpi-${domMetric}-previous`);
        animateStatValue(previousEl, hasPrevious ? previous : null, value => `${comparisonYear}: ${metric === 'avg_bill' ? formatCurrency(value) : formatValue(value)}`, `${comparisonYear}: N/A`);
        previousEl.title = comparisonDetail;
        updateComparisonBadge(`kpi-${domMetric}-growth-badge`, change, comparisonDetail, comparisonYear, label);
    }

}

function updateDashboardCharts(data) {
    // Section 1
    charts.perMin.data.labels = data.efficiency.map(d => d.time);
    charts.perMin.data.datasets[0].data = data.efficiency.map(d => d.cum_bills);
    
    // Map 2025 data to the same hourly labels for the line chart
    const cum_2025_map = {};
    if (data.efficiency_2025) {
        data.efficiency_2025.forEach(d => {
            cum_2025_map[d.time] = d.cum_bills;
        });
    }
    charts.perMin.data.datasets[1].data = data.efficiency.map(d => cum_2025_map[d.time] || 0);
    
    refreshDashboardChart(charts.perMin);

    charts.hourly.data.labels = data.efficiency.map(d => d.time);
    charts.hourly.data.datasets[0].data = data.efficiency.map(d => d.sum_hourly);
    
    // Map 2025 data to the same hourly labels
    const efficiency_2025_map = {};
    if (data.efficiency_2025) {
        data.efficiency_2025.forEach(d => {
            efficiency_2025_map[d.time] = d.sum_hourly;
        });
    }
    charts.hourly.data.datasets[1].data = data.efficiency.map(d => efficiency_2025_map[d.time] || 0);
    
    refreshDashboardChart(charts.hourly);

    // Top Locations for Per Minute Efficiency
    const topPerMinLoc = [...data.location_performance].sort((a, b) => b.avg_per_min - a.avg_per_min).slice(0, 10);
    charts.perMinLoc.data.labels = topPerMinLoc.map(d => d.location);
    charts.perMinLoc.data.datasets[0].data = topPerMinLoc.map(d => d.avg_per_min);
    refreshDashboardChart(charts.perMinLoc);

    // Top Locations for Hourly Bill Count
    const topHourlyLoc = [...data.location_performance].sort((a, b) => b.sum_hourly - a.sum_hourly).slice(0, 10);
    charts.hourlyLoc.data.labels = topHourlyLoc.map(d => d.location);
    charts.hourlyLoc.data.datasets[0].data = topHourlyLoc.map(d => d.sum_hourly);
    refreshDashboardChart(charts.hourlyLoc);

    // Section 2
    charts.scatter.data.datasets[0].data = data.efficiency.map(d => ({ x: d.sum_hourly, y: d.sum_revenue }));
    refreshDashboardChart(charts.scatter);

    charts.revenueHour.data.labels = data.efficiency.map(d => d.time);
    charts.revenueHour.data.datasets[0].data = data.efficiency.map(d => d.sum_revenue);
    refreshDashboardChart(charts.revenueHour);

    charts.daily.data.labels = data.trends.map(d => d.hour + ":00");
    charts.daily.data.datasets[0].data = data.trends.map(d => d.sum_revenue);
    charts.daily.data.datasets[1].data = data.trends.map(d => d.sum_turnover);
    refreshDashboardChart(charts.daily);

    // Section 3
    // Top Locations for Sales Revenue
    const topSalesLoc = [...data.location_performance].sort((a, b) => b.sum_revenue - a.sum_revenue).slice(0, 10);
    charts.salesLoc.data.labels = topSalesLoc.map(d => d.location);
    charts.salesLoc.data.datasets[0].data = topSalesLoc.map(d => d.sum_revenue / 100000);
    refreshDashboardChart(charts.salesLoc);

    charts.salesState.data.labels = data.state_performance.map(d => d.state);
    charts.salesState.data.datasets[0].data = data.state_performance.map(d => d.value);
    refreshDashboardChart(charts.salesState);

    const divisionLabels = data.division_sales.map(d => d.division);
    const divColors = ['#137fec', '#2dd4bf', '#6366f1', '#feb101', '#ec4899', '#8b5cf6'];
    const mappedColors = divisionLabels.map((label, i) => {
        const up = label.toUpperCase();
        if (up.includes('GOLD COIN')) return '#aedf1aff'; // Amber for Gold Coin
        if (up.includes('GOLD')) return '#fbbf24';      // Yellow for Gold
        if (up.includes('DIAMOND')) return '#6366f1';   // Indigo for Diamond
        if (up.includes('SILVER')) return '#94a3b8';    // Silver for Gray
        return divColors[i % divColors.length];
    });

    charts.salesDivision.data.labels = divisionLabels;
    charts.salesDivision.data.datasets[0].data = data.division_sales.map(d => d.value / 10000000);
    charts.salesDivision.data.datasets[0].backgroundColor = mappedColors;
    refreshDashboardChart(charts.salesDivision);

    // Top Locations for Avg Bill Value
    const topAvgBillLoc = [...data.location_performance].sort((a, b) => b.avg_bill_value - a.avg_bill_value).slice(0, 10);
    charts.avgBillLoc.data.labels = topAvgBillLoc.map(d => d.location);
    charts.avgBillLoc.data.datasets[0].data = topAvgBillLoc.map(d => d.avg_bill_value);
    refreshDashboardChart(charts.avgBillLoc);

    // Section 4
    charts.composition.data.labels = Object.keys(data.composition);
    charts.composition.data.datasets[0].data = Object.values(data.composition);
    refreshDashboardChart(charts.composition);

    // Note: Profit charts hidden as per request (Data unavailable)


    // Section 5
    charts.weightComp.data.datasets[0].data = [data.weight_analysis.gross / 1000];
    charts.weightComp.data.datasets[1].data = [data.weight_analysis.net / 1000];
    charts.weightComp.data.datasets[2].data = [data.weight_analysis_2025.gross / 1000];
    charts.weightComp.data.datasets[3].data = [data.weight_analysis_2025.net / 1000];
    refreshDashboardChart(charts.weightComp);

    charts.stoneAnalysis.data.datasets[0].data = [data.weight_analysis.diamond, data.weight_analysis.stone];
    refreshDashboardChart(charts.stoneAnalysis);

    // Heatmap (Bubble chart simulation)
    const uniqueDates = [...new Set(data.heatmap.map(h => h.date))].sort();
    if (charts.heatmap) {
        charts.heatmap.options.scales.y.labels = uniqueDates;
        charts.heatmap.data.datasets[0].data = data.heatmap.map(h => ({
            x: Number(h.hour),
            y: h.date,
            v: h.value,
            r: Math.max(3, Math.min(Math.sqrt(h.value) * 2, 16))
        }));
        refreshDashboardChart(charts.heatmap);
    }
}

function populateFilters(options, triggerId = null) {
    const hierarchy = ['filter-country', 'filter-region', 'filter-state', 'filter-location', 'filter-division', 'filter-subledger'];
    const mappings = {
        'filter-country': options.countries,
        'filter-region': options.regions,
        'filter-state': options.states,
        'filter-location': options.locations,
        'filter-division': options.divisions,
        'filter-subledger': options.subledgers
    };

    // Determine where to start the re-population
    let startIndex = 0;
    if (triggerId) {
        startIndex = hierarchy.indexOf(triggerId) + 1;
    }

    for (let i = startIndex; i < hierarchy.length; i++) {
        const id = hierarchy[i];
        const select = document.getElementById(id);
        const dataKey = id;
        
        if (id === 'filter-division' && select && mappings[dataKey]) {
            updateDivisionOptions(mappings[dataKey], [...select.selectedOptions].map(option => option.value));
            continue;
        }
        if (select && mappings[dataKey]) {
            const isCountry = (id === 'filter-country');

            // Save current value
            const currentValue = select.value;

            // Clear existing options, but keep or re-add the "All" version for sub-filters
            select.innerHTML = '';
            if (!isCountry) {
                const allOpt = document.createElement('option');
                allOpt.value = '';
                const label = id.replace('filter-', '').charAt(0).toUpperCase() + id.replace('filter-', '').slice(1);
                allOpt.innerText = `All ${label}s`;
                select.appendChild(allOpt);
            }

            mappings[dataKey].forEach(val => {
                if (!val) return;
                
                const opt = document.createElement('option');
                opt.value = val;
                opt.innerText = val;
                
                // Select India if on country and no existing selection
                if (isCountry && val.toLowerCase() === 'india' && (!currentValue || currentValue.toLowerCase() === 'india')) {
                    opt.selected = true;
                }
                
                select.appendChild(opt);
            });

            // Try to restore previous selection if it's still valid in the new list (case-insensitive for country)
            if (currentValue) {
                const matched = Array.from(select.options).find(o => 
                    isCountry ? o.value.toLowerCase() === currentValue.toLowerCase() : o.value === currentValue
                );
                if (matched) {
                    select.value = matched.value;
                }
            }
        }
    }
}
