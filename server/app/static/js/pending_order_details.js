let currentZoom = parseFloat(localStorage.getItem('pendingdetails-zoom')) || 1.0;

document.addEventListener('DOMContentLoaded', () => {
    adjustZoom(0);
});

function adjustZoom(delta, reset = false) {
    const tableArea = document.getElementById('table-area');
    if (!tableArea) return;

    if (reset) {
        currentZoom = 1.0;
    } else {
        currentZoom = Math.min(Math.max(currentZoom + delta, 0.7), 1.5);
    }

    tableArea.style.zoom = currentZoom;
    localStorage.setItem('pendingdetails-zoom', currentZoom);

    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

function getFilterValues() {
    return {
        division: document.getElementById('filter-division')?.value || '',
        group: document.getElementById('filter-group')?.value || '',
        purity: document.getElementById('filter-purity')?.value || '',
        supplier: document.getElementById('filter-supplier')?.value || '',
        classification_owner: document.getElementById('filter-classification-owner')?.value || '',
        collection_owner: document.getElementById('filter-collection-owner')?.value || '',
        make_owner: document.getElementById('filter-make-owner')?.value || '',
        classification: document.getElementById('filter-classification')?.value || '',
        make: document.getElementById('filter-make')?.value || '',
        order_type: document.getElementById('filter-order-type')?.value || '',
        order_ro: document.getElementById('filter-order-ro')?.value || '',
        order_request_type: document.getElementById('filter-order-request-type')?.value || '',
        provision_type: document.getElementById('filter-provision-type')?.value || '',
        branch_provision_type: document.getElementById('filter-branch-provision-type')?.value || '',
        branch_type: document.getElementById('filter-branch-type')?.value || '',
        search: document.getElementById('hierarchy-search')?.value || ''
    };
}

function applyFilters() {
    const params = new URLSearchParams(getFilterValues());
    window.location.search = params.toString();
}

function resetGlobalFilters() {
    window.location.search = '';
}

function changePerPage(val) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('per_page', val);
    urlParams.set('page', 1);
    window.location.search = urlParams.toString();
}

function changePage(page) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', page);
    window.location.search = urlParams.toString();
}

function onSearchInput(val) {
    const filter = val.toLowerCase();
    const rows = document.querySelectorAll('#table-area table tbody tr.parent-row');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        if (text.includes(filter)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Tree / Row Toggling
async function toggleRow(btn, level, value, grandparentValue) {
    const row = btn.closest('tr');
    const isExpanded = btn.querySelector('span').textContent === 'remove_circle';

    if (isExpanded) {
        // Collapse all children
        btn.querySelector('span').textContent = 'add_circle';
        let next = row.nextElementSibling;
        while (next && !next.classList.contains('parent-row')) {
            next.remove();
            next = row.nextElementSibling;
        }
        return;
    }

    // Expand
    btn.querySelector('span').textContent = 'remove_circle';
    const params = new URLSearchParams(getFilterValues());
    params.set('parent_level', level);
    params.set('parent_value', value);
    if (grandparentValue) {
        params.set('grandparent_value', grandparentValue);
    }

    try {
        const response = await fetch(`/partial/pendingorderdetails?${params.toString()}`);
        if (!response.ok) throw new Error('Failed to load child rows');
        
        const html = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const childRows = doc.querySelectorAll('tr');

        // Insert after current row
        let insertRef = row;
        childRows.forEach(child => {
            insertRef.after(child);
            insertRef = child;
        });
    } catch (e) {
        console.error(e);
        alert('Error loading child rows');
    }
}

// Leaf Modal Handler
async function openLeafModal(classificationOwner, makeOwner, collectionOwner) {
    const modal = document.getElementById('leaf-detail-modal');
    const overlay = document.getElementById('modal-overlay');
    const content = document.getElementById('leaf-detail-content');

    if (!modal || !overlay || !content) return;

    modal.classList.remove('hidden');
    overlay.classList.remove('hidden');
    content.innerHTML = `<div class="p-8 text-center text-gray-500 flex flex-col items-center justify-center h-full">
        <span class="animate-spin material-symbols-outlined text-4xl text-primary mb-2">sync</span>
        Loading details...
    </div>`;

    const params = new URLSearchParams(getFilterValues());
    params.set('parent_classification_owner', classificationOwner);
    params.set('parent_make_owner', makeOwner);
    params.set('parent_collection_owner', collectionOwner);

    try {
        const response = await fetch(`/partial/pendingorderdetails/leaf_detail?${params.toString()}`);
        if (!response.ok) throw new Error('Failed to fetch details');
        content.innerHTML = await response.text();
    } catch (e) {
        console.error(e);
        content.innerHTML = `<div class="p-8 text-center text-red-500">Error loading details.</div>`;
    }
}

function closeLeafModal() {
    const modal = document.getElementById('leaf-detail-modal');
    const overlay = document.getElementById('modal-overlay');
    if (modal) modal.classList.add('hidden');
    if (overlay) overlay.classList.add('hidden');
}
