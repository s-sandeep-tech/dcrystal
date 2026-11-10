(() => {
    'use strict';
    const $ = id => document.getElementById(`abc-${id}`);
    const form = $('filters');
    if (!form) return;
    const fields = [...form.querySelectorAll('select[multiple]')];
    const pickers = new Map();
    const controllers = new Map();
    const expanded = new Set();
    const extraColumns = new Set();
    let applied = new URLSearchParams(location.search), data = null, zoom = 1, sequence = 0;
    const number = value => Number(value).toLocaleString('en-IN', {maximumFractionDigits: 2});
    const percent = value => value == null ? '—' : `${number(value)}%`;
    const money = value => `${(value / 10000000).toLocaleString('en-IN', {maximumFractionDigits: 2, minimumFractionDigits: 2})} Cr`;
    const columns = [['overall', 'Overall Contribution %'], ['sold_weight', 'Sold Weight (kg)'], ['net_turnover', 'Net Turnover'], ['mcprofit', 'MC Profit']];
    function element(tag, text, className) {
        const node = document.createElement(tag);
        if (text != null) node.textContent = text;
        if (className) node.className = className;
        return node;
    }
    function headers() {
        const token = localStorage.getItem('access_token');
        return {'X-Requested-With': 'XMLHttpRequest', ...(token ? {Authorization: `Bearer ${token}`} : {})};
    }
    async function request(segment, params) {
        controllers.get(segment)?.abort();
        const controller = new AbortController();
        controllers.set(segment, controller);
        const response = await fetch(`/api/sales-qty-abc-analysis/${segment}?${params}`, {headers: headers(), signal: controller.signal, cache: 'no-store'});
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.message || body.msg || `Unable to load report (${response.status}).`);
        return body;
    }
    function failure(target, error, retry) {
        target.replaceChildren(element('span', error.message));
        const button = element('button', 'Retry'); button.type = 'button';
        button.addEventListener('click', retry); target.append(button);
    }
    function picker(select) {
        const title = select.getAttribute('aria-label');
        const details = element('details', null, 'abc-multiselect');
        const summary = element('summary'); summary.setAttribute('aria-label', `${title} selections`);
        const panel = element('div', null, 'abc-picker');
        const search = element('input'); search.type = 'search'; search.placeholder = `Search ${title.toLowerCase()}…`; search.setAttribute('aria-label', `Search ${title}`);
        const clear = element('button', 'Clear selections'); clear.type = 'button';
        const list = element('div', null, 'abc-choices');
        panel.append(search, clear, list); details.append(summary, panel); select.after(details);
        function label() {
            const chosen = [...select.selectedOptions];
            summary.textContent = chosen.length ? (chosen.length === 1 ? chosen[0].text : `${chosen.length} selected`) : `All ${title.toLowerCase()}`;
            summary.title = chosen.map(o => o.text).join(', ');
        }
        function refresh() {
            label(); list.replaceChildren();
            const matches = [...select.options].filter(o => o.text.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase()));
            for (const option of matches) {
                const row = element('label'), checkbox = element('input'); checkbox.type = 'checkbox'; checkbox.checked = option.selected;
                checkbox.addEventListener('change', () => {option.selected = checkbox.checked; label();});
                row.append(checkbox, element('span', option.text)); list.append(row);
            }
            if (!matches.length) list.append(element('span', 'No matching options'));
        }
        search.addEventListener('input', refresh);
        search.addEventListener('keydown', event => {if (event.key === 'Enter') event.preventDefault();});
        clear.addEventListener('click', () => {[...select.options].forEach(o => {o.selected = false;}); refresh();});
        details.addEventListener('toggle', () => {if (details.open) {pickers.forEach(p => {if (p.details !== details) p.details.open = false;}); search.focus();}});
        details.addEventListener('keydown', event => {if (event.key === 'Escape') {details.open = false; summary.focus();}});
        pickers.set(select, {refresh, details, reset() {search.value = ''; details.open = false; refresh();}});
        refresh();
    }
    function restore(params) {
        form.elements.start.value = params.get('start') || form.dataset.start;
        form.elements.end.value = params.get('end') || form.dataset.end;
        for (const select of fields) {
            const values = params.getAll(select.name);
            for (const value of values) if (![...select.options].some(o => o.value === value)) select.add(new Option(value, value));
            [...select.options].forEach(o => {o.selected = values.includes(o.value);});
            pickers.get(select).reset();
        }
    }
    function setPaths(rows, path = []) {
        for (const row of rows) {row.path = [...path, row.id]; row.key = JSON.stringify(row.path); setPaths(row.children, row.path);}
    }
    function render() {
        const container = $('content'); container.replaceChildren();
        if (!data) return;
        const query = $('search').value.trim().toLocaleLowerCase();
        const matches = new Set();
        function mark(rows) {
            let found = false;
            for (const row of rows) {
                const childMatch = mark(row.children);
                if (row.label.toLocaleLowerCase().includes(query) || childMatch) {matches.add(row.key); found = true;}
            }
            return found;
        }
        if (query) mark(data.rows);
        if (!data.rows.length || (query && !matches.size)) {
            $('summary').textContent = `${data.rows.length} makes · 0 visible rows · A 80% / B 15% / C 5%`;
            container.append(element('p', data.rows.length ? 'No hierarchy matches your search.' : 'No transactions match these filters.', 'abc-footnote')); return;
        }
        const wrap = element('div', null, 'abc-table-wrap'); wrap.tabIndex = 0; wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', 'Sales quantity ABC table; scroll for more columns');
        const table = element('table'); table.style.setProperty('--abc-zoom', zoom);
        const caption = element('caption', 'Sales Quantity ABC Analysis — ranked within each parent'); caption.className = 'sr-only'; table.append(caption);
        const head = table.createTHead().insertRow();
        ['Hierarchy', 'Rank', 'Sold Qty', 'Contribution %', 'Cumulative %', 'Category', ...columns.filter(([key]) => extraColumns.has(key)).map(([, title]) => title)].forEach((title, index) => {
            const th = element('th', title, index === 0 ? 'abc-hierarchy' : ''); th.scope = 'col'; head.append(th);
        });
        const body = table.createTBody(); let count = 0;
        function extras(tr, row, total = false) {
            for (const [key] of columns) if (extraColumns.has(key)) {
                const cell = tr.insertCell();
                cell.textContent = key === 'overall' ? percent(total ? (row.sold_qty > 0 ? 100 : null) : row.overall) : key === 'sold_weight' ? number(row[key]) : money(row[key]);
                if (key === 'net_turnover' || key === 'mcprofit') cell.title = number(row[key]);
            }
        }
        function append(rows) {
            for (const row of rows) {
                if (query && !matches.has(row.key)) continue;
                count++;
                const tr = body.insertRow(), label = element('th', null, 'abc-hierarchy'); label.scope = 'row';
                const open = query ? row.children.some(c => matches.has(c.key)) : expanded.has(row.key);
                const name = element(row.children.length ? 'button' : 'div', null, 'abc-node');
                name.style.paddingLeft = `${row.depth * 16}px`;
                name.append(element('span', row.children.length ? (open ? '▾' : '▸') : '·'));
                const text = element('span', row.label); text.append(element('small', row.level, 'abc-level')); name.append(text);
                if (row.children.length) {
                    name.type = 'button'; name.setAttribute('aria-expanded', String(open)); name.setAttribute('aria-label', `${open ? 'Collapse' : 'Expand'} ${row.level}: ${row.label}`);
                    name.dataset.key = row.key;
                    // Search reveals matching paths; clearing it restores manual expansion.
                    name.disabled = Boolean(query);
                    name.addEventListener('click', () => {
                        const top = wrap.scrollTop, left = wrap.scrollLeft;
                        expanded.has(row.key) ? expanded.delete(row.key) : expanded.add(row.key);
                        render();
                        const next = container.querySelector('.abc-table-wrap'); next.scrollTop = top; next.scrollLeft = left;
                        [...container.querySelectorAll('button[data-key]')].find(b => b.dataset.key === row.key)?.focus({preventScroll: true});
                    });
                }
                label.append(name); tr.append(label);
                tr.insertCell().textContent = row.rank; tr.insertCell().textContent = number(row.sold_qty);
                const contribution = tr.insertCell(); contribution.append(element('span', percent(row.contribution)));
                if (row.contribution != null) {const track = element('div', null, 'abc-track'), fill = element('span'); fill.style.width = `${Math.min(100, Math.max(0, row.contribution))}%`; track.setAttribute('aria-hidden', 'true'); track.append(fill); contribution.append(track);}
                tr.insertCell().textContent = percent(row.cumulative);
                tr.insertCell().append(element('span', row.category, `abc-badge abc-${row.category.toLowerCase()}`));
                extras(tr, row);
                if (open) append(row.children);
            }
        }
        append(data.rows);
        const footer = table.createTFoot().insertRow(), title = element('th', 'Filtered total', 'abc-hierarchy'); title.scope = 'row'; footer.append(title);
        const totalPct = data.totals.sold_qty > 0 ? '100%' : '—';
        ['—', number(data.totals.sold_qty), totalPct, totalPct, '—'].forEach(value => {footer.insertCell().textContent = value;});
        extras(footer, data.totals, true);
        wrap.append(table); container.append(wrap);
        $('summary').textContent = `${data.rows.length} makes · ${count} visible rows · A 80% / B 15% / C 5%`;
    }
    async function loadOptions(params, run) {
        $('options-status').textContent = 'Loading filters…';
        try {
            const response = await request('options', params);
            if (run !== sequence) return;
            for (const select of fields) {
                // Preserve in-progress edits while option requests are running.
                const selected = [...select.selectedOptions].map(o => o.value);
                const options = response.data[select.name] || [], known = new Set(options.map(o => o.value));
                select.replaceChildren();
                for (const item of [...options, ...selected.filter(v => !known.has(v)).map(v => ({value: v, label: v}))]) select.add(new Option(item.label, item.value, false, selected.includes(item.value)));
                pickers.get(select).refresh();
            }
            $('options-status').textContent = '';
        } catch (error) {if (error.name !== 'AbortError' && run === sequence) failure($('options-status'), error, () => loadOptions(applied, sequence));}
    }
    async function loadHierarchy(params, run) {
        data = null; render(); $('status').textContent = 'Loading sales hierarchy…'; $('content').setAttribute('aria-busy', 'true'); $('fetched').textContent = '';
        try {
            const response = await request('hierarchy', params);
            if (run !== sequence) return;
            data = response.data; setPaths(data.rows); expanded.clear(); applyDepth();
            $('status').textContent = ''; $('fetched').textContent = `Fetched ${new Date(response.fetched_at).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'})} IST`;
        } catch (error) {if (error.name !== 'AbortError' && run === sequence) failure($('status'), error, () => loadHierarchy(applied, sequence));}
        finally {if (run === sequence) $('content').setAttribute('aria-busy', 'false');}
    }
    function load() {
        const run = ++sequence;
        $('period').textContent = `${applied.get('start') || form.dataset.start} to ${applied.get('end') || form.dataset.end} · Invoice barcode quantity`;
        loadOptions(new URLSearchParams(applied), run); loadHierarchy(new URLSearchParams(applied), run);
    }
    function applyDepth() {
        if (!data) return;
        expanded.clear();
        const depth = Number($('depth').value);
        function walk(rows) {for (const row of rows) {if (row.depth < depth) expanded.add(row.key); walk(row.children);}}
        walk(data.rows); render();
    }
    function sidebar(show) {$('sidebar').hidden = !show; $('filter-toggle').setAttribute('aria-expanded', String(show));}
    fields.forEach(picker); restore(applied);
    form.addEventListener('submit', event => {event.preventDefault(); applied = new URLSearchParams(new FormData(form)); history.replaceState(null, '', `${location.pathname}?${applied}`); if (matchMedia('(max-width: 900px)').matches) sidebar(false); load();});
    form.addEventListener('reset', event => {event.preventDefault(); applied = new URLSearchParams({start: form.dataset.start, end: form.dataset.end}); restore(applied); $('search').value = ''; $('depth').value = '0'; history.replaceState(null, '', location.pathname); load();});
    window.addEventListener('popstate', () => {applied = new URLSearchParams(location.search); restore(applied); load();});
    $('refresh').addEventListener('click', load);
    $('search').addEventListener('input', render);
    $('depth').addEventListener('change', applyDepth);
    $('collapse').addEventListener('click', () => {expanded.clear(); $('depth').value = '0'; $('search').value = ''; render();});
    document.querySelectorAll('[data-abc-column]').forEach(input => input.addEventListener('change', () => {input.checked ? extraColumns.add(input.dataset.abcColumn) : extraColumns.delete(input.dataset.abcColumn); render();}));
    function setZoom(value) {zoom = Math.max(.7, Math.min(1.4, Math.round(value * 10) / 10)); $('zoom-reset').textContent = `${Math.round(zoom * 100)}%`; $('zoom-out').disabled = zoom === .7; $('zoom-in').disabled = zoom === 1.4; render();}
    $('zoom-out').addEventListener('click', () => setZoom(zoom - .1)); $('zoom-in').addEventListener('click', () => setZoom(zoom + .1)); $('zoom-reset').addEventListener('click', () => setZoom(1));
    $('info-open').addEventListener('click', () => $('info').showModal()); $('info-close').addEventListener('click', () => $('info').close());
    $('filter-toggle').addEventListener('click', () => sidebar($('sidebar').hidden));
    document.addEventListener('keydown', event => {if (event.key === 'Escape' && matchMedia('(max-width: 900px)').matches) sidebar(false);});
    document.addEventListener('click', event => {pickers.forEach(p => {if (!p.details.contains(event.target)) p.details.open = false;}); if (matchMedia('(max-width: 900px)').matches && !$('sidebar').contains(event.target) && !$('filter-toggle').contains(event.target)) sidebar(false);});
    sidebar(!matchMedia('(max-width: 900px)').matches);
    load();
})();
