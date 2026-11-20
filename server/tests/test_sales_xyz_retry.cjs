// Run with: node --test server/tests/test_sales_xyz_retry.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, '../app/static/js/sales_xyz_drilldown.js'), 'utf8');
// Isolate the actual request helpers so the clock and network are deterministic.
const helpers = source.slice(source.indexOf('    function retryDelay('), source.indexOf('    function nodes('));
const settle = () => new Promise(resolve => setImmediate(resolve));

function setup(outcomes, refreshRun = false) {
    const timers = new Map();
    const requests = [];
    const messages = [];
    let timerId = 0;
    const context = {
        URL, AbortController, refreshRun,
        report: {dataset: {api: '/api/sales-xyz-drilldown/hierarchy'}},
        location: {origin: 'https://example.test'},
        localStorage: {getItem: () => 'test-token'},
        setTimeout(fn, ms) { assert.equal(ms, 1000); timers.set(++timerId, fn); return timerId; },
        clearTimeout(id) { timers.delete(id); },
        async fetch(url, options) {
            requests.push({url: url.toString(), options});
            const outcome = outcomes.shift();
            if (outcome instanceof Error) throw outcome;
            assert.ok(outcome, 'Unexpected extra request');
            return {ok: outcome === 200, status: outcome,
                json: async () => ({data: {rows: []}, message: 'Unavailable'})};
        }
    };
    vm.runInNewContext(helpers + '\nthis.fetchData = fetchData;', context);
    const controller = new AbortController();
    return {
        requests, messages, timers, controller,
        run: (endpoint = 'hierarchy') => context.fetchData(endpoint,
            new URLSearchParams('start=2026-04-01&branch_type=SHOP&branch_type=FRANCHISE_SHOP'),
            controller.signal, message => messages.push(message)),
        async tick() {
            assert.equal(timers.size, 1);
            const [id, fn] = timers.entries().next().value;
            timers.delete(id); fn(); await settle();
        }
    };
}

test('503 recovers after a three-second countdown and preserves request settings', async () => {
    const app = setup([503, 200], true);
    const result = app.run(); await settle();
    assert.deepEqual(app.messages, ['Loading sales data… Next attempt in 3s (1/5).']);
    await app.tick();
    assert.equal(app.messages.at(-1), 'Loading sales data… Next attempt in 2s (1/5).');
    await app.tick();
    assert.equal(app.messages.at(-1), 'Loading sales data… Next attempt in 1s (1/5).');
    assert.equal(app.requests.length, 1);
    await app.tick(); await result;
    assert.equal(app.requests.length, 2);
    assert.equal(app.requests[0].url, app.requests[1].url);
    const url = new URL(app.requests[1].url);
    assert.equal(url.searchParams.get('refresh'), '1');
    assert.deepEqual(url.searchParams.getAll('branch_type'), ['SHOP', 'FRANCHISE_SHOP']);
    assert.equal(app.requests[1].options.headers.Authorization, 'Bearer test-token');
    assert.equal(app.timers.size, 0);
});

test('stops after five retries and a manual restart gets a fresh budget', async () => {
    const app = setup([503, 503, 503, 503, 503, 503, 200]);
    const failed = assert.rejects(app.run(), /Unavailable/); await settle();
    for (let i = 0; i < 15; i++) await app.tick();
    await failed;
    assert.equal(app.requests.length, 6);
    assert.equal(app.messages.filter(message => message.includes('Next attempt in 3s')).length, 5);
    assert.equal(app.timers.size, 0);
    await app.run();
    assert.equal(app.requests.length, 7);
});

test('network failure retries also apply to options', async () => {
    const app = setup([new TypeError('Failed to fetch'), 200]);
    const result = app.run('options'); await settle();
    for (let i = 0; i < 3; i++) await app.tick();
    await result;
    assert.equal(app.requests.length, 2);
    assert.equal(new URL(app.requests[1].url).pathname, '/api/sales-xyz-drilldown/options');
});

test('validation and authorization failures do not retry', async () => {
    for (const status of [400, 401, 403, 422]) {
        const app = setup([status]);
        await assert.rejects(app.run(), /Unavailable/);
        assert.equal(app.requests.length, 1);
        assert.equal(app.timers.size, 0);
    }
});

test('aborting a countdown clears its timer and prevents stale requests or updates', async () => {
    const app = setup([503]);
    const aborted = assert.rejects(app.run(), {name: 'AbortError'}); await settle();
    app.controller.abort(); await aborted;
    assert.equal(app.timers.size, 0);
    assert.equal(app.requests.length, 1);
    assert.equal(app.messages.length, 1);
});
