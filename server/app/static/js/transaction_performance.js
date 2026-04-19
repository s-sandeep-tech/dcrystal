let charts = {};
let filtersInitialized = false;

document.addEventListener('DOMContentLoaded', () => {
    // Set default date to today
    const dateInput = document.getElementById('filter-date');
    if (dateInput) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;
    }

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
    const otherFilters = ['region', 'state', 'location', 'division', 'subledger'];
    otherFilters.forEach(f => {
        const el = document.getElementById(`filter-${f}`);
        if (el) el.value = '';
    });

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
 
    charts.profitMarginLoc = new Chart(document.getElementById('chart-profit-margin-location').getContext('2d'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Profit Margin %', data: [], borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', fill: true, tension: 0.4 }] },
        options: chartDefaults
    });
 
    charts.profitLoc = new Chart(document.getElementById('chart-profit-location').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Total Profit (₹)', data: [], backgroundColor: '#10b981', borderRadius: 4 }] },
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

    // Heatmap (Simulated with small cells using Chart.js)
    charts.heatmap = new Chart(document.getElementById('chart-billing-heatmap').getContext('2d'), {
        type: 'matrix', // This requires chartjs-chart-matrix which might not be there. Fallback to bubble or simple grid.
        type: 'bubble',
        data: {
            datasets: [{
                label: 'Bill Count', data: [], backgroundColor: (ctx) => {
                    const v = ctx.raw ? ctx.raw.v : 0;
                    const alpha = Math.min(v / 50, 1);
                    return `rgba(19, 127, 236, ${alpha})`;
                }, borderRadius: 0
            }]
        },
        options: {
            ...chartDefaults, scales: {
                x: { title: { display: true, text: 'Hour (0-23)' } },
                y: { title: { display: true, text: 'Date' }, type: 'category' }
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
    const params = new URLSearchParams();
    const filterIds = ['date', 'country', 'region', 'state', 'location', 'division', 'subledger'];
    filterIds.forEach(id => {
        const val = document.getElementById(`filter-${id}`).value;
        if (val) params.append(id, val);
    });

    if (filtersInitialized === false) {
        params.append('is_initial', 'true');
    }

    if (bypassCache) {
        params.append('bypass_cache', 'true');
    }

    const loader = document.getElementById('loading-overlay');
    // Only show loader if not a silent refresh
    if (loader && !isSilent) loader.classList.remove('hidden');

    try {
        const response = await fetch(`/api/akt/transaction-data?${params.toString()}`);
        const data = await response.json();

        if (data.status === 'success') {
            updateKPIs(data.kpis);
            updateDashboardCharts(data);
            if (data.filter_options) {
                populateFilters(data.filter_options, triggerId);
                filtersInitialized = true;
            }
        } else {
            console.error('API Error:', data.message);
            // Only alert if not silent, or maybe just log for silent
            if (!isSilent) alert('Error loading dashboard data: ' + data.message);
        }
    } catch (error) {
        console.error('Fetch Error:', error);
    } finally {
        if (loader) loader.classList.add('hidden');
    }
}

function updateKPIs(kpis) {
    document.getElementById('kpi-per-min').innerText = kpis.avg_per_min.toFixed(2);
    document.getElementById('kpi-hourly').innerText = kpis.total_hourly.toLocaleString();
    document.getElementById('kpi-sales').innerText = formatCurrency(kpis.total_sales);
    document.getElementById('kpi-bills').innerText = kpis.total_bills.toLocaleString();
    document.getElementById('kpi-avg-bill').innerText = formatCurrency(kpis.avg_bill_value);
    document.getElementById('kpi-profit').innerText = formatCurrency(kpis.total_profit);
    document.getElementById('kpi-weight').innerText = kpis.total_net_weight.toFixed(2);
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
    
    charts.perMin.update();

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
    
    charts.hourly.update();

    // Top Locations for Per Minute Efficiency
    const topPerMinLoc = [...data.location_performance].sort((a, b) => b.avg_per_min - a.avg_per_min).slice(0, 10);
    charts.perMinLoc.data.labels = topPerMinLoc.map(d => d.location);
    charts.perMinLoc.data.datasets[0].data = topPerMinLoc.map(d => d.avg_per_min);
    charts.perMinLoc.update();

    // Top Locations for Hourly Bill Count
    const topHourlyLoc = [...data.location_performance].sort((a, b) => b.sum_hourly - a.sum_hourly).slice(0, 10);
    charts.hourlyLoc.data.labels = topHourlyLoc.map(d => d.location);
    charts.hourlyLoc.data.datasets[0].data = topHourlyLoc.map(d => d.sum_hourly);
    charts.hourlyLoc.update();

    // Section 2
    charts.scatter.data.datasets[0].data = data.efficiency.map(d => ({ x: d.sum_hourly, y: d.sum_revenue }));
    charts.scatter.update();

    charts.revenueHour.data.labels = data.efficiency.map(d => d.time);
    charts.revenueHour.data.datasets[0].data = data.efficiency.map(d => d.sum_revenue);
    charts.revenueHour.update();

    charts.daily.data.labels = data.trends.map(d => d.hour + ":00");
    charts.daily.data.datasets[0].data = data.trends.map(d => d.sum_revenue);
    charts.daily.data.datasets[1].data = data.trends.map(d => d.sum_turnover);
    charts.daily.update();

    // Section 3
    // Top Locations for Sales Revenue
    const topSalesLoc = [...data.location_performance].sort((a, b) => b.sum_revenue - a.sum_revenue).slice(0, 10);
    charts.salesLoc.data.labels = topSalesLoc.map(d => d.location);
    charts.salesLoc.data.datasets[0].data = topSalesLoc.map(d => d.sum_revenue / 100000);
    charts.salesLoc.update();

    charts.salesState.data.labels = data.state_performance.map(d => d.state);
    charts.salesState.data.datasets[0].data = data.state_performance.map(d => d.value);
    charts.salesState.update();

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
    charts.salesDivision.update();

    // Top Locations for Avg Bill Value
    const topAvgBillLoc = [...data.location_performance].sort((a, b) => b.avg_bill_value - a.avg_bill_value).slice(0, 10);
    charts.avgBillLoc.data.labels = topAvgBillLoc.map(d => d.location);
    charts.avgBillLoc.data.datasets[0].data = topAvgBillLoc.map(d => d.avg_bill_value);
    charts.avgBillLoc.update();

    // Section 4
    charts.composition.data.labels = Object.keys(data.composition);
    charts.composition.data.datasets[0].data = Object.values(data.composition);
    charts.composition.update();

    // Top Locations for Profit Margin
    const topMarginLoc = [...data.location_performance].sort((a, b) => b.profit_margin - a.profit_margin).slice(0, 20);
    charts.profitMarginLoc.data.labels = topMarginLoc.map(d => d.location);
    charts.profitMarginLoc.data.datasets[0].data = topMarginLoc.map(d => d.profit_margin);
    charts.profitMarginLoc.update();

    // Top Locations for Total Profit
    const topProfitLoc = [...data.location_performance].sort((a, b) => b.total_profit - a.total_profit).slice(0, 10);
    charts.profitLoc.data.labels = topProfitLoc.map(d => d.location);
    charts.profitLoc.data.datasets[0].data = topProfitLoc.map(d => d.total_profit);
    charts.profitLoc.update();

    // Section 5
    charts.weightComp.data.datasets[0].data = [data.weight_analysis.gross / 1000];
    charts.weightComp.data.datasets[1].data = [data.weight_analysis.net / 1000];
    charts.weightComp.data.datasets[2].data = [data.weight_analysis_2025.gross / 1000];
    charts.weightComp.data.datasets[3].data = [data.weight_analysis_2025.net / 1000];
    charts.weightComp.update();

    charts.stoneAnalysis.data.datasets[0].data = [data.weight_analysis.diamond, data.weight_analysis.stone];
    charts.stoneAnalysis.update();

    // Heatmap (Bubble chart simulation)
    charts.heatmap.data.datasets[0].data = data.heatmap.map(h => ({ x: h.hour, y: h.date, v: h.value, r: Math.min(h.value / 2, 8) }));
    charts.heatmap.update();
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

    let reloadRequired = false;

    for (let i = startIndex; i < hierarchy.length; i++) {
        const id = hierarchy[i];
        const select = document.getElementById(id);
        const dataKey = id;
        
        if (select && mappings[dataKey]) {
            const initialValue = select.value;
            const isCountry = (id === 'filter-country');

            // Save the current value to try and restore it later if it's still valid
            const currentValue = select.value;

            // Clear existing options, but keep or re-add the "All" version for sub-filters
            select.innerHTML = '';
            if (!isCountry) {
                const allOpt = document.createElement('option');
                allOpt.value = '';
                // e.g. "All Regions"
                const label = id.replace('filter-', '').charAt(0).toUpperCase() + id.replace('filter-', '').slice(1);
                allOpt.innerText = `All ${label}s`;
                select.appendChild(allOpt);
            }

            mappings[dataKey].forEach(val => {
                if (!val) return;
                
                const opt = document.createElement('option');
                opt.value = val;
                opt.innerText = val;
                
                // Case correction for India on initial load
                if (isCountry && val.toLowerCase() === 'india') {
                    if (!triggerId) { // only auto-select on very first load if nothing selected
                        opt.selected = true;
                        if (val !== initialValue) reloadRequired = true;
                    }
                }
                
                select.appendChild(opt);
            });

            // Try to restore previous selection if it's still valid in the new list
            if (currentValue && Array.from(select.options).some(o => o.value === currentValue)) {
                select.value = currentValue;
            }
        }
    }

    if (reloadRequired) {
        console.log('Corrected country case detected, reloading data...');
        loadDashboardData();
    }
}
