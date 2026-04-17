let charts = {};
let filtersInitialized = false;

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    loadDashboardData();
    
    // Setup filter listeners
    const filters = ['date', 'country', 'region', 'state', 'location', 'division', 'subledger'];
    filters.forEach(f => {
        const el = document.getElementById(`filter-${f}`);
        if (el) el.addEventListener('change', loadDashboardData);
    });

    // Real-time Sync Listener (Dedicated AKT Relay)
    if (window.socket) {
        window.socket.on('aktPerformanceRefresh', (data) => {
            console.log('Real-time AKT sync triggered:', data);
            
            // Show toast if available
            if (window.showToast) {
                window.showToast('Data Synced', data.message || 'Dashboard updated with latest transaction data', 'success');
            }
            
            // Refresh data (uses current filters)
            loadDashboardData();
        });
    }
});

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
        data: { labels: [], datasets: [{ label: 'Avg Per Min', data: [], borderColor: '#137fec', tension: 0.4, fill: true, backgroundColor: 'rgba(19, 127, 236, 0.1)' }] },
        options: { ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: false } } }
    });

    charts.hourly = new Chart(document.getElementById('chart-hourly-count').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Hourly Count', data: [], backgroundColor: '#137fec', borderRadius: 4 }] },
        options: chartDefaults
    });

    charts.perMinLoc = new Chart(document.getElementById('chart-per-min-location').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Avg Per Min', data: [], backgroundColor: '#2dd4bf', borderRadius: 4 }] },
        options: { ...chartDefaults, indexAxis: 'y' }
    });

    charts.hourlyLoc = new Chart(document.getElementById('chart-hourly-location').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Hourly Count', data: [], backgroundColor: '#6366f1', borderRadius: 4 }] },
        options: { ...chartDefaults, indexAxis: 'y' }
    });

    // --- Section 2: Revenue ---
    charts.scatter = new Chart(document.getElementById('chart-revenue-scatter').getContext('2d'), {
        type: 'scatter',
        data: { datasets: [{ label: 'Revenue (₹) vs Efficiency', data: [], backgroundColor: '#137fec', pointRadius: 5 }] },
        options: { ...chartDefaults, scales: { x: { title: { display: true, text: 'Efficiency (Bills/Min)' } }, y: { title: { display: true, text: 'Revenue (₹)' } } } }
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
        data: { labels: [], datasets: [{ label: 'Sales (₹)', data: [], backgroundColor: '#feb101', borderRadius: 4 }] },
        options: { ...chartDefaults, indexAxis: 'y' }
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
        options: { ...chartDefaults, cutout: '70%' }
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
        data: { labels: ['Weight (Gms)'], datasets: [
            { label: 'Gross Weight', data: [], backgroundColor: '#94a3b8' },
            { label: 'Net Weight', data: [], backgroundColor: '#137fec' }
        ] },
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
        data: { datasets: [{ label: 'Bill Count', data: [], backgroundColor: (ctx) => {
            const v = ctx.raw ? ctx.raw.v : 0;
            const alpha = Math.min(v / 50, 1);
            return `rgba(19, 127, 236, ${alpha})`;
        }, borderRadius: 0 }] },
        options: { ...chartDefaults, scales: { 
            x: { title: { display: true, text: 'Hour (0-23)' } }, 
            y: { title: { display: true, text: 'Date' }, type: 'category' } 
        } }
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

async function loadDashboardData() {
    const filterIds = ['date', 'country', 'region', 'state', 'location', 'division', 'subledger'];
    const params = new URLSearchParams();
    filterIds.forEach(id => {
        const val = document.getElementById(`filter-${id}`).value;
        if (val) params.append(id, val);
    });
    
    try {
        const response = await fetch(`/api/akt/transaction-data?${params.toString()}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            updateKPIs(data.kpis);
            updateDashboardCharts(data);
            if (!filtersInitialized && data.filter_options) {
                populateFilters(data.filter_options);
                filtersInitialized = true;
            }
        } else {
            console.error('API Error:', data.message);
            alert('Error loading dashboard data: ' + data.message);
        }
    } catch (error) {
        console.error('Fetch Error:', error);
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
    charts.perMin.data.datasets[0].data = data.efficiency.map(d => d.avg_per_min);
    charts.perMin.update();

    charts.hourly.data.labels = data.efficiency.map(d => d.time);
    charts.hourly.data.datasets[0].data = data.efficiency.map(d => d.sum_hourly);
    charts.hourly.update();

    charts.perMinLoc.data.labels = data.location_performance.slice(0, 10).map(d => d.location);
    charts.perMinLoc.data.datasets[0].data = data.location_performance.slice(0, 10).map(d => d.avg_per_min);
    charts.perMinLoc.update();

    charts.hourlyLoc.data.labels = data.location_performance.slice(0, 10).map(d => d.location);
    charts.hourlyLoc.data.datasets[0].data = data.location_performance.slice(0, 10).map(d => d.sum_hourly);
    charts.hourlyLoc.update();

    // Section 2
    charts.scatter.data.datasets[0].data = data.efficiency.map(d => ({ x: d.avg_per_min, y: d.sum_revenue }));
    charts.scatter.update();

    charts.revenueHour.data.labels = data.efficiency.map(d => d.time);
    charts.revenueHour.data.datasets[0].data = data.efficiency.map(d => d.sum_revenue);
    charts.revenueHour.update();

    charts.daily.data.labels = data.trends.map(d => d.date);
    charts.daily.data.datasets[0].data = data.trends.map(d => d.sum_revenue);
    charts.daily.data.datasets[1].data = data.trends.map(d => d.sum_turnover);
    charts.daily.update();

    // Section 3
    charts.salesLoc.data.labels = data.location_performance.slice(0, 10).map(d => d.location);
    charts.salesLoc.data.datasets[0].data = data.location_performance.slice(0, 10).map(d => d.sum_revenue);
    charts.salesLoc.update();

    charts.salesState.data.labels = data.state_performance.map(d => d.state);
    charts.salesState.data.datasets[0].data = data.state_performance.map(d => d.value);
    charts.salesState.update();

    charts.salesDivision.data.labels = data.division_sales.map(d => d.division);
    charts.salesDivision.data.datasets[0].data = data.division_sales.map(d => d.value);
    charts.salesDivision.update();

    charts.avgBillLoc.data.labels = data.location_performance.slice(0, 10).map(d => d.location);
    charts.avgBillLoc.data.datasets[0].data = data.location_performance.slice(0, 10).map(d => d.avg_bill_value);
    charts.avgBillLoc.update();

    // Section 4
    charts.composition.data.labels = Object.keys(data.composition);
    charts.composition.data.datasets[0].data = Object.values(data.composition);
    charts.composition.update();

    charts.profitMarginLoc.data.labels = data.location_performance.slice(0, 20).map(d => d.location);
    charts.profitMarginLoc.data.datasets[0].data = data.location_performance.slice(0, 20).map(d => d.profit_margin);
    charts.profitMarginLoc.update();

    charts.profitLoc.data.labels = data.location_performance.slice(0, 10).map(d => d.location);
    charts.profitLoc.data.datasets[0].data = data.location_performance.slice(0, 10).map(d => d.total_profit);
    charts.profitLoc.update();

    // Section 5
    charts.weightComp.data.datasets[0].data = [data.weight_analysis.gross];
    charts.weightComp.data.datasets[1].data = [data.weight_analysis.net];
    charts.weightComp.update();

    charts.stoneAnalysis.data.datasets[0].data = [data.weight_analysis.diamond, data.weight_analysis.stone];
    charts.stoneAnalysis.update();

    // Heatmap (Bubble chart simulation)
    charts.heatmap.data.datasets[0].data = data.heatmap.map(h => ({ x: h.hour, y: h.date, v: h.value, r: Math.min(h.value / 2, 8) }));
    charts.heatmap.update();
}

function populateFilters(options) {
    const mappings = {
        'country': options.countries,
        'region': options.regions,
        'state': options.states,
        'location': options.locations,
        'division': options.divisions,
        'subledger': options.subledgers
    };

    Object.keys(mappings).forEach(id => {
        const select = document.getElementById(`filter-${id}`);
        if (select && mappings[id]) {
            mappings[id].forEach(val => {
                if (!val) return;
                const opt = document.createElement('option');
                opt.value = val;
                opt.innerText = val;
                select.appendChild(opt);
            });
        }
    });
}
