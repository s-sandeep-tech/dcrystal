const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/online_provision_stock_status.js'), 'utf8');

function harness(fetch) {
    const elements = {};
    for (const name of ['Modal', 'Title', 'Status', 'Retry', 'Placeholder', 'Loader', 'Viewport', 'ZoomControls', 'ZoomLabel', 'ZoomIn', 'ZoomOut', '']) {
        elements[`online-designImage${name}`] = {
            hidden: false, dataset: {}, style: {}, open: false, scrollLeft: 0, scrollTop: 0,
            listeners: {}, captures: new Set(),
            addEventListener(name, fn, options) { this.listeners[name] = fn; this.listenerOptions = options; },
            setPointerCapture(id) { this.captures.add(id); },
            hasPointerCapture(id) { return this.captures.has(id); },
            releasePointerCapture(id) { this.captures.delete(id); },
            getBoundingClientRect() {
                const viewport = elements['online-designImageViewport'];
                return { width: parseFloat(this.style.width) || 160, height: parseFloat(this.style.height) || 200,
                    left: -viewport.scrollLeft, top: -viewport.scrollTop };
            },
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
    context.onlineSetupDesignImageGestures();
    return { elements, open: context.onlineOpenDesignImageModal, reset: context.onlineResetDesignImageModal, zoom: context.onlineSetDesignImageZoom };
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
    assert.equal(h.elements['online-designImageZoomControls'].hidden, false);
    h.zoom(2);
    assert.equal(img.style.width, '320px');
    assert.equal(img.style.height, '400px');
    assert.equal(h.elements['online-designImageZoomLabel'].textContent, '200%');
    h.zoom(5);
    assert.equal(img.style.width, '640px');
    assert.equal(h.elements['online-designImageZoomIn'].disabled, true);
    h.elements['online-designImageViewport'].scrollLeft = 90;
    h.zoom(0);
    assert.equal(img.style.width, '160px');
    assert.equal(h.elements['online-designImageZoomOut'].disabled, true);
    assert.equal(h.elements['online-designImageViewport'].scrollLeft, 0);
    h.reset();
    assert.equal(img.style.width, '');
    assert.equal(h.elements['online-designImageZoomControls'].hidden, true);
});

test('wheel zoom anchors the image under the pointer and drag pans until released', async () => {
    const h = harness(async () => ({ ok: true, json: async () => ({ image_url: 'https://images.example/A.jpg' }) }));
    await h.open('A');
    h.elements['online-designImage'].onload();
    const viewport = h.elements['online-designImageViewport'];
    let prevented = 0;
    const wheel = { deltaY: -120, clientX: 80, clientY: 100, preventDefault() { prevented++; } };
    viewport.listeners.wheel(wheel);
    assert.equal(prevented, 1);
    assert.equal(h.elements['online-designImageZoomLabel'].textContent, '125%');
    assert.equal(viewport.scrollLeft, 20);
    assert.equal(viewport.scrollTop, 25);
    const pointer = { pointerId: 1, button: 0, isPrimary: true, clientX: 80, clientY: 100, preventDefault() {} };
    viewport.listeners.pointerdown(pointer);
    assert.equal(viewport.dataset.dragging, 'true');
    assert.equal(viewport.hasPointerCapture(1), true);
    viewport.listeners.pointermove({ ...pointer, clientX: 70, clientY: 85 });
    assert.equal(viewport.scrollLeft, 30);
    assert.equal(viewport.scrollTop, 40);
    viewport.listeners.pointerup(pointer);
    assert.equal(viewport.hasPointerCapture(1), false);
    assert.equal(viewport.dataset.dragging, undefined);
    viewport.listeners.pointermove({ ...pointer, clientX: 10 });
    assert.equal(viewport.scrollLeft, 30);
    viewport.listeners.wheel({ ...wheel, deltaY: 120 });
    assert.equal(h.elements['online-designImageZoomLabel'].textContent, '100%');
    assert.equal(viewport.scrollLeft, 0);
    viewport.listeners.pointerdown(pointer);
    assert.equal(viewport.hasPointerCapture(1), false);
});

test('closing while dragging releases capture and hides gesture viewport', async () => {
    const h = harness(async () => ({ ok: true, json: async () => ({ image_url: 'https://images.example/A.jpg' }) }));
    await h.open('A');
    h.elements['online-designImage'].onload();
    h.zoom(2);
    const viewport = h.elements['online-designImageViewport'];
    viewport.listeners.pointerdown({ pointerId: 2, button: 0, isPrimary: true, clientX: 0, clientY: 0, preventDefault() {} });
    h.reset();
    assert.equal(viewport.hasPointerCapture(2), false);
    assert.equal(viewport.dataset.dragging, undefined);
    assert.equal(viewport.hidden, true);
});

test('missing image has a clear empty state', async () => {
    const h = harness(async () => ({ ok: true, json: async () => ({ image_url: null }) }));
    await h.open('A');
    assert.equal(h.elements['online-designImageStatus'].textContent, 'No image available for this design.');
    assert.equal(h.elements['online-designImage'].hidden, true);
    assert.equal(h.elements['online-designImageRetry'].hidden, true);
    assert.equal(h.elements['online-designImagePlaceholder'].hidden, false);
    assert.equal(h.elements['online-designImageLoader'].hidden, true);
    assert.equal(h.elements['online-designImageZoomControls'].hidden, true);
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
