// Toast notification function
function showToast(message, duration = 3000) {
    // Get existing toasts
    const existingToasts = document.querySelectorAll('.toast-notification');
    const toastCount = existingToasts.length;
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = 'toast-notification fixed right-4 bg-gray-800 text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-all duration-300';
    toast.textContent = message;
    
    // Position the toast based on how many existing toasts there are
    const bottomOffset = 16 + (toastCount * 60); // 16px initial offset + 60px per toast
    toast.style.bottom = bottomOffset + 'px';
    
    // Add to document
    document.body.appendChild(toast);
    
    // Extend duration based on number of toasts
    const extendedDuration = duration + (toastCount * 500); // Add 500ms per existing toast
    
    // Fade in
    setTimeout(() => {
        toast.classList.add('opacity-90');
    }, 10);
    
    // Fade out and remove
    setTimeout(() => {
        toast.classList.remove('opacity-90');
        toast.classList.add('opacity-0');
        
        // After fade out, remove the element and reposition other toasts
        setTimeout(() => {
            toast.remove();
            
            // Reposition remaining toasts
            repositionToasts();
        }, 300);
    }, extendedDuration);
}

// Function to reposition toasts after one is removed
function repositionToasts() {
    const toasts = document.querySelectorAll('.toast-notification');
    toasts.forEach((toast, index) => {
        const bottomOffset = 16 + (index * 60);
        toast.style.bottom = bottomOffset + 'px';
    });
}

