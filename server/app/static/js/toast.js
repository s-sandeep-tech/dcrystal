/**
 * Global Toast Notification System
 * A sleek, modern notification manager utilizing Tailwind utility classes constraints.
 */

(function () {
    window.showToast = function (title, message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) {
            console.error('Toast container not found in DOM (#toast-container)');
            return;
        }

        let icon = 'info';
        let iconColor = 'text-blue-500';
        let stripeColor = 'bg-blue-500';
        let bgColor = 'bg-white dark:bg-[#1a2330]';

        switch (type.toLowerCase()) {
            case 'success':
                icon = 'check_circle';
                iconColor = 'text-emerald-500';
                stripeColor = 'bg-emerald-500';
                break;
            case 'error':
                icon = 'error';
                iconColor = 'text-red-500';
                stripeColor = 'bg-red-500';
                bgColor = 'bg-white dark:bg-[#2c1313]'; // slightly reddish dark mode bg
                break;
            case 'warning':
                icon = 'warning';
                iconColor = 'text-amber-500';
                stripeColor = 'bg-amber-500';
                break;
            case 'astrisk':
            case 'asterisk':
                icon = 'emergency';
                iconColor = 'text-purple-500';
                stripeColor = 'bg-purple-500';
                bgColor = 'bg-white dark:bg-[#1e132c]'; // slightly purplish dark mode bg
                break;
            case 'info':
            default:
                icon = 'info';
                iconColor = 'text-blue-500';
                stripeColor = 'bg-blue-500';
                break;
        }

        // Create the toast wrapper
        const toast = document.createElement('div');
        // Base styling for the toast, utilizing Tailwind
        // Increased max width to max-w-md and added a minimum width so it doesn't shrink too much
        toast.className = `relative flex w-full min-w-[320px] max-w-md ${bgColor} shadow-xl border border-gray-100 dark:border-gray-800 rounded-lg pointer-events-auto overflow-hidden transform transition-all duration-300 translate-x-[120%] opacity-0 mb-3 ml-auto`;

        toast.innerHTML = `
            <div class="absolute left-0 top-0 bottom-0 w-1 ${stripeColor}"></div>
            <div class="flex items-start p-4 w-full">
                <div class="flex-shrink-0 mt-0.5">
                    <span class="material-symbols-outlined justify-center items-center flex ${iconColor} text-lg">${icon}</span>
                </div>
                <div class="ml-3 flex-1 flex flex-col justify-center min-w-0">
                    <p class="text-[13px] font-bold text-gray-900 dark:text-gray-100 leading-tight pr-2">
                        ${title}
                    </p>
                    ${message ? `<p class="mt-1.5 text-[11px] text-gray-500 dark:text-gray-400 leading-snug break-words pr-2">${message}</p>` : ''}
                </div>
                <div class="ml-4 flex-shrink-0 flex items-start">
                    <button type="button" class="bg-transparent rounded-sm inline-flex text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors close-btn focus:outline-none">
                        <span class="sr-only">Close</span>
                        <span class="material-symbols-outlined text-sm">close</span>
                    </button>
                </div>
            </div>
        `;

        container.appendChild(toast);

        // Trigger reflow and apply enter styles
        void toast.offsetWidth;
        toast.classList.remove('translate-x-[120%]', 'opacity-0');
        toast.classList.add('translate-x-0', 'opacity-100');

        let isDismissing = false;

        const dismiss = () => {
            if (isDismissing) return;
            isDismissing = true;
            toast.classList.remove('translate-x-0', 'opacity-100');
            toast.classList.add('opacity-0', 'translate-x-[120%]');

            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        };

        toast.querySelector('.close-btn').addEventListener('click', dismiss);

        // Auto close after 5 seconds
        setTimeout(() => {
            dismiss();
        }, 5000);
    };
})();
