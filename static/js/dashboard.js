// Wait for both DOM and all resources to be loaded
window.addEventListener('load', function() {
    // Initialize Lucide icons if we're using them
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    // Check if jQuery is loaded
    if (typeof $ === 'undefined') {
        console.error('jQuery is not loaded! Please ensure jQuery is included before dashboard.js');
        return;
    }

    // Check for required global variables
    if (typeof URLS === 'undefined' || typeof INITIAL_STATE === 'undefined') {
        console.error('Required global variables (URLS or INITIAL_STATE) are not defined!');
        return;
    }

    // Original document.ready code
    $(document).ready(function() {
        // Check if summary exists for today
        let summaryExists = INITIAL_STATE.hasSummary;
        
        // Handle Quick Add button clicks
        $(document).on('click', '.quick-add-button', function(e) {
            e.preventDefault();
            var $button = $(this);
            var foodId = $button.data('food-id');
            console.debug('Quick add button clicked for food ID:', foodId);
            
            // Add pressed effect
            $button.addClass('pressed');
            
            $.ajax({
                url: URLS.logQuickFood,
                type: 'POST',
                data: { food_id: foodId },
                success: function(response) {
                    if (response.success) {
                        if (!summaryExists) {
                            updateTodaysLog(response.log_entry);
                            // Ensure we're using the server's calculated totals
                            if (response.totals) {
                                updateTotals(response.totals);
                            } else {
                                console.warn('No totals data received from server');
                            }
                        }
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Quick Add AJAX Error:', {xhr, status, error});
                    showToast('❌ Error adding food', 'error');
                },
                complete: function() {
                    // Remove pressed effect after a short delay
                    setTimeout(function() {
                        $button.removeClass('pressed');
                        // Force a repaint to ensure the button returns to its original state
                        $button[0].offsetHeight;
                    }, 300);
                }
            });
        });

        // Handle Add to Quick Add form submission
        $('#addFoodForm').submit(function(e) {
            console.debug('Form submission detected. Action:', $(this).attr('action'), 'Event:', e);
            
            // Add a timestamp to track if multiple submissions are happening
            const submissionTime = new Date().getTime();
            console.debug('Form submission timestamp:', submissionTime);
            
            if ($(this).attr('action') === URLS.quickAddFood) {
                e.preventDefault();
                $.ajax({
                    url: $(this).attr('action'),
                    type: 'POST',
                    data: $(this).serialize(),
                    success: function(response) {
                        if (response.success) {
                            addQuickAddButton(response.food);
                            $('#addFoodForm')[0].reset();
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('Quick Add Form AJAX Error:', {xhr, status, error});
                    }
                });
            } else if ($(this).attr('action') === URLS.logFood) {
                e.preventDefault();
                console.debug('Log food form submission. Form data:', $(this).serialize());
                
                $.ajax({
                    url: $(this).attr('action'),
                    type: 'POST',
                    data: $(this).serialize(),
                    success: function(response) {
                        if (response.success) {
                            if (!summaryExists) {
                                updateTodaysLog(response.log_entry);
                                if (response.totals) {
                                    setTotals(response.totals);
                                } else {
                                    // Only show this toast manually since it's an edge case
                                    showToast('Unable to update totals. Please refresh the page.', 'warning');
                                }
                            }
                            $('#addFoodForm')[0].reset();
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('Log Food AJAX Error:', {xhr, status, error});
                    }
                });
            }
        });

        // Handle Remove Food button clicks
        $(document).on('click', '.delete-button', function(e) {
            e.preventDefault();
            var logId = $(this).data('log-id');
            
            // Construct the URL correctly
            var removeUrl = URLS.removeFood + logId;
            console.debug('Removing food with ID:', logId, 'URL:', removeUrl);
            
            $.ajax({
                url: removeUrl,
                type: 'POST',
                success: function(response) {
                    if (response.success) {
                        $('tr[data-log-id="' + logId + '"]').remove();
                        if (response.totals) {
                            setTotals(response.totals);
                        }
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Remove Food Error:', {xhr, status, error});
                    showToast('❌ Error removing food', 'error');
                }
            });
        });
        
        // Handle Save Summary button click
        $('#saveSummaryBtn').click(function() {
            const $button = $(this);
            
            // Prevent multiple clicks
            if ($button.hasClass('processing')) {
                return;
            }
            
            // Add processing state
            $button.addClass('processing').prop('disabled', true);
            $button.html('<i class="fas fa-spinner fa-spin mr-2"></i> Processing...');
            
            $.ajax({
                url: URLS.saveSummary,
                type: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                success: function(response) {
                    if (response.success) {
                        showToast('✅ ' + response.message);
                        
                        // Update UI to show summary saved state
                        summaryExists = true;
                        $('#todaysLogSection').hide();
                        $('#summaryExistsMessage').show();
                        
                        // Update the totals if they were returned
                        if (response.totals) {
                            // Use the existing setTotals function to update all UI elements
                            setTotals(response.totals);
                        }
                    }
                },
                error: function() {
                    showToast('❌ Error saving summary. Please try again.');
                },
                complete: function() {
                    // Remove processing state after a short delay
                    setTimeout(function() {
                        $button.removeClass('processing').prop('disabled', false);
                        $button.html('Update Daily Summary');
                    }, 500);
                }
            });
        });

        // Initialize recommendations
        initializeRecommendations();
    });
});

function updateTodaysLog(logEntry) {
    $('#daily-log').append(
        '<tr data-log-id="' + logEntry.id + '">' +
            '<td class="p-2">' + logEntry.food_name + '</td>' +
            '<td class="p-2">' + logEntry.calories + '</td>' +
            '<td class="p-2">' + logEntry.protein + 'g</td>' +
            '<td class="p-2">' +
                '<button class="delete-button bg-red-500 text-white py-1 px-2 rounded-md hover:bg-red-600" data-log-id="' + logEntry.id + '"><i class="fas fa-trash"></i></button>' +
            '</td>' +
        '</tr>'
    );
}

function updateTotals(totals) {    
    // Get current totals from DOM
    const currentCalories = parseInt($('#total-calories').text()) || 0;
    const currentProtein = parseInt($('#total-protein').text()) || 0;
    
    // Calculate new totals by adding new values to current totals
    const newCalories = currentCalories + totals.calories;
    const newProtein = currentProtein + totals.protein;
    
    // Update the original totals at bottom of page
    $('#total-calories').text(newCalories);
    $('#total-protein').text(newProtein + 'g');
    
    // Update desktop header totals
    $('#header-calories').text(newCalories);
    $('#header-protein').text(newProtein);
    
    // Update mobile header totals
    $('#mobile-header-calories').text(newCalories);
    $('#mobile-header-protein').text(newProtein);
    
    // Calculate percentages
    const calorieGoal = parseInt($('#calorie-goal').text());
    const proteinGoal = parseInt($('#protein-goal').text());
    
    const caloriePercentage = Math.min((newCalories / calorieGoal) * 100, 100);
    const proteinPercentage = Math.min((newProtein / proteinGoal) * 100, 100);
    
    // Update percentage indicators
    const caloriePercentageText = Math.round(newCalories / calorieGoal * 100) + '%';
    const proteinPercentageText = Math.round(newProtein / proteinGoal * 100) + '%';
    
    // Update desktop percentage indicators
    $('#header-calories-percentage').text(caloriePercentageText);
    $('#header-protein-percentage').text(proteinPercentageText);
    
    // Update mobile percentage indicators
    $('#mobile-header-calories-percentage').text(caloriePercentageText);
    $('#mobile-header-protein-percentage').text(proteinPercentageText);
    
    // Update all progress bars (desktop and mobile)
    $('#calorie-progress, #mobile-calorie-progress').css('width', caloriePercentage + '%');
    $('#protein-progress, #mobile-protein-progress').css('width', proteinPercentage + '%');
    
    // Add color indicators based on progress
    if (caloriePercentage > 100) {
        $('#calorie-progress, #mobile-calorie-progress').removeClass('bg-blue-500').addClass('bg-red-500');
    } else {
        $('#calorie-progress, #mobile-calorie-progress').removeClass('bg-red-500').addClass('bg-blue-500');
    }
    
    if (proteinPercentage > 100) {
        $('#protein-progress, #mobile-protein-progress').removeClass('bg-green-500').addClass('bg-yellow-500');
    } else {
        $('#protein-progress, #mobile-protein-progress').removeClass('yellow-500').addClass('bg-green-500');
    }
}

function setTotals(totals) {    
    // Set totals directly from server response instead of adding to current values
    const newCalories = totals.calories;
    const newProtein = totals.protein;
    
    // Update the original totals at bottom of page
    $('#total-calories').text(newCalories);
    $('#total-protein').text(newProtein + 'g');
    
    // Update desktop header totals
    $('#header-calories').text(newCalories);
    $('#header-protein').text(newProtein);
    
    // Update mobile header totals
    $('#mobile-header-calories').text(newCalories);
    $('#mobile-header-protein').text(newProtein);
    
    // Calculate percentages
    const calorieGoal = parseInt($('#calorie-goal').text());
    const proteinGoal = parseInt($('#protein-goal').text());
    
    const caloriePercentage = Math.min((newCalories / calorieGoal) * 100, 100);
    const proteinPercentage = Math.min((newProtein / proteinGoal) * 100, 100);
    
    // Update percentage indicators
    const caloriePercentageText = Math.round(newCalories / calorieGoal * 100) + '%';
    const proteinPercentageText = Math.round(newProtein / proteinGoal * 100) + '%';
    
    // Update desktop percentage indicators
    $('#header-calories-percentage').text(caloriePercentageText);
    $('#header-protein-percentage').text(proteinPercentageText);
    
    // Update mobile percentage indicators
    $('#mobile-header-calories-percentage').text(caloriePercentageText);
    $('#mobile-header-protein-percentage').text(proteinPercentageText);
    
    // Update all progress bars (desktop and mobile)
    $('#calorie-progress, #mobile-calorie-progress').css('width', caloriePercentage + '%');
    $('#protein-progress, #mobile-protein-progress').css('width', proteinPercentage + '%');
    
    // Add color indicators based on progress
    if (caloriePercentage > 100) {
        $('#calorie-progress, #mobile-calorie-progress').removeClass('bg-blue-500').addClass('bg-red-500');
    } else {
        $('#calorie-progress, #mobile-calorie-progress').removeClass('bg-red-500').addClass('bg-blue-500');
    }
    
    if (proteinPercentage > 100) {
        $('#protein-progress, #mobile-protein-progress').removeClass('bg-green-500').addClass('bg-yellow-500');
    } else {
        $('#protein-progress, #mobile-protein-progress').removeClass('yellow-500').addClass('bg-green-500');
    }
}

function addQuickAddButton(food) {
    $('.quick-add-grid').append(
        '<button type="button" class="quick-add-button w-full bg-gray-100 text-gray-700 py-2 px-4 rounded-md hover:bg-blue-500 text-sm border-2 border-blue-500 hover:text-white" data-food-id="' + food.id + '">' +
            food.name +
        '</button>'
    );
}

function initializeRecommendations() {
    document.getElementById('showRecommendationsBtn').addEventListener('click', function() {
        fetch('/get_recommendations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            const errorMessageDiv = document.getElementById('errorMessage');
            const recommendationResultsDiv = document.getElementById('recommendationResults');
            document.getElementById('recommendationsContainer').classList.remove('hidden');
            
            // Check if we received an insufficient foods message
            if (data.insufficient_foods) {
                errorMessageDiv.classList.remove('hidden');
                recommendationResultsDiv.classList.add('hidden');
                document.getElementById('hitBoth').textContent = data.message;
                return;
            }
            
            // Show recommendations
            errorMessageDiv.classList.add('hidden');
            recommendationResultsDiv.classList.remove('hidden');
            
            const formatRecommendation = (recommendation) => {
                if (!recommendation || !recommendation.foods || recommendation.foods.length === 0) {
                    return 'No recommendations available';
                }
                const foodList = recommendation.foods.map(food => 
                    `${food.name} ${food.calories}cal (${food.protein}g)`
                ).join(', ');
                return `${foodList} -- Recommendation Total: ${recommendation.total_calories}cal (${recommendation.total_protein}g) -- Day's Total: ${recommendation.day_total_calories}cal (${recommendation.day_total_protein}g)`;
            };

            document.getElementById('hitBothResult').textContent = formatRecommendation(data.hit_both);
            document.getElementById('prioritizeProtein').textContent = formatRecommendation(data.protein_first);
            document.getElementById('prioritizeCalories').textContent = formatRecommendation(data.calorie_first);
        })
        .catch((error) => {
            console.error('Error:', error);
            document.getElementById('recommendationsContainer').classList.remove('hidden');
            document.getElementById('errorMessage').classList.remove('hidden');
            document.getElementById('recommendationResults').classList.add('hidden');
            document.getElementById('hitBoth').textContent = 'Error getting recommendations. Please try again.';
        });
    });
}

function setFormAction(action) {
    document.getElementById('addFoodForm').action = action;
}