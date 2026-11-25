const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Exercise the actual browser request helper without requiring a browser/server.
const source = fs.readFileSync(path.join(__dirname, '../app/static/js/nip_stock_trend.js'), 'utf8');
const helpers = source.slice(source.indexOf('    function waitForRetry('), source.indexOf('    function setStatus('));
function harness(fetch, timers = {}) {
    const delays = [];
    const request = vm.runInNewContext(helpers + '\nfetchWithRetry;', {
        fetch, DOMException,
        setTimeout: (fn, delay) => { delays.push(delay); return setTimeout(fn, 0); },
        clearTimeout,
        ...timers,
    });
    return { request, delays };
}

test('transient source failures recover within five attempts with backoff', async () => {
    let calls = 0;
    const status = [];
    const success = { status: 200, ok: true };
    const { request, delays } = harness(async () => ++calls < 5 ? { status: 503 } : success);
    assert.equal(await request('/api/data', {}, message => status.push(message)), success);
    assert.equal(calls, 5);
    assert.deepEqual(delays, [1000, 2000, 4000, 8000]);
    assert.equal(status.length, 4);
    assert.match(status.at(-1), /5\/5/);
});

test('persistent server errors stop after five total attempts', async () => {
    let calls = 0;
    const { request } = harness(async () => { calls++; return { status: 503 }; });
    assert.equal((await request('/api/options')).status, 503);
    assert.equal(calls, 5);
});

test('network failures retry and return the first successful response', async () => {
    let calls = 0;
    const { request } = harness(async () => {
        if (++calls < 3) throw new TypeError('Failed to fetch');
        return { status: 200 };
    });
    assert.equal((await request('/api/data')).status, 200);
    assert.equal(calls, 3);
});

test('persistent network failures throw after five total attempts', async () => {
    let calls = 0;
    const { request } = harness(async () => { calls++; throw new TypeError('Failed to fetch'); });
    await assert.rejects(request('/api/data'), /Failed to fetch/);
    assert.equal(calls, 5);
});

test('authentication and validation errors never retry', async () => {
    for (const status of [400, 401, 403, 404]) {
        let calls = 0;
        const { request, delays } = harness(async () => { calls++; return { status }; });
        assert.equal((await request('/api/data')).status, status);
        assert.equal(calls, 1);
        assert.equal(delays.length, 0);
    }
});

test('changing filters aborts backoff and prevents further source requests', async () => {
    let calls = 0;
    let cancelled = false;
    const controller = new AbortController();
    const { request } = harness(async () => { calls++; return { status: 503 }; }, {
        setTimeout: () => { queueMicrotask(() => controller.abort()); return 42; },
        clearTimeout: id => { assert.equal(id, 42); cancelled = true; },
    });
    await assert.rejects(request('/api/data', { signal: controller.signal }), { name: 'AbortError' });
    assert.equal(calls, 1);
    assert.equal(cancelled, true);
});

test('an already cancelled request never calls the source', async () => {
    const controller = new AbortController();
    controller.abort();
    const { request } = harness(() => assert.fail('Cancelled request must not fetch'));
    await assert.rejects(request('/api/data', { signal: controller.signal }), { name: 'AbortError' });
});
