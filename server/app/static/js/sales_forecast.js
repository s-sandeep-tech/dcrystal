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
            ? `Sourced ${new Date(c.retrieved_at).toLocaleString('en-IN')}. Context is advisory; it does not adjust the numerical forecast.`
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
        const history = result?.history || state?.history || [];
        const period = Number(el('sf-period').value);
        const visible = period ? history.slice(-period) : history;
        const forecast = result?.forecast || [];
        const latest = history.at(-1);
        el('sf-actual').textContent = money(latest?.y);
        el('sf-actual-date').textContent = latest ? `${day(latest.ds)} · INR lakhs` : 'No sales history';
        el('sf-total').textContent = money(result?.three_day_total);
        el('sf-dates').textContent = forecast.length ? `${day(forecast[0].ds)} – ${day(forecast.at(-1).ds)}` : 'Forecast pending';
        el('sf-mae').textContent = money(result?.metrics?.backtest_mae);
        el('sf-model').textContent = result ? `${result.metrics.engine.replaceAll('_', ' ')} · 9 validation days` : 'No model run';
        el('sf-cutoff').textContent = result?.cutoff_date || latest?.ds || '—';
        el('sf-sync').textContent = state?.snapshot ? `Synced ${new Date(state.snapshot.synced_at).toLocaleString('en-IN')}` : 'Sync required';
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
            td.colSpan = 4; td.textContent = 'No forecast available'; tr.append(td); el('sf-rows').append(tr);
        }
        el('sf-quality').textContent = result ? `${result.metrics.interval_method}. ${result.metrics.zero_filled_days} missing dates filled with zero within the observed history. ${result.stale_days ? `History is ${result.stale_days} day(s) behind yesterday.` : ''}` : '';
        context(result);
        el('sf-empty').hidden = Boolean(visible.length);
        if (chart) chart.destroy();
        if (typeof Chart === 'undefined') { status('Chart library could not load. Forecast values remain available in the table.', true); return; }
        const blanks = Array(visible.length).fill(null);
        const predicted = [...blanks, ...forecast.map(r => r.baseline_yhat / 100000)];
        if (forecast.length && latest && visible.length) predicted[visible.length - 1] = latest.y / 100000;
        chart = new Chart(el('sf-chart'), {
            type: 'line', data: {labels: [...visible.map(r => r.ds), ...forecast.map(r => r.ds)], datasets: [
                {label: 'Lower', data: [...blanks, ...forecast.map(r => r.yhat_lower / 100000)], borderWidth: 0, pointRadius: 0},
                {label: 'Indicative range', data: [...blanks, ...forecast.map(r => r.yhat_upper / 100000)], borderWidth: 0, pointRadius: 0, fill: '-1', backgroundColor: 'rgba(228, 167, 53, .16)'},
                {label: 'Actual', data: [...visible.map(r => r.y / 100000), ...forecast.map(() => null)], borderColor: '#137fec', borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: .15},
                {label: 'Forecast', data: predicted, borderColor: '#bd7500', borderDash: [2, 5], borderWidth: 3, pointRadius: 4, pointBackgroundColor: '#fff', tension: 0}
            ]}, options: {responsive: true, maintainAspectRatio: false, animation: false,
                interaction: {mode: 'index', intersect: false}, plugins: {legend: {display: false}, tooltip: {callbacks: {label: ctx => `${ctx.dataset.label}: ${Number(ctx.raw).toLocaleString('en-IN', {maximumFractionDigits: 2})} lakhs`}}},
                scales: {x: {grid: {display: false}, ticks: {maxTicksLimit: 10, maxRotation: 0, callback: function(value) { return day(this.getLabelForValue(value)); }}},
                         y: {title: {display: true, text: 'INR lakhs'}, grid: {color: 'rgba(120,135,150,.13)'}}}
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
            if (data.forecast_run && !data.forecast_run.result) { busy(true); poll(data.forecast_run.task_id, token); }
            if (data.forecast_run?.result?.stale_days) status('Forecast uses older sales history. Check the forecast dates.');
        } catch (error) { if (token === sequence) { busy(false); status(error.message, true); } }
    }
    el('sf-location').addEventListener('change', load);
    el('sf-refresh').addEventListener('click', load);
    el('sf-period').addEventListener('change', draw);
    el('sf-run')?.addEventListener('click', async () => {
        const token = ++sequence; clearTimeout(pollTimer); busy(true); status('Queueing forecast...');
        try {
            const data = await api('/api/sales-turnover-forecast/run', {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({branch_id: el('sf-location').value || null, include_external: el('sf-external').checked})});
            if (token === sequence) poll(data.task_id, token);
        } catch (error) { if (token === sequence) { busy(false); status(error.message, true); } }
    });
    window.addEventListener('pagehide', () => { ++sequence; clearTimeout(pollTimer); });
    load();
})();
