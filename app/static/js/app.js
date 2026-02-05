/**
 * SendRice - Main JavaScript
 * HTMX + Alpine.js integration and utility functions
 */

// =====================
// Toast Notifications
// =====================

/**
 * Show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - Type: 'success', 'error', 'warning', 'info'
 * @param {number} duration - Duration in milliseconds
 */
function showToast(message, type = 'info', duration = 5000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        success: `<svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>`,
        error: `<svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>`,
        warning: `<svg class="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
        </svg>`,
        info: `<svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>`
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="flex items-center gap-2">
            ${icons[type] || icons.info}
            <span>${message}</span>
        </div>
        <button onclick="this.parentElement.remove()" class="ml-4 text-gray-400 hover:text-gray-600">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
        </button>
    `;

    // Animation
    toast.style.transform = 'translateX(100%)';
    toast.style.opacity = '0';
    toast.style.transition = 'all 300ms ease-out';

    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
    });

    // Auto remove
    setTimeout(() => {
        toast.style.transform = 'translateX(100%)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// =====================
// HTMX Event Handlers
// =====================

// Show loading indicator
document.body.addEventListener('htmx:beforeRequest', function(evt) {
    // Add loading class to target if needed
    const target = evt.detail.target;
    if (target && target.classList) {
        target.classList.add('htmx-loading');
    }
});

// Handle successful requests
document.body.addEventListener('htmx:afterRequest', function(evt) {
    const target = evt.detail.target;
    if (target && target.classList) {
        target.classList.remove('htmx-loading');
    }

    // Show success toast for certain actions
    const path = evt.detail.pathInfo.requestPath;
    if (evt.detail.successful) {
        if (path.includes('/send') && !path.includes('/batch')) {
            showToast('Đã gửi thông báo', 'success');
        } else if (path.includes('/generate-image') && !path.includes('/batch')) {
            showToast('Đã tạo ảnh lương', 'success');
        }
    }
});

// Handle errors
document.body.addEventListener('htmx:responseError', function(evt) {
    const status = evt.detail.xhr.status;
    let message = 'Có lỗi xảy ra';

    try {
        const response = JSON.parse(evt.detail.xhr.responseText);
        message = response.detail || response.message || message;
    } catch (e) {
        // Use default message
    }

    if (status === 400) {
        showToast(message, 'warning');
    } else if (status === 404) {
        showToast('Không tìm thấy dữ liệu', 'error');
    } else if (status === 500) {
        showToast('Lỗi server: ' + message, 'error');
    } else {
        showToast(message, 'error');
    }
});

// Handle upload progress
document.body.addEventListener('htmx:xhr:progress', function(evt) {
    if (evt.detail.lengthComputable) {
        const percentComplete = Math.round((evt.detail.loaded / evt.detail.total) * 100);
        // Could update a progress bar here
        console.log('Upload progress:', percentComplete + '%');
    }
});

// =====================
// Keyboard Shortcuts
// =====================

document.addEventListener('keydown', function(e) {
    // Escape to close modal
    if (e.key === 'Escape') {
        const modalContainer = document.getElementById('modal-container');
        if (modalContainer && modalContainer.innerHTML) {
            modalContainer.innerHTML = '';
        }
    }

    // Ctrl/Cmd + S to save settings (if on settings page)
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        const settingsForm = document.querySelector('form[hx-post*="/settings"]');
        if (settingsForm) {
            e.preventDefault();
            htmx.trigger(settingsForm, 'submit');
        }
    }
});

// =====================
// Utility Functions
// =====================

/**
 * Format number as Vietnamese currency
 * @param {number} amount - Amount to format
 * @returns {string} Formatted string
 */
function formatCurrency(amount) {
    if (typeof amount !== 'number') return 'N/A';
    return amount.toLocaleString('vi-VN') + ' VND';
}

/**
 * Format phone number for display
 * @param {string} phone - Phone number
 * @returns {string} Formatted phone
 */
function formatPhone(phone) {
    if (!phone) return '-';
    // Format as 0xxx xxx xxx
    const cleaned = phone.replace(/\D/g, '');
    if (cleaned.length === 10) {
        return `${cleaned.slice(0, 4)} ${cleaned.slice(4, 7)} ${cleaned.slice(7)}`;
    }
    return phone;
}

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Đã sao chép!', 'success', 2000);
    } catch (err) {
        showToast('Không thể sao chép', 'error');
    }
}

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// =====================
// File Upload Preview
// =====================

document.addEventListener('change', function(e) {
    if (e.target.type === 'file' && e.target.accept.includes('xls')) {
        const file = e.target.files[0];
        if (file) {
            // Validate file size (max 50MB)
            const maxSize = 50 * 1024 * 1024;
            if (file.size > maxSize) {
                showToast('File quá lớn. Tối đa 50MB.', 'error');
                e.target.value = '';
                return;
            }

            // Show file name
            console.log('Selected file:', file.name, 'Size:', Math.round(file.size / 1024) + 'KB');
        }
    }
});

// =====================
// Initialize
// =====================

document.addEventListener('DOMContentLoaded', function() {
    console.log('SendRice initialized');

    // Check for any flash messages from server
    const flashMessage = document.querySelector('meta[name="flash-message"]');
    if (flashMessage) {
        const type = flashMessage.getAttribute('data-type') || 'info';
        showToast(flashMessage.content, type);
    }
});

// Export functions for use in templates
window.showToast = showToast;
window.formatCurrency = formatCurrency;
window.formatPhone = formatPhone;
window.copyToClipboard = copyToClipboard;
window.debounce = debounce;
