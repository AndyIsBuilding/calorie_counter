// Make showToast globally available
window.showToast = function(message, type = 'success', duration = 3000) {
    // Create toast element
    const toast = document.createElement('div');
    
    // Set class for styling
    toast.className = `toast-notification ${type}`;
    
    toast.innerHTML = message;
    
    const container = document.getElementById('toast-container');
    container.appendChild(toast);
    
    // Force a reflow to ensure the transition works
    toast.offsetHeight;
    
    // Show the toast
    setTimeout(() => {
        toast.classList.add('visible');
        
        // Reposition all toasts
        repositionToasts();
    }, 10); // Small delay to ensure styles are applied
    
    // Remove after duration
    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => {
            toast.remove();
            repositionToasts();
        }, 300);
    }, duration);
    
    return toast;
}

// Helper function to reposition toasts - also make this global
window.repositionToasts = function() {
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
    
    // Set up progress bars
    document.querySelectorAll('.progress-bar-calories, .progress-bar-protein').forEach(bar => {
        const percentage = bar.dataset.percentage;
        bar.style.width = `${percentage}%`;
    });
});

// Set up a simple global AJAX success handler for toast messages
// This centralized approach handles all toast messages from server responses
$(document).off('ajaxSuccess').on('ajaxSuccess', function(event, xhr, settings) {
    try {
        const response = JSON.parse(xhr.responseText);
        
        // If there's a toast property in the response, show it
        if (response.toast) {
            showToast(response.toast.message, response.toast.category);
            
            // Handle redirects if included in the response
            if (response.redirect) {
                setTimeout(() => {
                    window.location.href = response.redirect;
                }, 1000);
            }
        }
    } catch (e) {
        // Not every response is JSON or has toast data, this is expected
    }
});
