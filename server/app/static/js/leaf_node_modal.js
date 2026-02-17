async function openLeafModal(classOwner, makeOwner, collOwner) {
    const modal = document.getElementById('leaf-detail-modal');
    const content = document.getElementById('leaf-detail-content');
    const overlay = document.getElementById('modal-overlay');

    if (!modal || !content || !overlay) return;

    // Show modal and loading state
    overlay.classList.remove('hidden');
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden'; // Prevent background scroll

    content.innerHTML = `
        <div class="flex flex-col items-center justify-center p-20 animate-pulse">
            <span class="material-symbols-outlined text-5xl text-primary/30">analytics</span>
            <p class="mt-4 text-gray-500 font-medium">Crunching hierarchical data...</p>
        </div>
    `;

    try {
        const params = new URLSearchParams({
            classification_owner: classOwner,
            make_owner: makeOwner,
            collection_owner: collOwner
        });

        const response = await fetch(`/partial/leaf_detail?${params.toString()}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });

        if (!response.ok) throw new Error("Failed to load details");

        const html = await response.text();
        content.innerHTML = html;

    } catch (e) {
        console.error(e);
        content.innerHTML = `
            <div class="p-20 text-center">
                <span class="material-symbols-outlined text-5xl text-red-300">error</span>
                <p class="mt-4 text-red-500 font-bold">Failed to load detailed analysis.</p>
                <button onclick="closeLeafModal()" class="mt-4 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors">Close</button>
            </div>
        `;
    }
}

function closeLeafModal() {
    const modal = document.getElementById('leaf-detail-modal');
    const overlay = document.getElementById('modal-overlay');
    if (modal) modal.classList.add('hidden');
    if (overlay) overlay.classList.add('hidden');
    document.body.style.overflow = ''; // Restore scroll
}

function toggleModalRow(btn) {
    const row = btn.closest('tr');
    const rowId = row.dataset.id;
    const icon = btn.querySelector('.toggle-icon');
    const isExpanded = icon.textContent === 'remove_circle';

    const table = row.closest('table');
    const allRows = Array.from(table.querySelectorAll('tr.modal-row'));

    if (isExpanded) {
        // Collapse: Hide all descendants (rows whose parent-id starts with current rowId)
        allRows.forEach(r => {
            if (r.dataset.parentId && r.dataset.parentId.startsWith(rowId)) {
                r.classList.add('hidden');
                const childIcon = r.querySelector('.toggle-icon');
                if (childIcon) childIcon.textContent = 'add_circle';
            }
        });
        icon.textContent = 'add_circle';
    } else {
        // Expand: Show only immediate children
        allRows.forEach(r => {
            if (r.dataset.parentId === rowId) {
                r.classList.remove('hidden');
            }
        });
        icon.textContent = 'remove_circle';
    }
}

// Close on escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLeafModal();
});
