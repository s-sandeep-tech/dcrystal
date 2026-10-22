(() => {
    const el = id => document.getElementById(id);
    const money = value => value == null ? '—' : (value / 100000).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    const day = value => new Date(value + 'T00:00:00').toLocaleDateString('en-IN', {day: '2-digit', month: 'short'});
    let chart, state, sequence = 0, pollTimer;
    const status = (message, error = false) => { el('sf-status').textContent = message; el('sf-status').classList.toggle('error', error); };
    async function api(url, options) {
        const response = await fetch(url, options);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || data.msg || 'Unable to load sales forecast');
        return data;
    }
    function busy(value) {
        if (el('sf-run')) el('sf-run').disabled = value;
        el('sf-refresh').disabled = value;
    }
    function context(result) {
        const c = result?.external_context;
        el('sf-context-text').textContent = c?.summary || '';
        el('sf-context-state').textContent = c?.status === 'available'
            ? `Sourced ${new Date(c.retrieved_at).toLocaleString('en-IN')}. ${c.affects_forecast ? 'Validated external features used in prediction.' : 'Baseline retained: external features did not pass validation or coverage requirements.'}`
            : c?.message || 'External context has not been requested.';
        el('sf-context-sources').replaceChildren();
        for (const source of c?.sources || []) {
            if (!source.url.startsWith('https://')) continue;
            const li = document.createElement('li'), link = document.createElement('a');
            link.textContent = source.title; link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
            li.append(link); el('sf-context-sources').append(li);
        }
        el('sf-search-suggestions').replaceChildren();
        if (c?.search_suggestions_html) {
            const frame = document.createElement('iframe');
            frame.setAttribute('sandbox', 'allow-popups allow-popups-to-escape-sandbox');
            frame.title = 'Google Search suggestions'; frame.srcdoc = c.search_suggestions_html;
            el('sf-search-suggestions').append(frame);
        }
    }
    function draw() {
        const result = state?.forecast_run?.result;
        const history = state?.history || result?.history || [];
        const period = Number(el('sf-period').value);
        const visibleHistory = period ? history.slice(-period) : history;
        const forecast = result?.forecast || [];
        const latest = history.at(-1);

        // Build predictions map from unversioned predictions and active forecast
        const predMap = new Map();
        for (const p of (state?.predictions || [])) {
            predMap.set(p.ds, { yhat: p.yhat, yhat_lower: p.yhat_lower, yhat_upper: p.yhat_upper });
        }
        for (const f of forecast) {
            predMap.set(f.ds, { yhat: f.baseline_yhat, yhat_lower: f.yhat_lower, yhat_upper: f.yhat_upper });
        }

        // Build actual sales map
        const actualMap = new Map();
        for (const h of history) {
            actualMap.set(h.ds, h.y);
        }

        // Stats summary cards
        el('sf-actual').textContent = money(latest?.y);
        el('sf-actual-date').textContent = latest ? `${day(latest.ds)} · INR lakhs` : 'No sales history';
        el('sf-total').textContent = money(result?.three_day_total);
        el('sf-dates').textContent = forecast.length ? `${day(forecast[0].ds)} – ${day(forecast.at(-1).ds)}` : 'Forecast pending';
        el('sf-mae').textContent = money(result?.metrics?.backtest_mae);
        el('sf-model').textContent = result ? `${result.metrics.engine.replaceAll('_', ' ')} · ${result.metrics.backtest_days || 9} validation days` : 'No model run';
        el('sf-cutoff').textContent = result?.cutoff_date || latest?.ds || '—';
        el('sf-sync').textContent = state?.snapshot ? `Synced ${new Date(state.snapshot.synced_at).toLocaleString('en-IN')}` : 'Sync required';

        // 1. Populate Outlook Table (Upcoming 3 Days)
        el('sf-rows').replaceChildren();
        for (const row of forecast) {
            const tr = document.createElement('tr');
            for (const value of [row.ds, money(row.baseline_yhat), money(row.yhat_lower), money(row.yhat_upper)]) {
                const td = document.createElement('td'); td.textContent = value; tr.append(td);
            }
            el('sf-rows').append(tr);
        }
        if (!forecast.length) {
            const tr = document.createElement('tr'), td = document.createElement('td');
            td.colSpan = 4; td.textContent = 'No upcoming forecast available'; tr.append(td); el('sf-rows').append(tr);
        }

        // 2. Populate Predicted vs Actual Historical Comparison Table
        const compareRows = [];
        for (const [ds, pred] of predMap.entries()) {
            if (actualMap.has(ds)) {
                const act = actualMap.get(ds);
                const variance = act - pred.yhat;
                const pct = act ? ((variance / act) * 100) : 0;
                const acc = Math.max(0, 100 - Math.abs(act ? ((pred.yhat - act) / act) * 100 : 0)).toFixed(1);
                compareRows.push({ ds, actual: act, predicted: pred.yhat, variance, pct, acc });
            }
        }
        compareRows.sort((a, b) => b.ds.localeCompare(a.ds));
        const compTbody = el('sf-compare-rows');
        if (compTbody) {
            compTbody.replaceChildren();
            for (const r of compareRows) {
                const tr = document.createElement('tr');
                const sign = r.variance >= 0 ? '+' : '';
                const diffCls = r.variance >= 0 ? 'sf-pos' : 'sf-neg';
                const varText = `${sign}${money(r.variance)} (${sign}${r.pct.toFixed(1)}%)`;
                for (const [idx, val] of [r.ds, money(r.actual), money(r.predicted), varText, `${r.acc}%`].entries()) {
                    const td = document.createElement('td');
                    td.textContent = val;
                    if (idx === 3) td.className = diffCls;
                    tr.append(td);
                }
                compTbody.append(tr);
            }
            if (!compareRows.length) {
                const tr = document.createElement('tr'), td = document.createElement('td');
                td.colSpan = 5;
                td.textContent = 'Predictions for upcoming dates will appear here once new daily sales data is synced.';
                tr.append(td);
                compTbody.append(tr);
            }
        }

        el('sf-quality').textContent = result ? `${result.metrics.interval_method}. ${result.metrics.fallback_reason || ''} ${result.snapshot_run_id !== state?.snapshot?.id ? 'Saved forecast retained from an earlier sales snapshot.' : ''}` : '';
        context(result);
        el('sf-empty').hidden = Boolean(visibleHistory.length || predMap.size);
        if (chart) chart.destroy();
        if (typeof Chart === 'undefined') { status('Chart library could not load. Forecast values remain available in the table.', true); return; }

        // Construct aligned timeline of all dates for chart
        const dateSet = new Set(visibleHistory.map(r => r.ds));
        for (const ds of predMap.keys()) {
            if (!actualMap.has(ds) || dateSet.has(ds)) dateSet.add(ds);
        }
        const allDates = Array.from(dateSet).sort();

        const actualSeries = allDates.map(d => actualMap.has(d) ? (actualMap.get(d) / 100000) : null);
        const predSeries = allDates.map(d => predMap.has(d) ? (predMap.get(d).yhat / 100000) : null);
        const lowerSeries = allDates.map(d => predMap.has(d) && predMap.get(d).yhat_lower != null ? (predMap.get(d).yhat_lower / 100000) : null);
        const upperSeries = allDates.map(d => predMap.has(d) && predMap.get(d).yhat_upper != null ? (predMap.get(d).yhat_upper / 100000) : null);

        // Connect prediction line and indicative range to the last actual day (e.g. 21st)
        const lastActualIdx = latest ? allDates.lastIndexOf(latest.ds) : -1;
        if (lastActualIdx !== -1 && forecast.length) {
            if (predSeries[lastActualIdx] == null) {
                predSeries[lastActualIdx] = latest.y / 100000;
            }
            if (lowerSeries[lastActualIdx] == null) {
                lowerSeries[lastActualIdx] = latest.y / 100000;
            }
            if (upperSeries[lastActualIdx] == null) {
                upperSeries[lastActualIdx] = latest.y / 100000;
            }
        }

        chart = new Chart(el('sf-chart'), {
            type: 'line', data: {labels: allDates, datasets: [
                {label: 'Lower', data: lowerSeries, borderWidth: 0, pointRadius: 0},
                {label: 'Indicative range', data: upperSeries, borderWidth: 0, pointRadius: 0, fill: '-1', backgroundColor: 'rgba(228, 167, 53, .16)'},
                {label: 'Actual', data: actualSeries, borderColor: '#137fec', borderWidth: 2, pointRadius: 1, pointHoverRadius: 4, tension: .15},
                {label: 'Predicted', data: predSeries, borderColor: '#bd7500', borderDash: [4, 4], borderWidth: 2.5, pointRadius: 2, pointHoverRadius: 5, pointBackgroundColor: '#fff', spanGaps: true, tension: .1}
            ]}, options: {responsive: true, maintainAspectRatio: false, animation: false,
                interaction: {mode: 'index', intersect: false},
                plugins: {
                    legend: {display: false},
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                if (ctx.raw == null) return null;
                                if (ctx.dataset.label === 'Predicted' && ctx.dataIndex === lastActualIdx && !predMap.has(latest?.ds)) {
                                    return null;
                                }
                                return `${ctx.dataset.label}: ${Number(ctx.raw).toLocaleString('en-IN', {maximumFractionDigits: 2})} lakhs`;
                            },
                            afterBody: items => {
                                const idx = items[0]?.dataIndex;
                                if (idx == null) return [];
                                const d = allDates[idx];
                                const act = actualMap.get(d);
                                const pr = predMap.get(d)?.yhat;
                                if (act != null && pr != null) {
                                    const diff = (act - pr) / 100000;
                                    const sign = diff >= 0 ? '+' : '';
                                    const pct = act ? ((act - pr) / act * 100).toFixed(1) : 0;
                                    return [`Diff: ${sign}${diff.toLocaleString('en-IN', {maximumFractionDigits: 2})} lakhs (${sign}${pct}%)`];
                                }
                                return [];
                            }
                        }
                    }
                },
                scales: {
                    x: {grid: {display: false}, ticks: {maxTicksLimit: 12, maxRotation: 0, callback: function(value) { return day(this.getLabelForValue(value)); }}},
                    y: {title: {display: true, text: 'INR lakhs'}, grid: {color: 'rgba(120,135,150,.13)'}}
                }
            }
        });
    }
    async function poll(taskId, token) {
        if (token !== sequence) return;
        try {
            const data = await api(`/api/sales-turnover-forecast/tasks/${encodeURIComponent(taskId)}`);
            if (token !== sequence) return;
            if (data.status === 'completed') {
                state.forecast_run = {task_id: taskId, result: data.result}; draw(); busy(false);
                status(data.result.stale_days ? 'Forecast ready. Sales history is behind yesterday; check the forecast dates.' : 'Three-day forecast ready.'); return;
            }
            if (data.status === 'failed') { busy(false); status(data.error || 'Forecast failed', true); return; }
            status(data.status === 'retrying' ? `Retrying forecast: ${data.error || 'temporary failure'}` : `Forecast ${data.status}.`);
        } catch (error) { if (token === sequence) status(error.message + ' Retrying status check...', true); }
        if (token === sequence) pollTimer = setTimeout(() => poll(taskId, token), 4000);
    }
    async function load() {
        const token = ++sequence;
        clearTimeout(pollTimer); busy(true); status('Loading sales history...');
        try {
            const branch = el('sf-location').value;
            const data = await api('/api/sales-turnover-forecast/data' + (branch ? `?branch_id=${encodeURIComponent(branch)}` : ''));
            if (token !== sequence) return;
            state = data;
            el('sf-location').replaceChildren(new Option('All locations', ''), ...data.locations.map(l => new Option(l.name, l.id)));
            el('sf-location').value = branch;
            draw(); busy(false);
            status(!data.snapshot ? 'Run Sales Prediction Data Sync from Settings to load history.' : 'Sales history loaded.');
            if (data.pending_task_id) { busy(true); poll(data.pending_task_id, token); }
            if (data.forecast_run?.result?.stale_days) status('Forecast uses older sales history. Check the forecast dates.');
        } catch (error) { if (token === sequence) { busy(false); status(error.message, true); } }
    }
    el('sf-location').addEventListener('change', load);
    el('sf-refresh').addEventListener('click', load);
    el('sf-period').addEventListener('change', draw);
    el('sf-tab-outlook')?.addEventListener('click', () => {
        el('sf-tab-outlook').classList.add('active');
        el('sf-tab-compare')?.classList.remove('active');
        if (el('sf-table-outlook')) el('sf-table-outlook').style.display = '';
        if (el('sf-table-compare')) el('sf-table-compare').style.display = 'none';
    });
    el('sf-tab-compare')?.addEventListener('click', () => {
        el('sf-tab-compare').classList.add('active');
        el('sf-tab-outlook')?.classList.remove('active');
        if (el('sf-table-outlook')) el('sf-table-outlook').style.display = 'none';
        if (el('sf-table-compare')) el('sf-table-compare').style.display = '';
    });
    el('sf-external')?.addEventListener('change', () => {
        el('sf-gemini-fallback').disabled = !el('sf-external').checked;
        if (!el('sf-external').checked) el('sf-gemini-fallback').checked = false;
    });
    el('sf-run')?.addEventListener('click', async () => {
        const token = ++sequence; clearTimeout(pollTimer); busy(true); status('Queueing forecast...');
        try {
            const data = await api('/api/sales-turnover-forecast/run', {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({branch_id: el('sf-location').value || null, include_external: el('sf-external').checked,
                    allow_gemini_fallback: el('sf-gemini-fallback').checked})});
            if (token === sequence) poll(data.task_id, token);
        } catch (error) { if (token === sequence) { busy(false); status(error.message, true); } }
    });
    window.addEventListener('pagehide', () => { ++sequence; clearTimeout(pollTimer); });
    load();
})();
