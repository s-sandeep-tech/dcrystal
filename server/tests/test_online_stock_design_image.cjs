const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/online_provision_stock_status.js'), 'utf8');

function harness(fetch) {
    const elements = {};
    for (const name of ['Modal', 'Title', 'Status', 'Retry', 'Placeholder', 'Loader', '']) {
        elements[`online-designImage${name}`] = {
            hidden: false, dataset: {}, open: false,
            showModal() { this.open = true; },
            removeAttribute(name) { delete this[name]; }
        };
    }
    const context = vm.createContext({
        document: { getElementById: id => elements[id] },
        fetch, AbortController, URL, URLSearchParams,
        localStorage: { getItem: () => 'test-token' }
    });
    vm.runInContext(source.slice(0, source.indexOf('function onlineToggleStockFilters')), context);
    return { elements, open: context.onlineOpenDesignImageModal, reset: context.onlineResetDesignImageModal };
}

test('single image uses encoded design number and waits for image load', async () => {
    let request;
    const h = harness(async (url, options) => {
        request = { url, options };
        return { ok: true, json: async () => ({ image_url: 'https://images.example/design.jpg' }) };
    });
    await h.open('A&B/1');
    assert.match(request.url, /design_no=A%26B%2F1/);
    assert.equal(request.options.headers.Authorization, 'Bearer test-token');
    const img = h.elements['online-designImage'];
    assert.equal(img.src, 'https://images.example/design.jpg');
    assert.equal(img.hidden, true);
    assert.equal(h.elements['online-designImageLoader'].hidden, false);
    img.onload();
    assert.equal(img.hidden, false);
    assert.equal(h.elements['online-designImageLoader'].hidden, true);
    assert.equal(h.elements['online-designImagePlaceholder'].hidden, true);
    assert.equal(h.elements['online-designImageStatus'].hidden, true);
    assert.equal(h.elements['online-designImageTitle'].textContent, 'Design A&B/1');
});

test('missing image has a clear empty state', async () => {
    const h = harness(async () => ({ ok: true, json: async () => ({ image_url: null }) }));
    await h.open('A');
    assert.equal(h.elements['online-designImageStatus'].textContent, 'No image available for this design.');
    assert.equal(h.elements['online-designImage'].hidden, true);
    assert.equal(h.elements['online-designImageRetry'].hidden, true);
    assert.equal(h.elements['online-designImagePlaceholder'].hidden, false);
    assert.equal(h.elements['online-designImageLoader'].hidden, true);
});

test('database and broken-image failures expose retry', async () => {
    const h = harness(async () => ({ ok: false }));
    await h.open('A');
    assert.equal(h.elements['online-designImageRetry'].hidden, false);
    assert.equal(h.elements['online-designImageLoader'].hidden, true);
    assert.equal(h.elements['online-designImagePlaceholder'].hidden, false);
    const imageHarness = harness(async () => ({ ok: true, json: async () => ({ image_url: 'https://images.example/broken.jpg' }) }));
    await imageHarness.open('A');
    imageHarness.elements['online-designImage'].onerror();
    assert.equal(imageHarness.elements['online-designImageRetry'].hidden, false);
    assert.equal(imageHarness.elements['online-designImage'].hidden, true);
    assert.equal(imageHarness.elements['online-designImageLoader'].hidden, true);
    assert.equal(imageHarness.elements['online-designImagePlaceholder'].hidden, false);
});

test('closing aborts lookup and prevents stale response from populating reopened modal', async () => {
    const requests = [];
    const h = harness((url, options) => new Promise(resolve => requests.push({ resolve, options })));
    const first = h.open('A');
    h.reset();
    assert.equal(requests[0].options.signal.aborted, true);
    const second = h.open('B');
    requests[1].resolve({ ok: true, json: async () => ({ image_url: 'https://images.example/B.jpg' }) });
    await second;
    requests[0].resolve({ ok: true, json: async () => ({ image_url: 'https://images.example/A.jpg' }) });
    await first;
    assert.equal(h.elements['online-designImage'].src, 'https://images.example/B.jpg');
});
