// settings.js - JavaScript logic for the settings page

document.addEventListener('DOMContentLoaded', () => {
    const socketDot = document.getElementById('socket-status-dot');
    const socketText = document.getElementById('socket-status-text');

    function updateSocketStatus(connected) {
        if (socketDot && socketText) {
            if (connected) {
                socketDot.className = 'size-2 rounded-full bg-green-500 animate-pulse';
                socketText.className = 'text-[11px] font-bold uppercase text-green-500';
                socketText.textContent = 'Online';
            } else {
                socketDot.className = 'size-2 rounded-full bg-red-500';
                socketText.className = 'text-[11px] font-bold uppercase text-red-500';
                socketText.textContent = 'Offline';
            }
        }
    }

    // Wait a small bit for notifications.js to definitely initialize window.socket
    function initSocketStatus() {
        if (window.socket) {
            updateSocketStatus(window.socket.connected);
            window.socket.on('connect', () => updateSocketStatus(true));
            window.socket.on('disconnect', () => updateSocketStatus(false));
        } else {
            console.warn('Socket instance not found globally, retrying...');
            setTimeout(initSocketStatus, 500);
        }
    }

    initSocketStatus();

    // Data Sync Logic
    const syncStatus = document.getElementById('sync-status');

    function setSyncLoading(btn, text) {
        if (!btn.disabled) {
            btn.dataset.originalHtml = btn.innerHTML;
        }
        btn.disabled = true;
        btn.innerHTML = `<span class="material-symbols-outlined text-[14px] animate-spin">sync</span> ${text}...`;
    }

    function resetSyncBtn(btn) {
        btn.disabled = false;
        btn.innerHTML = btn.dataset.originalHtml;
    }

    // SocketIO Sync Updates
    function initSyncSocket() {
        if (window.socket) {
            window.socket.on('sync_update', (data) => {
                console.log('Sync Update Received:', data);
                if (!syncStatus) return;

                syncStatus.classList.remove('hidden');

                if (data.status === 'processing') {
                    syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-blue-800/30';
                    const prefix = window.isSyncAllActive ? `<span class="font-bold uppercase text-[9px] mb-1 block">Batch Sync Progress</span>` : '';
                    syncStatus.innerHTML = `
                        <div class="flex flex-col gap-2">
                            ${prefix}
                            <div class="flex items-start justify-between">
                                <span class="flex items-start gap-2 leading-tight">
                                    <span class="material-symbols-outlined text-sm animate-spin mt-0.5">sync</span> 
                                    <span class="flex-1">${data.message}</span>
                                </span>
                                <span class="shrink-0 ml-4">${data.progress}%</span>
                            </div>
                            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 overflow-hidden">
                                <div class="bg-primary h-full transition-all duration-500" style="width: ${data.progress}%"></div>
                            </div>
                        </div>
                    `;
                } else if (data.status === 'success') {
                    syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 border border-green-100 dark:border-green-800/30';
                    syncStatus.innerHTML = `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-sm">check_circle</span> ${data.message}</div>`;

                    // Reset all sync buttons IF NOT in Sync All mode
                    if (!window.isSyncAllActive) {
                        [syncOwnerShowroomBtn, syncProcessBtn, syncOutstandingPOBtn, syncStageDelayBtn, syncOrderDelayBtn, syncPendingAcceptanceBtn, syncRejectedWeightBtn, syncProvisionStatusBtn, syncHallmarkingDelayedBtn, syncQCDelayedBtn, syncOrderProcessingPendingBtn, syncSupplierHMIssueBtn, syncHMReturnPendingBtn, syncHMQCIssuePendingBtn, syncSupplierQCIssueReceiptBtn, syncQCCompletedInvoiceBtn, syncInvoiceCompletedDeliverBtn, syncBranchAuthorityBtn, syncQCDelayManagementBtn, syncHMDelayManagementBtn, syncPartyDelayManagementBtn].forEach(btn => {
                            if (btn && btn.disabled) resetSyncBtn(btn);
                        });
                    }

                    // Remove highlight from wrapper div
                    if (data.type) {
                        const wrapper = document.getElementById(`sync-wrapper-${data.type}`);
                        if (wrapper) {
                            wrapper.classList.remove('border-primary', 'ring-1', 'ring-primary/20', 'bg-white', 'dark:bg-gray-800/80', 'shadow-lg');
                            wrapper.classList.add('bg-gray-50', 'dark:bg-gray-800/50', 'border-gray-100', 'dark:border-gray-700');
                        }
                    }
                } else if (data.status === 'error') {
                    syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border border-red-100 dark:border-red-800/30';
                    syncStatus.innerHTML = `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-sm">error</span> ${data.message}</div>`;

                    // Reset all sync buttons
                    if (!window.isSyncAllActive) {
                        [syncOwnerShowroomBtn, syncProcessBtn, syncOutstandingPOBtn, syncStageDelayBtn, syncOrderDelayBtn, syncPendingAcceptanceBtn, syncRejectedWeightBtn, syncProvisionStatusBtn, syncHallmarkingDelayedBtn, syncQCDelayedBtn, syncOrderProcessingPendingBtn, syncSupplierHMIssueBtn, syncHMReturnPendingBtn, syncHMQCIssuePendingBtn, syncSupplierQCIssueReceiptBtn, syncQCCompletedInvoiceBtn, syncInvoiceCompletedDeliverBtn, syncBranchAuthorityBtn, syncQCDelayManagementBtn, syncHMDelayManagementBtn, syncPartyDelayManagementBtn].forEach(btn => {
                            if (btn && btn.disabled) resetSyncBtn(btn);
                        });
                    }

                    // Remove highlight from wrapper div
                    if (data.type) {
                        const wrapper = document.getElementById(`sync-wrapper-${data.type}`);
                        if (wrapper) {
                            wrapper.classList.remove('border-primary', 'ring-1', 'ring-primary/20', 'bg-white', 'dark:bg-gray-800/80', 'shadow-lg');
                            wrapper.classList.add('bg-gray-50', 'dark:bg-gray-800/50', 'border-gray-100', 'dark:border-gray-700');
                        }
                    }

                    if (typeof window.showToast === 'function') {
                        window.showToast(data.message, 'error');
                    }
                }
            });
        } else {
            setTimeout(initSyncSocket, 500);
        }
    }
    initSyncSocket();

    const syncOwnerShowroomBtn = document.getElementById('sync-owner-showroom-btn');
    const syncProcessBtn = document.getElementById('sync-process-delay-btn');
    const syncOutstandingPOBtn = document.getElementById('sync-outstanding-po-btn');
    const syncStageDelayBtn = document.getElementById('sync-stage-delay-btn');
    const syncOrderDelayBtn = document.getElementById('sync-order-delay-btn');
    const syncPendingAcceptanceBtn = document.getElementById('sync-pending-acceptance-btn');
    const syncRejectedWeightBtn = document.getElementById('sync-rejected-weight-btn');
    const syncProvisionStatusBtn = document.getElementById('sync-provision-status-btn');
    const syncHallmarkingDelayedBtn = document.getElementById('sync-hallmarking-delayed-btn');
    const syncQCDelayedBtn = document.getElementById('sync-qc-delayed-btn');
    const syncOrderProcessingPendingBtn = document.getElementById('sync-order-processing-pending-btn');
    const syncSupplierHMIssueBtn = document.getElementById('sync-supplier-hm-issue-btn');
    const syncHMReturnPendingBtn = document.getElementById('sync-hm-return-pending-btn');
    const syncHMQCIssuePendingBtn = document.getElementById('sync-hm-qc-issue-pending-btn');
    const syncSupplierQCIssueReceiptBtn = document.getElementById('sync-supplier-qc-issue-receipt-btn');
    const syncQCCompletedInvoiceBtn = document.getElementById('sync-qc-completed-invoice-btn');
    const syncInvoiceCompletedDeliverBtn = document.getElementById('sync-invoice-completed-deliver-btn');
    const syncBranchAuthorityBtn = document.getElementById('sync-branch-authority-btn');
    const syncQCDelayManagementBtn = document.getElementById('sync-qc-delay-management-btn');
    const syncHMDelayManagementBtn = document.getElementById('sync-hm-delay-management-btn');
    const syncPartyDelayManagementBtn = document.getElementById('sync-party-delay-management-btn');
    const syncAllBtn = document.getElementById('sync-all-btn');

    async function triggerSync(btn, url, label, type) {
        setSyncLoading(btn, 'Queueing');
        syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
        syncStatus.textContent = `Queueing ${label}...`;
        syncStatus.classList.remove('hidden');

        // Add highlight
        if (type) {
            const wrapper = document.getElementById(`sync-wrapper-${type}`);
            if (wrapper) {
                wrapper.classList.remove('bg-gray-50', 'dark:bg-gray-800/50', 'border-gray-100', 'dark:border-gray-700');
                wrapper.classList.add('border-primary', 'ring-1', 'ring-primary/20', 'bg-white', 'dark:bg-gray-800/80', 'shadow-lg');
            }
        }

        try {
            const response = await fetch(url, { method: 'POST' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.message || 'Queueing failed');
            syncStatus.textContent = data.message;
            return true;
        } catch (error) {
            syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-red-50 text-red-600 border border-red-100';
            syncStatus.innerHTML = `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-sm">error</span> ${error.message}</div>`;
            resetSyncBtn(btn);

            // Remove highlight on quick fail
            if (type) {
                const wrapper = document.getElementById(`sync-wrapper-${type}`);
                if (wrapper) {
                    wrapper.classList.remove('border-primary', 'ring-1', 'ring-primary/20', 'bg-white', 'dark:bg-gray-800/80', 'shadow-lg');
                    wrapper.classList.add('bg-gray-50', 'dark:bg-gray-800/50', 'border-gray-100', 'dark:border-gray-700');
                }
            }
            return false;
        }
    }

    if (syncOwnerShowroomBtn) syncOwnerShowroomBtn.addEventListener('click', () => triggerSync(syncOwnerShowroomBtn, window.SETTINGS_CONFIG.syncOwnerShowroomUrl, 'Owner & Showroom Wise Order Summary Sync', 'owner_showroom_combined'));
    if (syncProcessBtn) syncProcessBtn.addEventListener('click', () => triggerSync(syncProcessBtn, window.SETTINGS_CONFIG.syncProcessDelayUrl, 'Process Delay Sync', 'process_delay'));
    if (syncOutstandingPOBtn) syncOutstandingPOBtn.addEventListener('click', () => triggerSync(syncOutstandingPOBtn, window.SETTINGS_CONFIG.syncOutstandingPOUrl, 'PO Sync', 'outstanding_po'));
    if (syncStageDelayBtn) syncStageDelayBtn.addEventListener('click', () => triggerSync(syncStageDelayBtn, window.SETTINGS_CONFIG.syncStageDelayUrl, 'Stage Delay Sync', 'stage_delay'));
    if (syncOrderDelayBtn) syncOrderDelayBtn.addEventListener('click', () => triggerSync(syncOrderDelayBtn, window.SETTINGS_CONFIG.syncOrderDelayUrl, 'Order Delay Sync', 'order_delay_tracking'));
    if (syncPendingAcceptanceBtn) syncPendingAcceptanceBtn.addEventListener('click', () => triggerSync(syncPendingAcceptanceBtn, window.SETTINGS_CONFIG.syncPendingAcceptanceUrl, 'Pending Acceptance Sync', 'pending_acceptance'));
    if (syncRejectedWeightBtn) syncRejectedWeightBtn.addEventListener('click', () => triggerSync(syncRejectedWeightBtn, window.SETTINGS_CONFIG.syncRejectedWeightUrl, 'Rejected Weight Sync', 'rejected_weight'));
    if (syncProvisionStatusBtn) syncProvisionStatusBtn.addEventListener('click', () => triggerSync(syncProvisionStatusBtn, window.SETTINGS_CONFIG.syncProvisionStatusUrl, 'Provision & Stock Status Sync', 'provision_stock_status'));
    if (syncHallmarkingDelayedBtn) syncHallmarkingDelayedBtn.addEventListener('click', () => triggerSync(syncHallmarkingDelayedBtn, window.SETTINGS_CONFIG.syncHallmarkingDelayedUrl, 'Hallmarking Delayed Sync', 'hallmarking_delayed'));
    if (syncQCDelayedBtn) syncQCDelayedBtn.addEventListener('click', () => triggerSync(syncQCDelayedBtn, window.SETTINGS_CONFIG.syncQCDelayedUrl, 'QC Pending Sync', 'qc_delayed'));
    if (syncOrderProcessingPendingBtn) syncOrderProcessingPendingBtn.addEventListener('click', () => triggerSync(syncOrderProcessingPendingBtn, window.SETTINGS_CONFIG.syncOrderProcessingPendingUrl, 'Barcode completed – HM issue pending Sync', 'order_processing_pending'));
    if (syncSupplierHMIssueBtn) syncSupplierHMIssueBtn.addEventListener('click', () => triggerSync(syncSupplierHMIssueBtn, window.SETTINGS_CONFIG.syncSupplierHMIssueUrl, 'HM issue completed – Receipt pending Sync', 'supplier_hm_issue'));
    if (syncHMReturnPendingBtn) syncHMReturnPendingBtn.addEventListener('click', () => triggerSync(syncHMReturnPendingBtn, window.SETTINGS_CONFIG.syncHMReturnPendingUrl, 'HM Completed Return Pending Sync', 'hm_return_pending'));
    if (syncHMQCIssuePendingBtn) syncHMQCIssuePendingBtn.addEventListener('click', () => triggerSync(syncHMQCIssuePendingBtn, window.SETTINGS_CONFIG.syncHMQCIssuePendingUrl, 'HM Return Received QC Pending Sync', 'hm_qc_issue_pending'));
    if (syncSupplierQCIssueReceiptBtn) syncSupplierQCIssueReceiptBtn.addEventListener('click', () => triggerSync(syncSupplierQCIssueReceiptBtn, window.SETTINGS_CONFIG.syncSupplierQCIssueReceiptUrl, 'QC issue completed – KJ receipt pending Sync', 'supplier_qc_issue_receipt_pending'));
    if (syncQCCompletedInvoiceBtn) syncQCCompletedInvoiceBtn.addEventListener('click', () => triggerSync(syncQCCompletedInvoiceBtn, window.SETTINGS_CONFIG.syncQCCompletedInvoiceUrl, 'QC Completed Invoice Pending Sync', 'qc_completed_invoice_pending'));
    if (syncInvoiceCompletedDeliverBtn) syncInvoiceCompletedDeliverBtn.addEventListener('click', () => triggerSync(syncInvoiceCompletedDeliverBtn, window.SETTINGS_CONFIG.syncInvoiceCompletedDeliverUrl, 'Invoice Completed Pending Delivery Sync', 'invoice_completed_pending_deliver'));
    if (syncBranchAuthorityBtn) syncBranchAuthorityBtn.addEventListener('click', () => triggerSync(syncBranchAuthorityBtn, window.SETTINGS_CONFIG.syncBranchAuthorityUrl, 'Branch Authority Sync', 'branch_authority'));
    if (syncQCDelayManagementBtn) syncQCDelayManagementBtn.addEventListener('click', () => triggerSync(syncQCDelayManagementBtn, window.SETTINGS_CONFIG.syncQCDelayManagementUrl, 'QC Delay Summary Sync', 'qc_delay_management'));
    if (syncHMDelayManagementBtn) syncHMDelayManagementBtn.addEventListener('click', () => triggerSync(syncHMDelayManagementBtn, '/settings/sync-hm-delay-management', 'HM Delay Management Sync', 'hm_delay_management'));
    if (syncPartyDelayManagementBtn) syncPartyDelayManagementBtn.addEventListener('click', () => triggerSync(syncPartyDelayManagementBtn, '/settings/sync-party-delay-management', 'Vendor Delay Management Sync', 'party_delay_management'));

    function showConfirmModal(title, message) {
        return new Promise((resolve) => {
            const modal = document.getElementById('confirmModal');
            const content = document.getElementById('confirmModalContent');
            const titleEl = document.getElementById('confirmModalTitle');
            const messageEl = document.getElementById('confirmModalMessage');
            const cancelBtn = document.getElementById('confirmCancelBtn');
            const proceedBtn = document.getElementById('confirmProceedBtn');

            titleEl.textContent = title;
            messageEl.textContent = message;

            modal.classList.remove('hidden');
            setTimeout(() => {
                modal.classList.add('opacity-100');
                content.classList.remove('scale-95');
                content.classList.add('scale-100');
            }, 10);

            const cleanup = (result) => {
                modal.classList.remove('opacity-100');
                content.classList.remove('scale-100');
                content.classList.add('scale-95');
                setTimeout(() => {
                    modal.classList.add('hidden');
                    cancelBtn.removeEventListener('click', onCancel);
                    proceedBtn.removeEventListener('click', onProceed);
                    resolve(result);
                }, 200);
            };

            const onCancel = () => cleanup(false);
            const onProceed = () => cleanup(true);

            cancelBtn.addEventListener('click', onCancel);
            proceedBtn.addEventListener('click', onProceed);
        });
    }

    if (syncAllBtn) {
        syncAllBtn.addEventListener('click', async () => {
            const confirmed = await showConfirmModal(
                'Sync All Data',
                'Start all sync processes sequentially? This may take several minutes and will overwrite current cached snapshots.'
            );
            if (!confirmed) return;

            const tasks = [
                { url: window.SETTINGS_CONFIG.syncOwnerShowroomUrl, label: 'Owner & Showroom Wise Order Summary', type: 'owner_showroom_combined' },
                { url: window.SETTINGS_CONFIG.syncProcessDelayUrl, label: 'Process Delay', type: 'process_delay' },
                { url: window.SETTINGS_CONFIG.syncOutstandingPOUrl, label: 'Outstanding PO', type: 'outstanding_po' },
                { url: window.SETTINGS_CONFIG.syncStageDelayUrl, label: 'Stage Delay', type: 'stage_delay' },
                { url: window.SETTINGS_CONFIG.syncOrderDelayUrl, label: 'Order Delay', type: 'order_delay_tracking' },
                { url: window.SETTINGS_CONFIG.syncPendingAcceptanceUrl, label: 'Pending Acceptance', type: 'pending_acceptance' },
                { url: window.SETTINGS_CONFIG.syncRejectedWeightUrl, label: 'Rejected Weight', type: 'rejected_weight' },
                { url: window.SETTINGS_CONFIG.syncProvisionStatusUrl, label: 'Provision & Stock Status', type: 'provision_stock_status' },
                { url: window.SETTINGS_CONFIG.syncHallmarkingDelayedUrl, label: 'Hallmarking Delayed', type: 'hallmarking_delayed' },
                { url: window.SETTINGS_CONFIG.syncQCDelayedUrl, label: 'QC Pending', type: 'qc_delayed' },
                { url: window.SETTINGS_CONFIG.syncOrderProcessingPendingUrl, label: 'Barcode completed – HM issue pending', type: 'order_processing_pending' },
                { url: window.SETTINGS_CONFIG.syncSupplierHMIssueUrl, label: 'HM issue completed – Receipt pending', type: 'supplier_hm_issue' },
                { url: window.SETTINGS_CONFIG.syncHMReturnPendingUrl, label: 'HM Completed Return Pending', type: 'hm_return_pending' },
                { url: window.SETTINGS_CONFIG.syncHMQCIssuePendingUrl, label: 'HM Return Received QC Pending', type: 'hm_qc_issue_pending' },
                { url: window.SETTINGS_CONFIG.syncSupplierQCIssueReceiptUrl, label: 'QC issue completed – KJ receipt pending', type: 'supplier_qc_issue_receipt_pending' },
                { url: window.SETTINGS_CONFIG.syncQCCompletedInvoiceUrl, label: 'QC Completed Invoice Pending', type: 'qc_completed_invoice_pending' },
                { url: window.SETTINGS_CONFIG.syncInvoiceCompletedDeliverUrl, label: 'Invoice Completed Pending Delivery', type: 'invoice_completed_pending_deliver' },
                { url: window.SETTINGS_CONFIG.syncBranchAuthorityUrl, label: 'Branch Authority', type: 'branch_authority' },
                { url: window.SETTINGS_CONFIG.syncQCDelayManagementUrl, label: 'QC Delay Summary', type: 'qc_delay_management' },
                { url: '/settings/sync-hm-delay-management', label: 'HM Delay Management', type: 'hm_delay_management' },
                { url: '/settings/sync-party-delay-management', label: 'Vendor Delay Management', type: 'party_delay_management' },
            ];

            setSyncLoading(syncAllBtn, 'Processing');
            window.isSyncAllActive = true;

            // Clear any existing highlights
            tasks.forEach(t => {
                const wrapper = document.getElementById(`sync-wrapper-${t.type}`);
                if (wrapper) {
                    wrapper.classList.remove('border-primary', 'ring-1', 'ring-primary/20', 'bg-white', 'dark:bg-gray-800/80');
                }
            });

            for (let i = 0; i < tasks.length; i++) {
                const task = tasks[i];

                syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-blue-50 text-blue-600 border border-blue-100';
                syncStatus.innerHTML = `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-sm animate-spin">sync</span> [${i + 1}/${tasks.length}] ${task.label}: Initializing...</div>`;
                syncStatus.classList.remove('hidden');

                const success = await triggerSync(syncAllBtn, task.url, task.label, task.type);
                if (!success) {
                    window.isSyncAllActive = false;
                    return;
                }

                // Wait for task completion via socket
                await new Promise((resolve) => {
                    let timeoutId;
                    const handler = (data) => {
                        if (data.type === task.type && (data.status === 'success' || data.status === 'error')) {
                            clearTimeout(timeoutId);
                            window.socket.off('sync_update', handler);
                            if (data.status === 'error') {
                                window.isSyncAllActive = false;
                                resolve(false);
                            } else {
                                resolve(true);
                            }
                        }
                    };
                    window.socket.on('sync_update', handler);

                    // Add a timeout fallback (5 minutes) in case the socket response is lost
                    timeoutId = setTimeout(() => {
                        window.socket.off('sync_update', handler);
                        syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-amber-50 text-amber-600 border border-amber-100';
                        syncStatus.innerHTML = `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-sm">warning</span> Task timed out waiting for response</div>`;
                        window.isSyncAllActive = false;
                        resolve(false);
                    }, 5 * 60 * 1000);
                });

                if (!window.isSyncAllActive) break;
            }

            if (window.isSyncAllActive) {
                // All tasks completed successfully, clear cache
                syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-blue-50 text-blue-600 border border-blue-100';
                syncStatus.innerHTML = `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-sm animate-spin">sync</span> Clearing Application Cache...</div>`;
                syncStatus.classList.remove('hidden');

                try {
                    const clearUrl = window.SETTINGS_CONFIG ? window.SETTINGS_CONFIG.clearCacheUrl : '/settings/clear-cache';
                    const response = await fetch(clearUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 border border-green-100 dark:border-green-800/30';
                        syncStatus.innerHTML = `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-sm">check_circle</span> All Sync Tasks and Cache Clear Completed</div>`;
                        if (typeof window.showToast === 'function') {
                            window.showToast('All sync tasks completed and cache cleared successfully', 'success');
                        }
                    } else {
                        throw new Error(data.message || 'Clear cache failed');
                    }
                } catch (error) {
                    syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border border-amber-100 dark:border-amber-800/30';
                    syncStatus.innerHTML = `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-sm">warning</span> Sync completed but failed to clear cache: ${error.message}</div>`;
                    if (typeof window.showToast === 'function') {
                        window.showToast('Sync completed, cache clear failed: ' + error.message, 'warning');
                    }
                }
            }

            window.isSyncAllActive = false;
            resetSyncBtn(syncAllBtn);
        });
    }

    // Clear Cache Logic
    const clearCacheBtn = document.getElementById('clear-cache-btn');
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener('click', async () => {
            const confirmed = await showConfirmModal(
                'Clear Application Cache',
                'Are you sure you want to flush all application cache? This will clear all report snapshots and temporary data for all users.'
            );
            if (!confirmed) return;

            const originalContent = clearCacheBtn.innerHTML;
            clearCacheBtn.disabled = true;
            clearCacheBtn.innerHTML = '<span class="material-symbols-outlined text-[14px] animate-spin">sync</span> Clearing...';

            syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
            syncStatus.textContent = 'Clearing Redis database...';
            syncStatus.classList.remove('hidden');

            try {
                const clearUrl = window.SETTINGS_CONFIG ? window.SETTINGS_CONFIG.clearCacheUrl : '/settings/clear-cache';
                const response = await fetch(clearUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();

                if (response.ok) {
                    syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 border border-green-100 dark:border-green-800/30';
                    syncStatus.innerHTML = `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-sm">check_circle</span> ${data.message}</div>`;
                    if (typeof window.showToast === 'function') {
                        window.showToast('Cache cleared successfully', 'success');
                    }
                } else {
                    throw new Error(data.message || 'Clear cache failed');
                }
            } catch (error) {
                syncStatus.className = 'mt-4 p-3 rounded-lg text-[11px] font-medium bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border border-red-100 dark:border-red-800/30';
                syncStatus.innerHTML = `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-sm">error</span> Error: ${error.message}</div>`;
                if (typeof window.showToast === 'function') {
                    window.showToast('Failed to clear cache: ' + error.message, 'error');
                }
            } finally {
                clearCacheBtn.disabled = false;
                clearCacheBtn.innerHTML = originalContent;
            }
        });
    }

    // Generic RBAC Data State
    let gRoles = [];
    let gMenus = [];
    let currentUserTarget = null;
    // Auth Token
    window.jwtToken = localStorage.getItem('access_token');
    if (!window.jwtToken) {
        console.warn('JWT Token not found in localStorage. Some features may not work.');
    }
    const toastContainer = document.getElementById('toast-container');

    // === USERS MANAGEMENT LOGIC ===
    let userCurrentPage = 1;
    let gManagedUsers = [];

    async function fetchUsers(page = 1) {
        console.log(`Fetching users page ${page}...`);
        const searchInput = document.getElementById('userSearchInput');
        const search = searchInput ? searchInput.value : '';
        try {
            const res = await fetch(`/api/admin/users?page=${page}&search=${encodeURIComponent(search)}`, {
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            if (res.ok) {
                const data = await res.json();
                console.log('Users fetched successfully:', data.users.length);
                gManagedUsers = data.users;
                renderUsersTable(data.users);
                renderUserPagination(data);
                userCurrentPage = data.current_page;
            } else {
                console.error('Failed to fetch users:', res.status, res.statusText);
                const tbody = document.getElementById('usersTableBody');
                if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="p-8 text-center text-red-500 font-medium whitespace-nowrap">Error loading users (${res.status})</td></tr>`;
            }
        } catch (e) {
            console.error('fetchUsers error:', e);
            const tbody = document.getElementById('usersTableBody');
            if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="p-8 text-center text-red-500 font-medium whitespace-nowrap">Network error loading users</td></tr>`;
        }
    }
    window.fetchUsers = fetchUsers;

    window.openUserModal = function (user = null) {
        const modal = document.getElementById('userModal');
        const content = document.getElementById('userModalContent');
        const title = document.getElementById('userModalTitle');
        const form = document.getElementById('userForm');
        const passLabel = document.getElementById('manageUserPassLabel');
        const passHint = document.getElementById('manageUserPassHint');

        if (!modal || !content || !title || !form) return;

        form.reset();
        if (user) {
            title.innerText = 'Edit User';
            document.getElementById('manageUserId').value = user.id;
            document.getElementById('manageUserBizId').value = user.user_id;
            document.getElementById('manageUsername').value = user.username;
            document.getElementById('manageUserEmail').value = user.email;
            document.getElementById('manageUserPassword').value = '';
            if (passLabel) passLabel.innerText = 'New Password';
            if (passHint) passHint.classList.remove('hidden');
        } else {
            title.innerText = 'Create New User';
            document.getElementById('manageUserId').value = '';
            if (passLabel) passLabel.innerText = 'Password *';
            if (passHint) passHint.classList.add('hidden');
        }

        modal.classList.remove('hidden');
        setTimeout(() => {
            modal.classList.remove('opacity-0');
            content.classList.remove('scale-95');
        }, 10);
    };

    window.closeUserModal = function () {
        const modal = document.getElementById('userModal');
        const content = document.getElementById('userModalContent');
        if (!modal || !content) return;
        modal.classList.add('opacity-0');
        content.classList.add('scale-95');
        setTimeout(() => modal.classList.add('hidden'), 300);
    };

    function renderUsersTable(users) {
        const tbody = document.getElementById('usersTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="p-8 text-center text-gray-400 font-medium whitespace-nowrap">No users matched your search.</td></tr>';
            return;
        }

        users.forEach(u => {
            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-50/50 dark:hover:bg-gray-800/20 transition-colors border-b border-gray-100 dark:border-gray-800";
            tr.innerHTML = `
                <td class="px-4 py-3 font-mono font-bold text-primary uppercase tracking-wider">#${u.user_id}</td>
                <td class="px-4 py-3 font-bold text-gray-900 dark:text-white">
                    <div class="flex items-center gap-2">
                        ${u.username}
                        <span class="inline-flex items-center px-1.5 py-0.5 rounded-full text-[8px] font-bold uppercase tracking-wider ${u.is_active ? 'bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400 border border-green-100 dark:border-green-800/30' : 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400 border border-red-100 dark:border-red-800/30'}">
                            ${u.is_active ? 'Active' : 'Disabled'}
                        </span>
                    </div>
                </td>
                <td class="px-4 py-3">${u.email}</td>
                <td class="px-4 py-3 flex flex-wrap gap-1 justify-center">
                    ${(u.roles || []).map(r => `
                        <span class="inline-flex items-center px-1.5 py-0.5 rounded-full text-[8px] font-bold uppercase tracking-wider ${r === 'ADMIN' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-200 dark:border-amber-800' : 'bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400 border border-blue-100 dark:border-blue-800/30'}">
                            ${r}
                        </span>
                    `).join('')}
                    ${(!u.roles || u.roles.length === 0) ? `
                        <span class="inline-flex items-center px-1.5 py-0.5 rounded-full text-[8px] font-bold uppercase tracking-wider bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500 border border-gray-200 dark:border-gray-700">
                            NO ROLES
                        </span>
                    ` : ''}
                </td>
                <td class="px-4 py-3 text-gray-400 whitespace-nowrap">${new Date(u.created_at).toLocaleDateString()}</td>
                <td class="px-4 py-3 text-right whitespace-nowrap">
                    ${u.is_admin ? '<span class="text-gray-300 p-1 opacity-20" title="Admin password cannot be reset through user management"><span class="material-symbols-outlined text-[16px]">lock</span></span>' : `
                        <button onclick="openChangePasswordModal(${u.id})" class="text-gray-400 hover:text-amber-500 transition-colors p-1" title="Change Password"><span class="material-symbols-outlined text-[16px]">key</span></button>
                        <button onclick="openForceResetModal(${u.id})" class="text-gray-400 hover:text-orange-500 transition-colors p-1 ml-1" title="Force Password Reset"><span class="material-symbols-outlined text-[16px]">lock_reset</span></button>
                    `}
                    ${(u.failed_attempt_count > 0 || u.lockout_until) ? `<button onclick="clearUserLockout(${u.id})" class="text-gray-400 hover:text-green-500 transition-colors p-1 ml-1" title="Clear Lockout"><span class="material-symbols-outlined text-[16px]">restart_alt</span></button>` : ''}
                    <button onclick="editUser(${u.id})" class="text-gray-400 hover:text-primary transition-colors p-1 ml-1" title="Edit User"><span class="material-symbols-outlined text-[16px]">edit</span></button>
                    <button onclick="toggleUserStatus(${u.id}, ${u.is_active})" class="text-gray-400 ${u.is_active ? 'hover:text-red-500' : 'hover:text-green-500'} transition-colors p-1 ml-1" title="${u.is_active ? 'Disable User' : 'Enable User'}">
                        <span class="material-symbols-outlined text-[16px]">${u.is_active ? 'person_off' : 'person_check'}</span>
                    </button>
                    <button onclick="deleteUser(${u.id})" class="text-gray-400 hover:text-red-500 transition-colors p-1 ml-1" title="Delete User"><span class="material-symbols-outlined text-[16px]">delete</span></button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderUserPagination(data) {
        const info = document.getElementById('userPaginationInfo');
        if (!info) return;
        const start = data.total > 0 ? (data.current_page - 1) * 8 + 1 : 0;
        const end = Math.min(data.current_page * 8, data.total);
        info.innerText = `Showing ${start} to ${end} of ${data.total} users`;

        const buttons = document.getElementById('userPaginationButtons');
        if (!buttons) return;
        buttons.innerHTML = '';

        // Prev
        const prev = document.createElement('button');
        prev.className = `p-1.5 rounded border transition-all ${data.current_page > 1 ? 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800' : 'opacity-30 cursor-not-allowed border-gray-100 dark:border-gray-800'}`;
        prev.innerHTML = '<span class="material-symbols-outlined text-sm block">chevron_left</span>';
        if (data.current_page > 1) prev.onclick = () => fetchUsers(data.current_page - 1);
        buttons.appendChild(prev);

        // Page numbers (simplified)
        for (let i = 1; i <= data.pages; i++) {
            if (data.pages > 5 && i > 2 && i < data.pages - 1 && Math.abs(i - data.current_page) > 1) {
                if (i === 3 || i === data.pages - 1) {
                    const dot = document.createElement('span');
                    dot.innerText = '...';
                    dot.className = "px-2 text-gray-400";
                    buttons.appendChild(dot);
                }
                continue;
            }
            const btn = document.createElement('button');
            btn.className = `min-w-[28px] h-7 rounded text-[10px] font-bold border transition-all ${i === data.current_page ? 'bg-primary text-white border-primary shadow-sm shadow-primary/20' : 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800'}`;
            btn.innerText = i;
            btn.onclick = () => fetchUsers(i);
            buttons.appendChild(btn);
        }

        // Next
        const next = document.createElement('button');
        next.className = `p-1.5 rounded border transition-all ${data.current_page < data.pages ? 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800' : 'opacity-30 cursor-not-allowed border-gray-100 dark:border-gray-800'}`;
        next.innerHTML = '<span class="material-symbols-outlined text-sm block">chevron_right</span>';
        if (data.current_page < data.pages) next.onclick = () => fetchUsers(data.current_page + 1);
        buttons.appendChild(next);
    }

    async function saveUser() {
        const id = document.getElementById('manageUserId').value;
        const bizId = document.getElementById('manageUserBizId').value.toUpperCase();
        const username = document.getElementById('manageUsername').value;
        const email = document.getElementById('manageUserEmail').value;
        const password = document.getElementById('manageUserPassword').value;

        if (!id && !password) return showToast('Password is required for new users', 'error');

        const payload = { user_id: bizId, username, email };
        if (password) payload.password = password;

        const url = id ? `/api/admin/users/${id}` : '/api/admin/users';
        const method = id ? 'PUT' : 'POST';

        try {
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${window.jwtToken}` },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                showToast(`User ${id ? 'updated' : 'created'} successfully`, 'success');
                window.closeUserModal();
                fetchUsers(userCurrentPage);
            } else {
                const err = await res.json();
                showToast(err.msg || 'Error saving user', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Network error', 'error');
        }
    }
    window.saveUser = saveUser;

    function editUser(id) {
        const user = gManagedUsers.find(u => u.id === id);
        if (user) window.openUserModal(user);
    }
    window.editUser = editUser;

    async function deleteUser(id) {
        if (!confirm('Are you sure you want to delete this user?')) return;
        try {
            const res = await fetch(`/api/admin/users/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            if (res.ok) {
                showToast('User deleted', 'success');
                fetchUsers(userCurrentPage);
            } else {
                showToast('Error deleting user', 'error');
            }
        } catch (e) { console.error(e); }
    }
    window.deleteUser = deleteUser;
    
    async function toggleUserStatus(id, currentlyActive) {
        const user = gManagedUsers.find(u => u.id === id);
        if (!user) return;
        
        const action = currentlyActive ? 'disable' : 'enable';
        const confirmed = await showConfirmModal(
            `${action.charAt(0).toUpperCase() + action.slice(1)} User`,
            `Are you sure you want to ${action} user "${user.username}"? ${currentlyActive ? 'They will no longer be able to log in to the system.' : 'They will regain access to the system.'}`
        );
        
        if (!confirmed) return;
        
        try {
            const res = await fetch(`/api/admin/users/${id}/toggle-status`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            
            const data = await res.json();
            
            if (res.ok) {
                showToast(data.msg, 'success');
                fetchUsers(userCurrentPage);
            } else {
                showToast(data.msg || `Error ${action}ing user`, 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Network error', 'error');
        }
    }
    window.toggleUserStatus = toggleUserStatus;

    window.openChangePasswordModal = function (id) {
        const user = gManagedUsers.find(u => u.id === id);
        if (!user) return;

        document.getElementById('changePassUserId').value = user.id;
        document.getElementById('changePassTargetUser').innerText = `Updating password for ${user.username} (#${user.user_id})`;
        document.getElementById('newPasswordInput').value = '';

        const modal = document.getElementById('changePasswordModal');
        const content = document.getElementById('changePasswordModalContent');
        if (modal && content) {
            modal.classList.remove('hidden');
            setTimeout(() => { modal.classList.remove('opacity-0'); content.classList.remove('scale-95'); }, 10);
        }
    };

    window.closeChangePasswordModal = function () {
        const modal = document.getElementById('changePasswordModal');
        const content = document.getElementById('changePasswordModalContent');
        if (modal && content) {
            modal.classList.add('opacity-0');
            content.classList.add('scale-95');
            setTimeout(() => modal.classList.add('hidden'), 300);
        }
    };

    window.updateUserPassword = async function () {
        const id = document.getElementById('changePassUserId').value;
        const password = document.getElementById('newPasswordInput').value;

        if (!password) return showToast('Password is required', 'error');

        try {
            const res = await fetch(`/api/admin/users/${id}/password`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${window.jwtToken}` },
                body: JSON.stringify({ password })
            });

            if (res.ok) {
                showToast('Password updated successfully', 'success');
                window.closeChangePasswordModal();
            } else {
                const err = await res.json();
                showToast(err.msg || 'Error updating password', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Network error', 'error');
        }
    };

    window.clearUserLockout = async function(id) {
        const user = gManagedUsers.find(u => u.id === id);
        if (!user) return;
        
        const confirmed = await showConfirmModal('Clear User Lockout', `Are you sure you want to clear the lockout for ${user.username}?`);
        if (!confirmed) return;

        try {
            const res = await fetch(`/api/admin/users/${id}/clear-lockout`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });

            if (res.ok) {
                showToast('User lockout cleared successfully', 'success');
                const activeTab = document.querySelector('.tab-pane:not(.hidden)');
                if (activeTab && activeTab.id === 'tab-reset-password') {
                    fetchResetPassUsers(resetPassCurrentPage);
                } else {
                    fetchUsers(userCurrentPage);
                }
            } else {
                const err = await res.json();
                showToast(err.msg || 'Error clearing lockout', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Network error', 'error');
        }
    };

    window.openForceResetModal = function(id) {
        const user = gManagedUsers.find(u => u.id === id);
        if (!user) return;

        const modal = document.getElementById('forceResetModal');
        const content = document.getElementById('forceResetModalContent');
        const proceedBtn = document.getElementById('confirmForceResetBtn');
        const msg = document.getElementById('forceResetModalMessage');
        const checkbox = document.getElementById('invalidateSessions');

        msg.innerHTML = `Are you sure you want to force a password reset for user <strong>${user.username}</strong> (#${user.user_id})? They will be prompted to change it on their next login.`;
        checkbox.checked = false; // Default unchecked

        const onConfirm = () => {
            forcePasswordReset(id, checkbox.checked);
            closeForceResetModal();
            proceedBtn.removeEventListener('click', onConfirm);
        };

        // Remove existing listener if any (from previous opens)
        const newBtn = proceedBtn.cloneNode(true);
        proceedBtn.parentNode.replaceChild(newBtn, proceedBtn);
        newBtn.addEventListener('click', onConfirm);

        modal.classList.remove('hidden');
        setTimeout(() => {
            modal.classList.remove('opacity-0');
            content.classList.remove('scale-95');
        }, 10);
    };

    window.closeForceResetModal = function() {
        const modal = document.getElementById('forceResetModal');
        const content = document.getElementById('forceResetModalContent');
        if (modal && content) {
            modal.classList.add('opacity-0');
            content.classList.add('scale-95');
            setTimeout(() => modal.classList.add('hidden'), 300);
        }
    };

    async function forcePasswordReset(id, invalidateSessions) {
        try {
            const res = await fetch(`/api/admin/users/${id}/force-password-reset`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${window.jwtToken}` 
                },
                body: JSON.stringify({ invalidate_sessions: invalidateSessions })
            });

            const data = await res.json();

            if (res.ok) {
                showToast('Success', data.msg, 'success');
                fetchUsers(userCurrentPage);
            } else {
                showToast('Error', data.msg || 'Failed to force password reset', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Network Error', 'Failed to connect to the server', 'error');
        }
    }

    // === RESET PASSWORD MANAGEMENT LOGIC ===
    let resetPassCurrentPage = 1;
    let gResetPassUsers = [];

    async function fetchResetPassUsers(page = 1) {
        const searchInput = document.getElementById('resetPassSearchInput');
        const search = searchInput ? searchInput.value : '';
        try {
            const res = await fetch(`/api/admin/users?page=${page}&search=${encodeURIComponent(search)}`, {
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            if (res.ok) {
                const data = await res.json();
                gResetPassUsers = data.users;
                renderResetPassTable(data.users);
                renderResetPassPagination(data);
                resetPassCurrentPage = data.current_page;
            } else {
                const tbody = document.getElementById('resetPassTableBody');
                if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="p-8 text-center text-red-500 font-medium whitespace-nowrap">Error loading users (${res.status})</td></tr>`;
            }
        } catch (e) {
            const tbody = document.getElementById('resetPassTableBody');
            if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="p-8 text-center text-red-500 font-medium whitespace-nowrap">Network error loading users</td></tr>`;
        }
    }
    window.fetchResetPassUsers = fetchResetPassUsers;

    function renderResetPassTable(users) {
        const tbody = document.getElementById('resetPassTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-gray-400 font-medium whitespace-nowrap">No users matched your search.</td></tr>';
            return;
        }

        users.forEach(u => {
            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-50/50 dark:hover:bg-gray-800/20 transition-colors border-b border-gray-100 dark:border-gray-800";
            tr.innerHTML = `
                <td class="px-4 py-3 font-mono font-bold text-primary uppercase tracking-wider">#${u.user_id}</td>
                <td class="px-4 py-3 font-bold text-gray-900 dark:text-white">${u.username}</td>
                <td class="px-4 py-3">${u.email}</td>
                <td class="px-4 py-3">
                    <span class="inline-flex items-center px-1.5 py-0.5 rounded-full text-[8px] font-bold uppercase tracking-wider ${u.is_active ? 'bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400 border border-green-100' : 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400 border border-red-100'}">
                        ${u.is_active ? 'Active' : 'Disabled'}
                    </span>
                </td>
                <td class="px-4 py-3 text-right whitespace-nowrap">
                    ${u.is_admin ? '<span class="text-[9px] text-gray-400 italic">Admin protected</span>' : `
                        <button onclick="openResetTabPasswordModal(${u.id})" class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white text-[10px] font-bold uppercase tracking-wider rounded transition-all shadow-sm shadow-amber-500/20" title="Reset Password">
                            <span class="material-symbols-outlined text-[14px]">key</span> Reset
                        </button>
                        <button onclick="openResetTabClearLockout(${u.id})" class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-[10px] font-bold uppercase tracking-wider rounded transition-all shadow-sm shadow-green-500/20 ml-1" title="Clear Lockout">
                            <span class="material-symbols-outlined text-[14px]">restart_alt</span> Unlock
                        </button>
                    `}
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    window.openResetTabPasswordModal = function(id) {
        const user = gResetPassUsers.find(u => u.id === id);
        if (user) {
            if (!gManagedUsers.find(u => u.id === id)) gManagedUsers.push(user);
            window.openChangePasswordModal(id);
        }
    }

    window.openResetTabForceResetModal = function(id) {
        const user = gResetPassUsers.find(u => u.id === id);
        if (user) {
            if (!gManagedUsers.find(u => u.id === id)) gManagedUsers.push(user);
            window.openForceResetModal(id);
        }
    }

    window.openResetTabClearLockout = function(id) {
        const user = gResetPassUsers.find(u => u.id === id);
        if (user) {
            if (!gManagedUsers.find(u => u.id === id)) gManagedUsers.push(user);
            window.clearUserLockout(id);
        }
    }

    function renderResetPassPagination(data) {
        const info = document.getElementById('resetPassPaginationInfo');
        if (!info) return;
        const start = data.total > 0 ? (data.current_page - 1) * 8 + 1 : 0;
        const end = Math.min(data.current_page * 8, data.total);
        info.innerText = `Showing ${start} to ${end} of ${data.total} users`;

        const buttons = document.getElementById('resetPassPaginationButtons');
        if (!buttons) return;
        buttons.innerHTML = '';

        const prev = document.createElement('button');
        prev.className = `p-1.5 rounded border transition-all ${data.current_page > 1 ? 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800' : 'opacity-30 cursor-not-allowed border-gray-100 dark:border-gray-800'}`;
        prev.innerHTML = '<span class="material-symbols-outlined text-sm block">chevron_left</span>';
        if (data.current_page > 1) prev.onclick = () => fetchResetPassUsers(data.current_page - 1);
        buttons.appendChild(prev);

        for (let i = 1; i <= data.pages; i++) {
            if (data.pages > 5 && i > 2 && i < data.pages - 1 && Math.abs(i - data.current_page) > 1) {
                if (i === 3 || i === data.pages - 1) {
                    const dot = document.createElement('span');
                    dot.innerText = '...';
                    dot.className = "px-2 text-gray-400";
                    buttons.appendChild(dot);
                }
                continue;
            }
            const btn = document.createElement('button');
            btn.className = `min-w-[28px] h-7 rounded text-[10px] font-bold border transition-all ${i === data.current_page ? 'bg-primary text-white border-primary shadow-sm shadow-primary/20' : 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800'}`;
            btn.innerText = i;
            btn.onclick = () => fetchResetPassUsers(i);
            buttons.appendChild(btn);
        }

        const next = document.createElement('button');
        next.className = `p-1.5 rounded border transition-all ${data.current_page < data.pages ? 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800' : 'opacity-30 cursor-not-allowed border-gray-100 dark:border-gray-800'}`;
        next.innerHTML = '<span class="material-symbols-outlined text-sm block">chevron_right</span>';
        if (data.current_page < data.pages) next.onclick = () => fetchResetPassUsers(data.current_page + 1);
        buttons.appendChild(next);
    }

    // Generic Toast Function (if not defined globally in base.html)
    function showToast(message, type = 'info') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
            return;
        }
        const toast = document.createElement('div');
        toast.className = `p-3 rounded-lg shadow-lg mb-2 text-xs font-bold text-white ${type === 'error' ? 'bg-red-500' : 'bg-green-500'} flex items-center justify-between w-64 translate-x-full transition-transform duration-300`;
        toast.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()" class="text-white hover:text-gray-200"><span class="material-symbols-outlined text-[14px]">close</span></button>`;
        if (toastContainer) {
            toastContainer.appendChild(toast);
            setTimeout(() => toast.classList.remove('translate-x-full'), 10);
            setTimeout(() => {
                toast.classList.add('translate-x-full');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        } else {
            alert(message);
        }
    }

    // === ROLES LOGIC ===
    async function fetchRoles() {
        try {
            const res = await fetch('/api/admin/roles', { headers: { 'Authorization': `Bearer ${window.jwtToken}` } });
            if (res.ok) {
                gRoles = await res.json();
                renderRoles();
                renderRoleCheckboxes(); // Used for mappings tab
            } else {
                showToast('Failed to fetch roles', 'error');
            }
        } catch (e) {
            console.error(e);
        }
    }
    window.fetchRoles = fetchRoles;

    function renderRoles() {
        const tbody = document.getElementById('rolesTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (gRoles.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center p-4">No roles found.</td></tr>';
            return;
        }

        gRoles.forEach(r => {
            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-50/50 dark:hover:bg-gray-800/20 transition-colors";
            tr.innerHTML = `
                <td class="p-3 text-[11px] text-gray-500 font-mono">#${r.id}</td>
                <td class="p-3 text-[11px] font-bold"><span class="bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 px-2 py-0.5 rounded border border-blue-100 dark:border-blue-800 uppercase tracking-widest">${r.name}</span></td>
                <td class="p-3 text-[11px] text-gray-600 dark:text-gray-400">${r.description || '-'}</td>
                <td class="p-3 text-right">
                    <button onclick="openRolePermissionModal(${r.id})" class="text-gray-400 hover:text-primary transition-colors p-1" title="Manage Permissions"><span class="material-symbols-outlined text-[16px]">security</span></button>
                    <button onclick="openRoleMenuModal(${r.id})" class="text-gray-400 hover:text-primary transition-colors p-1 ml-1" title="Assign Menus"><span class="material-symbols-outlined text-[16px]">account_tree</span></button>
                    <button onclick="editRole(${r.id})" class="text-gray-400 hover:text-primary transition-colors p-1 ml-1" title="Edit Role"><span class="material-symbols-outlined text-[16px]">edit</span></button>
                    ${r.name !== 'ADMIN' ? `<button onclick="deleteRole(${r.id})" class="text-gray-400 hover:text-red-500 transition-colors p-1 ml-1" title="Delete"><span class="material-symbols-outlined text-[16px]">delete</span></button>` : ''}
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    window.openRoleModal = function (role = null) {
        const modal = document.getElementById('roleModal');
        const content = document.getElementById('roleModalContent');
        if (role) {
            document.getElementById('roleModalTitle').innerText = 'Edit Role';
            document.getElementById('roleId').value = role.id;
            document.getElementById('roleName').value = role.name;
            document.getElementById('roleDesc').value = role.description || '';
        } else {
            document.getElementById('roleModalTitle').innerText = 'Create New Role';
            const roleForm = document.getElementById('roleForm');
            if (roleForm) roleForm.reset();
            document.getElementById('roleId').value = '';
        }
        if (modal && content) {
            modal.classList.remove('hidden');
            setTimeout(() => { modal.classList.remove('opacity-0'); content.classList.remove('scale-95'); }, 10);
        }
    };

    window.closeRoleModal = function () {
        const modal = document.getElementById('roleModal');
        const content = document.getElementById('roleModalContent');
        if (modal && content) {
            modal.classList.add('opacity-0');
            content.classList.add('scale-95');
            setTimeout(() => modal.classList.add('hidden'), 300);
        }
    };

    window.editRole = function (id) {
        const role = gRoles.find(r => r.id === id);
        if (role) window.openRoleModal(role);
    };

    window.saveRole = async function () {
        const id = document.getElementById('roleId').value;
        const name = document.getElementById('roleName').value.toUpperCase();
        const desc = document.getElementById('roleDesc').value;

        const payload = { name: name, description: desc };
        const method = id ? 'PUT' : 'POST';
        const url = id ? `/api/admin/roles/${id}` : '/api/admin/roles';

        try {
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${window.jwtToken}` },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                showToast(`Role ${id ? 'updated' : 'created'} successfully`, 'success');
                window.closeRoleModal();
                fetchRoles();
            } else {
                const err = await res.json();
                showToast(err.msg || 'Error saving role', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Network error', 'error');
        }
    };

    window.deleteRole = async function (id) {
        if (!confirm('Are you sure you want to delete this role? This might break user access.')) return;
        try {
            const res = await fetch(`/api/admin/roles/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            if (res.ok) {
                showToast('Role deleted', 'success');
                fetchRoles();
            } else {
                showToast('Error deleting role', 'error');
            }
        } catch (e) { console.error(e); }
    };

    // --- ROLE-MENU MAPPING LOGIC ---
    let currentMappingRoleId = null;

    window.openRoleMenuModal = async function (roleId) {
        const role = gRoles.find(r => r.id === roleId);
        if (!role) return;

        currentMappingRoleId = roleId;
        document.getElementById('mappingRoleName').innerText = `ROLE: ${role.name}`;

        // Fetch menus if not loaded
        if (typeof gMenus === 'undefined' || gMenus.length === 0) {
            await fetchMenus();
        }

        // Populate grid with all menus
        renderMenuMappingGrid();

        // Show modal
        const modal = document.getElementById('roleMenuModal');
        const content = document.getElementById('roleMenuModalContent');
        if (modal && content) {
            modal.classList.remove('hidden');
            setTimeout(() => { modal.classList.remove('opacity-0'); content.classList.remove('scale-95'); }, 10);
        }

        try {
            const res = await fetch(`/api/admin/roles/${roleId}/menus`, { headers: { 'Authorization': `Bearer ${window.jwtToken}` } });
            if (res.ok) {
                const assignedMenuIds = await res.json();
                document.querySelectorAll('.role-menu-checkbox').forEach(cb => {
                    cb.checked = assignedMenuIds.includes(parseInt(cb.value));
                });
            } else {
                console.error('Failed to fetch assigned menus for role:', res.status, res.statusText);
            }
        } catch (e) { console.error(e); }
    };

    function renderMenuMappingGrid() {
        const grid = document.getElementById('menuMappingGrid');
        if (!grid) return;
        grid.innerHTML = '';

        gMenus.forEach(m => {
            const div = document.createElement('div');
            div.className = "flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-800/50 rounded border border-gray-100 dark:border-gray-800 text-[10px]";
            div.innerHTML = `
                <input type="checkbox" value="${m.id}" class="role-menu-checkbox size-3 rounded border-gray-300 dark:border-gray-700 text-primary focus:ring-primary">
                <div class="flex flex-col">
                    <span class="font-bold text-gray-700 dark:text-gray-200">${m.title}</span>
                    <span class="text-[9px] text-gray-400">${m.url || 'No URL'}</span>
                </div>
            `;
            grid.appendChild(div);
        });
    }

    window.closeRoleMenuModal = function () {
        const modal = document.getElementById('roleMenuModal');
        const content = document.getElementById('roleMenuModalContent');
        if (modal && content) {
            modal.classList.add('opacity-0');
            content.classList.add('scale-95');
            setTimeout(() => modal.classList.add('hidden'), 300);
        }
    };

    const saveRoleMenusBtn = document.getElementById('saveRoleMenusBtn');
    if (saveRoleMenusBtn) {
        saveRoleMenusBtn.addEventListener('click', async () => {
            if (!currentMappingRoleId) return;

            const selectedMenuIds = Array.from(document.querySelectorAll('.role-menu-checkbox:checked')).map(cb => parseInt(cb.value));

            try {
                const res = await fetch(`/api/admin/roles/${currentMappingRoleId}/menus`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${window.jwtToken}` },
                    body: JSON.stringify({ menu_ids: selectedMenuIds })
                });

                if (res.ok) {
                    showToast('Role menus updated', 'success');
                    window.closeRoleMenuModal();
                } else {
                    showToast('Error updating mappings', 'error');
                }
            } catch (e) {
                console.error(e);
            }
        });
    }

    // === MENUS LOGIC ===
    async function fetchMenus() {
        try {
            const res = await fetch('/api/admin/menus', { headers: { 'Authorization': `Bearer ${window.jwtToken}` } });
            if (res.ok) {
                gMenus = await res.json();
                renderMenus();
                populateParentSelect();
            } else {
                showToast('Failed to fetch menus', 'error');
            }
        } catch (e) { console.error(e); }
    }
    window.fetchMenus = fetchMenus;

    function renderMenus() {
        const tbody = document.getElementById('menusTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (gMenus.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center p-4">No menus found.</td></tr>';
            return;
        }

        gMenus.sort((a, b) => a.sort_order - b.sort_order);

        gMenus.forEach(m => {
            const parentLabel = m.parent_id ? ` <span class="text-[9px] text-gray-400 font-normal ml-2">└ Child of #${m.parent_id}</span>` : '';
            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-50/50 dark:hover:bg-gray-800/20 transition-colors";
            tr.innerHTML = `
                <td class="p-3 text-[11px] text-gray-500 font-mono">#${m.id}</td>
                <td class="p-3 text-[11px] font-bold flex items-center gap-2 text-gray-900 dark:text-white">
                    <span class="material-symbols-outlined text-primary text-[16px]">${m.icon || 'folder'}</span>
                    ${m.title} ${parentLabel}
                </td>
                <td class="p-3 text-[11px] font-mono text-gray-500">${m.url || '-'}</td>
                <td class="p-3 text-[10px]"><span class="bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 px-2 py-0.5 rounded border border-gray-200 dark:border-gray-700">${m.permission_required || 'None'}</span></td>
                <td class="p-3 text-[11px] text-gray-500">${m.sort_order}</td>
                <td class="p-3 text-right">
                    <button onclick="window.editMenu(${m.id})" class="text-gray-400 hover:text-primary transition-colors p-1" title="Edit"><span class="material-symbols-outlined text-[16px]">edit</span></button>
                    ${m.url !== '/' ? `<button onclick="window.deleteMenu(${m.id})" class="text-gray-400 hover:text-red-500 transition-colors p-1 ml-1" title="Delete"><span class="material-symbols-outlined text-[16px]">delete</span></button>` : ''}
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    function populateParentSelect() {
        const sel = document.getElementById('menuParent');
        if (!sel) return;
        sel.innerHTML = '<option value="">None (Top Level)</option>';
        gMenus.filter(m => !m.parent_id).forEach(m => {
            sel.innerHTML += `<option value="${m.id}">${m.title}</option>`;
        });
    }

    window.openMenuModal = function (menu = null) {
        const modal = document.getElementById('menuModal');
        const content = document.getElementById('menuModalContent');
        if (menu) {
            document.getElementById('menuModalTitle').innerText = 'Edit Menu';
            document.getElementById('menuId').value = menu.id;
            document.getElementById('menuTitle').value = menu.title;
            document.getElementById('menuUrl').value = menu.url || '';
            document.getElementById('menuIcon').value = menu.icon || '';
            document.getElementById('menuOrder').value = menu.sort_order;
            document.getElementById('menuParent').value = menu.parent_id || '';
            document.getElementById('menuPerm').value = menu.permission_required || '';
        } else {
            document.getElementById('menuModalTitle').innerText = 'Create New Menu';
            const menuForm = document.getElementById('menuForm');
            if (menuForm) menuForm.reset();
            document.getElementById('menuId').value = '';
        }
        if (modal && content) {
            modal.classList.remove('hidden');
            setTimeout(() => { modal.classList.remove('opacity-0'); content.classList.remove('scale-95'); }, 10);
        }
    };

    window.closeMenuModal = function () {
        const modal = document.getElementById('menuModal');
        const content = document.getElementById('menuModalContent');
        if (modal && content) {
            modal.classList.add('opacity-0');
            content.classList.add('scale-95');
            setTimeout(() => modal.classList.add('hidden'), 300);
        }
    };

    window.editMenu = function (id) {
        const menu = gMenus.find(m => m.id === id);
        if (menu) window.openMenuModal(menu);
    };

    window.saveMenu = async function () {
        const id = document.getElementById('menuId').value;
        const payload = {
            title: document.getElementById('menuTitle').value,
            url: document.getElementById('menuUrl').value,
            icon: document.getElementById('menuIcon').value,
            sort_order: parseInt(document.getElementById('menuOrder').value) || 0,
            parent_id: document.getElementById('menuParent').value ? parseInt(document.getElementById('menuParent').value) : null,
            permission_required: document.getElementById('menuPerm').value || null
        };

        const method = id ? 'PUT' : 'POST';
        const url = id ? `/api/admin/menus/${id}` : '/api/admin/menus';

        try {
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${window.jwtToken}` },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                showToast(`Menu ${id ? 'updated' : 'created'} successfully. Sidebar layout refreshed inside system. Refresh browser to see full effect on left rail if it was cached.`, 'success');
                window.closeMenuModal();
                fetchMenus();
            } else {
                const err = await res.json();
                showToast(err.msg || 'Error saving menu', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Network error', 'error');
        }
    };

    window.deleteMenu = async function (id) {
        if (!confirm('Delete this menu item? Children will also be cascade deleted.')) return;
        try {
            const res = await fetch(`/api/admin/menus/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            if (res.ok) {
                showToast('Menu deleted', 'success');
                fetchMenus();
            } else {
                showToast('Error deleting menu', 'error');
            }
        } catch (e) { console.error(e); }
    };


    // === MAPPINGS LOGIC ===
    function renderRoleCheckboxes() {
        const grid = document.getElementById('rolesGrid');
        if (!grid) return;
        grid.innerHTML = '';
        gRoles.forEach(r => {
            grid.innerHTML += `
                <label class="flex items-start p-3 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded cursor-pointer hover:border-primary transition-colors shadow-sm">
                    <div class="flex items-center h-5">
                        <input type="checkbox" value="${r.id}" class="role-checkbox form-checkbox h-4 w-4 text-primary bg-gray-50 border-gray-300 rounded focus:ring-primary focus:ring-2">
                    </div>
                    <div class="ml-3 text-sm flex-1">
                        <label class="font-bold text-[11px] uppercase tracking-wider text-gray-900 dark:text-white cursor-pointer">${r.name}</label>
                        <p class="text-gray-500 text-[10px] mt-0.5 leading-tight">${r.description || 'No description'}</p>
                    </div>
                </label>
            `;
        });
    }

    window.searchUser = async function () {
        const input = document.getElementById('userInput').value;
        if (!input || input.length < 2) return showToast('Enter at least 2 characters', 'warning');

        try {
            const res = await fetch(`/api/admin/users/search?q=${encodeURIComponent(input)}`, {
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            const users = await res.json();

            if (users.length === 0) {
                showToast('No users found', 'info');
                return;
            }

            // For simplicity, we auto-select the first one if it's an exact match or only one result
            const user = users[0];
            selectUser(user);
        } catch (e) {
            console.error(e);
            showToast('Search failed', 'error');
        }
    };

    async function selectUser(user) {
        const selectedUsername = document.getElementById('selectedUsername');
        const selectedUserEmail = document.getElementById('selectedUserEmail');
        const selectedUserId = document.getElementById('selectedUserId');
        const selectedUserBox = document.getElementById('selectedUserBox');
        const rolesSection = document.getElementById('rolesSection');

        if (selectedUsername) selectedUsername.innerText = user.username;
        if (selectedUserEmail) selectedUserEmail.innerText = user.email;
        if (selectedUserId) selectedUserId.innerText = `ID: ${user.id} (${user.user_id})`;

        if (selectedUserBox) selectedUserBox.classList.remove('hidden');
        if (rolesSection) rolesSection.classList.remove('opacity-50', 'pointer-events-none');

        currentUserTarget = user.id;

        // Fetch and pre-fill roles
        try {
            const res = await fetch(`/api/admin/users/${user.id}/roles`, {
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            const roleIds = await res.json();

            document.querySelectorAll('.role-checkbox').forEach(cb => {
                cb.checked = roleIds.includes(parseInt(cb.value));
            });
        } catch (e) {
            console.error(e);
        }
    }

    window.saveUserRoles = async function () {
        if (!currentUserTarget) return;

        const selectedRoleIds = Array.from(document.querySelectorAll('.role-checkbox:checked')).map(cb => parseInt(cb.value));

        try {
            const res = await fetch(`/api/admin/users/${currentUserTarget}/roles`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${window.jwtToken}` },
                body: JSON.stringify({ role_ids: selectedRoleIds })
            });

            if (res.ok) {
                showToast('User roles updated successfully', 'success');
            } else {
                const data = await res.json();
                showToast(data.msg || 'Error updating roles', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Network error', 'error');
        }
    };


    // Tab Switching Logic Extended
    const allTabs = {
        'status': { nav: document.getElementById('nav-status'), pane: document.getElementById('tab-status') },
        'report-status': { nav: document.getElementById('nav-report-status'), pane: document.getElementById('tab-report-status') },
        'general': { nav: document.getElementById('nav-general'), pane: null },
        'notifications': { nav: document.getElementById('nav-notifications'), pane: document.getElementById('tab-notifications') },
        'sessions': { nav: document.getElementById('nav-sessions'), pane: document.getElementById('tab-sessions') },
        'login-logs': { nav: document.getElementById('nav-login-logs'), pane: document.getElementById('tab-login-logs') },
        'download-logs': { nav: document.getElementById('nav-download-logs'), pane: document.getElementById('tab-download-logs') },
        'audit-logs': { nav: document.getElementById('nav-audit-logs'), pane: document.getElementById('tab-audit-logs') },
        'roles': { nav: document.getElementById('nav-roles'), pane: document.getElementById('tab-roles') },
        'menus': { nav: document.getElementById('nav-menus'), pane: document.getElementById('tab-menus') },
        'mappings': { nav: document.getElementById('nav-mappings'), pane: document.getElementById('tab-mappings') },
        'permissions': { nav: document.getElementById('nav-permissions'), pane: document.getElementById('tab-permissions') },
        'manage-users': { nav: document.getElementById('nav-manage-users'), pane: document.getElementById('tab-manage-users') },
        'reset-password': { nav: document.getElementById('nav-reset-password'), pane: document.getElementById('tab-reset-password') }
    };

    function switchTab(tabId) {
        Object.values(allTabs).forEach(tab => {
            if (tab.nav) {
                tab.nav.className = 'nav-tab flex items-center gap-3 px-4 py-2.5 text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800/50 text-[11px] font-bold uppercase tracking-wider rounded-lg transition-all';
            }
            if (tab.pane) {
                tab.pane.classList.add('hidden');
            }
        });

        if (allTabs[tabId]) {
            if (allTabs[tabId].nav) {
                allTabs[tabId].nav.className = 'nav-tab flex items-center gap-3 px-4 py-2.5 bg-primary/10 text-primary text-[11px] font-bold uppercase tracking-wider rounded-lg transition-all';
            }
            if (allTabs[tabId].pane) {
                allTabs[tabId].pane.classList.remove('hidden');
            }
        }

        // Execute tab specific triggers
        switch (tabId) {
            case 'sessions':
                fetchActiveUsers();
                break;
            case 'notifications':
                fetchUserNotifications();
                break;
            case 'login-logs':
                fetchLoginLogs(1);
                break;
            case 'download-logs':
                fetchDownloadLogs(1);
                break;
            case 'audit-logs':
                fetchAuditLogs(1);
                break;
            case 'roles':
                fetchRoles();
                break;
            case 'menus':
                fetchMenus();
                break;
            case 'mappings':
                if (gRoles.length === 0) fetchRoles();
                break;
            case 'permissions':
                fetchPermissions();
                break;
            case 'manage-users':
                fetchUsers();
                break;
            case 'reset-password':
                fetchResetPassUsers();
                break;
        }

        // Update URL parameter without reloading
        if (history.pushState) {
            const newurl = window.location.protocol + "//" + window.location.host + window.location.pathname + '?tab=' + tabId;
            window.history.pushState({ path: newurl }, '', newurl);
        }
    }

    window.debounce = function (func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    };

    // Bind click handlers dynamically
    Object.keys(allTabs).forEach(tabId => {
        const tab = allTabs[tabId];
        if (tab.nav) {
            tab.nav.addEventListener('click', (e) => {
                e.preventDefault();
                switchTab(tabId);
            });
        }
    });


    // Permission Management Logic
    let currentPermissionPage = 1;
    async function fetchPermissions(page = 1) {
        currentPermissionPage = page;
        const permissionSearchInput = document.getElementById('permissionSearchInput');
        const search = permissionSearchInput ? permissionSearchInput.value : '';
        try {
            const response = await fetch(`/api/admin/permissions?page=${page}&per_page=8&search=${encodeURIComponent(search)}`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
            });
            if (response.ok) {
                const data = await response.json();
                renderPermissionsTable(data.permissions);
                renderPermissionPagination(data);
            }
        } catch (error) {
            console.error('Error fetching permissions:', error);
        }
    }
    window.fetchPermissions = fetchPermissions;

    function renderPermissionsTable(perms) {
        const tbody = document.getElementById('permissionsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (perms.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="p-8 text-center text-gray-400 font-medium whitespace-nowrap">No permissions found.</td></tr>';
            return;
        }

        perms.forEach(p => {
            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-50/50 dark:hover:bg-gray-800/20 transition-colors border-b border-gray-100 dark:border-gray-800";
            tr.innerHTML = `
                <td class="px-4 py-3 font-mono text-gray-400">#${p.id}</td>
                <td class="px-4 py-3"><span class="px-2 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded text-[10px] font-bold border border-blue-100 dark:border-blue-800/30">${p.name}</span></td>
                <td class="px-4 py-3 text-gray-500">${p.description || 'No description'}</td>
                <td class="px-4 py-3 text-right whitespace-nowrap">
                    <button onclick="window.openPermissionModal(${JSON.stringify(p).replace(/"/g, '&quot;')})" class="text-gray-400 hover:text-primary transition-colors p-1" title="Edit Permission"><span class="material-symbols-outlined text-[16px]">edit</span></button>
                    <button onclick="window.deletePermission(${p.id})" class="text-gray-400 hover:text-red-500 transition-colors p-1 ml-1" title="Delete Permission"><span class="material-symbols-outlined text-[16px]">delete</span></button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderPermissionPagination(data) {
        const info = document.getElementById('permissionPaginationInfo');
        if (!info) return;
        const start = data.total > 0 ? (data.current_page - 1) * 8 + 1 : 0;
        const end = Math.min(data.current_page * 8, data.total);
        info.innerText = `Showing ${start} to ${end} of ${data.total} permissions`;

        const buttons = document.getElementById('permissionPaginationButtons');
        if (!buttons) return;
        buttons.innerHTML = '';

        // Previous
        const prevBtn = document.createElement('button');
        prevBtn.className = `px-2 py-1 rounded border text-[10px] font-bold transition-colors ${data.current_page > 1 ? 'border-gray-200 hover:bg-gray-100 text-gray-600' : 'border-gray-100 text-gray-300 cursor-not-allowed'}`;
        prevBtn.innerHTML = '<span class="material-symbols-outlined text-xs">chevron_left</span>';
        if (data.current_page > 1) prevBtn.onclick = () => fetchPermissions(data.current_page - 1);
        buttons.appendChild(prevBtn);

        // Page numbers (limited)
        for (let i = 1; i <= data.pages; i++) {
            if (i === 1 || i === data.pages || (i >= data.current_page - 1 && i <= data.current_page + 1)) {
                const btn = document.createElement('button');
                btn.className = `px-2.5 py-1 rounded border text-[10px] font-bold transition-colors ${i === data.current_page ? 'bg-primary border-primary text-white' : 'border-gray-200 hover:bg-gray-100 text-gray-600'}`;
                btn.innerText = i;
                btn.onclick = () => fetchPermissions(i);
                buttons.appendChild(btn);
            } else if (i === data.current_page - 2 || i === data.current_page + 2) {
                const dots = document.createElement('span');
                dots.className = "px-1 text-gray-400";
                dots.innerText = "...";
                buttons.appendChild(dots);
            }
        }

        // Next
        const nextBtn = document.createElement('button');
        nextBtn.className = `px-2 py-1 rounded border text-[10px] font-bold transition-colors ${data.current_page < data.pages ? 'border-gray-200 hover:bg-gray-100 text-gray-600' : 'border-gray-100 text-gray-300 cursor-not-allowed'}`;
        nextBtn.innerHTML = '<span class="material-symbols-outlined text-xs">chevron_right</span>';
        if (data.current_page < data.pages) nextBtn.onclick = () => fetchPermissions(data.current_page + 1);
        buttons.appendChild(nextBtn);
    }

    window.filterPermissions = window.debounce(() => fetchPermissions(1), 500);

    window.openPermissionModal = function (perm = null) {
        const modal = document.getElementById('permissionModal');
        const title = document.getElementById('permissionModalTitle');
        const content = document.getElementById('permissionModalContent');

        const permissionForm = document.getElementById('permissionForm');
        if (permissionForm) permissionForm.reset();

        if (perm) {
            title.innerText = 'Edit Permission';
            document.getElementById('managePermissionId').value = perm.id;
            document.getElementById('managePermissionName').value = perm.name;
            document.getElementById('managePermissionDescription').value = perm.description;
        } else {
            title.innerText = 'Create New Permission';
            document.getElementById('managePermissionId').value = '';
        }

        if (modal && content) {
            modal.classList.remove('hidden');
            setTimeout(() => {
                modal.classList.remove('opacity-0');
                content.classList.remove('scale-95');
            }, 10);
        }
    };

    window.closePermissionModal = function () {
        const modal = document.getElementById('permissionModal');
        const content = document.getElementById('permissionModalContent');
        if (modal && content) {
            modal.classList.add('opacity-0');
            content.classList.add('scale-95');
            setTimeout(() => modal.classList.add('hidden'), 300);
        }
    };

    window.savePermission = async function () {
        const id = document.getElementById('managePermissionId').value;
        const name = document.getElementById('managePermissionName').value;
        const description = document.getElementById('managePermissionDescription').value;

        const url = id ? `/api/admin/permissions/${id}` : '/api/admin/permissions';
        const method = id ? 'PUT' : 'POST';

        try {
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify({ name, description })
            });

            if (response.ok) {
                showToast(id ? 'Permission updated' : 'Permission created', 'success');
                window.closePermissionModal();
                fetchPermissions(currentPermissionPage);
            } else {
                const data = await response.json();
                showToast(data.msg || 'Save failed', 'error');
            }
        } catch (error) {
            showToast('Network error', 'error');
        }
    };

    window.deletePermission = async function (id) {
        if (!confirm('Are you sure you want to delete this permission? This may affect roles using it.')) return;
        try {
            const response = await fetch(`/api/admin/permissions/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
            });
            if (response.ok) {
                showToast('Permission deleted', 'success');
                fetchPermissions(currentPermissionPage);
            }
        } catch (error) {
            showToast('Network error', 'error');
        }
    };

    // --- ROLE-PERMISSION MAPPING LOGIC ---
    let currentMappingRolePermId = null;
    let gAllPermissions = [];

    window.openRolePermissionModal = async function (roleId) {
        const role = gRoles.find(r => r.id === roleId);
        if (!role) return;

        currentMappingRolePermId = roleId;
        document.getElementById('permMappingRoleName').innerText = `ROLE: ${role.name}`;

        // Fetch all permissions if not already loaded (or refresh)
        try {
            const res = await fetch('/api/admin/permissions?per_page=100', {
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            if (res.ok) {
                const data = await res.json();
                gAllPermissions = data.permissions;
            }
        } catch (e) {
            console.error('Failed to fetch permissions', e);
        }

        renderPermissionMappingGrid();

        // Show modal
        const modal = document.getElementById('rolePermissionModal');
        const content = document.getElementById('rolePermissionModalContent');
        if (modal && content) {
            modal.classList.remove('hidden');
            setTimeout(() => { modal.classList.remove('opacity-0'); content.classList.remove('scale-95'); }, 10);
        }

        // Fetch assigned permissions
        try {
            const res = await fetch(`/api/admin/roles/${roleId}/permissions`, {
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            if (res.ok) {
                const assignedPermIds = await res.json();
                document.querySelectorAll('.role-perm-checkbox').forEach(cb => {
                    cb.checked = assignedPermIds.includes(parseInt(cb.value));
                });
            }
        } catch (e) {
            console.error('Failed to fetch assigned permissions', e);
        }
    };

    function renderPermissionMappingGrid() {
        const grid = document.getElementById('permissionMappingGrid');
        if (!grid) return;
        grid.innerHTML = '';

        gAllPermissions.forEach(p => {
            const div = document.createElement('div');
            div.className = "flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-800/50 rounded border border-gray-100 dark:border-gray-800 text-[10px]";
            div.innerHTML = `
                <input type="checkbox" value="${p.id}" class="role-perm-checkbox size-3 rounded border-gray-300 dark:border-gray-700 text-primary focus:ring-primary">
                <div class="flex flex-col">
                    <span class="font-bold text-gray-700 dark:text-gray-200">${p.name}</span>
                    <span class="text-[9px] text-gray-400">${p.description || 'No description'}</span>
                </div>
            `;
            grid.appendChild(div);
        });
    }

    window.closeRolePermissionModal = function () {
        const modal = document.getElementById('rolePermissionModal');
        const content = document.getElementById('rolePermissionModalContent');
        if (modal && content) {
            modal.classList.add('opacity-0');
            content.classList.add('scale-95');
            setTimeout(() => modal.classList.add('hidden'), 300);
        }
    };

    const saveRolePermissionsBtn = document.getElementById('saveRolePermissionsBtn');
    if (saveRolePermissionsBtn) {
        saveRolePermissionsBtn.addEventListener('click', async () => {
            if (!currentMappingRolePermId) return;

            const selectedPermIds = Array.from(document.querySelectorAll('.role-perm-checkbox:checked')).map(cb => parseInt(cb.value));

            try {
                const res = await fetch(`/api/admin/roles/${currentMappingRolePermId}/permissions`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${window.jwtToken}` },
                    body: JSON.stringify({ permission_ids: selectedPermIds })
                });

                if (res.ok) {
                    showToast('Role permissions updated', 'success');
                    window.closeRolePermissionModal();
                } else {
                    const data = await res.json();
                    showToast(data.msg || 'Error updating mappings', 'error');
                }
            } catch (e) {
                console.error(e);
                showToast('Network error', 'error');
            }
        });
    }

    // Active Users Fetch Logic
    const refreshUsersBtn = document.getElementById('refresh-users-btn');
    const activeUsersTbody = document.getElementById('active-users-tbody');

    if (refreshUsersBtn) {
        refreshUsersBtn.addEventListener('click', fetchActiveUsers);
    }

    // Active Users Pagination State
    let currentActiveUsersPage = 1;
    const activeUsersPerPage = 12;
    let allActiveUsers = [];

    async function fetchActiveUsers() {
        if (typeof window.socket === 'undefined' || !window.socket.connected) {
            if (activeUsersTbody) activeUsersTbody.innerHTML = `<tr><td colspan="5" class="px-4 py-6 text-center text-red-500">Socket connection offline</td></tr>`;
            return;
        }

        if (activeUsersTbody) activeUsersTbody.innerHTML = `<tr><td colspan="5" class="px-4 py-6 text-center text-gray-400"><span class="material-symbols-outlined animate-spin inline-block text-lg align-middle mr-2">sync</span> Refreshing...</td></tr>`;

        window.socket.emit('get_active_users', {}, async (response) => {
            if (!activeUsersTbody) return;

            if (!response || !response.users || response.users.length === 0) {
                activeUsersTbody.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-gray-500">No active users found.</td></tr>`;
                allActiveUsers = [];
                renderActiveUsersPagination();
                return;
            }

            allActiveUsers = response.users;
            currentActiveUsersPage = 1; // Reset to page 1 on refresh
            renderActiveUsers();
        });
    }

    async function renderActiveUsers() {
        if (!activeUsersTbody) return;
        activeUsersTbody.innerHTML = '';

        const start = (currentActiveUsersPage - 1) * activeUsersPerPage;
        const end = Math.min(start + activeUsersPerPage, allActiveUsers.length);
        const usersToDisplay = allActiveUsers.slice(start, end);

        const userIds = usersToDisplay.map(u => u.user_id).filter(id => id && id !== 'Guest' && id !== 'N/A');
        let userNamesMap = {};

        if (userIds.length > 0) {
            try {
                const res = await fetch('/api/admin/users/batch', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                    },
                    body: JSON.stringify({ user_ids: userIds })
                });
                if (res.ok) {
                    userNamesMap = await res.json();
                }
            } catch (e) {
                console.error("Failed to fetch user details", e);
            }
        }

        usersToDisplay.forEach((user, index) => {
            const actualIndex = start + index + 1;
            let displayUsername = user.username && user.username !== 'Unknown' && user.username !== 'Guest' ? user.username : 'Unknown';
            let displayUserId = user.user_id || 'N/A';

            if (userNamesMap[user.user_id]) {
                displayUsername = userNamesMap[user.user_id].username;
                displayUserId = userNamesMap[user.user_id].user_id;
            }

            let timeString = 'Just now';
            if (user.connected_at) {
                const connectedDate = new Date(user.connected_at);
                const istOptions = {
                    timeZone: 'Asia/Kolkata', year: 'numeric', month: 'short', day: 'numeric',
                    hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true
                };
                const formattedDate = connectedDate.toLocaleString('en-IN', istOptions);
                const diffMs = new Date() - connectedDate;
                const diffMins = Math.floor(diffMs / 60000);
                const diffHours = Math.floor(diffMins / 60);
                const diffDays = Math.floor(diffHours / 24);

                let timeAgo = diffMins < 1 ? 'Just now' : diffMins < 60 ? `${diffMins} Min ago` : diffHours < 24 ? `${diffHours} Hr${diffHours > 1 ? 's' : ''} ago` : `${diffDays} Day${diffDays > 1 ? 's' : ''} ago`;
                timeString = timeAgo === 'Just now' ? 'Just now' : `${formattedDate} ( ${timeAgo} )`;
            }

            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-50/50 dark:hover:bg-gray-800/20";
            tr.innerHTML = `
                <td class="px-4 py-3 font-medium text-center">${actualIndex}</td>
                <td class="px-4 py-3 font-semibold text-gray-900 dark:text-white">
                    <div class="flex items-center gap-2">
                        <div class="size-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-[10px] font-bold">
                            ${displayUsername !== 'Unknown' && displayUsername ? displayUsername.substring(0, 2).toUpperCase() : '??'}
                        </div>
                        ${displayUsername} <span class="text-[9px] text-gray-400 font-normal">(${displayUserId})</span>
                    </div>
                </td>
                <td class="px-4 py-3 font-mono text-[10px]">${user.ip_address || 'Unknown IP'}</td>
                <td class="px-4 py-3 text-[10px]">${timeString}</td>
                <td class="px-4 py-3 font-mono text-[9px] text-gray-400 text-right"><span class="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded break-all">${user.sid}</span></td>
            `;
            activeUsersTbody.appendChild(tr);
        });

        renderActiveUsersPagination();
    }

    function renderActiveUsersPagination() {
        const total = allActiveUsers.length;
        const totalPages = Math.ceil(total / activeUsersPerPage);
        const start = total > 0 ? (currentActiveUsersPage - 1) * activeUsersPerPage + 1 : 0;
        const end = Math.min(currentActiveUsersPage * activeUsersPerPage, total);

        const info = document.getElementById('active-users-pagination-info');
        const prevBtn = document.getElementById('prev-active-users-btn');
        const nextBtn = document.getElementById('next-active-users-btn');

        if (info) info.textContent = `Showing ${start}-${end} of ${total}`;
        if (prevBtn) {
            prevBtn.disabled = currentActiveUsersPage === 1;
            prevBtn.onclick = () => {
                if (currentActiveUsersPage > 1) {
                    currentActiveUsersPage--;
                    renderActiveUsers();
                }
            };
        }
        if (nextBtn) {
            nextBtn.disabled = currentActiveUsersPage >= totalPages || total === 0;
            nextBtn.onclick = () => {
                if (currentActiveUsersPage < totalPages) {
                    currentActiveUsersPage++;
                    renderActiveUsers();
                }
            };
        }
    }

    // Handle URL params on load will be at the very bottom
    // === LOGIN LOGS LOGIC ===
    let loginLogsCurrentPage = 1;

    async function fetchLoginLogs(page = 1) {
        const tbody = document.getElementById('login-logs-tbody');
        if (!tbody) return;

        try {
            const res = await fetch(`/api/auth/login-logs?page=${page}&per_page=10`, {
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            if (res.ok) {
                const data = await res.json();
                renderLoginLogsTable(data.logs);
                renderLoginLogsPagination(data);
                loginLogsCurrentPage = data.current_page;
            } else {
                tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-red-500">Error loading logs (${res.status})</td></tr>`;
            }
        } catch (e) {
            console.error('fetchLoginLogs error:', e);
            tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-red-500">Network error loading logs</td></tr>`;
        }
    }

    function renderLoginLogsTable(logs) {
        const tbody = document.getElementById('login-logs-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-gray-400">No login logs found.</td></tr>';
            return;
        }

        logs.forEach(log => {
            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-50/50 dark:hover:bg-gray-800/20 transition-colors border-b border-gray-100 dark:border-gray-800";

            const statusClass = log.status === 'success'
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';

            const istOptions = {
                timeZone: 'Asia/Kolkata',
                year: 'numeric', month: 'numeric', day: 'numeric',
                hour: 'numeric', minute: 'numeric', second: 'numeric',
                hour12: true
            };
            const localTime = log.timestamp ? new Date(log.timestamp).toLocaleString('en-IN', istOptions) : 'N/A';

            tr.innerHTML = `
                <td class="px-4 py-3 text-gray-500 font-mono">${localTime}</td>
                <td class="px-4 py-3 font-mono text-primary font-bold">${log.user_code || '---'}</td>
                <td class="px-4 py-3 font-bold text-gray-900 dark:text-white">${log.user_name}</td>
                <td class="px-4 py-3 font-mono">${log.ip}</td>
                <td class="px-4 py-3">
                    <span class="inline-flex items-center px-1.5 py-0.5 rounded-full text-[8px] font-bold uppercase tracking-wider ${statusClass} border border-transparent">
                        ${log.status}
                    </span>
                </td>
                <td class="px-4 py-3 text-gray-400">${log.reason || '-'}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderLoginLogsPagination(data) {
        const info = document.getElementById('login-logs-pagination-info');
        if (info) {
            const start = data.total > 0 ? (data.current_page - 1) * 10 + 1 : 0;
            const end = Math.min(data.current_page * 10, data.total);
            info.innerText = `Showing ${start}-${end} of ${data.total}`;
        }

        const buttons = document.getElementById('login-logs-pagination-buttons');
        if (!buttons) return;
        buttons.innerHTML = '';

        // Prev
        const prev = document.createElement('button');
        prev.className = `p-1.5 rounded border transition-all ${data.current_page > 1 ? 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800' : 'opacity-30 cursor-not-allowed border-gray-100 dark:border-gray-800'}`;
        prev.innerHTML = '<span class="material-symbols-outlined text-sm block">chevron_left</span>';
        if (data.current_page > 1) prev.onclick = () => fetchLoginLogs(data.current_page - 1);
        buttons.appendChild(prev);

        // Next
        const next = document.createElement('button');
        next.className = `p-1.5 rounded border transition-all ${data.current_page < data.pages ? 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800' : 'opacity-30 cursor-not-allowed border-gray-100 dark:border-gray-800'}`;
        next.innerHTML = '<span class="material-symbols-outlined text-sm block">chevron_right</span>';
        if (data.current_page < data.pages) next.onclick = () => fetchLoginLogs(data.current_page + 1);
        buttons.appendChild(next);
    }

    const refreshLoginLogsBtn = document.getElementById('refresh-login-logs-btn');
    if (refreshLoginLogsBtn) {
        refreshLoginLogsBtn.onclick = () => fetchLoginLogs(loginLogsCurrentPage);
    }

    // === DOWNLOAD LOGS LOGIC ===
    let downloadLogsCurrentPage = 1;

    async function fetchDownloadLogs(page = 1) {
        const tbody = document.getElementById('download-logs-tbody');
        if (!tbody) return;

        try {
            const res = await fetch(`/api/admin/download-logs?page=${page}&per_page=10`, {
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            if (res.ok) {
                const data = await res.json();
                renderDownloadLogsTable(data.logs);
                renderDownloadLogsPagination(data);
                downloadLogsCurrentPage = data.current_page;
            } else {
                tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-red-500">Error loading logs (${res.status})</td></tr>`;
            }
        } catch (e) {
            console.error('fetchDownloadLogs error:', e);
            tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-red-500">Network error loading logs</td></tr>`;
        }
    }

    function renderDownloadLogsTable(logs) {
        const tbody = document.getElementById('download-logs-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-gray-400">No download logs found.</td></tr>';
            return;
        }

        logs.forEach(log => {
            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-50/50 dark:hover:bg-gray-800/20 transition-colors border-b border-gray-100 dark:border-gray-800";

            const istOptions = {
                timeZone: 'Asia/Kolkata',
                year: 'numeric', month: 'numeric', day: 'numeric',
                hour: 'numeric', minute: 'numeric', second: 'numeric',
                hour12: true
            };
            const localTime = log.downloaded_at ? new Date(log.downloaded_at).toLocaleString('en-IN', istOptions) : 'N/A';

            tr.innerHTML = `
                <td class="px-4 py-3 text-gray-500 font-mono">${localTime}</td>
                <td class="px-4 py-3 font-mono text-primary font-bold">${log.user_id || '---'}</td>
                <td class="px-4 py-3 font-bold text-gray-900 dark:text-white">${log.username || '-'}</td>
                <td class="px-4 py-3 font-mono text-xs truncate max-w-[200px]" title="${log.filename}">${log.filename}</td>
                <td class="px-4 py-3 font-mono">${log.ip_address}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderDownloadLogsPagination(data) {
        const info = document.getElementById('download-logs-pagination-info');
        if (info) {
            const start = data.total > 0 ? (data.current_page - 1) * 10 + 1 : 0;
            const end = Math.min(data.current_page * 10, data.total);
            info.innerText = `Showing ${start}-${end} of ${data.total}`;
        }

        const buttons = document.getElementById('download-logs-pagination-buttons');
        if (!buttons) return;
        buttons.innerHTML = '';

        const prev = document.createElement('button');
        prev.className = `p-1.5 rounded border transition-all ${data.current_page > 1 ? 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800' : 'opacity-30 cursor-not-allowed border-gray-100 dark:border-gray-800'}`;
        prev.innerHTML = '<span class="material-symbols-outlined text-sm block">chevron_left</span>';
        if (data.current_page > 1) prev.onclick = () => fetchDownloadLogs(data.current_page - 1);
        buttons.appendChild(prev);

        const next = document.createElement('button');
        next.className = `p-1.5 rounded border transition-all ${data.current_page < data.pages ? 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800' : 'opacity-30 cursor-not-allowed border-gray-100 dark:border-gray-800'}`;
        next.innerHTML = '<span class="material-symbols-outlined text-sm block">chevron_right</span>';
        if (data.current_page < data.pages) next.onclick = () => fetchDownloadLogs(data.current_page + 1);
        buttons.appendChild(next);
    }

    const refreshDownloadLogsBtn = document.getElementById('refresh-download-logs-btn');
    if (refreshDownloadLogsBtn) {
        refreshDownloadLogsBtn.onclick = () => fetchDownloadLogs(downloadLogsCurrentPage);
    }

    // === NOTIFICATIONS LOGIC ===
    async function fetchUserNotifications() {
        const notificationsList = document.getElementById('notifications-list');
        const notificationsCountInfo = document.getElementById('notifications-count-info');
        if (!notificationsList) return;

        notificationsList.innerHTML = `
            <div class="p-8 text-center text-gray-400">
                <span class="material-symbols-outlined block text-2xl mb-2 animate-spin">sync</span>
                Refreshing notifications...
            </div>
        `;

        try {
            const url = window.SETTINGS_CONFIG ? window.SETTINGS_CONFIG.notificationsUrl : '/settings/notifications';
            const response = await fetch(url);
            if (response.ok) {
                const data = await response.json();
                renderNotifications(data.notifications);
                if (notificationsCountInfo) {
                    notificationsCountInfo.innerText = `${data.notifications.length} total notifications`;
                }
            } else {
                notificationsList.innerHTML = `<div class="p-8 text-center text-red-500 font-medium whitespace-nowrap">Error loading notifications (${response.status})</div>`;
            }
        } catch (e) {
            console.error('fetchUserNotifications error:', e);
            notificationsList.innerHTML = `<div class="p-8 text-center text-red-500 font-medium whitespace-nowrap">Network error loading notifications</div>`;
        }
    }

    function renderNotifications(notifications) {
        const list = document.getElementById('notifications-list');
        if (!list) return;
        list.innerHTML = '';

        if (notifications.length === 0) {
            list.innerHTML = `
                <div class="p-12 text-center text-gray-400">
                    <span class="material-symbols-outlined block text-4xl mb-3 opacity-20">notifications_off</span>
                    <p class="text-sm font-medium">No system notifications found.</p>
                </div>
            `;
            return;
        }

        notifications.forEach(n => {
            const div = document.createElement('div');
            div.className = `p-4 hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-all ${n.is_read ? 'opacity-80' : 'border-l-4 border-l-primary bg-primary/[0.02]'}`;
            
            const typeColors = {
                success: 'text-green-500 bg-green-50 dark:bg-green-900/20',
                warning: 'text-amber-500 bg-amber-50 dark:bg-amber-900/20',
                error: 'text-red-500 bg-red-50 dark:bg-red-900/20',
                info: 'text-blue-500 bg-blue-50 dark:bg-blue-900/20',
                alert: 'text-purple-500 bg-purple-50 dark:bg-purple-900/20'
            };
            
            const colorClass = typeColors[n.notification_type] || 'text-gray-500 bg-gray-50';

            div.innerHTML = `
                <div class="flex items-start gap-4">
                    <div class="size-10 rounded-xl flex items-center justify-center shrink-0 ${colorClass}">
                        <span class="material-symbols-outlined text-xl">${n.icon || 'notifications'}</span>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center justify-between mb-1">
                            <h4 class="text-[13px] font-bold text-gray-900 dark:text-white truncate">${n.title}</h4>
                            <span class="text-[10px] font-medium text-gray-400 whitespace-nowrap">${n.time_ago}</span>
                        </div>
                        <p class="text-[12px] text-gray-500 dark:text-gray-400 leading-relaxed mb-2">${n.message}</p>
                        <div class="flex items-center gap-3">
                            <span class="text-[9px] font-black uppercase tracking-widest ${colorClass.split(' ')[0]}">${n.notification_type}</span>
                            ${n.priority === 'high' ? '<span class="text-[9px] font-black uppercase tracking-widest text-red-500 bg-red-50 dark:bg-red-900/20 px-1.5 rounded">High Priority</span>' : ''}
                            ${n.action_url ? `<a href="${n.action_url}" target="_blank" class="text-[9px] font-black uppercase tracking-widest text-primary hover:underline flex items-center gap-1"><span class="material-symbols-outlined text-[12px]">open_in_new</span> View Details</a>` : ''}
                        </div>
                    </div>
                </div>
            `;
            list.appendChild(div);
        });
    }

    const refreshNotificationsBtn = document.getElementById('refresh-notifications-btn');
    if (refreshNotificationsBtn) {
        refreshNotificationsBtn.onclick = () => fetchUserNotifications();
    }

    // --- Sync Logs Modal Logic
    const syncLogsBtn = document.getElementById('sync-logs-btn');
    const syncLogsModal = document.getElementById('syncLogsModal');
    const syncLogsTableBody = document.getElementById('syncLogsTableBody');
    const syncLogsEmpty = document.getElementById('syncLogsEmpty');
    const syncLogsLoading = document.getElementById('syncLogsLoading');
    const syncLogsMetrics = document.getElementById('syncLogsMetrics');

    if (syncLogsBtn) {
        syncLogsBtn.onclick = () => openSyncLogsModal();
    }

    function formatDuration(seconds) {
        if (!seconds || isNaN(seconds)) return '0s';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        if (mins > 0) return `${mins}m ${secs}s`;
        return `${secs}s`;
    }

    function formatDate(isoString) {
        if (!isoString) return '-';
        return new Date(isoString).toLocaleString('en-US', {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    }

    let syncLogsCurrentPage = 1;

    window.openSyncLogsModal = function() {
        if (!syncLogsModal) return;
        syncLogsModal.classList.remove('hidden');
        setTimeout(() => syncLogsModal.classList.remove('opacity-0'), 10);
        
        syncLogsCurrentPage = 1;
        fetchSyncLogsData(syncLogsCurrentPage);
    }

    window.fetchSyncLogsPage = function(delta) {
        syncLogsCurrentPage += delta;
        fetchSyncLogsData(syncLogsCurrentPage);
    }

    async function fetchSyncLogsData(page) {
        syncLogsTableBody.innerHTML = '';
        syncLogsEmpty.classList.add('hidden');
        syncLogsLoading.classList.remove('hidden');
        syncLogsMetrics.textContent = 'Loading metrics...';
        
        const prevBtn = document.getElementById('syncLogsPrevBtn');
        const nextBtn = document.getElementById('syncLogsNextBtn');
        const pageInfo = document.getElementById('syncLogsPageInfo');
        
        if (prevBtn) prevBtn.disabled = true;
        if (nextBtn) nextBtn.disabled = true;
        
        try {
            const url = `${window.SETTINGS_CONFIG.syncLogsUrl}?page=${page}&per_page=20`;
            const res = await fetch(url);
            const data = await res.json();
            
            syncLogsLoading.classList.add('hidden');
            
            if (data.status === 'success' && data.logs && data.logs.length > 0) {
                let totalSeconds = 0;
                
                data.logs.forEach(log => {
                    totalSeconds += (log.duration || 0);
                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors group';
                    
                    const statusColors = {
                        'success': 'text-green-500 bg-green-50 dark:bg-green-900/20',
                        'error': 'text-red-500 bg-red-50 dark:bg-red-900/20',
                        'processing': 'text-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    };
                    const colorClass = statusColors[log.status] || 'text-gray-500 bg-gray-50';
                    
                    tr.innerHTML = `
                        <td class="p-3 text-xs font-bold text-gray-900 dark:text-gray-100 uppercase tracking-widest whitespace-nowrap">${(log.task_name || '').replace(/_/g, ' ')}</td>
                        <td class="p-3 text-center">
                            <span class="inline-block px-2 py-1 text-[9px] font-black uppercase tracking-widest rounded ${colorClass}">${log.status}</span>
                        </td>
                        <td class="p-3 text-xs text-gray-500 dark:text-gray-400 font-medium whitespace-nowrap">${formatDate(log.start_time)}</td>
                        <td class="p-3 text-xs text-gray-500 dark:text-gray-400 font-medium whitespace-nowrap">${formatDate(log.end_time)}</td>
                        <td class="p-3 text-xs font-bold text-gray-900 dark:text-gray-100 text-right whitespace-nowrap">${formatDuration(log.duration)}</td>
                        <td class="p-3 text-xs text-gray-500 dark:text-gray-400 font-medium text-right">${log.initiated_by || 'System'}</td>
                    `;
                    syncLogsTableBody.appendChild(tr);
                });
                
                syncLogsMetrics.textContent = `Total tasks: ${data.total} • Combined duration (visible): ${formatDuration(totalSeconds)}`;
                
                if (pageInfo) pageInfo.textContent = `Page ${data.current_page} of ${data.pages}`;
                if (prevBtn) prevBtn.disabled = data.current_page <= 1;
                if (nextBtn) nextBtn.disabled = data.current_page >= data.pages;
            } else {
                syncLogsEmpty.classList.remove('hidden');
                syncLogsMetrics.textContent = 'No records found';
                if (pageInfo) pageInfo.textContent = `Page 1 of 1`;
            }
        } catch (e) {
            console.error('Failed to fetch sync logs', e);
            syncLogsLoading.classList.add('hidden');
            syncLogsEmpty.classList.remove('hidden');
            syncLogsEmpty.innerHTML = '<p class="text-sm text-red-500">Failed to load logs</p>';
            syncLogsMetrics.textContent = 'Error loading logs';
        }
    }

    window.closeSyncLogsModal = function() {
        if (!syncLogsModal) return;
        syncLogsModal.classList.add('opacity-0');
        setTimeout(() => syncLogsModal.classList.add('hidden'), 300);
    }

    // === AUDIT LOGS LOGIC ===
    let auditLogsCurrentPage = 1;

    async function fetchAuditLogs(page = 1) {
        const tbody = document.getElementById('audit-logs-tbody');
        if (!tbody) return;

        try {
            const res = await fetch(`${window.SETTINGS_CONFIG.auditLogsUrl}?page=${page}&per_page=15`, {
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            if (res.ok) {
                const data = await res.json();
                renderAuditLogsTable(data.logs);
                renderAuditLogsPagination(data);
                auditLogsCurrentPage = data.current_page;
            } else {
                tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-red-500">Error loading audit logs (${res.status})</td></tr>`;
            }
        } catch (e) {
            console.error('fetchAuditLogs error:', e);
            tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-red-500">Network error loading logs</td></tr>`;
        }
    }

    function renderAuditLogsTable(logs) {
        const tbody = document.getElementById('audit-logs-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-gray-400">No audit logs found.</td></tr>';
            return;
        }

        logs.forEach(log => {
            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-50/50 dark:hover:bg-gray-800/20 transition-colors border-b border-gray-100 dark:border-gray-800";

            const istOptions = {
                timeZone: 'Asia/Kolkata',
                year: 'numeric', month: 'numeric', day: 'numeric',
                hour: 'numeric', minute: 'numeric', second: 'numeric',
                hour12: true
            };
            const localTime = log.created_at ? new Date(log.created_at).toLocaleString('en-IN', istOptions) : 'N/A';

            // Action Badge color
            let badgeClass = 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
            if (log.action === 'CREATE') badgeClass = 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400';
            else if (log.action === 'UPDATE' || log.action.includes('UPDATE')) badgeClass = 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400';
            else if (log.action === 'DELETE') badgeClass = 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';

            const detailsStr = log.details ? JSON.stringify(log.details) : '{}';

            tr.innerHTML = `
                <td class="px-4 py-3 text-gray-500 font-mono text-[10px]">${localTime}</td>
                <td class="px-4 py-3">
                    <div class="flex flex-col">
                        <span class="font-bold text-gray-900 dark:text-white">${log.username}</span>
                        <span class="text-[9px] text-primary font-mono font-bold uppercase tracking-tighter">#${log.user_id}</span>
                    </div>
                </td>
                <td class="px-4 py-3 text-center">
                    <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider ${badgeClass}">
                        ${log.action}
                    </span>
                </td>
                <td class="px-4 py-3 font-medium text-gray-600 dark:text-gray-400">
                    <span class="text-[9px] font-bold text-gray-400 uppercase tracking-widest block">${log.target_type}</span>
                    <span class="font-mono text-[10px]">${log.target_id || '---'}</span>
                </td>
                <td class="px-4 py-3 font-mono text-[10px] text-gray-500/70 truncate max-w-[250px]" title="${detailsStr}">${detailsStr}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderAuditLogsPagination(data) {
        const info = document.getElementById('audit-logs-pagination-info');
        if (info) {
            const start = data.total > 0 ? (data.current_page - 1) * 15 + 1 : 0;
            const end = Math.min(data.current_page * 15, data.total);
            info.innerText = `Showing ${start}-${end} of ${data.total}`;
        }

        const buttons = document.getElementById('audit-logs-pagination-buttons');
        if (!buttons) return;
        buttons.innerHTML = '';

        const prev = document.createElement('button');
        prev.className = `p-1.5 rounded border transition-all ${data.current_page > 1 ? 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800' : 'opacity-30 cursor-not-allowed border-gray-100 dark:border-gray-800'}`;
        prev.innerHTML = '<span class="material-symbols-outlined text-sm block">chevron_left</span>';
        if (data.current_page > 1) prev.onclick = () => fetchAuditLogs(data.current_page - 1);
        buttons.appendChild(prev);

        const next = document.createElement('button');
        next.className = `p-1.5 rounded border transition-all ${data.current_page < data.pages ? 'border-gray-200 dark:border-gray-700 hover:bg-white dark:hover:bg-gray-800' : 'opacity-30 cursor-not-allowed border-gray-100 dark:border-gray-800'}`;
        next.innerHTML = '<span class="material-symbols-outlined text-sm block">chevron_right</span>';
        if (data.current_page < data.pages) next.onclick = () => fetchAuditLogs(data.current_page + 1);
        buttons.appendChild(next);
    }

    const refreshAuditLogsBtn = document.getElementById('refresh-audit-logs-btn');
    if (refreshAuditLogsBtn) {
        refreshAuditLogsBtn.onclick = () => fetchAuditLogs(auditLogsCurrentPage);
    }

    // === REPORT STATUS LOGIC ===
    let gReportStatuses = {};
    const reportStatusTbody = document.getElementById('report-status-tbody');
    const reportSearchInput = document.getElementById('report-search');
    const refreshReportStatusBtn = document.getElementById('refresh-report-status-btn');

    async function fetchReportStatus() {
        if (!reportStatusTbody) return;
        
        reportStatusTbody.innerHTML = `
            <tr>
                <td colspan="4" class="px-6 py-12 text-center text-gray-400">
                    <div class="flex flex-col items-center gap-3">
                        <span class="material-symbols-outlined text-3xl animate-spin">sync</span>
                        <span class="font-bold uppercase tracking-widest text-[10px]">Updating catalog...</span>
                    </div>
                </td>
            </tr>
        `;

        try {
            const res = await fetch('/settings/report-offline-status', {
                headers: { 'Authorization': `Bearer ${window.jwtToken}` }
            });
            const data = await res.json();
            if (data.status === 'success') {
                gReportStatuses = data.reports;
                renderReportStatusTable();
            } else {
                showToast(data.message || 'Failed to fetch status', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Network error fetching report status', 'error');
        }
    }

    function renderReportStatusTable() {
        if (!reportStatusTbody) return;
        
        const filter = reportSearchInput ? reportSearchInput.value.toLowerCase() : '';
        reportStatusTbody.innerHTML = '';
        
        const reports = Object.keys(gReportStatuses).filter(url => {
            // Simple filter logic
            const name = url.split('/').pop().replace(/-/g, ' ').replace(/_/g, ' ');
            return url.toLowerCase().includes(filter) || name.toLowerCase().includes(filter);
        }).sort();

        if (reports.length === 0) {
            reportStatusTbody.innerHTML = `
                <tr>
                    <td colspan="4" class="px-6 py-12 text-center text-gray-400">
                        <span class="material-symbols-outlined text-2xl mb-2 opacity-20">search_off</span>
                        <p class="font-bold uppercase tracking-widest text-[10px]">No matching reports found</p>
                    </td>
                </tr>
            `;
            return;
        }

        reports.forEach(url => {
            const isOffline = gReportStatuses[url];
            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-50/80 dark:hover:bg-gray-800/40 transition-all border-b border-gray-50 dark:border-gray-800/50 group";
            
            const reportName = url.split('/').pop().replace(/-/g, ' ').replace(/_/g, ' ') || 'Dashboard Home';
            
            tr.innerHTML = `
                <td class="px-6 py-4">
                    <div class="flex items-center gap-3">
                        <div class="size-8 rounded-lg ${isOffline ? 'bg-red-500/10 text-red-500' : 'bg-green-500/10 text-green-500'} flex items-center justify-center">
                            <span class="material-symbols-outlined text-[18px]">${isOffline ? 'block' : 'check_circle'}</span>
                        </div>
                        <div>
                            <span class="text-[12px] font-black text-gray-900 dark:text-white uppercase tracking-tight block">${reportName}</span>
                            <span class="text-[9px] text-gray-400 font-bold uppercase tracking-widest">Module Access Control</span>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4">
                    <span class="font-mono text-[10px] text-gray-400 bg-gray-50 dark:bg-gray-800 px-2 py-0.5 rounded border border-gray-100 dark:border-gray-700">${url}</span>
                </td>
                <td class="px-6 py-4 text-center">
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest border ${isOffline ? 'bg-red-50 text-red-600 border-red-100 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800/30' : 'bg-green-50 text-green-600 border-green-100 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800/30'}">
                        ${isOffline ? 'Offline' : 'Online'}
                    </span>
                </td>
                <td class="px-6 py-4 text-right">
                    <div class="flex items-center justify-end gap-2">
                        <button onclick="toggleReportOfflineStatus('${url}', ${!isOffline})" 
                            class="px-4 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${isOffline ? 'bg-green-500 text-white hover:bg-green-600 shadow-md shadow-green-500/20' : 'bg-red-500 text-white hover:bg-red-600 shadow-md shadow-red-500/20'}">
                            Set ${isOffline ? 'Online' : 'Offline'}
                        </button>
                    </div>
                </td>
            `;
            reportStatusTbody.appendChild(tr);
        });
    }

    window.toggleReportOfflineStatus = async function(url, isOffline) {
        const confirmed = await showConfirmModal(
            `Confirm Status Change`,
            `Are you sure you want to set "${url}" to ${isOffline ? 'OFFLINE' : 'ONLINE'}? This will affect access for all non-admin users immediately.`
        );
        if (!confirmed) return;

        try {
            const res = await fetch('/settings/toggle-report-offline', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${window.jwtToken}`
                },
                body: JSON.stringify({ url, is_offline: isOffline })
            });
            const data = await res.json();
            if (data.status === 'success') {
                showToast(data.message, 'success');
                gReportStatuses[url] = isOffline;
                renderReportStatusTable();
            } else {
                showToast(data.message || 'Update failed', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Network error during update', 'error');
        }
    };

    if (refreshReportStatusBtn) {
        refreshReportStatusBtn.onclick = fetchReportStatus;
    }

    if (reportSearchInput) {
        reportSearchInput.oninput = renderReportStatusTable;
    }

    // Add to tab switch listener
    const originalSwitchTab = window.switchTab;
    window.switchTab = function(tabId) {
        if (typeof originalSwitchTab === 'function') {
            originalSwitchTab(tabId);
        }
        if (tabId === 'report-status') {
            fetchReportStatus();
        }
    };

    // Handle URL params on load - Ensure all constants are initialized first
    const urlParams = new URLSearchParams(window.location.search);
    const activeTab = urlParams.get('tab');
    if (activeTab && allTabs[activeTab]) {
        window.switchTab(activeTab);
    } else {
        window.switchTab('status');
    }
});

