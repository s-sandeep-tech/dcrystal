let physicalDesignPreviewAnchor = null;
let physicalDesignPreviewController = null;
let physicalDesignPreviewRequest = 0;

function physicalHideDesignPreview() {
    physicalDesignPreviewRequest++;
    physicalDesignPreviewController?.abort();
    physicalDesignPreviewAnchor = null;
    const preview = document.getElementById('physical-designPreview');
    if (preview) preview.hidden = true;
    const image = document.getElementById('physical-designPreviewImage');
    if (image) {
        image.onload = image.onerror = null;
        image.removeAttribute('src');
        image.hidden = true;
    }
}

function physicalPositionDesignPreview() {
    if (!physicalDesignPreviewAnchor?.isConnected) {
        physicalHideDesignPreview();
        return;
    }
    const preview = document.getElementById('physical-designPreview');
    const rect = physicalDesignPreviewAnchor.getBoundingClientRect();
    const width = preview.offsetWidth;
    const height = preview.offsetHeight;
    let left = rect.right + 8;
    if (left + width > window.innerWidth - 8) left = rect.left - width - 8;
    preview.style.left = `${Math.max(8, Math.min(left, window.innerWidth - width - 8))}px`;
    preview.style.top = `${Math.max(8, Math.min(rect.top, window.innerHeight - height - 8))}px`;
}

async function physicalShowDesignPreview(anchor) {
    if (physicalDesignPreviewAnchor === anchor) return;
    physicalHideDesignPreview();
    physicalDesignPreviewAnchor = anchor;
    const requestId = physicalDesignPreviewRequest;
    physicalDesignPreviewController = new AbortController();
    const preview = document.getElementById('physical-designPreview');
    const image = document.getElementById('physical-designPreviewImage');
    const status = document.getElementById('physical-designPreviewStatus');
    const loader = document.getElementById('physical-designPreviewLoader');
    const designNo = anchor.dataset.designPreview;
    document.getElementById('physical-designPreviewTitle').textContent = `Design ${designNo}`;
    status.textContent = 'Loading image…';
    status.hidden = false;
    loader.hidden = false;
    preview.hidden = false;
    physicalPositionDesignPreview();

    function showMessage(message) {
        if (requestId !== physicalDesignPreviewRequest) return;
        loader.hidden = true;
        image.hidden = true;
        status.hidden = false;
        status.textContent = message;
        physicalPositionDesignPreview();
    }

    try {
        const params = new URLSearchParams({ design_uid: anchor.dataset.designUid });
        const response = await fetch(`/api/location-physical-stock-status/design-image?${params}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
            signal: physicalDesignPreviewController.signal
        });
        if (!response.ok) throw new Error('Preview unavailable');
        const data = await response.json();
        if (requestId !== physicalDesignPreviewRequest) return;
        if (!data.image_url) {
            showMessage('No image available.');
            return;
        }
        const url = new URL(data.image_url);
        if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Invalid image URL');
        image.alt = `Design ${designNo}`;
        image.onload = () => {
            if (requestId !== physicalDesignPreviewRequest) return;
            image.hidden = false;
            status.hidden = loader.hidden = true;
            physicalPositionDesignPreview();
        };
        image.onerror = () => showMessage('Unable to load image.');
        image.src = url.href;
    } catch (error) {
        if (error.name !== 'AbortError') showMessage('Unable to load image.');
    }
}

function physicalSetupDesignPreviews() {
    document.addEventListener('pointerover', event => {
        const icon = event.target.closest('[data-design-preview]');
        if (icon && !icon.contains(event.relatedTarget)) physicalShowDesignPreview(icon);
    });
    document.addEventListener('pointerout', event => {
        const icon = event.target.closest('[data-design-preview]');
        if (icon && !icon.contains(event.relatedTarget)) physicalHideDesignPreview();
    });
    document.addEventListener('focusin', event => {
        const icon = event.target.closest('[data-design-preview]');
        if (icon) physicalShowDesignPreview(icon);
    });
    document.addEventListener('focusout', event => {
        if (event.target.closest('[data-design-preview]')) physicalHideDesignPreview();
    });
    document.addEventListener('scroll', physicalHideDesignPreview, true);
    window.addEventListener('resize', physicalHideDesignPreview);
}

