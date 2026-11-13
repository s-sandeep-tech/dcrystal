(() => {
    'use strict';

    const report = document.getElementById('xyz-report');
    const form = document.getElementById('xyz-filters');
    const status = document.getElementById('xyz-status');
    const tbody = document.getElementById('xyz-rows');
    const tableWrap = tbody.closest('.xyz-table-wrap');
    const tfoot = document.getElementById('xyz-totals');
    const sidebar = document.getElementById('xyz-sidebar');
    const filterToggle = document.getElementById('xyz-filter-toggle');
    const filters = [...form.querySelectorAll('[data-field]')];
    const number = new Intl.NumberFormat('en-IN', {maximumFractionDigits: 3});
    const currency = new Intl.NumberFormat('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    const percent = new Intl.NumberFormat('en-IN', {style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2});
    const metricKeys = ['pieces', 'weight', 'turnover', 'profit'];
    const categoryKeys = ['pieces', 'weight', 'turnover', 'tsk'];
    const rowsByButton = new WeakMap();

    let applied = new URLSearchParams(location.search);
    const hierarchyMenu = report.querySelector('.xyz-hierarchy-menu');
    const hierarchyButtons = [...hierarchyMenu.querySelectorAll('[data-hierarchy]')];
    let hierarchy = hierarchyButtons.find(button => button.dataset.hierarchy === applied.get('hierarchy'))
        ?? hierarchyButtons[0];
    let controller;
    let roots = [];
    let rootTotals;

    function element(tag, text, className) {
        const node = document.createElement(tag);
        if (text != null) node.textContent = text;
        if (className) node.className = className;
        return node;
    }

    function showLoading(target, message) {
        const spinner = element('span', null, 'xyz-loading-spinner');
        spinner.setAttribute('aria-hidden', 'true');
        target.replaceChildren(spinner, document.createTextNode(message));
    }

    async function fetchData(endpoint, params, signal) {
        const url = new URL(report.dataset.api, location.origin);
        if (endpoint === 'options') url.pathname = url.pathname.replace(/hierarchy$/, 'options');
        url.search = params.toString();
        const token = localStorage.getItem('access_token');
        const headers = token ? {Authorization: `Bearer ${token}`} : {};
        const response = await fetch(url, {headers, signal, cache: 'no-store'});
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.message || 'Could not load the report.');
        return payload.data;
    }

    function nodes(data, parent = []) {
        return data.rows.map(row => ({
            ...row, parent, level: data.level, leaf: data.leaf,
            open: false, children: null, loading: false, error: null,
        }));
    }

    function appendMetrics(tr, row, isTotal = false) {
        for (const key of metricKeys) {
            const cell = tr.insertCell();
            const value = Number(row[key]);
            if (key === 'turnover' || key === 'profit') {
                cell.textContent = currency.format(value / 10000000);
                cell.title = number.format(value);
            } else {
                cell.textContent = number.format(value);
            }
            const share = isTotal ? (value > 0 ? 100 : null) : row.contributions[key];
            if (share != null) {
                cell.append(element('small', percent.format(Number(share) / 100), 'xyz-contribution'));
            }
        }
    }

    async function toggleNode(row) {
        row.open = !row.open;
        if (!row.open || row.children || row.loading) {
            render(row);
            return;
        }

        row.loading = true;
        row.error = null;
        render(row);
        const path = [...row.parent, row.id];
        const params = new URLSearchParams(applied);
        params.set('parent', JSON.stringify(path));
        const {signal} = controller;
        try {
            const data = await fetchData('hierarchy', params, signal);
            if (!signal.aborted) row.children = nodes(data, path);
        } catch (error) {
            if (!signal.aborted) row.error = error.message;
        } finally {
            if (!signal.aborted) {
                row.loading = false;
                render();
            }
        }
    }

    function render(focusRow) {
        const wrap = tbody.closest('.xyz-table-wrap');
        const scroll = [wrap.scrollLeft, wrap.scrollTop];
        const rows = document.createDocumentFragment();
        const focusedRow = rowsByButton.get(document.activeElement) || focusRow;
        let focusTarget;
        function append(children) {
            for (const row of children) {
                const tr = element('tr');
                tr.dataset.depth = row.parent.length;
                tr.classList.toggle('xyz-open', row.open);
                const heading = element('th');
                heading.scope = 'row';
                heading.style.paddingInlineStart = `${12 + row.parent.length * 16}px`;
                if (row.leaf) {
                    heading.textContent = '—';
                } else {
                    const button = element('button', null, 'xyz-expand');
                    button.type = 'button';
                    button.setAttribute('aria-expanded', String(row.open));
                    const arrow = element('span', row.open ? '▾' : '▸');
                    arrow.setAttribute('aria-hidden', 'true');
                    const label = element('span', row.label);
                    label.append(element('small', row.level));
                    button.append(arrow, label);
                    button.addEventListener('click', () => toggleNode(row));
                    rowsByButton.set(button, row);
                    if (row === focusedRow) focusTarget = button;
                    heading.append(button);
                }
                tr.append(heading);
                tr.insertCell().textContent = row.leaf ? row.label : '—';
                appendMetrics(tr, row);
                for (const key of categoryKeys) {
                    const category = row.categories[key];
                    const cell = tr.insertCell();
                    if (category && category !== 'Unclassified') {
                        cell.append(element('span', category, `xyz-category xyz-${category.toLowerCase()}`));
                    }
                }
                rows.append(tr);
                if (!row.open) continue;
                if (row.children?.length) {
                    append(row.children);
                    continue;
                }
                const detail = element('tr', null, 'xyz-detail-status');
                const cell = detail.insertCell();
                cell.colSpan = 2 + metricKeys.length + categoryKeys.length;
                cell.setAttribute('role', 'status');
                cell.style.paddingInlineStart = `${28 + row.parent.length * 16}px`;
                if (row.loading) {
                    showLoading(cell, 'Loading…');
                } else if (row.error) {
                    cell.textContent = row.error;
                    const retry = element('button', 'Retry');
                    retry.type = 'button';
                    retry.addEventListener('click', () => { row.open = false; toggleNode(row); });
                    cell.append(retry);
                } else {
                    cell.textContent = 'No matching detail rows.';
                }
                rows.append(detail);
            }
        }
        append(roots);
        tbody.replaceChildren(rows);
        tfoot.replaceChildren();
        if (rootTotals) {
            const tr = tfoot.insertRow();
            const heading = element('th', 'Grand Total');
            heading.scope = 'row';
            tr.append(heading);
            tr.insertCell();
            appendMetrics(tr, rootTotals, true);
            tr.insertCell().colSpan = categoryKeys.length;
        }
        wrap.scrollTo(...scroll);
        if (focusTarget && document.activeElement === document.body) {
            focusTarget.focus({preventScroll: true});
        }
    }

    function replaceOptions(select, options, selected) {
        const values = new Set(options.map(option => option.value));
        const fullOptions = [...options, ...selected.filter(value => !values.has(value)).map(value => ({value, label: value}))];
        select.replaceChildren(...fullOptions.map(({value, label}) => new Option(label, value, false, selected.includes(value))));
        renderChoices(select);
        updateCount(select);
    }

    function renderChoices(select) {
        const choices = select.closest('details').querySelector('.xyz-filter-choices');
        choices.replaceChildren();
        for (const option of select.options) {
            const label = element('label');
            const checkbox = element('input');
            checkbox.type = 'checkbox';
            checkbox.checked = option.selected;
            checkbox.addEventListener('change', () => {
                option.selected = checkbox.checked;
                updateCount(select);
            });
            label.append(checkbox, document.createTextNode(option.text));
            choices.append(label);
        }
    }

    function updateCount(select) {
        const count = select.selectedOptions.length;
        select.closest('details').querySelector('summary span').textContent = count ? `${count} selected` : '';
    }

    async function loadOptions(panel) {
        const params = new URLSearchParams({start: form.elements.start.value, end: form.elements.end.value,
                                            field: panel.dataset.field, exclude_make_set: '1'});
        for (const value of new FormData(form).getAll('exclude_make')) params.append('exclude_make', value);
        const key = params.toString();
        if (panel.dataset.loaded === key || panel.dataset.loading === key) return;
        panel.dataset.loading = key;
        const select = panel.querySelector('select');
        const message = panel.querySelector('.xyz-filter-status');
        message.textContent = 'Loading…';
        const {signal} = controller;
        try {
            const options = await fetchData('options', params, signal);
            if (signal.aborted || panel.dataset.loading !== key) return;
            replaceOptions(select, options, [...select.selectedOptions].map(option => option.value));
            panel.dataset.loaded = key;
            message.textContent = options.length ? '' : 'No values in this date range.';
        } catch (error) {
            if (!signal.aborted && panel.dataset.loading === key) message.textContent = error.message;
        } finally {
            if (!signal.aborted && panel.dataset.loading === key) delete panel.dataset.loading;
        }
    }

    function restoreForm() {
        for (const key of ['start', 'end']) {
            const input = form.elements[key];
            input.value = applied.get(key) || input.defaultValue;
            applied.set(key, input.value);
        }
        const exclusions = applied.has('exclude_make_set') || applied.has('exclude_make')
            ? applied.getAll('exclude_make') : null;
        for (const input of form.querySelectorAll('[name="exclude_make"]')) {
            input.checked = exclusions ? exclusions.includes(input.value) : input.defaultChecked;
        }
        for (const panel of filters) {
            const select = panel.querySelector('select');
            replaceOptions(select, [], applied.getAll(select.name));
            delete panel.dataset.loaded;
        }
    }

    async function reload() {
        applied.set('hierarchy', hierarchy.dataset.hierarchy);
        controller?.abort();
        controller = new AbortController();
        const {signal} = controller;
        for (const panel of filters) {
            delete panel.dataset.loading;
            if (panel.open) loadOptions(panel);
        }
        history.replaceState(null, '', `${location.pathname}?${applied}`);
        document.getElementById('xyz-period').textContent = `${applied.get('start')} to ${applied.get('end')}`;
        showLoading(status, 'Loading hierarchy…');
        tableWrap.hidden = true;
        roots = [];
        rootTotals = null;
        render();
        try {
            const data = await fetchData('hierarchy', applied, signal);
            if (signal.aborted) return;
            roots = nodes(data);
            rootTotals = data.totals;
            status.textContent = roots.length ? '' : 'No sales match these filters.';
            render();
        } catch (error) {
            if (signal.aborted) return;
            const retry = element('button', 'Retry');
            retry.type = 'button';
            retry.addEventListener('click', reload);
            status.replaceChildren(document.createTextNode(error.message), retry);
        } finally {
            if (!signal.aborted) tableWrap.hidden = false;
        }
    }

    for (const panel of filters) {
        const select = panel.querySelector('select');
        panel.addEventListener('toggle', () => { if (panel.open) loadOptions(panel); });
        select.addEventListener('change', () => updateCount(select));
        panel.querySelector('[data-clear]').addEventListener('click', () => {
            for (const option of select.options) option.selected = false;
            renderChoices(select);
            updateCount(select);
        });
    }
    form.addEventListener('submit', event => {
        event.preventDefault();
        applied = new URLSearchParams(new FormData(form));
        reload();
    });
    form.addEventListener('reset', event => {
        event.preventDefault();
        applied = new URLSearchParams();
        restoreForm();
        reload();
    });
    document.getElementById('xyz-refresh').addEventListener('click', reload);
    function showSelectedHierarchy() {
        for (const button of hierarchyButtons) {
            button.setAttribute('aria-pressed', String(button === hierarchy));
        }
        document.getElementById('xyz-order-label').textContent = hierarchy.querySelector('strong').textContent;
        const selectedPath = hierarchy.querySelector('span').textContent;
        const selectedHierarchy = document.getElementById('xyz-selected-hierarchy');
        selectedHierarchy.textContent = selectedPath;
        selectedHierarchy.title = selectedPath;
        document.getElementById('xyz-info-hierarchy').textContent = selectedPath;
    }
    for (const button of hierarchyButtons) {
        button.addEventListener('click', () => {
            hierarchyMenu.open = false;
            hierarchyMenu.querySelector('summary').focus();
            if (hierarchy === button) return;
            hierarchy = button;
            showSelectedHierarchy();
            reload();
        });
    }
    const infoDialog = document.getElementById('xyz-info-dialog');
    document.getElementById('xyz-info-open').addEventListener('click', () => infoDialog.showModal());
    document.getElementById('xyz-info-close').addEventListener('click', () => infoDialog.close());
    document.getElementById('xyz-collapse').addEventListener('click', () => {
        function collapse(rows) {
            for (const row of rows) {
                row.open = false;
                if (row.children) collapse(row.children);
            }
        }
        collapse(roots);
        render();
    });
    function setSidebar(open) {
        sidebar.hidden = !open;
        filterToggle.setAttribute('aria-expanded', String(open));
    }
    filterToggle.addEventListener('click', () => setSidebar(sidebar.hidden));
    setSidebar(!matchMedia('(max-width: 700px)').matches);
    restoreForm();
    showSelectedHierarchy();
    reload();
})();
