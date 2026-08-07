(function () {
    const chartDataElement = document.getElementById('party-matrix-chart-data');
    const chartData = chartDataElement ? JSON.parse(chartDataElement.textContent) : {};
    const partyOptionsElement = document.getElementById('party-matrix-party-options');
    const partyOptions = partyOptionsElement ? JSON.parse(partyOptionsElement.textContent) : [];
    let partyMultiSelect;
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
        if (typeof Chart === 'undefined' || !(chartData.labels || []).length) return;
        const failureRates = [...(chartData.hm_fail_rate || []), ...(chartData.qc_fail_rate || [])];
        const failureScaleMax = Math.min(100, Math.max(5, Math.ceil(Math.max(0, ...failureRates) / 5) * 5));
        const coverageBarStyle = { borderRadius: 3, barPercentage: 0.62, categoryPercentage: 0.78, maxBarThickness: 14 };

        new Chart(document.getElementById('party-order-coverage-chart'), {
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

        new Chart(document.getElementById('party-quality-chart'), {
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

        new Chart(document.getElementById('party-delivery-days-chart'), {
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

    function navigate(mutator) {
        const params = new URLSearchParams(window.location.search);
        mutator(params);
        window.location.href = `${window.location.pathname}?${params.toString()}`;
    }

    window.applyPartyMatrixFilters = function () {
        navigate((params) => {
            const filters = {
                order_type: 'matrix-filter-order-type',
                provision_type: 'matrix-filter-provision-type',
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
        });
    };

    window.resetPartyMatrixFilters = function () {
        window.location.href = window.location.pathname;
    };

    window.sortPartyMatrix = function (column) {
        navigate((params) => {
            const current = params.get('sort_by') || 'order_wt';
            const direction = params.get('sort_dir') || 'desc';
            params.set('sort_by', column);
            params.set('sort_dir', current === column && direction === 'desc' ? 'asc' : 'desc');
            params.set('page', '1');
        });
    };

    window.changeMatrixPage = function (page) {
        navigate((params) => params.set('page', String(page)));
    };

    window.changeMatrixPerPage = function (value) {
        navigate((params) => {
            params.set('per_page', value);
            params.set('page', '1');
        });
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
})();
