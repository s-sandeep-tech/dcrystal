(() => {
    'use strict';
    const form = document.getElementById('sales-filters');
    if (!form) return;
    const fields = [...form.querySelectorAll('select[multiple]')];
    const filterDropdowns = new Map();
    const controllers = new Map();
    const group = document.getElementById('monthly-group');
    let applied = new URLSearchParams(location.search);
    const number = value => Number(value).toLocaleString('en-IN', {maximumFractionDigits: 2});
    const money = value => `${(value / 10000000).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})} Cr`;
    const monthName = value => new Date(`${value}T12:00:00`).toLocaleDateString('en-IN', {month:'short', year:'numeric'});
    const headers = () => {
        const token = localStorage.getItem('access_token');
        return {'X-Requested-With':'XMLHttpRequest', ...(token ? {Authorization:`Bearer ${token}`} : {})};
    };
    function element(tag, text, className) {
        const node = document.createElement(tag);
        if (text != null) node.textContent = text;
        if (className) node.className = className;
        return node;
    }
    function setOptions(select, options, selected) {
        select.replaceChildren();
        const known = new Set(options.map(o => o.value));
        const all = [...options, ...selected.filter(v => !known.has(v)).map(v => ({ value: v, label: v }))];
        for (const item of all) select.add(new Option(item.label, item.value, false, selected.includes(item.value)));
        filterDropdowns.get(select)?.refresh();
    }
    function buildFilterDropdown(select) {
        const label = select.getAttribute('aria-label');
        const allText = `All ${label === 'Purity' ? 'purities' : label.toLowerCase() + 's'}`;
        const details = element('details', null, 'sales-multiselect');
        const summary = element('summary'); summary.setAttribute('aria-labelledby', `filter-label-${select.name} filter-value-${select.name}`);
        const value = element('span', allText); value.id = `filter-value-${select.name}`;
        const icon = element('span', 'expand_more', 'material-symbols-outlined'); icon.setAttribute('aria-hidden', 'true');
        summary.append(value, icon);
        const panel = element('div', null, 'sales-multiselect-panel');
        const search = element('input'); search.type = 'search'; search.placeholder = `Search ${label.toLowerCase()}…`; search.setAttribute('aria-label', `Search ${label.toLowerCase()}`);
        const tools = element('div', null, 'sales-multiselect-tools');
        const count = element('span'); count.setAttribute('aria-live', 'polite');
        const clear = element('button', 'Clear'); clear.type = 'button'; clear.setAttribute('aria-label', `Clear ${label.toLowerCase()}`); tools.append(count, clear);
        const list = element('div', null, 'sales-multiselect-options'); list.setAttribute('role', 'group'); list.setAttribute('aria-label', `${label} options`);
        panel.append(search, tools, list); details.append(summary, panel); select.after(details);
        function updateSummary() {
            const chosen = [...select.selectedOptions];
            value.textContent = chosen.length === 0 ? allText : chosen.length === 1 ? chosen[0].text : `${chosen.length} selected`;
            summary.title = chosen.map(option => option.text).join(', ') || allText;
            details.classList.toggle('has-selection', chosen.length > 0); clear.disabled = !chosen.length;
        }
        function refresh() {
            updateSummary(); list.replaceChildren();
            const query = search.value.trim().toLocaleLowerCase();
            const matches = [...select.options].filter(option => !option.disabled && option.text.toLocaleLowerCase().includes(query));
            count.textContent = `${matches.length} options · ${select.selectedOptions.length} selected`;
            if (!matches.length) list.append(element('p', 'No matching options', 'sales-multiselect-empty'));
            for (const option of matches) {
                const row = element('label'); const checkbox = element('input'); checkbox.type = 'checkbox'; checkbox.checked = option.selected;
                checkbox.addEventListener('change', () => { option.selected = checkbox.checked; updateSummary(); count.textContent = `${matches.length} options · ${select.selectedOptions.length} selected`; });
                row.append(checkbox, element('span', option.text)); list.append(row);
            }
        }
        details.addEventListener('toggle', () => {
            if (details.open) {
                filterDropdowns.forEach(dropdown => { if (dropdown.details !== details) dropdown.details.open = false; });
                search.focus();
            }
        });
        search.addEventListener('input', refresh);
        search.addEventListener('keydown', event => { if (event.key === 'Enter') event.preventDefault(); });
        details.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); details.open = false; summary.focus(); } });
        clear.addEventListener('click', () => { [...select.options].forEach(option => { option.selected = false; }); refresh(); });
        filterDropdowns.set(select, { details, refresh, reset() { search.value = ''; details.open = false; refresh(); } });
        refresh();
    }
    document.addEventListener('click', event => filterDropdowns.forEach(dropdown => {
        if (!dropdown.details.contains(event.target)) dropdown.details.open = false;
    }));
    function retry(status, message, fn) {
        status.replaceChildren(element('span', message));
        const button = element('button', 'Retry', 'sales-retry');
        button.type = 'button'; button.addEventListener('click', fn); status.append(button);
    }
    async function request(segment, params, signal) {
        const response = await fetch(`/api/sales-tsk-monthly-analyse/${segment}?${params}`, { headers: headers(), signal, cache: 'no-store' });
        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            throw new Error(body.message || body.msg || `Unable to load report (${response.status}).`);
        }
        return response;
    }
    function render(data) {
        const container = document.getElementById('monthly-content');
        container.replaceChildren();
        document.getElementById('monthly-title').textContent = `${data.group_label} performance`;
        document.getElementById('monthly-summary').textContent = `${data.rows.length} groups · ${data.months.length} months · amounts in Cr`;
        if (!data.rows.length) { container.append(element('p', 'No transactions match these filters.', 'sales-note')); return; }
        const wrap = element('div', null, 'sales-table-wrap');
        wrap.tabIndex = 0; wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', 'Monthly comparison, scroll horizontally for more months');
        const table = element('table', null, 'sales-table');
        const caption = element('caption', `Monthly sales by ${data.group_label.toLowerCase()}`, 'sr-only');
        const head = table.createTHead(), top = head.insertRow(), sub = head.insertRow();
        const label = element('th', data.group_label, 'monthly-label'); label.rowSpan = 2; label.scope = 'col'; top.append(label);
        for (const month of data.months) {
            const th = element('th', monthName(month.month), 'monthly-end'); th.colSpan = 5; th.scope = 'colgroup';
            if (month.is_partial) th.append(element('span', 'Partial', 'monthly-partial'));
            top.append(th);
            ['Weight / Pieces', 'Share %', 'Net Turnover', 'TSK Total', 'Sales Growth %'].forEach((name, i) => {
                const cell = element('th', name, i === 4 ? 'monthly-end' : ''); cell.scope = 'col'; sub.append(cell);
            });
        }
        function appendRow(parent, name, cells) {
            const tr = parent.insertRow(); const title = element('th', name, 'monthly-label'); title.scope = 'row'; tr.append(title);
            for (const cell of cells) {
                const weight = tr.insertCell(); weight.append(element('span', `${number(cell.net_weight)} kg`), element('span', `${number(cell.pieces)} pcs`, 'monthly-pieces'));
                const share = tr.insertCell(); share.append(element('span', cell.share == null ? '—' : `${number(cell.share)}%`));
                if (cell.share != null) {
                    const track = element('div', null, 'monthly-track'), fill = element('span');
                    fill.style.width = `${Math.max(0, Math.min(100, cell.share))}%`; track.setAttribute('aria-hidden', 'true'); track.append(fill); share.append(track);
                }
                for (const key of ['net_turnover', 'total_tsk']) { const td = tr.insertCell(); td.textContent = money(cell[key]); td.title = number(cell[key]); }
                const growth = tr.insertCell(); growth.className = 'monthly-end';
                const value = cell.growth;
                const badge = element('span', value == null ? '—' : `${value > 0 ? '↑ +' : value < 0 ? '↓ ' : ''}${number(value)}%`, `sales-mom-badge ${value == null || value === 0 ? 'is-neutral' : value > 0 ? 'is-up' : 'is-down'}`);
                badge.title = value == null ? 'No comparable complete previous month with a nonzero sales base.' : 'Change in net turnover versus the previous selected month.';
                growth.append(badge);
            }
        }
        const body = table.createTBody(); data.rows.forEach(row => appendRow(body, row.label, row.months));
        appendRow(table.createTFoot(), 'Total', data.totals);
        table.prepend(caption); wrap.append(table); container.append(wrap);
    }
    async function loadMatrix() {
        controllers.get('matrix')?.abort(); const controller = new AbortController(); controllers.set('matrix', controller);
        const panel = document.getElementById('monthly-panel'), status = document.getElementById('monthly-status');
        panel.setAttribute('aria-busy', 'true'); status.textContent = 'Loading monthly analysis…';
        document.getElementById('monthly-fetched').textContent = '';
        try {
            const {data, fetched_at} = await (await request('matrix', applied, controller.signal)).json();
            if (controller.signal.aborted) return;
            render(data); status.replaceChildren();
            document.getElementById('monthly-fetched').textContent = `Updated ${new Date(fetched_at).toLocaleString('en-IN', {timeZone:'Asia/Kolkata'})} IST`;
        } catch (error) {
            if (controller.signal.aborted) return;
            document.getElementById('monthly-content').replaceChildren();
            retry(status, error.message, loadMatrix);
        } finally { if (!controller.signal.aborted) panel.setAttribute('aria-busy', 'false'); }
    }
    async function loadOptions() {
        controllers.get('options')?.abort(); const controller = new AbortController(); controllers.set('options', controller);
        const status = document.getElementById('sales-options-status'); status.textContent = 'Loading filters…';
        try {
            const {data} = await (await request('options', applied, controller.signal)).json();
            if (controller.signal.aborted) return;
            fields.forEach(select => setOptions(select, data[select.name] || [], [...select.selectedOptions].map(o => o.value)));
            status.replaceChildren();
        } catch (error) { if (!controller.signal.aborted) retry(status, error.message, loadOptions); }
    }
    function reload() {
        history.replaceState(null, '', `${location.pathname}?${applied}`);
        document.getElementById('sales-period').textContent = `${applied.get('start')} to ${applied.get('end')} · Monthly comparison`;
        loadMatrix(); loadOptions();
    }
    function restore() {
        for (const key of ['start', 'end']) {
            if (!applied.get(key)) applied.set(key, form.dataset[key === 'start' ? 'defaultStart' : 'defaultEnd']);
            form.elements[key].value = applied.get(key);
        }
        group.value = applied.get('group_by') || 'section';
        if (!group.value) group.value = 'section';
        applied.set('group_by', group.value);
        fields.forEach(select => setOptions(select, [...select.options].map(o => ({value:o.value, label:o.text})), applied.getAll(select.name)));
    }
    form.addEventListener('submit', event => { event.preventDefault(); applied = new URLSearchParams(new FormData(form)); filterDropdowns.forEach(d => {d.details.open = false;}); reload(); });
    group.addEventListener('change', () => { applied.set('group_by', group.value); reload(); });
    form.addEventListener('reset', event => { event.preventDefault(); applied = new URLSearchParams(); restore(); filterDropdowns.forEach(d => d.reset()); reload(); });
    document.getElementById('sales-refresh').addEventListener('click', reload);
    function toggleFilters(open) {
        const sidebar = document.getElementById('sales-sidebar'); sidebar.classList.toggle('is-collapsed', !open); sidebar.inert = !open;
        document.getElementById('sales-filter-toggle').setAttribute('aria-expanded', String(open));
    }
    document.getElementById('sales-filter-toggle').addEventListener('click', () => toggleFilters(document.getElementById('sales-sidebar').classList.contains('is-collapsed')));
    document.getElementById('sales-filter-close').addEventListener('click', () => toggleFilters(false));
    if (matchMedia('(max-width: 680px)').matches) toggleFilters(false);
    fields.forEach(select => { select.replaceChildren(); buildFilterDropdown(select); }); restore(); reload();
})();
