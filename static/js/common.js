// Updated showToast function with cleaner code
function showToast(message, type = 'success', duration = 3000) {
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
    
    // Create a global namespace for our toast tracking
    window.TOAST_TRACKER = window.TOAST_TRACKER || {
        processedResponses: new Set(),
        requestCount: 0
    };
    
    // Set up AJAX to handle toast responses with better deduplication
    $(document).off('ajaxSuccess').on('ajaxSuccess', function(event, xhr, settings) {
        // Increment request counter for debugging
        window.TOAST_TRACKER.requestCount++;
        console.log(`[${window.TOAST_TRACKER.requestCount}] ajaxSuccess triggered for URL:`, settings.url);
        
        try {
            const response = JSON.parse(xhr.responseText);
            
            // Generate a unique response ID based on URL and response content
            const responseId = `${settings.url}_${JSON.stringify(response)}`;
            console.log(`[${window.TOAST_TRACKER.requestCount}] Response ID:`, responseId);
            console.log(`[${window.TOAST_TRACKER.requestCount}] Already processed:`, window.TOAST_TRACKER.processedResponses.has(responseId));
            
            // Check if we've already processed this exact response
            if (window.TOAST_TRACKER.processedResponses.has(responseId)) {
                console.log(`[${window.TOAST_TRACKER.requestCount}] Skipping duplicate toast for already processed response`);
                return;
            }
            
            // Mark this response as processed
            window.TOAST_TRACKER.processedResponses.add(responseId);
            console.log(`[${window.TOAST_TRACKER.requestCount}] Added to processed responses. Current size:`, window.TOAST_TRACKER.processedResponses.size);
            
            // Clean up the set periodically to prevent memory leaks
            setTimeout(() => {
                window.TOAST_TRACKER.processedResponses.delete(responseId);
                console.log(`Removed ${responseId} from processed responses. Current size:`, window.TOAST_TRACKER.processedResponses.size);
            }, 5000);
            
            if (response.toast) {
                console.log(`[${window.TOAST_TRACKER.requestCount}] Showing toast:`, response.toast.message);
                showToast(response.toast.message, response.toast.category);
                
                if (response.redirect) {
                    setTimeout(() => {
                        window.location.href = response.redirect;
                    }, 1000);
                }
            }
        } catch (e) {
            console.log(`[${window.TOAST_TRACKER.requestCount}] Error parsing response or no toast found:`, e);
        }
    });

    // Set up progress bars
    document.querySelectorAll('.progress-bar-calories, .progress-bar-protein').forEach(bar => {
        const percentage = bar.dataset.percentage;
        bar.style.width = `${percentage}%`;
    });
});
