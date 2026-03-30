/**
 * My Account Page Functionality
 * Includes Password Update Modal and Admin File Upload logic.
 */

document.addEventListener('DOMContentLoaded', function () {
    // === Password Update Modal Logic ===
    const passwordModal = document.getElementById('password-modal');
    const passwordForm = document.getElementById('password-form');
    const updatePasswordBtn = document.getElementById('update-password-btn');
    const submitPasswordBtn = document.getElementById('submit-password-btn');

    if (passwordModal && passwordForm && updatePasswordBtn) {
        function openPasswordModal() {
            passwordModal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }

        window.closePasswordModal = function () {
            passwordModal.classList.add('hidden');
            document.body.style.overflow = 'auto';
            passwordForm.reset();
        };

        updatePasswordBtn.addEventListener('click', openPasswordModal);

        // Auto-open if redirected from login with force_reset flag
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('force_reset') === '1') {
            openPasswordModal();
            if (window.showToast) {
                window.showToast('Reset Required', 'A password reset has been forced for your account. Please update your password to continue.', 'warning', 60000);
            }
        }

        passwordForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const currentPassword = document.getElementById('current_password').value;
            const newPassword = document.getElementById('new_password').value;
            const confirmPassword = document.getElementById('confirm_password').value;

            if (newPassword === currentPassword) {
                if (window.showToast) window.showToast('Error', 'New password cannot be the same as current password', 'error');
                else alert('New password cannot be the same as current password');
                return;
            }

            if (newPassword !== confirmPassword) {
                if (window.showToast) window.showToast('Error', 'New passwords do not match', 'error');
                else alert('New passwords do not match');
                return;
            }

            submitPasswordBtn.disabled = true;
            const originalContent = submitPasswordBtn.innerHTML;
            submitPasswordBtn.innerHTML = '<span class="material-symbols-outlined text-sm animate-spin">sync</span><span>Saving...</span>';

            try {
                const response = await fetch('/api/auth/update-password', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        current_password: currentPassword,
                        new_password: newPassword,
                        confirm_password: confirmPassword
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    if (window.showToast) window.showToast('Success', 'Password updated successfully', 'success');
                    else alert('Password updated successfully');
                    window.closePasswordModal();
                } else {
                    if (window.showToast) window.showToast('Error', data.msg || 'Update failed', 'error');
                    else alert('Error: ' + (data.msg || 'Update failed'));
                }
            } catch (error) {
                console.error('Password update error:', error);
                if (window.showToast) window.showToast('Error', 'An unexpected error occurred', 'error');
                else alert('An unexpected error occurred');
            } finally {
                submitPasswordBtn.disabled = false;
                submitPasswordBtn.innerHTML = originalContent;
            }
        });
    }

    // === Admin File Upload Logic ===
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const statusDiv = document.getElementById('upload-status');
    const fileNameSpan = document.getElementById('file-name');
    const percentSpan = document.getElementById('upload-percent');
    const progressBar = document.getElementById('progress-bar');

    if (dropZone && fileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        const dropInner = dropZone.querySelector('.border-2');

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropInner.classList.add('border-primary', 'bg-primary/5'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropInner.classList.remove('border-primary', 'bg-primary/5'), false);
        });

        dropZone.addEventListener('drop', e => {
            const files = e.dataTransfer.files;
            if (files.length) handleFiles(files[0]);
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) handleFiles(fileInput.files[0]);
        });

        function handleFiles(file) {
            if (!file.name.match(/\.(sql|dump|bak)$/i)) {
                if (window.showToast) window.showToast('Invalid File', 'Please upload a SQL or DUMP file', 'error');
                else alert('Please upload a SQL or DUMP file');
                return;
            }

            fileNameSpan.textContent = file.name;
            statusDiv.classList.remove('hidden');
            progressBar.classList.remove('bg-red-500');
            progressBar.style.width = '0%';
            percentSpan.textContent = '0%';

            const formData = new FormData();
            formData.append('file', file);

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload-file', true);

            xhr.upload.onprogress = e => {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    progressBar.style.width = percent + '%';
                    percentSpan.textContent = percent + '%';
                }
            };

            xhr.onload = () => {
                if (xhr.status === 200) {
                    if (window.showToast) window.showToast('Upload Success', 'Database dump saved to ' + file.name, 'success');
                    else alert('File uploaded successfully');
                    setTimeout(() => {
                        statusDiv.classList.add('opacity-0', 'transition-opacity', 'duration-500');
                        setTimeout(() => {
                            statusDiv.classList.add('hidden');
                            statusDiv.classList.remove('opacity-0');
                        }, 500);
                    }, 3000);
                } else {
                    let errorMsg = 'Upload failed';
                    try {
                        errorMsg = JSON.parse(xhr.responseText).error || errorMsg;
                    } catch (e) { }
                    if (window.showToast) window.showToast('Upload Failed', errorMsg, 'error');
                    else alert('Error: ' + errorMsg);
                    progressBar.classList.add('bg-red-500');
                }
            };

            xhr.onerror = () => {
                if (window.showToast) window.showToast('Network Error', 'Connection lost during upload', 'error');
                else alert('Network Error');
                progressBar.classList.add('bg-red-500');
            };

            xhr.send(formData);
        }
    }
});
