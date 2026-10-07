document.addEventListener('DOMContentLoaded', () => {
    const el = id => document.getElementById(`monitor-${id}`);
    const selects = {};
    let params = new URLSearchParams(location.search);
    let charts = {}, payload, controller;
    const format = (n, decimals = 0) => Number(n || 0).toLocaleString(undefined, {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
    const setParam = (key, value) => value ? params.set(key, value) : params.delete(key);
    const colors = ['#db2777', '#64748b', '#d97706', '#2563eb', '#6366f1', '#dc2626', '#9333ea', '#0891b2', '#ea580c', '#059669'];

    function restoreControls() {
        el('search').value = params.get('search') || '';
        el('sort').value = params.get('sort') || 'priority';
        el('direction').value = params.get('direction') || 'asc';
        el('stage').value = params.get('stage') || '';
        el('size').value = params.get('per_page') || '25';
        el('outstanding').checked = params.get('outstanding') !== '0';
        document.querySelectorAll('[data-date]').forEach(input => { input.value = params.get(input.dataset.date) || ''; });
    }

    function options(data) {
        document.querySelectorAll('.monitor-filter').forEach(container => {
            const key = container.dataset.filter;
            const values = (params.get(key) || '').split(',');
            if (!selects[key]) {
                selects[key] = new CustomMultiSelect({containerId: container.id, label: container.dataset.label,
                    defaultText: `All ${container.dataset.label}`, options: data[key] || []});
            } else selects[key].populateOptions(data[key] || []);
            container.querySelectorAll('input[type=checkbox]').forEach(cb => { cb.checked = values.includes(cb.value); });
            selects[key].updateTriggerText();
        });
    }

    function collect() {
        Object.entries(selects).forEach(([key, select]) => setParam(key, select.getValues().join(',')));
        ['sort', 'direction', 'stage', 'search'].forEach(key => setParam(key, el(key).value));
        params.set('per_page', el('size').value);
        params.set('outstanding', el('outstanding').checked ? '1' : '0');
        document.querySelectorAll('[data-date]').forEach(input => setParam(input.dataset.date, input.value));
    }

    function choose(values) {
        Object.entries(values).forEach(([key, value]) => setParam(key, value));
        params.set('page', '1');
        restoreControls();
        load();
    }

    function buildCharts() {
        if (typeof Chart === 'undefined') {
            el('warnings').textContent += ' Chart library unavailable; the table remains available.';
            return;
        }
        Object.values(charts).forEach(chart => chart.destroy());
        const stageMeasure = el('stage-measure').value;
        function bar(id, labels, values, palette, action) {
            return new Chart(el(id), {type: 'bar', data: {labels, datasets: [{data: values, backgroundColor: palette, borderRadius: 3}]},
                options: {responsive: true, maintainAspectRatio: false, plugins: {legend: {display: false}, tooltip: {callbacks: {label: ctx => format(ctx.raw, id === 'stages' && stageMeasure === 'wt' ? 3 : 0) + (id === 'stages' ? stageMeasure === 'wt' ? ' g' : ' pcs' : ' requests')}}},
                    scales: {y: {beginAtZero: true, ticks: {precision: 0}}, x: {ticks: {font: {size: 9}, maxRotation: 65, minRotation: 30}}},
                    onClick: (_, points) => { if (points.length) action(points[0].index); },
                    onHover: (event, points) => { event.native.target.style.cursor = points.length ? 'pointer' : 'default'; }}});
        }
        charts.stages = bar('stages', payload.charts.stages.map(s => s.label), payload.charts.stages.map(s => s[stageMeasure]), colors,
            index => choose({stage: payload.charts.stages[index].key}));
        charts.risk = bar('risk', payload.charts.risks.map(r => r.label), payload.charts.risks.map(r => r.count), ['#dc2626', '#d97706', '#ca8a04', '#059669', '#94a3b8'],
            index => choose({risk: payload.charts.risks[index].key}));
    }

    function heatmap() {
        const measure = el('heat-measure').value;
        const branches = [...payload.charts.branches];
        branches.sort(el('heat-sort').value === 'branch' ? (a, b) => a.label.localeCompare(b.label) :
            (a, b) => Math.max(...b[measure]) - Math.max(...a[measure]));
        const max = Math.max(1, ...branches.flatMap(b => b[measure]));
        const table = document.createElement('table');
        const head = table.createTHead().insertRow();
        ['Branch', ...payload.charts.stages.map(s => s.label)].forEach(label => {
            const th = document.createElement('th'); th.textContent = label; head.append(th);
        });
        const body = table.createTBody();
        branches.forEach(branch => {
            const row = body.insertRow();
            const label = document.createElement('th'); label.textContent = branch.label; row.append(label);
            branch[measure].forEach((value, i) => {
                const cell = row.insertCell();
                const button = document.createElement('button');
                button.textContent = value ? format(value, measure === 'wt' ? 3 : 0) : '-';
                button.title = `${branch.label} / ${payload.charts.stages[i].label}: ${format(value, measure === 'wt' ? 3 : 0)} ${measure === 'wt' ? 'g' : 'pcs'}`;
                button.setAttribute('aria-label', button.title);
                const intensity = value / max;
                button.style.backgroundColor = value ? `rgba(13,148,136,${0.12 + intensity * 0.88})` : 'transparent';
                button.style.color = intensity > 0.5 ? '#fff' : 'inherit';
                button.onclick = () => choose({branch: branch.key, stage: payload.charts.stages[i].key});
                cell.append(button);
            });
        });
        el('heatmap').replaceChildren(table);
        if (!branches.length) el('heatmap').textContent = 'No outstanding orders';
    }

    async function load() {
        controller?.abort();
        controller = new AbortController();
        el('loading-overlay').hidden = false;
        el('error').textContent = '';
        const spinner = document.createElement('span');
        spinner.className = 'monitor-spinner';
        spinner.setAttribute('aria-hidden', 'true');
        el('loading').replaceChildren(spinner, document.createTextNode('Loading customer orders...'));
        el('retry').hidden = true;
        el('table').setAttribute('aria-busy', 'true');
        try {
            const response = await fetch(`/api/customer-order-performance-monitoring/data?${params}`, {signal: controller.signal});
            if (response.status === 401) throw new Error('Session expired. Please sign in again.');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Unable to load report.');
            payload = data;
            params.set('page', data.page);
            history.replaceState(null, '', `${location.pathname}?${params}`);
            options(data.options);
            Object.entries(data.stats).forEach(([key, value]) => { el(`stat-${key}`).textContent = format(value, key === 'weight' ? 3 : 0); });
            el('table').innerHTML = data.html;
            el('warnings').textContent = data.warnings.join(' ');
            el('count').textContent = `${format(data.total)} items`;
            el('page').textContent = `${data.page} / ${data.pages}`;
            el('prev').disabled = data.page <= 1; el('next').disabled = data.page >= data.pages;
            el('selections').textContent = ['stage', 'branch', 'risk'].filter(k => params.has(k)).map(k => {
                const value = params.get(k);
                const label = k === 'stage' ? data.charts.stages.find(s => s.key === value)?.label : k === 'risk' ? data.charts.risks.find(r => r.key === value)?.label : data.charts.branches.find(b => b.key === value)?.label;
                return `${k}: ${label || value}`;
            }).join(' | ');
            el('clear').hidden = !['stage', 'branch', 'risk'].some(k => params.has(k));
            buildCharts(); heatmap();
            el('loading-overlay').hidden = true;
            el('table').setAttribute('aria-busy', 'false');
        } catch (error) {
            if (error.name === 'AbortError') return;
            el('loading-overlay').hidden = true;
            el('error').textContent = error.message;
            el('retry').hidden = false;
            el('table').setAttribute('aria-busy', 'false');
        }
    }

    el('apply').onclick = () => { collect(); params.set('page', '1'); load(); };
    el('reset').onclick = () => { params = new URLSearchParams(); restoreControls(); load(); };
    el('retry').onclick = load;
    el('clear').onclick = () => { ['stage', 'branch', 'risk'].forEach(k => params.delete(k)); restoreControls(); load(); };
    el('toggle').onclick = () => {
        const collapsed = el('sidebar').classList.toggle('is-collapsed');
        el('toggle').setAttribute('aria-expanded', String(!collapsed));
    };
    el('size').onchange = () => { collect(); params.set('page', '1'); load(); };
    el('prev').onclick = () => { params.set('page', payload.page - 1); load(); };
    el('next').onclick = () => { params.set('page', payload.page + 1); load(); };
    el('search').onkeydown = event => { if (event.key === 'Enter') el('apply').click(); };
    el('stage-measure').onchange = () => { if (payload) buildCharts(); };
    ['heat-measure', 'heat-sort'].forEach(id => { el(id).onchange = () => { if (payload) heatmap(); }; });
    const heatDialog = el('heat-dialog');
    const heatPanel = el('heat-panel');
    const heatExpand = el('heat-expand');
    const heatPosition = document.createComment('Branch heatmap position');
    heatPanel.before(heatPosition);
    heatExpand.onclick = () => {
        if (heatDialog.open) {
            heatDialog.close();
            return;
        }
        heatDialog.append(heatPanel);
        heatExpand.setAttribute('aria-expanded', 'true');
        heatExpand.setAttribute('aria-label', 'Collapse Branch / Production Stage');
        heatExpand.title = 'Collapse Branch / Production Stage';
        heatExpand.querySelector('span').textContent = 'fullscreen_exit';
        heatDialog.showModal();
        heatExpand.focus();
    };
    heatDialog.addEventListener('close', () => {
        heatPosition.after(heatPanel);
        heatExpand.setAttribute('aria-expanded', 'false');
        heatExpand.setAttribute('aria-label', 'Expand Branch / Production Stage');
        heatExpand.title = 'Expand Branch / Production Stage';
        heatExpand.querySelector('span').textContent = 'fullscreen';
        heatExpand.focus();
    });
    if (el('export')) el('export').onclick = () => { location.href = `/api/customer-order-performance-monitoring/export?${params}`; };
    const ownersDialog = el('owners-dialog');
    el('owners-close').onclick = () => ownersDialog.close();
    ownersDialog.addEventListener('click', event => {
        if (event.target !== ownersDialog) return;
        const bounds = ownersDialog.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) ownersDialog.close();
    });
    el('table').onclick = event => {
        const ownerButton = event.target.closest('[data-owners]');
        if (ownerButton) {
            el('owners-content').replaceChildren(document.getElementById(ownerButton.dataset.owners).content.cloneNode(true));
            ownersDialog.showModal();
        }
        const sort = event.target.closest('[data-sort]');
        if (sort) {
            const direction = params.get('sort') === sort.dataset.sort && params.get('direction') !== 'desc' ? 'desc' : 'asc';
            choose({sort: sort.dataset.sort, direction});
        }
        const expand = event.target.closest('[data-detail]');
        if (expand) {
            const row = document.getElementById(expand.dataset.detail);
            row.hidden = !row.hidden;
            expand.setAttribute('aria-expanded', String(!row.hidden));
            expand.querySelector('.material-symbols-outlined').textContent = row.hidden ? 'add_circle' : 'remove_circle';
        }
    };
    restoreControls();
    if (window.innerWidth < 900) el('sidebar').classList.add('is-collapsed');
    el('toggle').setAttribute('aria-expanded', String(!el('sidebar').classList.contains('is-collapsed')));
    load();
});
