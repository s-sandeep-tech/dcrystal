// Run with: node --test server/tests/test_sales_tsk_monthly_browser.cjs
// Execute the complete browser script with a minimal DOM and controlled network.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const script = readFileSync(join(__dirname, '../app/static/js/sales_tsk_monthly_analyse.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));

function setup() {
    function node() {
        return {
            listeners: {}, children: [], value: '',
            classList: {toggle() {}, contains() { return false; }},
            addEventListener(name, fn) { this.listeners[name] = fn; },
            fire(name) { this.listeners[name]({preventDefault() {}}); },
            replaceChildren(...children) { this.children = children; },
            append(...children) { this.children.push(...children); },
            setAttribute() {}, querySelector() { return null; }, querySelectorAll() { return []; }
        };
    }
    const nodes = new Map();
    const get = id => { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); };
    const form = get('sales-filters');
    form.dataset = {defaultStart: '2026-04-01', defaultEnd: '2026-06-30'};
    form.elements = {start: node(), end: node()};
    const group = get('monthly-group');
    group.options = [{value: 'section', text: 'Section'}, {value: 'make', text: 'Make'}];
    const requests = [];
    vm.runInNewContext(script, {
        URLSearchParams, AbortController, Intl, console,
        FormData: class { *[Symbol.iterator]() {
            yield ['start', form.elements.start.value];
            yield ['end', form.elements.end.value];
            yield ['group_by', group.value];
        } },
        location: {search: '', pathname: '/sales-tsk-monthly-analyse'},
        history: {replaceState() {}}, localStorage: {getItem() { return null; }},
        matchMedia: () => ({matches: false}),
        document: {getElementById: get, createElement: node, createTextNode: text => text,
            addEventListener() {}, querySelector() { return null; }},
        fetch(url, {signal}) {
            return new Promise(resolve => requests.push({url, signal,
                finish(ok = true) { resolve({ok, json: async () => ok ? {data: {}} : {message: 'Failed'}}); }
            }));
        }
    });
    return {get, form, group, requests, options: () => requests.filter(r => r.url.includes('/options?'))};
}

test('group changes reuse both pending and completed dropdown requests', async () => {
    const app = setup();
    assert.equal(app.options().length, 1);
    app.group.value = 'make'; app.group.fire('change');
    assert.equal(app.options().length, 1);
    assert.equal(app.requests.filter(r => r.url.includes('/matrix?')).length, 2);
    assert.equal(app.options()[0].signal.aborted, false);
    app.options()[0].finish(); await settle();
    app.group.value = 'section'; app.group.fire('change');
    app.form.fire('submit');
    assert.equal(app.options().length, 1);
});

test('changed dates replace options and stale responses cannot invalidate the new cache', async () => {
    const app = setup();
    const old = app.options()[0];
    app.form.elements.start.value = '2026-05-01'; app.form.fire('submit');
    assert.equal(app.options().length, 2);
    assert.equal(old.signal.aborted, true);
    assert.match(app.options()[1].url, /start=2026-05-01/);
    app.options()[1].finish(); await settle();
    old.finish(); await settle();
    app.form.fire('submit');
    assert.equal(app.options().length, 2);
});

test('explicit refresh reloads dropdowns even with unchanged dates', async () => {
    const app = setup();
    app.options()[0].finish(); await settle();
    app.get('sales-refresh').fire('click');
    assert.equal(app.options().length, 2);
    assert.equal(app.options()[0].url, app.options()[1].url);
});

test('failed dropdown request can be retried', async () => {
    const app = setup();
    app.options()[0].finish(false); await settle();
    const status = app.get('sales-options-status');
    status.children[1].fire('click');
    assert.equal(app.options().length, 2);
    app.options()[1].finish(); await settle();
    assert.equal(status.children.length, 0);
});
