/**
 * CustomMultiSelect - A reusable Tailwind CSS multi-select dropdown component
 *
 * Usage:
 * const mySelect = new CustomMultiSelect({
 *     containerId: 'my-container',
 *     label: 'Location',
 *     defaultText: 'All Locations',
 *     options: ['Singapore', 'Portland', 'Seattle'],
 *     onChange: (selectedValues) => {
 *         console.log(selectedValues);
 *     }
 * });
 *
 * To reset:
 * mySelect.reset();
 * 
 * To get values:
 * const values = mySelect.getValues();
 */

class CustomMultiSelect {
    constructor(config) {
        this.containerId = config.containerId;
        this.container = document.getElementById(this.containerId);
        if (!this.container) {
            console.error(`CustomMultiSelect: Container with id '${this.containerId}' not found.`);
            return;
        }

        this.label = config.label || '';
        this.defaultText = config.defaultText || 'All Options';
        this.options = config.options || [];
        this.onChange = config.onChange || null;
        this.onSearch = config.onSearch || null;

        this.render();
        this.attachEvents();
    }

    render() {
        this.container.innerHTML = `
            <div class="space-y-1.5 relative" id="${this.containerId}-multiselect-container">
                ${this.label ? `<label class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">${this.label}</label>` : ''}
                <!-- Trigger -->
                <div id="${this.containerId}-trigger" class="w-full bg-gray-50 dark:bg-gray-800 border-gray-200 border dark:border-gray-700 rounded text-xs focus:ring-0 focus:border-primary p-2 cursor-pointer flex justify-between items-center transition-colors hover:border-gray-300 dark:hover:border-gray-600">
                    <span id="${this.containerId}-text" class="truncate text-gray-700 dark:text-gray-300">${this.defaultText}</span>
                    <span class="material-symbols-outlined text-[16px] text-gray-400 pointer-events-none transition-transform duration-200" id="${this.containerId}-icon">expand_more</span>
                </div>
                
                <!-- Dropdown Panel -->
                <div id="${this.containerId}-dropdown" class="hidden absolute left-0 right-0 top-[100%] mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-50 flex flex-col max-h-96 overflow-hidden">
                    <div class="p-2 border-b border-gray-100 dark:border-gray-700 shrink-0 bg-white dark:bg-gray-800 z-10 sticky top-0">
                        <div class="flex items-center gap-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded px-2 py-1.5">
                            <span class="material-symbols-outlined text-gray-400 text-[14px]">search</span>
                            <input type="text" id="${this.containerId}-search" placeholder="Search..." class="w-full bg-transparent border-none text-[11px] p-0 focus:ring-0 placeholder:text-gray-400 text-gray-700 dark:text-gray-200" />
                        </div>
                    </div>
                    <div id="${this.containerId}-options-list" class="overflow-y-auto flex-1 p-1">
                        <!-- Options dynamically loaded -->
                    </div>
                </div>
            </div>
        `;
        
        this.populateOptions(this.options);
    }

    populateOptions(options) {
        this.options = options;
        const locContainer = document.getElementById(`${this.containerId}-options-list`);
        if (!locContainer) return;

        // OPTIMIZATION: Use DocumentFragment to avoid reflows during DOM manipulation
        const fragment = document.createDocumentFragment();
        
        this.options.forEach(optVal => {
            const label = document.createElement('label');
            label.className = 'flex items-center gap-2 px-2 py-2.5 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer rounded-sm';
            label.dataset.text = optVal.toLowerCase();
            
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = optVal;
            cb.className = `rounded border-gray-300 text-primary focus:ring-primary w-3 h-3 ${this.containerId}-checkbox`;
            
            const span = document.createElement('span');
            span.className = 'text-[11px] text-gray-700 dark:text-gray-300 select-none';
            span.textContent = optVal;
            
            label.appendChild(cb);
            label.appendChild(span);
            fragment.appendChild(label);
        });
        
        locContainer.innerHTML = '';
        locContainer.appendChild(fragment);
        
        this.updateTriggerText();
    }

    attachEvents() {
        const trigger = document.getElementById(`${this.containerId}-trigger`);
        const dropdown = document.getElementById(`${this.containerId}-dropdown`);
        const icon = document.getElementById(`${this.containerId}-icon`);
        const searchInput = document.getElementById(`${this.containerId}-search`);
        const containerRoot = document.getElementById(`${this.containerId}-multiselect-container`);
        const optionsList = document.getElementById(`${this.containerId}-options-list`);

        // Toggle dropdown
        trigger.addEventListener('click', () => {
            if (dropdown.classList.contains('hidden')) {
                dropdown.classList.remove('hidden');
                if(icon) icon.style.transform = 'rotate(180deg)';
                if(searchInput) searchInput.focus();

                // DYNAMIC LOAD ON FOCUS: If dynamic and no options yet, load them
                if (this.onSearch && this.options.length === 0) {
                    const optionsList = document.getElementById(`${this.containerId}-options-list`);
                    if (optionsList) {
                        optionsList.innerHTML = '<div class="p-4 text-center text-gray-400 text-[10px]">Loading...</div>';
                    }
                    this.onSearch('', (data) => {
                        this.populateOptions(data);
                    });
                }
            } else {
                dropdown.classList.add('hidden');
                if(icon) icon.style.transform = 'rotate(0deg)';
            }
        });

        // Search filtering
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const searchValue = e.target.value;
                const searchValueLower = searchValue.toLowerCase();
                
                // If remote search callback is provided
                if (this.onSearch) {
                    // Debounce remote search
                    clearTimeout(this.searchTimeout);
                    this.searchTimeout = setTimeout(() => {
                        this.onSearch(searchValue, (newOptions) => {
                            // Merge new options with currently selected values to ensure they don't disappear
                            const selectedValues = this.getValues();
                            const mergedOptions = [...new Set([...selectedValues, ...newOptions])];
                            this.populateOptions(mergedOptions);
                            
                            // Restore selections
                            document.querySelectorAll(`.${this.containerId}-checkbox`).forEach(cb => {
                                if (selectedValues.includes(cb.value)) {
                                    cb.checked = true;
                                }
                            });
                            this.updateTriggerText();
                        });
                    }, 300);
                    return;
                }

                // Local filtering (default behavior)
                const optionLabels = optionsList.querySelectorAll('label');
                optionLabels.forEach(opt => {
                    const text = opt.dataset.text;
                    if (text.includes(searchValueLower)) {
                        opt.style.display = 'flex';
                    } else {
                        opt.style.display = 'none';
                    }
                });
            });
        }

        // OPTIMIZATION: Event delegation for checkbox changes
        if (optionsList) {
            optionsList.addEventListener('change', (e) => {
                if (e.target.classList.contains(`${this.containerId}-checkbox`)) {
                    this.updateTriggerText();
                    if (this.onChange) {
                        this.onChange(this.getValues());
                    }
                }
            });
        }

        // Click outside to close (Ensuring it binds correctly avoiding duplicates if re-rendered)
        document.addEventListener('click', (e) => {
            if (containerRoot && dropdown && !containerRoot.contains(e.target)) {
                dropdown.classList.add('hidden');
                if(icon) icon.style.transform = 'rotate(0deg)';
            }
        });
    }

    updateTriggerText() {
        const checked = document.querySelectorAll(`.${this.containerId}-checkbox:checked`);
        const textEl = document.getElementById(`${this.containerId}-text`);
        if(!textEl) return;
        
        if (checked.length === 0) {
            textEl.textContent = this.defaultText;
        } else if (checked.length === 1) {
            textEl.textContent = checked[0].value;
        } else {
            textEl.textContent = `${checked.length} Selected`;
        }
    }

    getValues() {
        const checked = document.querySelectorAll(`.${this.containerId}-checkbox:checked`);
        return Array.from(checked).map(cb => cb.value);
    }

    reset() {
        document.querySelectorAll(`.${this.containerId}-checkbox`).forEach(cb => cb.checked = false);
        this.updateTriggerText();
        const searchInput = document.getElementById(`${this.containerId}-search`);
        if(searchInput) {
            searchInput.value = '';
            // Trigger input event to reset list
            searchInput.dispatchEvent(new Event('input'));
        }
        if (this.onChange) {
            this.onChange([]);
        }
    }
}

window.CustomMultiSelect = CustomMultiSelect;
