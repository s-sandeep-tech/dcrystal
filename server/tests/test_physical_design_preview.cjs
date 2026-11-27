const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/physical_stock_design_preview.js'), 'utf8');

function harness(fetch) {
    const elements = {}, events = {}, windowEvents = {};
    for (const name of ['', 'Title', 'Image', 'Status', 'Loader']) {
        elements[`physical-designPreview${name}`] = {
            hidden: true, style: {}, offsetWidth: 220, offsetHeight: 280,
            removeAttribute(name) { delete this[name]; }
        };
    }
    const context = vm.createContext({
        document: { getElementById: id => elements[id], addEventListener: (name, fn) => events[name] = fn },
        window: { innerWidth: 800, innerHeight: 600, addEventListener: (name, fn) => windowEvents[name] = fn },
        fetch, AbortController, URL, URLSearchParams, localStorage: { getItem: () => 'token' }
    });
    vm.runInContext(source, context);
    context.physicalSetupDesignPreviews();
    function icon(uid = 'uid-A') {
        const button = {
            dataset: { designPreview: 'DESIGN-A', designUid: uid }, isConnected: true,
            getBoundingClientRect: () => ({ left: 750, right: 770, top: 500 }),
            closest: () => button,
            contains: target => target === button
        };
        return button;
    }
    return { elements, events, windowEvents, icon, show: context.physicalShowDesignPreview, hide: context.physicalHideDesignPreview };
}

test('preview fetches by UID, loads image and stays within viewport', async () => {
    let requested;
    const h = harness(async url => {
        requested = url;
        return { ok: true, json: async () => ({ image_url: 'https://images.example/A.jpg' }) };
    });
    await h.show(h.icon('uid A&B'));
    assert.match(requested, /design_uid=uid\+A%26B/);
    assert.equal(h.elements['physical-designPreview'].hidden, false);
    assert.equal(h.elements['physical-designPreviewLoader'].hidden, false);
    const image = h.elements['physical-designPreviewImage'];
    image.onload();
    assert.equal(image.hidden, false);
    assert.equal(h.elements['physical-designPreviewLoader'].hidden, true);
    assert.equal(h.elements['physical-designPreview'].style.left, '522px');
    assert.equal(h.elements['physical-designPreview'].style.top, '312px');
});

test('mouse-out cancels a pending request and stale responses cannot reopen the preview', async () => {
    let finish, signal;
    const h = harness((url, options) => {
        signal = options.signal;
        return new Promise(resolve => finish = resolve);
    });
    const icon = h.icon();
    const pending = h.show(icon);
    h.events.pointerout({ target: icon, relatedTarget: null });
    assert.equal(signal.aborted, true);
    finish({ ok: true, json: async () => ({ image_url: 'https://images.example/A.jpg' }) });
    await pending;
    assert.equal(h.elements['physical-designPreview'].hidden, true);
    assert.equal(h.elements['physical-designPreviewImage'].src, undefined);
});

test('moving inside the icon does not dismiss the preview; focus-out and scroll do', async () => {
    const h = harness(async () => ({ ok: true, json: async () => ({ image_url: null }) }));
    const icon = h.icon();
    await h.show(icon);
    h.events.pointerout({ target: icon, relatedTarget: icon });
    assert.equal(h.elements['physical-designPreview'].hidden, false);
    h.events.focusout({ target: icon });
    assert.equal(h.elements['physical-designPreview'].hidden, true);
    await h.show(icon);
    h.events.scroll();
    assert.equal(h.elements['physical-designPreview'].hidden, true);
});

test('missing and failed images show status text', async () => {
    const h = harness(async () => ({ ok: true, json: async () => ({ image_url: null }) }));
    await h.show(h.icon());
    assert.equal(h.elements['physical-designPreviewStatus'].textContent, 'No image available.');
    const failed = harness(async () => ({ ok: false }));
    await failed.show(failed.icon());
    assert.equal(failed.elements['physical-designPreviewStatus'].textContent, 'Unable to load image.');
    assert.equal(failed.elements['physical-designPreviewLoader'].hidden, true);
});
