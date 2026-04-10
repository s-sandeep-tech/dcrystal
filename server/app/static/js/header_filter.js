/**
 * HeaderFilter - A premium multi-select dropdown for table headers
 */
class HeaderFilter {
    constructor(config) {
        this.id = config.id;
        this.title = config.title || 'Filter';
        this.options = config.options || [];
        this.selectedValues = config.selectedValues || [];
        this.onApply = config.onApply || null;
        this.onClear = config.onClear || null;
        
        this.dropdown = null;
        this.isOpen = false;
        
        // Bind methods
        this.handleOutsideClick = this.handleOutsideClick.bind(this);
    }

    render(anchorElement) {
        if (this.dropdown) {
            this.dropdown.remove();
        }

        const rect = anchorElement.getBoundingClientRect();
        
        this.dropdown = document.createElement('div');
        this.dropdown.id = `header-filter-dropdown-${this.id}`;
        this.dropdown.className = 'header-filter-dropdown';
        
        // Calculate available space
        const spaceBelow = window.innerHeight - rect.bottom - 10;
        const spaceAbove = rect.top - 10;
        
        // Estimated height for a full dropdown: search(30) + select-all(25) + options(150) + actions(35) + padding(10) =~ 250px
        const estimatedHeight = 250;
        let maxHeight;
        let topPos;
        
        // Open downwards if there's enough space, or if space below is greater than space above
        if (spaceBelow >= estimatedHeight || spaceBelow >= spaceAbove) {
            topPos = rect.bottom + 5;
            maxHeight = spaceBelow;
            this.dropdown.style.top = `${topPos}px`;
        } else {
            // Open upwards
            maxHeight = spaceAbove;
            // Use bottom positioning relative to window to let it grow upwards
            this.dropdown.style.bottom = `${window.innerHeight - rect.top + 5}px`;
        }
        
        // Constrain the dropdown strictly to the visible area
        this.dropdown.style.maxHeight = `${maxHeight}px`;
        
        // Positioning - Align left edge of dropdown with left edge of icon
        let leftPos = rect.left;
        
        // Safety check: if it goes off screen on the right, align right instead
        if (leftPos + 160 > window.innerWidth - 10) {
            leftPos = rect.right - 160;
        }
        
        if (leftPos < 10) leftPos = 10;
        this.dropdown.style.left = `${leftPos}px`;

        this.dropdown.innerHTML = `
            <div class="header-filter-search-container">
                <input type="text" class="header-filter-search-input" placeholder="Search ${this.title}..." id="filter-search-${this.id}">
            </div>
            <div class="header-filter-select-all">
                <label class="header-filter-option">
                    <input type="checkbox" id="filter-select-all-${this.id}">
                    <span>Select All</span>
                </label>
            </div>
            <div class="header-filter-options" id="filter-options-list-${this.id}">
                ${this.renderOptions(this.options)}
            </div>
            <div class="header-filter-actions">
                <button class="header-filter-btn header-filter-btn-clear" id="filter-clear-${this.id}" title="Clear Filter">
                    <span class="material-symbols-outlined text-[18px]">refresh</span>
                </button>
                <button class="header-filter-btn header-filter-btn-apply" id="filter-apply-${this.id}" title="Apply Filter">
                    <span class="material-symbols-outlined text-[18px]">check</span>
                </button>
            </div>
        `;

        document.body.appendChild(this.dropdown);
        this.isOpen = true;
        
        this.attachEvents();
        this.updateSelectAllState();
        
        // Focus search
        setTimeout(() => {
            const searchInput = this.dropdown.querySelector('.header-filter-search-input');
            if (searchInput) searchInput.focus();
        }, 50);

        // Add document click listener with delay to avoid immediate trigger from the icon click
        setTimeout(() => {
            document.addEventListener('click', this.handleOutsideClick);
            
            // Close on scroll of the main table area
            const tableArea = document.getElementById('table-area');
            if (tableArea) {
                tableArea.addEventListener('scroll', () => this.close(), { once: true });
            }
            
            // Also handle window scroll
            window.addEventListener('scroll', () => this.close(), { once: true });
        }, 100);
    }

    renderOptions(options) {
        if (options.length === 0) {
            return '<div class="header-filter-no-results">No values found</div>';
        }

        return options.map(opt => `
            <label class="header-filter-option" data-value="${String(opt).toLowerCase()}">
                <input type="checkbox" class="header-filter-checkbox" value="${opt}" ${this.selectedValues.includes(String(opt)) || this.selectedValues.includes(Number(opt)) || this.selectedValues.includes(opt) ? 'checked' : ''}>
                <span>${opt}</span>
            </label>
        `).join('');
    }

    attachEvents() {
        const searchInput = this.dropdown.querySelector('.header-filter-search-input');
        const selectAll = this.dropdown.querySelector(`#filter-select-all-${this.id}`);
        const applyBtn = this.dropdown.querySelector(`#filter-apply-${this.id}`);
        const clearBtn = this.dropdown.querySelector(`#filter-clear-${this.id}`);
        const optionsList = this.dropdown.querySelector(`#filter-options-list-${this.id}`);

        // Search filtering
        searchInput.addEventListener('input', (e) => {
            const val = e.target.value.toLowerCase();
            const optionLabels = optionsList.querySelectorAll('.header-filter-option');
            let hasVisible = false;
            
            optionLabels.forEach(label => {
                if (label.dataset.value.includes(val)) {
                    label.style.display = 'flex';
                    hasVisible = true;
                } else {
                    label.style.display = 'none';
                }
            });

            // Handle "No Results" display if needed (could be improved)
        });

        // Select All
        selectAll.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            const checkboxes = optionsList.querySelectorAll('.header-filter-checkbox');
            checkboxes.forEach(cb => {
                if (cb.parentElement.style.display !== 'none') {
                    cb.checked = isChecked;
                }
            });
        });

        // Individual checkbox changes
        optionsList.addEventListener('change', (e) => {
            if (e.target.classList.contains('header-filter-checkbox')) {
                this.updateSelectAllState();
            }
        });

        // Apply
        applyBtn.addEventListener('click', () => {
            const checked = optionsList.querySelectorAll('.header-filter-checkbox:checked');
            this.selectedValues = Array.from(checked).map(cb => cb.value);
            if (this.onApply) this.onApply(this.selectedValues);
            this.close();
        });

        // Clear
        clearBtn.addEventListener('click', () => {
            this.selectedValues = [];
            if (this.onClear) this.onClear();
            this.close();
        });
    }

    updateSelectAllState() {
        const selectAll = this.dropdown.querySelector(`#filter-select-all-${this.id}`);
        const checkboxes = this.dropdown.querySelectorAll('.header-filter-checkbox');
        const checked = this.dropdown.querySelectorAll('.header-filter-checkbox:checked');
        
        if (checkboxes.length > 0) {
            selectAll.checked = checkboxes.length === checked.length;
            selectAll.indeterminate = checked.length > 0 && checked.length < checkboxes.length;
        }
    }

    handleOutsideClick(e) {
        if (this.dropdown && !this.dropdown.contains(e.target)) {
            this.close();
        }
    }

    close() {
        if (this.dropdown) {
            this.dropdown.remove();
            this.dropdown = null;
        }
        this.isOpen = false;
        document.removeEventListener('click', this.handleOutsideClick);
        
        // Notify UI to update icon state
        const icon = document.querySelector(`.header-filter-container[data-id="${this.id}"]`);
        if (icon) {
            icon.classList.remove('active');
            if (this.selectedValues.length > 0) {
                icon.classList.add('filtered');
            } else {
                icon.classList.remove('filtered');
            }
        }
    }

    setOptions(options) {
        this.options = options;
    }

    setSelectedValues(values) {
        this.selectedValues = values || [];
    }
}

window.HeaderFilter = HeaderFilter;
