document.addEventListener('DOMContentLoaded', function() {
    // Show success message if it exists
    if (INITIAL_STATE.successMessage) {
        showToast(INITIAL_STATE.successMessage, 'success');
    }

    const form = document.getElementById('settings-form');
    const saveButton = document.getElementById('save-button');
    const cancelFormButton = document.getElementById('cancel-form-button');
    const confirmationModal = document.getElementById('confirmation-modal');
    const cancelButton = document.getElementById('cancel-button');
    const confirmButton = document.getElementById('confirm-button');
    const calorieInput = document.getElementById('calorie-goal');
    const proteinInput = document.getElementById('protein-goal');
    const currentWeightInput = document.getElementById('current-weight');
    const weightGoalInput = document.getElementById('weight-goal');
    
    // Store initial values
    const originalCalorieValue = INITIAL_STATE.calorieGoal.toString();
    const originalProteinValue = INITIAL_STATE.proteinGoal.toString();
    const originalWeightGoalValue = INITIAL_STATE.weightGoal ? INITIAL_STATE.weightGoal.toString() : '';
    const originalWeightUnit = INITIAL_STATE.weightUnit;
    let currentWeightUnit = originalWeightUnit;

    // Quick Add Food Removal - always set this up if foods exist
    if (INITIAL_STATE.foods && INITIAL_STATE.foods.length > 0) {
        setupQuickAddFoodRemoval();
    }

    // Store the original weight unit value
    const weightUnitRadios = document.querySelectorAll('input[name="weight_unit"]');
    const weightUnitLabels = document.querySelectorAll('.weight-unit');
    
    // Function to validate inputs
    function validateInputs() {
        let isValid = true;
        
        // Clear previous error messages
        document.querySelectorAll('.error-message').forEach(el => el.remove());
        calorieInput.classList.remove('input-error');
        proteinInput.classList.remove('input-error');
        
        // Validate calorie input
        if (!calorieInput.value || parseInt(calorieInput.value) <= 0) {
            const errorMsg = document.createElement('p');
            errorMsg.className = 'error-message';
            errorMsg.textContent = 'Please enter a positive number';
            calorieInput.parentNode.parentNode.appendChild(errorMsg);
            calorieInput.classList.add('input-error');
            isValid = false;
        }
        
        // Validate protein input
        if (!proteinInput.value || parseInt(proteinInput.value) <= 0) {
            const errorMsg = document.createElement('p');
            errorMsg.className = 'error-message';
            errorMsg.textContent = 'Please enter a positive number';
            proteinInput.parentNode.parentNode.appendChild(errorMsg);
            proteinInput.classList.add('input-error');
            isValid = false;
        }
        
        return isValid;
    }
    
    // Check if form values have changed
    function checkFormChanged() {
        const calorieChanged = calorieInput.value !== originalCalorieValue;
        const proteinChanged = proteinInput.value !== originalProteinValue;
        const weightUnitChanged = currentWeightUnit !== originalWeightUnit;
        const weightGoalChanged = weightGoalInput.value !== originalWeightGoalValue;
        const currentWeightEntered = currentWeightInput.value.trim() !== '';
        
        if (calorieChanged || proteinChanged || weightUnitChanged || weightGoalChanged || currentWeightEntered) {
            form.classList.add('settings-form-changed');
        } else {
            form.classList.remove('settings-form-changed');
        }
    }
    
    // Function to reset form to original values
    function resetForm() {
        // Reset calorie and protein goals
        calorieInput.value = originalCalorieValue;
        proteinInput.value = originalProteinValue;
        
        // Reset weight unit
        const originalUnitRadio = document.querySelector(`input[name="weight_unit"][value="${originalWeightUnit}"]`);
        if (originalUnitRadio && originalUnitRadio.checked !== true) {
            originalUnitRadio.checked = true;
            
            // Update unit labels
            const unitText = originalWeightUnit === 1 ? 'lbs' : 'kg';
            weightUnitLabels.forEach(label => {
                label.textContent = unitText;
            });
            
            currentWeightUnit = originalWeightUnit;
        }
        
        // Reset weight goal
        weightGoalInput.value = originalWeightUnit === 1 && originalWeightGoalValue ? 
            (parseFloat(originalWeightGoalValue) * 2.20462).toFixed(1) : 
            originalWeightGoalValue;
        
        // Reset hidden weight goal field
        document.getElementById('weight-goal-precise').value = originalWeightGoalValue;
        
        // Clear current weight input
        currentWeightInput.value = '';
        
        // Remove any error messages
        document.querySelectorAll('.error-message').forEach(el => el.remove());
        calorieInput.classList.remove('input-error');
        proteinInput.classList.remove('input-error');
        
        // Reset form changed state
        form.classList.remove('settings-form-changed');
        
        // Show confirmation toast
        showToast('Changes cancelled. Form reset to original values.', 'info');
    }
    
    // Update weight unit labels when the user changes their preference
    weightUnitRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const unitText = this.value === '1' ? 'lbs' : 'kg';
            const newUnit = parseInt(this.value);
            const origUnit = parseInt(originalWeightUnit);
            
            // Update unit labels
            weightUnitLabels.forEach(label => {
                label.textContent = unitText;
            });
            
            // Only convert if the unit actually changed
            if (newUnit !== origUnit) {
                // Get the precise value in kg from the hidden field
                const preciseKgValue = parseFloat(document.getElementById('weight-goal-precise').value);
                
                // Convert weight goal display value when unit changes
                if (!isNaN(preciseKgValue)) {
                    if (newUnit === 1) {
                        // Convert from kg to lbs for display
                        weightGoalInput.value = (preciseKgValue * 2.20462).toFixed(1);
                    } else {
                        // Display kg value (rounded for display)
                        weightGoalInput.value = preciseKgValue.toFixed(1);
                    }
                }
                
                // Also convert current weight if it has a value
                if (currentWeightInput.value && !isNaN(parseFloat(currentWeightInput.value))) {
                    const currentValue = parseFloat(currentWeightInput.value);
                    
                    if (newUnit === 1 && origUnit === 0) {
                        // Convert from kg to lbs
                        currentWeightInput.value = (currentValue * 2.20462).toFixed(1);
                    } else if (newUnit === 0 && origUnit === 1) {
                        // Convert from lbs to kg
                        currentWeightInput.value = (currentValue / 2.20462).toFixed(1);
                    }
                }
            }
            
            // Update current unit for future conversions
            currentWeightUnit = this.value;
            
            checkFormChanged();
        });
    });
    
    // Update the precise value when the display value changes
    weightGoalInput.addEventListener('input', function() {
        const displayValue = parseFloat(this.value);
        if (!isNaN(displayValue)) {
            // If in pounds, convert to kg for storage
            if (currentWeightUnit === '1') {
                document.getElementById('weight-goal-precise').value = (displayValue / 2.20462).toString();
            } else {
                document.getElementById('weight-goal-precise').value = displayValue.toString();
            }
        } else {
            document.getElementById('weight-goal-precise').value = '';
        }
        checkFormChanged();
    });
    
    // Show confirmation modal
    saveButton.addEventListener('click', function() {
        if (validateInputs()) {
            // Check what values have changed
            const calorieChanged = calorieInput.value !== originalCalorieValue;
            const proteinChanged = proteinInput.value !== originalProteinValue;
            const weightUnitChanged = currentWeightUnit !== originalWeightUnit;
            const weightGoalChanged = weightGoalInput.value !== originalWeightGoalValue;
            const currentWeightEntered = currentWeightInput.value.trim() !== '';
            
            // Only show confirmation if values have changed
            if (calorieChanged || proteinChanged || weightUnitChanged || weightGoalChanged || currentWeightEntered) {
                // Update confirmation message based on what's changing
                let changeMessage = 'Are you sure you want to update your settings?';
                const changes = [];
                
                if (calorieChanged) {
                    changes.push('calorie goal');
                }
                if (proteinChanged) {
                    changes.push('protein goal');
                }
                if (weightUnitChanged) {
                    changes.push('weight unit preference');
                }
                if (weightGoalChanged) {
                    changes.push('weight goal');
                }
                if (currentWeightEntered) {
                    changes.push('current weight');
                }
                
                if (changes.length > 0) {
                    changeMessage = `Are you sure you want to update your ${changes.join(', ')}?`;
                }
                
                document.querySelector('#confirmation-modal p').textContent = changeMessage;
                confirmationModal.classList.remove('hidden');
            } else {
                // If no changes, just inform the user
                alert('No changes to save.');
            }
        }
    });
    
    // Cancel form changes
    cancelFormButton.addEventListener('click', function() {
        // Only show confirmation if values have changed
        if (form.classList.contains('settings-form-changed')) {
            if (confirm('Are you sure you want to cancel your changes? All modifications will be lost.')) {
                resetForm();
            }
        } else {
            showToast('No changes to cancel.', 'info');
        }
    });
    
    // Cancel button closes the modal
    cancelButton.addEventListener('click', function() {
        confirmationModal.classList.add('hidden');
    });
    
    // Confirm button submits the form
    confirmButton.addEventListener('click', function() {
        form.submit();
    });
    
    // Add input event listeners
    calorieInput.addEventListener('input', function() {
        checkFormChanged();
    });
    
    proteinInput.addEventListener('input', function() {
        checkFormChanged();
    });
    
    currentWeightInput.addEventListener('input', function() {
        checkFormChanged();
    });
    
    weightGoalInput.addEventListener('input', function() {
        checkFormChanged();
    });

    // Form submission with AJAX
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        $.ajax({
            url: URLS.updateSettings,
            type: "POST",
            data: $(form).serialize(),
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            error: function(xhr, status, error) {
                console.error('Settings update error:', {xhr, status, error});
                showToast('An error occurred. Please try again.', 'error');
            }
        });
    });

    // Set up progress bars
    document.querySelectorAll('.progress-fill').forEach(fill => {
        const percentage = fill.dataset.percentage;
        fill.style.width = `${Math.min(percentage, 100)}%`;
        
        // Add over-limit class if needed
        if (fill.classList.contains('progress-fill-calories') && percentage > 100) {
            fill.classList.add('over-limit');
        }
    });
});

// Helper function for Quick Add Food removal
function setupQuickAddFoodRemoval() {
    const removeFoodModal = document.getElementById('remove-food-modal');
    const cancelRemoveButton = document.getElementById('cancel-remove-button');
    const confirmRemoveButton = document.getElementById('confirm-remove-button');
    let foodIdToRemove = null;

    // Add event listeners to all remove buttons
    document.querySelectorAll('.remove-quick-add-btn').forEach(button => {
        button.addEventListener('click', function() {
            foodIdToRemove = this.getAttribute('data-food-id');
            removeFoodModal.classList.remove('hidden');
        });
    });

    // Cancel removal
    cancelRemoveButton.addEventListener('click', function() {
        removeFoodModal.classList.add('hidden');
        foodIdToRemove = null;
    });

    // Confirm removal
    confirmRemoveButton.addEventListener('click', function() {
        if (foodIdToRemove) {
            $.ajax({
                url: URLS.removeQuickAddFood,
                type: 'POST',
                data: { food_id: foodIdToRemove },
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                success: function(response) {
                    if (response.success) {
                        const foodItem = document.querySelector(
                            `.remove-quick-add-btn[data-food-id="${foodIdToRemove}"]`
                        ).closest('.quick-add-food-item');
                        foodItem.remove();
                        
                        // Check if there are no more foods
                        const remainingFoods = document.querySelectorAll('.quick-add-food-item');
                        if (remainingFoods.length === 0) {
                            document.getElementById('quick-add-foods-container').innerHTML = `
                                <div class="text-center p-8 bg-gray-50 rounded-md border border-dashed border-gray-300">
                                    <p class="text-gray-600">You don't have any Quick Add foods yet. Add some from the Dashboard page!</p>
                                    <a href="${URLS.dashboard}" class="mt-4 inline-block bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600">Go to Dashboard</a>
                                </div>
                            `;
                        }
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Remove food error:', {xhr, status, error});
                    showToast('Error removing food', 'error');
                },
                complete: function() {
                    removeFoodModal.classList.add('hidden');
                    foodIdToRemove = null;
                }
            });
        }
    });
}