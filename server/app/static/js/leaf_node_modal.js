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
        const urlParams = new URLSearchParams(window.location.search);

        // Start with existing global filters
        const params = new URLSearchParams(urlParams);

        // Override or set owner parameters specific to the modal item
        params.set('classification_owner', classOwner);
        params.set('make_owner', makeOwner);
        params.set('collection_owner', collOwner);

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

    const depth = parseInt(row.dataset.depth || '0');

    // Gradient classes based on depth
    const highlightMap = {
        0: ['bg-gradient-to-b', 'from-blue-100', 'to-transparent', 'dark:from-blue-900/40', 'dark:to-transparent'],
        1: ['bg-gradient-to-b', 'from-emerald-100', 'to-transparent', 'dark:from-emerald-900/40', 'dark:to-transparent'],
        2: ['bg-gradient-to-b', 'from-purple-100', 'to-transparent', 'dark:from-purple-900/40', 'dark:to-transparent'],
        3: ['bg-gradient-to-b', 'from-amber-100', 'to-transparent', 'dark:from-amber-900/40', 'dark:to-transparent'],
        4: ['bg-gradient-to-b', 'from-cyan-100', 'to-transparent', 'dark:from-cyan-900/40', 'dark:to-transparent'],
        5: ['bg-gradient-to-b', 'from-indigo-100', 'to-transparent', 'dark:from-indigo-900/40', 'dark:to-transparent'],
        6: ['bg-gradient-to-b', 'from-rose-100', 'to-transparent', 'dark:from-rose-900/40', 'dark:to-transparent']
    };

    const defaultHighlight = ['bg-gradient-to-b', 'from-gray-100', 'to-transparent', 'dark:from-gray-800/40', 'dark:to-transparent'];
    const highlightClasses = highlightMap[depth] || defaultHighlight;

    // Background classes to remove from cells so row gradient shows through
    const bgClassesToRemove = [
        'bg-white', 'dark:bg-gray-900',
        'bg-emerald-50/10', 'bg-red-50/10', 'bg-indigo-50/10',
        'bg-gray-50/5', 'bg-cyan-50/10', 'bg-amber-50/10',
        'bg-blue-50/10', 'bg-teal-50/10'
    ];

    if (isExpanded) {
        // Collapse: Hide all descendants (rows whose parent-id starts with current rowId)
        allRows.forEach(r => {
            if (r.dataset.parentId && r.dataset.parentId.startsWith(rowId)) {
                r.classList.add('hidden');
                r.classList.remove(...highlightClasses); // Remove highlight from descendants

                // Restore background on descendant cells if needed (though they are hidden)
                const cells = r.querySelectorAll('td');
                cells.forEach(cell => {
                    if (cell.dataset.originalBg) {
                        const classes = cell.dataset.originalBg.split(' ');
                        cell.classList.add(...classes);
                        delete cell.dataset.originalBg;
                    }
                });

                const childIcon = r.querySelector('.toggle-icon');
                if (childIcon) childIcon.textContent = 'add_circle';
            }
        });
        icon.textContent = 'add_circle';
        row.classList.remove(...highlightClasses); // Remove highlight from current row

        // Restore background on current row cells
        const cells = row.querySelectorAll('td');
        cells.forEach(cell => {
            if (cell.dataset.originalBg) {
                const classes = cell.dataset.originalBg.split(' ');
                cell.classList.add(...classes);
                delete cell.dataset.originalBg;
            }
        });

    } else {
        // Expand: Show only immediate children
        allRows.forEach(r => {
            if (r.dataset.parentId === rowId) {
                r.classList.remove('hidden');
            }
        });
        icon.textContent = 'remove_circle';
        row.classList.add(...highlightClasses); // Add highlight to current row

        // Remove backgrounds from cells so gradient shows
        const cells = row.querySelectorAll('td');
        cells.forEach(cell => {
            const originalClasses = [];
            bgClassesToRemove.forEach(cls => {
                if (cell.classList.contains(cls)) {
                    originalClasses.push(cls);
                    cell.classList.remove(cls);
                }
            });
            if (originalClasses.length > 0) {
                cell.dataset.originalBg = originalClasses.join(' ');
            }
        });
    }
}

// Close on escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLeafModal();
});
