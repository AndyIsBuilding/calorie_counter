document.addEventListener('DOMContentLoaded', function() {
    // Show success message if it exists
    if (INITIAL_STATE.successMessage) {
        showToast(INITIAL_STATE.successMessage, 'success');
    }

    // Get settings form current state 
    const settingsForm = document.getElementById('settings-form');
    const unitPreferenceForm = document.getElementById('unit-preference-form');
    const saveButton = document.getElementById('save-button');
    const saveUnitButton = document.getElementById('save-unit-button');
    const cancelUnitButton = document.getElementById('cancel-unit-button');
    const unitPreferenceActions = document.getElementById('unit-preference-actions');
    const cancelFormButton = document.getElementById('cancel-form-button');
    const confirmationModal = document.getElementById('confirmation-modal');
    const cancelButton = document.getElementById('cancel-button');
    const confirmButton = document.getElementById('confirm-button');
    const calorieInput = document.getElementById('calorie-goal');
    const proteinInput = document.getElementById('protein-goal');
    const currentWeightInput = document.getElementById('current-weight');
    const weightGoalInput = document.getElementById('weight-goal');
    
    // Store initial values - using let for values that might need to be updated
    let originalCalorieValue = INITIAL_STATE.calorieGoal.toString();
    let originalProteinValue = INITIAL_STATE.proteinGoal.toString();
    let originalWeightGoalValue = INITIAL_STATE.weightGoal ? INITIAL_STATE.weightGoal.toString() : '';
    const originalWeightUnit = INITIAL_STATE.weightUnit; // This stays constant
    let currentWeightUnit = originalWeightUnit.toString();
    
    // Debug info
    console.log('Initial setup:', {
        originalWeightUnit,
        currentWeightUnit,
        unitPreferenceActions: unitPreferenceActions ? 'found' : 'not found',
        weightUnitRadios: document.querySelectorAll('.weight-unit-radio').length
    });

    // Quick Add Food Removal - always set this up if foods exist
    if (INITIAL_STATE.foods && INITIAL_STATE.foods.length > 0) {
        setupQuickAddFoodRemoval();
    }

    // Store the original weight unit value
    const weightUnitRadios = document.querySelectorAll('.weight-unit-radio');
    const weightUnitLabels = document.querySelectorAll('.weight-unit');
    
    // Check if the unit preference is already different from the original on page load
    // This could happen if the user changed it but didn't save before refreshing
    function checkInitialUnitPreference() {
        const selectedUnit = document.querySelector('input[name="weight_unit"]:checked').value;
        if (selectedUnit !== originalWeightUnit.toString()) {
            console.log('Initial unit different from original, showing buttons');
            unitPreferenceActions.classList.remove('hidden');
        } else {
            console.log('Initial unit same as original, hiding buttons');
            unitPreferenceActions.classList.add('hidden');
        }
    }
    
    // Check initial state
    checkInitialUnitPreference();
    
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
        const weightGoalChanged = weightGoalInput.value !== (originalWeightUnit === 1 && originalWeightGoalValue ? 
            (parseFloat(originalWeightGoalValue) * 2.20462).toFixed(1) : originalWeightGoalValue);
        const currentWeightEntered = currentWeightInput.value.trim() !== '';
        
        if (calorieChanged || proteinChanged || weightGoalChanged || currentWeightEntered) {
            settingsForm.classList.add('settings-form-changed');
        } else {
            settingsForm.classList.remove('settings-form-changed');
        }
    }
    
    // Function to check if the unit preference has changed
    function checkUnitPreferenceChanged() {
        const selectedUnit = document.querySelector('input[name="weight_unit"]:checked').value;
        console.log('Checking unit preference change:', {
            selectedUnit,
            originalWeightUnit: originalWeightUnit.toString(),
            currentWeightUnit
        });
        
        // Compare with the original value, not the current value
        if (selectedUnit !== originalWeightUnit.toString()) {
            console.log('Unit changed, showing buttons');
            unitPreferenceActions.classList.remove('hidden');
        } else {
            console.log('Unit unchanged, hiding buttons');
            unitPreferenceActions.classList.add('hidden');
        }
    }
    
    // Function to reset form to original values
    function resetForm() {
        // Reset calorie and protein goals
        calorieInput.value = originalCalorieValue;
        proteinInput.value = originalProteinValue;
        
        // Reset weight goal - display in the current unit (kg or lbs)
        weightGoalInput.value = originalWeightUnit === 1 && originalWeightGoalValue ? 
            (parseFloat(originalWeightGoalValue) * 2.20462).toFixed(1) : 
            originalWeightGoalValue;
        
        // Clear current weight input
        currentWeightInput.value = '';
        
        // Remove any error messages
        document.querySelectorAll('.error-message').forEach(el => el.remove());
        calorieInput.classList.remove('input-error');
        proteinInput.classList.remove('input-error');
        
        // Reset form changed state
        settingsForm.classList.remove('settings-form-changed');
        
        // Show confirmation toast
        showToast('Changes cancelled. Form reset to original values.', 'info');
    }
    
    // Function to reset unit preference to original value
    function resetUnitPreference() {
        // Reset to original unit
        const originalUnitRadio = document.querySelector(`.weight-unit-radio[value="${originalWeightUnit}"]`);
        if (originalUnitRadio) {
            originalUnitRadio.checked = true;
            
            // Update unit labels
            const unitText = originalWeightUnit === 1 ? 'lbs' : 'kg';
            weightUnitLabels.forEach(label => {
                label.textContent = unitText;
            });
            
            // Reset current unit
            currentWeightUnit = originalWeightUnit.toString();
            
            // Hide action buttons
            unitPreferenceActions.classList.add('hidden');
            
            // Show toast message
            showToast('Unit preference change cancelled.', 'info');
        }
    }
    
    // Add event listeners to weight unit radio buttons
    weightUnitRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const unitText = this.value === '1' ? 'lbs' : 'kg';
            const newUnit = parseInt(this.value);
            const origUnit = parseInt(originalWeightUnit);
            
            console.log('Weight unit radio changed:', {
                from: origUnit,
                to: newUnit,
                unitText
            });
            
            // Update unit labels
            weightUnitLabels.forEach(label => {
                label.textContent = unitText;
            });
            
            // Only convert if the unit actually changed
            if (newUnit !== origUnit) {
                // Get the current weight goal value
                if (weightGoalInput.value && !isNaN(parseFloat(weightGoalInput.value))) {
                    const currentValue = parseFloat(weightGoalInput.value);
                    
                    if (newUnit === 1 && origUnit === 0) {
                        // Convert from kg to lbs for display
                        const lbsValue = (currentValue * 2.20462).toFixed(1);
                        weightGoalInput.value = lbsValue;
                        console.log('Converting weight goal from kg to lbs:', {
                            currentValue,
                            lbsValue
                        });
                    } else if (newUnit === 0 && origUnit === 1) {
                        // Convert from lbs to kg for display
                        const kgValue = (currentValue / 2.20462).toFixed(1);
                        weightGoalInput.value = kgValue;
                        console.log('Converting weight goal from lbs to kg:', {
                            currentValue,
                            kgValue
                        });
                    }
                }
                
                // Also convert current weight if it has a value
                if (currentWeightInput.value && !isNaN(parseFloat(currentWeightInput.value))) {
                    const currentValue = parseFloat(currentWeightInput.value);
                    
                    if (newUnit === 1 && origUnit === 0) {
                        // Convert from kg to lbs
                        const lbsValue = (currentValue * 2.20462).toFixed(1);
                        currentWeightInput.value = lbsValue;
                        console.log('Converting current weight from kg to lbs:', {
                            currentValue,
                            lbsValue
                        });
                    } else if (newUnit === 0 && origUnit === 1) {
                        // Convert from lbs to kg
                        const kgValue = (currentValue / 2.20462).toFixed(1);
                        currentWeightInput.value = kgValue;
                        console.log('Converting current weight from lbs to kg:', {
                            currentValue,
                            kgValue
                        });
                    }
                }
            }
            
            // Update current_display_unit hidden field
            document.getElementById('current_display_unit').value = this.value;
            
            currentWeightUnit = this.value;
            console.log('Updated currentWeightUnit:', currentWeightUnit);
            checkUnitPreferenceChanged();
        });
    });
    
    // No need to update a hidden field - we're sending the raw input value to the backend
    weightGoalInput.addEventListener('input', function() {
        checkFormChanged();
    });
    
    // Show confirmation modal for settings form
    saveButton.addEventListener('click', function() {
        if (validateInputs()) {
            // Check what values have changed
            const calorieChanged = calorieInput.value !== originalCalorieValue;
            const proteinChanged = proteinInput.value !== originalProteinValue;
            const weightGoalChanged = weightGoalInput.value !== originalWeightGoalValue;
            const currentWeightEntered = currentWeightInput.value.trim() !== '';
            
            // Only show confirmation if values have changed
            if (calorieChanged || proteinChanged || weightGoalChanged || currentWeightEntered) {
                // Update confirmation message based on what's changing
                let changeMessage = 'Are you sure you want to update your settings?';
                const changes = [];
                
                if (calorieChanged) {
                    changes.push('calorie goal');
                }
                if (proteinChanged) {
                    changes.push('protein goal');
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
                showToast('No changes to save.', 'info');
            }
        }
    });
    
    // Save unit preference
    saveUnitButton.addEventListener('click', function(e) {
        e.preventDefault();
        
        const selectedUnit = document.querySelector('input[name="weight_unit"]:checked').value;
        
        // Create a form data object
        const formData = new FormData();
        formData.append('weight_unit', selectedUnit);
        
        // Send AJAX request to update unit preference
        fetch('/update_weight_unit', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Create new variables instead of modifying the original constants
                // This avoids the "Attempted to assign to readonly property" error
                currentWeightUnit = selectedUnit;
                
                // Hide action buttons
                unitPreferenceActions.classList.add('hidden');
                
                // Show success message
                showToast('Weight unit preference updated successfully!', 'success');
                
                // Reload the page to ensure all values are updated correctly
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                showToast('Failed to update weight unit preference. Please try again.', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('An error occurred. Please try again.', 'error');
        });
    });
    
    // Cancel unit preference change
    cancelUnitButton.addEventListener('click', function(e) {
        e.preventDefault();
        
        // Reset to original weight unit
        document.querySelector(`input[name="weight_unit"][value="${originalWeightUnit}"]`).checked = true;
        
        // Update labels back to original
        const unitText = originalWeightUnit.toString() === '1' ? 'lbs' : 'kg';
        weightUnitLabels.forEach(label => {
            label.textContent = unitText;
        });
        
        // Reset current weight unit
        currentWeightUnit = originalWeightUnit.toString();
        
        // Update the hidden field
        document.getElementById('current_display_unit').value = originalWeightUnit.toString();
        
        // Hide action buttons
        unitPreferenceActions.classList.add('hidden');
        
        // Since we now have conversions happening in the UI, we need to reload
        // to ensure the values are correctly displayed in the original unit
        if (weightGoalInput.value || currentWeightInput.value) {
            // For simplicity, we'll reload the page to reset all values
            window.location.reload();
            return;
        }
        
        showToast('Changes cancelled', 'info');
    });
    
    // Cancel form changes
    cancelFormButton.addEventListener('click', function() {
        // Only show confirmation if values have changed
        if (settingsForm.classList.contains('settings-form-changed')) {
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
    
    // Confirm button submits the form via AJAX
    confirmButton.addEventListener('click', function() {
        // Hide the modal
        confirmationModal.classList.add('hidden');
        
        // Use the common function for AJAX submission
        submitFormViaAjax();
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

    // Create a function for form submission via AJAX to avoid duplication
    function submitFormViaAjax() {
        // First, show processing state
        const saveBtn = document.getElementById('save-button');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
        }
        
        $.ajax({
            url: URLS.updateSettings,
            type: "POST",
            data: $(settingsForm).serialize(),
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function(response) {
                if (response.success) {
                    // Update original values to match current form values
                    originalCalorieValue = calorieInput.value;
                    originalProteinValue = proteinInput.value;
                    originalWeightGoalValue = weightGoalInput.value;
                    
                    // Clear current weight input
                    currentWeightInput.value = '';
                    
                    // Reset form changed state
                    settingsForm.classList.remove('settings-form-changed');
                    
                    // Add a visual indication that the form was saved
                    settingsForm.classList.add('form-saved');
                    setTimeout(() => {
                        settingsForm.classList.remove('form-saved');
                    }, 1500);
                    
                    // Show success toast
                    showToast('Settings updated successfully!', 'success');
                    
                    // Run checkFormChanged to update UI state
                    checkFormChanged();
                }
            },
            error: function(xhr, status, error) {
                console.error('Settings update error:', {xhr, status, error});
                showToast('An error occurred. Please try again.', 'error');
            },
            complete: function() {
                // Reset button state
                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.textContent = 'Save Changes';
                }
            }
        });
    }
    
    // Form submission with AJAX
    settingsForm.addEventListener('submit', function(e) {
        e.preventDefault();
        submitFormViaAjax();
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