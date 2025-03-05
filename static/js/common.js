// Single, centralized toast function
function showToast(message, type = 'success', duration = 3000) {
    // Get existing toasts
    const existingToasts = document.querySelectorAll('.toast-notification');
    const toastCount = existingToasts.length;
    
    // Create toast element
    const toast = document.createElement('div');
    
    // Set background color based on type
    const bgColors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        warning: 'bg-yellow-500',
        info: 'bg-blue-500'
    };
    
    const bgColor = bgColors[type] || bgColors.success;
    
    // Set toast classes
    toast.className = `toast-notification fixed right-4 ${bgColor} text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-all duration-300 opacity-0`;
    toast.textContent = message;
    
    // Position the toast
    const bottomOffset = 16 + (toastCount * 60);
    toast.style.bottom = bottomOffset + 'px';
    
    // Add to document
    document.getElementById('toast-container').appendChild(toast);
    
    // Extend duration based on number of toasts
    const extendedDuration = duration + (toastCount * 500);
    
    // Fade in
    requestAnimationFrame(() => {
        toast.classList.add('opacity-90');
    });
    
    // Fade out and remove
    setTimeout(() => {
        toast.classList.remove('opacity-90');
        toast.classList.add('opacity-0');
        
        setTimeout(() => {
            toast.remove();
            repositionToasts();
        }, 300);
    }, extendedDuration);
}

// Helper function to reposition toasts
function repositionToasts() {
    const toasts = document.querySelectorAll('.toast-notification');
    toasts.forEach((toast, index) => {
        const bottomOffset = 16 + (index * 60);
        toast.style.bottom = bottomOffset + 'px';
    });
}

// Initialize mobile menu and toast functionality
document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu functionality
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    
    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', function(e) {
            e.stopPropagation();
            const isExpanded = this.getAttribute('aria-expanded') === 'true';
            
            mobileMenu.classList.toggle('hidden');
            this.setAttribute('aria-expanded', !isExpanded);
            
            // Toggle icons
            this.querySelectorAll('svg').forEach(icon => icon.classList.toggle('hidden'));
        });
        
        // Close mobile menu when clicking outside
        document.addEventListener('click', function(event) {
            if (!event.target.closest('#mobile-menu, #mobile-menu-button') && 
                !mobileMenu.classList.contains('hidden')) {
                mobileMenu.classList.add('hidden');
                mobileMenuButton.setAttribute('aria-expanded', 'false');
                mobileMenuButton.querySelector('svg:first-child').classList.remove('hidden');
                mobileMenuButton.querySelector('svg:last-child').classList.add('hidden');
            }
        });
    }
    
    // Display any flash messages from server
    if (COMMON_STATE.flashMessages) {
        COMMON_STATE.flashMessages.forEach(([category, message]) => {
            showToast(message, category);
        });
    }
    
    // Set up AJAX to handle toast responses
    $(document).ajaxSuccess(function(event, xhr, settings) {
        try {
            const response = JSON.parse(xhr.responseText);
            if (response.toast) {
                showToast(response.toast.message, response.toast.category);
                
                if (response.redirect) {
                    setTimeout(() => {
                        window.location.href = response.redirect;
                    }, 1000);
                }
            }
        } catch (e) {
            // Not a JSON response or doesn't have toast property
        }
    });

    // Set up progress bars
    document.querySelectorAll('.progress-bar-calories, .progress-bar-protein').forEach(bar => {
        const percentage = bar.dataset.percentage;
        bar.style.width = `${percentage}%`;
    });
});
