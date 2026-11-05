(() => {
    'use strict';
    const form = document.getElementById('sales-filters');
    const page = document.getElementById('sales-tsk-page');
    if (!form || !page) return;
    const segments = ['kpis', 'trend', 'sections', 'branches', 'ledger'];
    const controllers = new Map();
    const charts = new Map();
    const nf = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 });
    const number = value => value == null ? '—' : nf.format(value);
    const crores = value => value == null ? '—' : `${(Number(value) / 10000000).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Cr`;
    const axisCrores = value => `${(Number(value) / 10000000).toLocaleString('en-IN', { maximumFractionDigits: Math.abs(Number(value)) < 100000 ? 6 : 2 })} Cr`;
    const amountKeys = new Set(['invoice_turnover', 'return_turnover', 'net_turnover', 'total_tsk', 'prior_turnover']);
    const percent = value => value == null ? '—' : `${Number(value).toFixed(1)}%`;
    const monthLabel = value => new Date(`${value}T12:00:00`).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
    const fields = [...form.querySelectorAll('select[name]')];
    let applied = new URLSearchParams(location.search);
    let kpiTrend = null;
    let kpiTrendStatus = 'Loading monthly trend…';
    const headers = () => {
        const token = localStorage.getItem('access_token');
        return { 'X-Requested-With': 'XMLHttpRequest', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
    };
    function element(tag, text, className) {
        const el = document.createElement(tag);
        if (text != null) el.textContent = text;
        if (className) el.className = className;
        return el;
    }
    function restoreDates() {
        for (const key of ['start', 'end']) {
            if (!applied.get(key)) applied.set(key, form.dataset[key === 'start' ? 'defaultStart' : 'defaultEnd']);
            form.elements[key].value = applied.get(key);
        }
    }
    function setOptions(select, options, selected) {
        select.replaceChildren();
        const known = new Set(options.map(o => o.value));
        const all = [...options, ...selected.filter(v => !known.has(v)).map(v => ({ value: v, label: v }))];
        for (const item of all) select.add(new Option(item.label, item.value, false, selected.includes(item.value)));
    }
    function retry(status, message, fn) {
        status.replaceChildren(element('span', message));
        const button = element('button', 'Retry', 'sales-retry');
        button.type = 'button'; button.addEventListener('click', fn); status.append(button);
    }
    async function request(segment, params, signal) {
        const response = await fetch(`/api/sales-tsk-performance/${segment}?${params}`, { headers: headers(), signal, cache: 'no-store' });
        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            throw new Error(body.message || body.msg || `Unable to load report (${response.status}).`);
        }
        return response;
    }
    async function loadOptions(params) {
        controllers.get('options')?.abort();
        const controller = new AbortController(); controllers.set('options', controller);
        const status = document.getElementById('sales-options-status'); status.textContent = 'Loading filters…';
        try {
            const { data } = await (await request('options', params, controller.signal)).json();
            if (controller.signal.aborted) return;
            for (const select of fields) {
                // Preserve edits made while option lists were loading.
                const selected = [...select.selectedOptions].map(o => o.value);
                setOptions(select, data[select.name] || [], selected);
            }
            status.textContent = '';
        } catch (error) {
            if (error.name !== 'AbortError') retry(status, error.message, () => loadOptions(applied));
        }
    }
    function table(container, columns, rows, footer) {
        const wrap = element('div', null, 'sales-table-wrap');
        const tbl = element('table', null, 'sales-table');
        const head = document.createElement('thead'); const tr = document.createElement('tr');
        columns.forEach(c => { const th = element('th', c.label); th.scope = 'col'; tr.append(th); });
        head.append(tr); tbl.append(head);
        const renderRow = row => {
            const line = document.createElement('tr');
            if (row.is_peak) line.classList.add('sales-ledger-peak');
            if (row.rank === 1) line.classList.add('sales-branch-leader');
            columns.forEach(c => {
                const value = row[c.key];
                const td = element('td', c.format ? c.format(value) : value ?? '—');
                if (c.key === 'period_share' || c.progress) {
                    td.className = 'sales-ledger-share';
                    if (value != null) {
                        const label = element('span', percent(value));
                        const track = element('div', null, 'sales-share-track');
                        const fill = element('div', null, 'sales-share-fill');
                        fill.style.width = `${Math.max(0, Math.min(100, value))}%`;
                        track.setAttribute('aria-hidden', 'true'); track.append(fill);
                        td.replaceChildren(label, track);
                        td.title = `${percent(value)} of selected-period net turnover${c.progress ? ' across all matching branches' : ''}. This is contribution, not target attainment.`;
                    }
                }
                if (c.key === 'mom') {
                    td.replaceChildren(element('span', value == null ? '—' : `${value > 0 ? '+' : ''}${percent(value)}`,
                        `sales-mom-badge ${value == null || value === 0 ? 'is-neutral' : value > 0 ? 'is-up' : 'is-down'}`));
                    td.title = value == null ? 'Comparison requires two complete, consecutive months with transactions and a nonzero prior total.' : 'Net turnover change versus the previous complete month.';
                }
                if (c.key === 'month' && (row.is_partial || row.is_peak)) {
                    td.append(element('span', row.is_partial ? 'Partial' : 'Peak', 'sales-ledger-month-tag'));
                }
                if (c.key === 'rank' && value != null) {
                    td.replaceChildren(element('span', String(value), `sales-rank-badge ${value <= 3 ? 'is-top' : ''}`));
                }
                if (c.key === 'net_weight' && value != null) td.title = `${number(value)} kg`;
                if (c.swatch) { const dot = element('span', null, 'sales-section-dot'); dot.style.backgroundColor = row.chart_color; td.prepend(dot); }
                if (amountKeys.has(c.key) && value != null) { td.title = number(value); td.setAttribute('aria-label', `${c.label}: ${number(value)}`); }
                if (c.key === 'yoy' && value != null) td.className = value >= 0 ? 'sales-positive' : 'sales-negative';
                line.append(td);
            }); return line;
        };
        const body = document.createElement('tbody'); rows.forEach(r => body.append(renderRow(r))); tbl.append(body);
        if (footer) { const foot = document.createElement('tfoot'); foot.append(renderRow(footer)); tbl.append(foot); }
        wrap.append(tbl); container.append(wrap);
    }
    const metricColumns = [
        { key: 'invoice_turnover', label: 'Invoice turnover', format: crores },
        { key: 'return_turnover', label: 'Returns (signed)', format: crores },
        { key: 'net_turnover', label: 'Net turnover', format: crores },
        { key: 'net_weight', label: 'Net weight (kg)', format: number },
        { key: 'total_tsk', label: 'TSK · source total', format: crores }
    ];
    function themeChart(chart) {
        const style = getComputedStyle(page);
        const text = style.getPropertyValue('--sales-text').trim();
        const grid = style.getPropertyValue('--sales-border').trim();
        chart.options.plugins.legend.labels.color = text;
        for (const scale of Object.values(chart.options.scales || {})) {
            scale.ticks.color = text;
            scale.grid.color = grid;
            scale.title.color = text;
        }
        chart.update('none');
    }
    new MutationObserver(() => charts.forEach(themeChart)).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    function drawChart(segment, container, config) {
        if (typeof Chart === 'undefined') { container.append(element('p', 'Chart library unavailable. Values are shown below.', 'sales-note')); return; }
        const wrap = element('div', null, 'sales-canvas'); const canvas = document.createElement('canvas');
        canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', segment === 'trend' ? 'Monthly turnover and TSK chart' : 'Section turnover contribution chart');
        wrap.append(canvas); container.append(wrap);
        const style = getComputedStyle(page);
        config.options = { responsive: true, maintainAspectRatio: false, layout: { padding: 8 }, ...config.options,
            plugins: { ...config.options?.plugins, tooltip: { callbacks: { label: context => `${context.dataset.label}: ${crores(context.raw)} (${number(context.raw)})` } }, legend: { display: segment !== 'sections', position: 'bottom', labels: { usePointStyle: true, padding: 18, color: style.getPropertyValue('--sales-text').trim(), boxWidth: 10 } } } };
        const chart = new Chart(canvas, config);
        charts.set(segment, chart); themeChart(chart);
    }
    function updateKpiSparklines() {
        const svgNS = 'http://www.w3.org/2000/svg';
        for (const slot of page.querySelectorAll('.sales-kpi-sparkline')) {
            slot.replaceChildren();
            if (!kpiTrend || !kpiTrend.length || !kpiTrend.some(row => row.row_count)) {
                slot.append(element('span', kpiTrend ? 'No monthly transactions' : kpiTrendStatus, 'sales-sparkline-caption'));
                continue;
            }
            const values = kpiTrend.map(row => Number(row[slot.dataset.metric]));
            if (!values.every(Number.isFinite)) {
                slot.append(element('span', 'Monthly trend unavailable', 'sales-sparkline-caption'));
                continue;
            }
            const low = Math.min(...values), high = Math.max(...values);
            const points = values.map((value, i) => ({
                x: values.length === 1 ? 120 : 8 + i * 224 / (values.length - 1),
                y: high === low ? 30 : 52 - (value - low) / (high - low) * 44
            }));
            const svg = document.createElementNS(svgNS, 'svg');
            svg.setAttribute('viewBox', '0 0 240 60');
            svg.setAttribute('role', 'img');
            svg.setAttribute('aria-label', `${slot.dataset.label}: ${kpiTrend.map((row, i) => `${monthLabel(row.month)} ${number(values[i])}`).join('; ')}`);
            const defs = document.createElementNS(svgNS, 'defs');
            const gradient = document.createElementNS(svgNS, 'linearGradient');
            const gradientId = `sales-spark-fill-${slot.dataset.metric}`;
            gradient.setAttribute('id', gradientId);
            gradient.setAttribute('x1', '0'); gradient.setAttribute('y1', '0');
            gradient.setAttribute('x2', '0'); gradient.setAttribute('y2', '1');
            for (const [offset, opacity] of [['0%', '0.20'], ['100%', '0.01']]) {
                const stop = document.createElementNS(svgNS, 'stop');
                stop.setAttribute('offset', offset); stop.setAttribute('stop-color', 'currentColor');
                stop.setAttribute('stop-opacity', opacity); gradient.append(stop);
            }
            defs.append(gradient); svg.append(defs);
            if (points.length > 1) {
                const area = document.createElementNS(svgNS, 'polygon');
                area.setAttribute('points', `${points[0].x},60 ${points.map(point => `${point.x},${point.y}`).join(' ')} ${points[points.length - 1].x},60`);
                area.setAttribute('fill', `url(#${gradientId})`); svg.append(area);
            }
            const line = document.createElementNS(svgNS, 'polyline');
            line.setAttribute('points', points.map(point => `${point.x},${point.y}`).join(' '));
            line.setAttribute('fill', 'none'); line.setAttribute('stroke', 'currentColor');
            line.setAttribute('stroke-width', '2.5'); line.setAttribute('stroke-linecap', 'round');
            line.setAttribute('stroke-linejoin', 'round');
            svg.append(line);
            points.forEach((point, i) => {
                const dot = document.createElementNS(svgNS, 'circle');
                dot.setAttribute('cx', point.x); dot.setAttribute('cy', point.y);
                dot.setAttribute('r', i === points.length - 1 ? '4' : '6');
                dot.setAttribute('fill', i === points.length - 1 ? 'currentColor' : 'transparent');
                const title = document.createElementNS(svgNS, 'title');
                title.textContent = `${monthLabel(kpiTrend[i].month)}: ${number(values[i])}${slot.dataset.metric === 'net_weight' ? ' kg' : ''}`;
                dot.append(title); svg.append(dot);
            });
            const caption = element('div', null, 'sales-sparkline-caption');
            const shortMonth = value => new Date(`${value}T12:00:00`).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
            caption.append(element('span', 'Monthly trend'), element('span', `${shortMonth(kpiTrend[0].month)} – ${shortMonth(kpiTrend[kpiTrend.length - 1].month)}`, 'sales-sparkline-period'));
            slot.append(svg, caption);
        }
    }
    function render(segment, data, container) {
        if (segment === 'kpis') {
            if (!data.row_count) { container.append(element('p', 'No matching transactions.', 'sales-note')); return; }
            for (const column of metricColumns) {
                const card = element('article', null, 'sales-kpi');
                card.dataset.metric = column.key;
                const icons = { invoice_turnover: 'receipt_long', return_turnover: 'undo', net_turnover: 'account_balance_wallet', net_weight: 'scale', total_tsk: 'diamond' };
                const heading = element('div', null, 'sales-kpi-heading');
                const icon = element('span', icons[column.key], 'material-symbols-outlined sales-kpi-icon');
                icon.setAttribute('aria-hidden', 'true');
                heading.append(element('small', column.label), icon);
                const sparkline = element('div', null, 'sales-kpi-sparkline');
                sparkline.dataset.metric = column.key; sparkline.dataset.label = column.label;
                const valueRow = element('div', null, 'sales-kpi-value');
                const change = data.yoy?.[column.key];
                const available = typeof change === 'number' && Number.isFinite(change);
                const rounded = available ? Number(change.toFixed(1)) : null;
                const badge = element('span', available ? `${rounded > 0 ? '+' : ''}${rounded.toFixed(1)}% YoY` : 'YoY —',
                    `sales-kpi-change ${available && rounded !== 0 ? (rounded > 0 ? 'is-up' : 'is-down') : 'is-neutral'}`);
                const period = data.prior_period;
                const comparison = period ? `${period.start} to ${period.end}` : 'the same period last year';
                badge.title = available
                    ? `Compared with ${number(data.prior_totals?.[column.key])} for ${comparison}. Change = (current − prior) / |prior| × 100.`
                    : `No percentage comparison for ${comparison}: the prior value is zero or data is unavailable.`;
                badge.setAttribute('aria-label', `${column.label}: ${available ? `${rounded}% change` : 'comparison unavailable'} versus ${comparison}`);
                const isAmount = column.key !== 'net_weight';
                const amount = element('strong', isAmount && data[column.key] != null
                    ? crores(data[column.key])
                    : number(data[column.key]));
                amount.title = `${number(data[column.key])}${isAmount ? '' : ' kg'}`;
                amount.setAttribute('aria-label', `${column.label}: ${amount.title}`);
                if (isAmount) valueRow.classList.add('sales-kpi-value-crores');
                valueRow.append(amount, badge);
                card.append(heading, valueRow, sparkline);
                container.append(card);
            }
            updateKpiSparklines();
            return;
        }
        if (!data.length || (['trend', 'ledger'].includes(segment) && !data.some(r => r.row_count))) {
            container.append(element('p', 'No matching transactions for these filters.', 'sales-note')); return;
        }
        if (segment === 'trend') {
            const hasPrior = data.some(row => row.prior_turnover != null);
            const summary = element('div', null, 'sales-chart-summary');
            const totals = { net_turnover: data.reduce((sum, row) => sum + row.net_turnover, 0), total_tsk: data.reduce((sum, row) => sum + row.total_tsk, 0) };
            for (const [key, label] of [['net_turnover', 'Net turnover'], ['total_tsk', 'Total TSK']]) {
                const item = element('div'); const value = element('strong', crores(totals[key])); value.title = number(totals[key]);
                item.append(element('small', label), value); summary.append(item);
            }
            const period = element('div'); period.append(element('small', 'Monthly view'), element('strong', `${data.length} months`)); summary.append(period); container.append(summary);
            const datasets = [
                { label: 'Net turnover', data: data.map(r => r.net_turnover), backgroundColor: '#137fec', borderRadius: 5, maxBarThickness: 30, yAxisID: 'y' },
                { label: 'TSK · source total', type: 'line', data: data.map(r => r.total_tsk), borderColor: '#8b5cf6', backgroundColor: '#8b5cf6', borderWidth: 2.5, pointRadius: 3, pointHoverRadius: 5, yAxisID: 'tsk' }
            ];
            if (hasPrior) datasets.push({ label: 'Prior-year turnover', type: 'line', data: data.map(r => r.prior_turnover), borderColor: '#94a3b8', borderDash: [5, 4], pointRadius: 2, yAxisID: 'y' });
            drawChart(segment, container, { type: 'bar', data: { labels: data.map(r => monthLabel(r.month)), datasets }, options: { interaction: { mode: 'index', intersect: false }, scales: {
                x: { grid: { display: false }, ticks: { maxRotation: 0, font: { size: 10 } } },
                y: { beginAtZero: true, ticks: { callback: axisCrores, maxTicksLimit: 6 }, border: { display: false }, title: { display: true, text: 'Turnover (Cr)' } },
                tsk: { position: 'right', beginAtZero: true, grid: { drawOnChartArea: false }, border: { display: false }, ticks: { callback: axisCrores, maxTicksLimit: 6 }, title: { display: true, text: 'TSK (Cr)' } }
            } } });
            container.append(element('p', `Each point represents one month; boundary months may be partial.${hasPrior ? '' : ' Prior-year comparison is unavailable for this selection.'}`, 'sales-chart-note'));
            const details = element('details', null, 'sales-chart-details'); details.append(element('summary', 'View monthly values'));
            const columns = [{ key: 'month', label: 'Month', format: monthLabel }, metricColumns[2], metricColumns[4]];
            if (hasPrior) columns.push({ key: 'prior_turnover', label: 'Prior-year turnover', format: crores });
            table(details, columns, data); container.append(details);
        } else if (segment === 'sections') {
            const positive = data.every(r => r.net_turnover >= 0) && data.some(r => r.net_turnover > 0);
            const palette = ['#137fec', '#059669', '#8b5cf6', '#0891b2', '#d97706', '#f43f5e', '#64748b', '#84cc16', '#cbd5e1'];
            const top = data.slice(0, 8);
            const chartRows = data.length > 8 ? [...top, { label: 'Other sections', net_turnover: data.slice(8).reduce((a, r) => a + r.net_turnover, 0) }] : top;
            const total = data.reduce((sum, row) => sum + row.net_turnover, 0);
            const summary = element('div', null, 'sales-section-summary'); summary.append(element('span', `${data.length} sections`), element('span', 'Net turnover share')); container.append(summary);
            drawChart(segment, container, { type: positive ? 'doughnut' : 'bar', data: { labels: chartRows.map(r => r.label), datasets: [{ label: 'Net turnover', data: chartRows.map(r => r.net_turnover), backgroundColor: palette, borderWidth: 0, spacing: 3, hoverOffset: 5, borderRadius: 3 }] }, options: positive ? { cutout: '76%' } : { indexAxis: 'y', scales: { x: { ticks: { callback: axisCrores }, title: { display: true, text: 'Net turnover (Cr)' } } } } });
            if (positive && container.querySelector('.sales-canvas')) {
                const center = element('div', null, 'sales-donut-center'); const value = element('strong', crores(total)); value.title = number(total);
                center.append(element('small', 'NET TURNOVER'), value); container.querySelector('.sales-canvas').append(center);
            }
            table(container, [{ key: 'label', label: 'Section', swatch: true }, metricColumns[2], { key: 'share', label: 'Share', format: percent }, metricColumns[4]], data.map((row, i) => ({ ...row, chart_color: palette[Math.min(i, 8)] })));
        } else if (segment === 'branches') {
            const shown = data.slice(0, 10).map((row, i) => ({ ...row, rank: i + 1 }));
            const allTurnover = data.reduce((sum, row) => sum + row.net_turnover, 0);
            const summary = element('div', null, 'sales-ledger-summary sales-branch-summary');
            summary.append(element('span', `Top ${shown.length} of ${data.length} branches`, 'sales-ledger-pill'));
            summary.append(element('span', `Leading branch: ${shown[0].label}`));
            const total = element('strong', `All branches: ${crores(allTurnover)}`); total.title = number(allTurnover); summary.append(total); container.append(summary);
            const footer = { rank: null, label: `Top ${shown.length} total` };
            for (const key of ['net_turnover', 'net_weight', 'total_tsk']) footer[key] = shown.reduce((sum, row) => sum + row[key], 0);
            footer.share = allTurnover > 0 ? footer.net_turnover / allTurnover * 100 : null;
            table(container, [{ key: 'rank', label: 'Rank' }, { key: 'label', label: 'Branch / location' }, metricColumns[2], metricColumns[3], metricColumns[4],
                { key: 'share', label: 'Contribution', format: percent, progress: true }], shown, footer);
            container.append(element('p', 'Contribution is the share of net turnover across all matching branches, including those outside the top 10. Bars show contribution, not target achievement. Shares are unavailable when the overall total is zero or negative.', 'sales-chart-note sales-ledger-note'));
        } else if (segment === 'ledger') {
            const footer = { month: 'Period total', leading_branch: null, mom: null };
            metricColumns.forEach(c => { footer[c.key] = data.reduce((sum, row) => sum + row[c.key], 0); });
            footer.period_share = footer.net_turnover > 0 ? 100 : null;
            const peak = data.filter(row => row.row_count).reduce((best, row) => !best || row.net_turnover > best.net_turnover ? row : best, null);
            const summary = element('div', null, 'sales-ledger-summary');
            summary.append(element('span', `${data.length} monthly periods`, 'sales-ledger-pill'));
            if (peak) summary.append(element('span', `Highest turnover: ${monthLabel(peak.month)} · ${crores(peak.net_turnover)}`));
            const total = element('strong', `Period net turnover: ${crores(footer.net_turnover)}`); total.title = number(footer.net_turnover); summary.append(total); container.append(summary);
            table(container, [{ key: 'month', label: 'Month', format: v => v === 'Period total' ? v : monthLabel(v) }, ...metricColumns,
                { key: 'period_share', label: 'Period share', format: percent }, { key: 'mom', label: 'MoM change', format: percent },
                { key: 'leading_branch', label: 'Leading branch' }], data.map(row => ({ ...row, is_peak: row === peak })), footer);
            container.append(element('p', 'Bars show each month’s share of period net turnover, not progress against a target. MoM compares complete consecutive months; partial months are labeled and excluded from comparison. Shares are unavailable when period net turnover is zero or negative.', 'sales-chart-note sales-ledger-note'));
        }
    }
    async function load(segment, params) {
        controllers.get(segment)?.abort();
        const controller = new AbortController(); controllers.set(segment, controller);
        const panel = page.querySelector(`[data-segment="${segment}"]`);
        const status = panel.querySelector('.sales-status'); const content = panel.querySelector('.sales-content');
        panel.setAttribute('aria-busy', 'true'); status.textContent = 'Loading…';
        if (segment === 'trend') {
            kpiTrend = null; kpiTrendStatus = 'Loading monthly trend…'; updateKpiSparklines();
        }
        try {
            const payload = await (await request(segment, params, controller.signal)).json();
            if (controller.signal.aborted) return;
            charts.get(segment)?.destroy(); charts.delete(segment); content.replaceChildren();
            if (segment === 'trend') { kpiTrend = payload.data; updateKpiSparklines(); }
            render(segment, payload.data, content); status.textContent = '';
            panel.querySelector('.sales-fetched')?.remove();
            panel.append(element('p', `Fetched ${new Date(payload.fetched_at).toLocaleTimeString('en-IN')}`, 'sales-fetched'));
        } catch (error) {
            if (error.name !== 'AbortError') {
                if (segment === 'trend') {
                    kpiTrend = null; kpiTrendStatus = 'Trend unavailable · retry monthly trend'; updateKpiSparklines();
                }
                content.replaceChildren(); panel.querySelector('.sales-fetched')?.remove();
                retry(status, error.message, () => load(segment, applied));
            }
        } finally {
            if (!controller.signal.aborted) panel.removeAttribute('aria-busy');
        }
    }
    function reload() {
        const params = new URLSearchParams(applied);
        document.getElementById('sales-period').textContent = `${params.get('start')} to ${params.get('end')} · Live external data`;
        history.replaceState({}, '', `${location.pathname}?${params}`);
        segments.forEach(segment => load(segment, params)); loadOptions(params);
    }
    form.addEventListener('submit', event => {
        event.preventDefault(); applied = new URLSearchParams(new FormData(form)); reload();
    });
    form.addEventListener('reset', event => {
        event.preventDefault(); applied = new URLSearchParams(); restoreDates(); fields.forEach(select => [...select.options].forEach(o => { o.selected = false; })); reload();
    });
    document.getElementById('sales-refresh').addEventListener('click', reload);
    function toggleFilters(open) {
        const sidebar = document.getElementById('sales-sidebar');
        sidebar.classList.toggle('is-collapsed', !open);
        sidebar.inert = !open;
        document.getElementById('sales-filter-toggle').setAttribute('aria-expanded', String(open));
    }
    document.getElementById('sales-filter-toggle').addEventListener('click', () => toggleFilters(document.getElementById('sales-sidebar').classList.contains('is-collapsed')));
    document.getElementById('sales-filter-close').addEventListener('click', () => toggleFilters(false));
    if (matchMedia('(max-width: 680px)').matches) toggleFilters(false);
    restoreDates(); fields.forEach(select => setOptions(select, [], applied.getAll(select.name))); reload();
})();
