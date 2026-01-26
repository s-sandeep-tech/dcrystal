document.addEventListener('DOMContentLoaded', function () {
    // Connect to the socket server
    const token = localStorage.getItem('access_token');
    const socket = io({
        auth: { token: token },
        path: "/realtimedata/" // Ensure path matches socket server config if needed, but current base.html suggests default or specific
    });

    socket.on('connect_error', (err) => {
        if (err.message.includes('Authentication error')) {
            console.error('Socket authentication failed:', err.message);
            localStorage.removeItem('access_token');
            window.location.href = '/login';
        }
    });

    const notifBtn = document.getElementById('notifBtn');
    const notifDropdown = document.getElementById('notifDropdown');
    const notifList = document.getElementById('notifList');

    // Toggle Dropdown
    if (notifBtn && notifDropdown) {
        notifBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            const isHidden = notifDropdown.classList.contains('hidden');
            if (isHidden) {
                showDropdown();
                fetchNotifications(); // Fetch notifications when opening
            } else {
                hideDropdown();
            }
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', function (event) {
        if (notifDropdown && !notifDropdown.contains(event.target) && !notifBtn.contains(event.target)) {
            hideDropdown();
        }
    });

    function updateSyncTime() {
        const syncTimeEl = document.getElementById('syncTime');
        if (syncTimeEl) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
            syncTimeEl.textContent = timeStr;
        }
    }

    // Initial sync time on load
    updateSyncTime();

    function showDropdown() {
        if (notifDropdown) {
            notifDropdown.classList.remove('hidden');
        }
    }

    function hideDropdown() {
        if (notifDropdown) {
            notifDropdown.classList.add('hidden');
        }
    }

    function fetchNotifications() {
        if (!notifList) return;

        // Reset to loading spinner
        notifList.innerHTML = `
            <div class="py-12 text-center">
                <div class="inline-block size-6 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
                <p class="text-[10px] text-gray-400 mt-2">Loading notifications...</p>
            </div>
        `;

        fetch('/notifications/list', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        })
            .then(response => response.text())
            .then(html => {
                // Capture current height (spinner height)
                const initialHeight = notifList.offsetHeight;

                // Set fixed height to animate from
                notifList.style.height = initialHeight + 'px';
                notifList.style.overflow = 'hidden';
                notifList.style.transition = 'height 0.8s cubic-bezier(0.4, 0, 0.2, 1)';

                // Wrap content in an animated container
                const animatedHtml = `
                    <div id="notifFadeWrapper" class="transition-all duration-700 opacity-0 translate-y-2">
                        ${html}
                    </div>
                `;
                notifList.innerHTML = animatedHtml;

                // Calculate target height (capped by max-h-96 which is 384px)
                const targetHeight = Math.min(notifList.scrollHeight, 384);

                // Update sync time since we just refreshed
                updateSyncTime();

                // Trigger animations
                requestAnimationFrame(() => {
                    notifList.style.height = targetHeight + 'px';

                    const wrapper = document.getElementById('notifFadeWrapper');
                    if (wrapper) {
                        wrapper.classList.remove('opacity-0', 'translate-y-2');
                        wrapper.classList.add('opacity-100', 'translate-y-0');
                    }
                });

                // Clean up after animation
                setTimeout(() => {
                    notifList.style.height = '';
                    notifList.style.overflow = '';
                }, 800);
            })
            .catch(error => {
                console.error('Error fetching notifications:', error);
                notifList.innerHTML = '<div class="py-12 text-center text-red-500 text-[10px]">Failed to load notifications</div>';
                notifList.style.height = '';
                notifList.style.overflow = '';
            });
    }

    // SocketIO Event Listeners
    socket.on('connect', function () {
        console.log('Connected to socket server');
        updateConnectionStatus(true);
    });

    socket.on('disconnect', function () {
        console.log('Disconnected from socket server');
        updateConnectionStatus(false);
    });

    socket.on('new_notification', function (data) {
        console.log('New notification received:', data);
        updateBadge();

        // If the dropdown is currently open and visible, prepend the new notification
        if (notifList && !notifDropdown.classList.contains('hidden')) {
            prependNotification(data);
        }
    });

    function updateConnectionStatus(isConnected) {
        const statusDiv = document.getElementById('connectionStatus');
        const statusDot = document.getElementById('connectionDot');

        if (statusDiv && statusDot) {
            if (isConnected) {
                statusDiv.classList.remove('bg-gray-50', 'bg-red-50', 'border-gray-100', 'border-red-100');
                statusDiv.classList.add('bg-emerald-50', 'border-emerald-100');
                statusDiv.setAttribute('title', 'Connected');

                statusDot.classList.remove('bg-gray-500', 'bg-red-500');
                statusDot.classList.add('bg-emerald-500');
            } else {
                statusDiv.classList.remove('bg-emerald-50', 'border-emerald-100');
                statusDiv.classList.add('bg-red-50', 'border-red-100');
                statusDiv.setAttribute('title', 'Disconnected');

                statusDot.classList.remove('bg-emerald-500');
                statusDot.classList.add('bg-red-500');
            }
        }
    }

    function updateBadge() {
        let badge = document.getElementById('notifBadge');

        if (badge) {
            let countStr = badge.textContent.replace('+', '');
            let count = parseInt(countStr);
            if (isNaN(count)) count = 0;
            count++;
            badge.textContent = count > 9 ? '9+' : count;
        } else {
            // Create badge if it doesn't exist
            const badgeHtml = '<span id="notifBadge" class="absolute top-0.5 right-1 size-3.5 bg-red-500 rounded-full border border-white dark:border-background-dark flex items-center justify-center text-[7px] font-bold text-white">1</span>';
            notifBtn.insertAdjacentHTML('beforeend', badgeHtml);
        }
    }

    function prependNotification(data) {
        const wrapper = document.getElementById('notifFadeWrapper');
        const targetContainer = wrapper || notifList;

        const emptyState = targetContainer.querySelector('.text-center');
        if (emptyState && emptyState.querySelector('.material-symbols-outlined')) {
            targetContainer.innerHTML = ''; // Clear "no notifications" or loading state
        }

        // Determine color classes based on type
        let colorClass = 'text-blue-500';
        let bgClass = 'bg-blue-50/30';
        let timeColor = 'text-blue-600';

        if (data.type === 'success') {
            colorClass = 'text-emerald-500';
            timeColor = 'text-emerald-600';
        } else if (data.type === 'warning') {
            colorClass = 'text-amber-500';
            timeColor = 'text-amber-600';
        } else if (data.type === 'error') {
            colorClass = 'text-red-500';
            timeColor = 'text-red-600';
        } else if (data.type === 'alert') {
            colorClass = 'text-purple-500';
            timeColor = 'text-purple-600';
        }

        const relatedOrderHtml = data.related_order_id
            ? `<span class="text-[8px] px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-600 dark:text-gray-400 font-mono">${data.related_order_id}</span>`
            : '';

        const itemHtml = `
        <div class="p-3 border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-all duration-500 opacity-0 -translate-y-2 ${bgClass}">
            <div class="flex gap-3">
                <div class="shrink-0 mt-0.5">
                    <span class="material-symbols-outlined ${colorClass} text-base">${data.icon}</span>
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-start justify-between gap-2">
                        <p class="text-[11px] font-bold text-gray-700 dark:text-gray-200 leading-tight">${data.title}</p>
                        <span class="size-2 bg-primary rounded-full shrink-0 mt-1"></span>
                    </div>
                    <p class="text-[10px] text-gray-500 dark:text-gray-400 mt-1 leading-snug">${data.message}</p>
                    <div class="flex items-center justify-between mt-1.5">
                        <p class="text-[9px] font-bold ${timeColor}">${data.time || 'Just now'}</p>
                        ${relatedOrderHtml}
                    </div>
                </div>
            </div>
        </div>
        `;

        targetContainer.insertAdjacentHTML('afterbegin', itemHtml);

        // Animate the new item
        requestAnimationFrame(() => {
            const newItem = targetContainer.firstElementChild;
            if (newItem) {
                // Small timeout to ensure transition works
                setTimeout(() => {
                    newItem.classList.remove('opacity-0', '-translate-y-2');
                    newItem.classList.add('opacity-100', 'translate-y-0');
                }, 10);
            }
        });
    }
});
