(function () {
    const chartDataElement = document.getElementById('party-matrix-chart-data');
    let chartData = chartDataElement ? JSON.parse(chartDataElement.textContent) : {};
    const partyOptionsElement = document.getElementById('party-matrix-party-options');
    const partyOptions = partyOptionsElement ? JSON.parse(partyOptionsElement.textContent) : [];
    let partyMultiSelect;
    const charts = {};
    const colors = {
        blue: '#137fec',
        green: '#10b981',
        cyan: '#06b6d4',
        amber: '#f59e0b',
        red: '#ef4444',
        violet: '#7c3aed',
        grid: '#e8edf3',
        text: '#64748b'
    };

    function baseScales(maxValue) {
        const fixedMax = typeof maxValue === 'number' ? maxValue : undefined;
        return {
            x: {
                grid: { color: colors.grid },
                ticks: { color: colors.text, font: { size: 8 }, maxRotation: 0 }
            },
            y: {
                beginAtZero: true,
                suggestedMax: fixedMax,
                max: fixedMax,
                grid: { color: colors.grid },
                ticks: { color: colors.text, font: { size: 8 } }
            }
        };
    }

    function chartOptions(maxValue) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 8, boxHeight: 8, color: colors.text, font: { size: 8 } }
                },
                tooltip: {
                    titleFont: { size: 10 },
                    bodyFont: { size: 9 }
                }
            },
            scales: baseScales(maxValue)
        };
    }

    function buildCharts() {
        if (typeof Chart === 'undefined') return;
        const failureRates = [...(chartData.hm_fail_rate || []), ...(chartData.qc_fail_rate || [])];
        const failureScaleMax = Math.min(100, Math.max(5, Math.ceil(Math.max(0, ...failureRates) / 5) * 5));
        const coverageBarStyle = { borderRadius: 3, barPercentage: 0.62, categoryPercentage: 0.78, maxBarThickness: 14 };

        charts.orderCoverage = new Chart(document.getElementById('party-order-coverage-chart'), {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [
                    { label: 'Ordered Wt', data: chartData.order_weight, backgroundColor: colors.blue, ...coverageBarStyle },
                    { label: 'Accepted Wt', data: chartData.accepted_weight, backgroundColor: colors.cyan, ...coverageBarStyle },
                    { label: 'Delivered Wt', data: chartData.delivered_weight, backgroundColor: colors.green, ...coverageBarStyle },
                    { label: 'Cancelled Wt', data: chartData.cancelled_weight, backgroundColor: colors.red, ...coverageBarStyle }
                ]
            },
            options: chartOptions(false)
        });

        charts.quality = new Chart(document.getElementById('party-quality-chart'), {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [
                    { label: 'HM Failed %', data: chartData.hm_fail_rate, backgroundColor: colors.amber, borderRadius: 3 },
                    { label: 'QC Failed %', data: chartData.qc_fail_rate, backgroundColor: colors.violet, borderRadius: 3 }
                ]
            },
            options: chartOptions(failureScaleMax)
        });

        charts.deliveryDays = new Chart(document.getElementById('party-delivery-days-chart'), {
            type: 'line',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: 'Average Days',
                    data: chartData.delivery_days,
                    borderColor: colors.blue,
                    backgroundColor: 'rgba(19, 127, 236, 0.10)',
                    pointBackgroundColor: colors.blue,
                    pointRadius: 3,
                    borderWidth: 2,
                    tension: 0.25,
                    fill: true
                }]
            },
            options: chartOptions(false)
        });
    }

    function updateCharts(data) {
        chartData = data || {};
        if (!charts.orderCoverage || !charts.quality || !charts.deliveryDays) return;

        const labels = chartData.labels || [];
        charts.orderCoverage.data.labels = labels;
        charts.orderCoverage.data.datasets[0].data = chartData.order_weight || [];
        charts.orderCoverage.data.datasets[1].data = chartData.accepted_weight || [];
        charts.orderCoverage.data.datasets[2].data = chartData.delivered_weight || [];
        charts.orderCoverage.data.datasets[3].data = chartData.cancelled_weight || [];
        charts.orderCoverage.update();

        charts.quality.data.labels = labels;
        charts.quality.data.datasets[0].data = chartData.hm_fail_rate || [];
        charts.quality.data.datasets[1].data = chartData.qc_fail_rate || [];
        const failureRates = [...charts.quality.data.datasets[0].data, ...charts.quality.data.datasets[1].data];
        const failureScaleMax = Math.min(100, Math.max(5, Math.ceil(Math.max(0, ...failureRates) / 5) * 5));
        charts.quality.options.scales.y.max = failureScaleMax;
        charts.quality.options.scales.y.suggestedMax = failureScaleMax;
        charts.quality.update();

        charts.deliveryDays.data.labels = labels;
        charts.deliveryDays.data.datasets[0].data = chartData.delivery_days || [];
        charts.deliveryDays.update();
    }

    function updateStats(stats) {
        const values = {
            'matrix-stat-parties': Number(stats.party_count || 0).toLocaleString(),
            'matrix-stat-designs': Number(stats.design_count || 0).toLocaleString(),
            'matrix-stat-order-weight': Number(stats.order_wt || 0).toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 }),
            'matrix-stat-delivery': `${Number(stats.delivery_pct || 0).toFixed(1)}%`,
            'matrix-stat-hm-pass': `${Number(stats.hm_pass_pct || 0).toFixed(1)}%`,
            'matrix-stat-qc-pass': `${Number(stats.qc_pass_pct || 0).toFixed(1)}%`
        };
        Object.entries(values).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
    }

    async function loadMatrixData(params) {
        const panel = document.querySelector('.party-matrix-table-panel');
        if (!panel) return;

        panel.classList.add('matrix-ajax-loading');
        panel.setAttribute('aria-busy', 'true');

        try {
            const response = await fetch(`/partial/party-performance-matrix?${params.toString()}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) throw new Error(await response.text());

            const payload = await response.json();
            const wrapper = document.createElement('div');
            wrapper.innerHTML = payload.html.trim();
            const nextPanel = wrapper.firstElementChild;
            if (!nextPanel) throw new Error('Matrix table response was empty.');

            panel.replaceWith(nextPanel);
            const query = params.toString();
            window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
            updateCharts(payload.chart_data);
            updateStats(payload.stats || {});
        } catch (error) {
            console.error('Unable to load party comparison matrix:', error);
            panel.classList.remove('matrix-ajax-loading');
            panel.removeAttribute('aria-busy');
        }
    }

    window.applyPartyMatrixFilters = function () {
        const params = new URLSearchParams(window.location.search);
        const filters = {
            order_type: 'matrix-filter-order-type',
            sort_by: 'matrix-sort-by',
            sort_dir: 'matrix-sort-dir'
        };
        const selectedParties = partyMultiSelect ? partyMultiSelect.getValues() : [];
        if (selectedParties.length) params.set('party', selectedParties.join(','));
        else params.delete('party');
        Object.entries(filters).forEach(([name, id]) => {
            const value = document.getElementById(id)?.value || '';
            if (value) params.set(name, value);
            else params.delete(name);
        });
        const search = document.getElementById('matrix-search')?.value.trim() || '';
        if (search) params.set('search', search);
        else params.delete('search');
        params.set('page', '1');
        loadMatrixData(params);
    };

    window.resetPartyMatrixFilters = function () {
        document.querySelectorAll('.matrix-filter-party-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        partyMultiSelect?.updateTriggerText();
        const orderType = document.getElementById('matrix-filter-order-type');
        const sortBy = document.getElementById('matrix-sort-by');
        const sortDirection = document.getElementById('matrix-sort-dir');
        const search = document.getElementById('matrix-search');
        if (orderType) orderType.value = '';
        if (sortBy) sortBy.value = 'order_wt';
        if (sortDirection) sortDirection.value = 'desc';
        if (search) search.value = '';
        loadMatrixData(new URLSearchParams());
    };

    window.togglePartyMatrixSidebar = function (show) {
        const sidebar = document.getElementById('party-matrix-sidebar');
        const openButton = document.getElementById('matrix-filter-open');
        if (!sidebar || !openButton) return;

        const shouldShow = typeof show === 'boolean'
            ? show
            : sidebar.classList.contains('is-collapsed');
        sidebar.classList.toggle('is-collapsed', !shouldShow);
        sidebar.setAttribute('aria-hidden', shouldShow ? 'false' : 'true');
        openButton.setAttribute('aria-expanded', shouldShow ? 'true' : 'false');
    };

    window.sortPartyMatrix = function (column) {
        const params = new URLSearchParams(window.location.search);
        const current = params.get('sort_by') || 'order_wt';
        const direction = params.get('sort_dir') || 'desc';
        params.set('sort_by', column);
        params.set('sort_dir', current === column && direction === 'desc' ? 'asc' : 'desc');
        params.set('page', '1');
        loadMatrixData(params);
    };

    window.changeMatrixPage = function (page) {
        const params = new URLSearchParams(window.location.search);
        params.set('page', String(page));
        loadMatrixData(params);
    };

    window.changeMatrixPerPage = function (value) {
        const params = new URLSearchParams(window.location.search);
        params.set('per_page', value);
        params.set('page', '1');
        loadMatrixData(params);
    };

    let searchTimer;
    document.getElementById('matrix-search')?.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(window.applyPartyMatrixFilters, 450);
    });

    partyMultiSelect = new CustomMultiSelect({
        containerId: 'matrix-filter-party',
        label: 'Party',
        defaultText: 'All Parties',
        options: partyOptions
    });
    const selectedParties = (new URLSearchParams(window.location.search).get('party') || '')
        .split(',')
        .map(value => value.trim())
        .filter(Boolean);
    document.querySelectorAll('.matrix-filter-party-checkbox').forEach(checkbox => {
        checkbox.checked = selectedParties.includes(checkbox.value);
    });
    partyMultiSelect.updateTriggerText();

    buildCharts();
    loadMatrixData(new URLSearchParams(window.location.search));
})();
