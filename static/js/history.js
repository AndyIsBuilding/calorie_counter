// Use initial state data instead of template variables
const {
    chartDates: allDates,
    chartCalories: allCalories,
    chartCalorieGoals: allCalorieGoals,
    chartProteins: allProteins,
    chartProteinGoals: allProteinGoals,
    weightDates: allWeightDates,
    weights: allWeights,
    weightUnit,
    weightGoal
} = INITIAL_STATE;

// Format number with commas for thousands
function formatNumberWithCommas(number) {
    return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Calculate summary statistics
function updateSummaryStats(data) {
    // Calculate average calories
    const avgCalories = data.calories.length > 0 
        ? Math.round(data.calories.reduce((a, b) => a + b, 0) / data.calories.length) 
        : 0;
    document.getElementById('avgCalories').textContent = formatNumberWithCommas(avgCalories);
    
    // Set calorie goal (use the most recent one)
    const calorieGoal = data.calorieGoals.length > 0 
        ? data.calorieGoals[data.calorieGoals.length - 1] 
        : 0;
    document.getElementById('calorieGoal').textContent = formatNumberWithCommas(calorieGoal);
    
    // Calculate average protein
    const avgProtein = data.proteins.length > 0 
        ? Math.round(data.proteins.reduce((a, b) => a + b, 0) / data.proteins.length) 
        : 0;
    document.getElementById('avgProtein').textContent = formatNumberWithCommas(avgProtein) + 'g';
    
    // Set protein goal (use the most recent one)
    const proteinGoal = data.proteinGoals.length > 0 
        ? data.proteinGoals[data.proteinGoals.length - 1] 
        : 0;
    document.getElementById('proteinGoal').textContent = formatNumberWithCommas(proteinGoal) + 'g';
    
    // Set latest weight (replace Jinja conditional)
    if (allWeights.length > 0) {
        const latestWeight = data.weights.length > 0 
            ? data.weights[data.weights.length - 1] 
            : 0;
        document.getElementById('latestWeight').textContent = latestWeight.toFixed(1) + ` ${weightUnit}`;
    }
}

// Format dates for better display
function formatDates(dates) {
    return dates.map(date => {
        const [year, month, day] = date.split('-');
        return `${month}/${day}`;
    });
}

// Filter data based on selected time range
function filterDataByDays(days) {
    // Check if we have any data at all
    if (allDates.length === 0) {
        return {
            dates: [],
            calories: [],
            calorieGoals: [],
            proteins: [],
            proteinGoals: [],
            weightDates: [],
            weights: []
        };
    }
    
    if (days === 'all') {
        return {
            dates: allDates,
            calories: allCalories,
            calorieGoals: allCalorieGoals,
            proteins: allProteins,
            proteinGoals: allProteinGoals,
            weightDates: allWeightDates,
            weights: allWeights
        };
    }
    
    const daysNum = parseInt(days);
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - daysNum);
    const cutoffDateStr = cutoffDate.toISOString().split('T')[0];
    
    // Filter nutrition data
    const filteredIndices = [];
    for (let i = 0; i < allDates.length; i++) {
        if (allDates[i] >= cutoffDateStr) {
            filteredIndices.push(i);
        }
    }
    
    const filteredDates = filteredIndices.map(i => allDates[i]);
    const filteredCalories = filteredIndices.map(i => allCalories[i]);
    const filteredCalorieGoals = filteredIndices.map(i => allCalorieGoals[i]);
    const filteredProteins = filteredIndices.map(i => allProteins[i]);
    const filteredProteinGoals = filteredIndices.map(i => allProteinGoals[i]);
    
    // Filter weight data
    const filteredWeightIndices = [];
    for (let i = 0; i < allWeightDates.length; i++) {
        if (allWeightDates[i] >= cutoffDateStr) {
            filteredWeightIndices.push(i);
        }
    }
    
    const filteredWeightDates = filteredWeightIndices.map(i => allWeightDates[i]);
    const filteredWeights = filteredWeightIndices.map(i => allWeights[i]);
    
    return {
        dates: filteredDates,
        calories: filteredCalories,
        calorieGoals: filteredCalorieGoals,
        proteins: filteredProteins,
        proteinGoals: filteredProteinGoals,
        weightDates: filteredWeightDates,
        weights: filteredWeights
    };
}

// Wrap all initialization code in a DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', function() {
    // Calculate the actual data range in days
    let oldestDate = null;
    if (allDates.length > 0) {
        // Find the oldest date in nutrition data
        oldestDate = new Date(Math.min(...allDates.map(d => new Date(d))));
        
        // Check if we have weight data that goes back further
        if (allWeightDates.length > 0) {
            const oldestWeightDate = new Date(Math.min(...allWeightDates.map(d => new Date(d))));
            
            if (oldestWeightDate < oldestDate) {
                oldestDate = oldestWeightDate;
            }
        }
    }
    
    // Calculate days of data available
    let daysOfDataAvailable = 0;
    if (oldestDate) {
        const today = new Date();
        const diffTime = Math.abs(today - oldestDate);
        daysOfDataAvailable = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    }
    
    // Update time range selector options based on available data
    const timeRangeSelector = document.getElementById('timeRangeSelector');
    if (timeRangeSelector) {
        // Remove options that exceed our data range
        Array.from(timeRangeSelector.options).forEach(option => {
            const value = parseInt(option.value);
            if (!isNaN(value) && value > daysOfDataAvailable) {
                option.disabled = true;
                option.text += ` (insufficient data - only ${daysOfDataAvailable} days available)`;
            }
        });
        
        // Set the default selection to the appropriate option
        if (daysOfDataAvailable <= 7) {
            timeRangeSelector.value = 'all';
        } else if (daysOfDataAvailable <= 14) {
            timeRangeSelector.value = '7';
        } else if (daysOfDataAvailable <= 30) {
            timeRangeSelector.value = '14';
        } else {
            timeRangeSelector.value = '30'; // Default to 30 days
        }
    }

    // Initialize charts with default data (30 days or all if less data available)
    let initialTimeRange = timeRangeSelector ? timeRangeSelector.value : '30';
    let filteredData = filterDataByDays(initialTimeRange);
    updateSummaryStats(filteredData);

    // Calorie Chart
    const calorieCtx = document.getElementById('calorieChart')?.getContext('2d');
    let calorieChart;
    if (calorieCtx) {
        calorieChart = new Chart(calorieCtx, {
            type: 'bar',
            data: {
                labels: formatDates(filteredData.dates),
                datasets: [
                    {
                        label: 'Calories',
                        data: filteredData.calories,
                        backgroundColor: 'rgba(39, 76, 119, 0.5)',
                        borderColor: 'rgba(39, 76, 119, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Calorie Goal',
                        data: filteredData.calorieGoals,
                        type: 'line',
                        fill: false,
                        borderColor: 'rgba(163, 206, 241, 1)',
                        borderWidth: 2,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Calories'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Date'
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            autoSkip: true,
                            maxTicksLimit: 15
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            title: function(tooltipItems) {
                                const index = tooltipItems[0].dataIndex;
                                return filteredData.dates[index];
                            }
                        }
                    },
                    decimation: {
                        enabled: true,
                        algorithm: 'min-max'
                    }
                }
            }
        });
    }

    // Protein Chart
    const proteinCtx = document.getElementById('proteinChart')?.getContext('2d');
    let proteinChart;
    if (proteinCtx) {
        proteinChart = new Chart(proteinCtx, {
            type: 'bar',
            data: {
                labels: formatDates(filteredData.dates),
                datasets: [
                    {
                        label: 'Protein (g)',
                        data: filteredData.proteins,
                        backgroundColor: 'rgba(96, 150, 186, 0.5)',
                        borderColor: 'rgba(96, 150, 186, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Protein Goal (g)',
                        data: filteredData.proteinGoals,
                        type: 'line',
                        fill: false,
                        borderColor: 'rgba(96, 150, 186, 1)',
                        borderWidth: 2,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Protein (g)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Date'
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            autoSkip: true,
                            maxTicksLimit: 15
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            title: function(tooltipItems) {
                                const index = tooltipItems[0].dataIndex;
                                return filteredData.dates[index];
                            }
                        }
                    },
                    decimation: {
                        enabled: true,
                        algorithm: 'min-max'
                    }
                }
            }
        });
    }

    // Weight Chart (replace Jinja conditional)
    let weightChart;
    if (allWeights.length > 0) {
        const weightCtx = document.getElementById('weightChart')?.getContext('2d');
        if (weightCtx) {
            // Create an array of the weight goal for each date point
            let weightGoalArray = Array(filteredData.weights.length).fill(weightGoal);

            weightChart = new Chart(weightCtx, {
                type: 'line',
                data: {
                    labels: formatDates(filteredData.weightDates),
                    datasets: [
                        {
                            label: `Weight (${weightUnit})`,
                            data: filteredData.weights,
                            backgroundColor: 'rgba(139, 140, 137, 0.5)',
                            borderColor: 'rgba(139, 140, 137, 1)',
                            borderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            tension: 0.1
                        },
                        // Replace Jinja weight_goal conditional
                        ...(weightGoal ? [{
                            label: `Weight Goal (${weightUnit})`,
                            data: weightGoalArray,
                            backgroundColor: 'rgba(139, 140, 137, 0.5)',
                            borderColor: 'rgba(139, 140, 137, 1)',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            pointRadius: 0,
                            fill: false
                        }] : [])
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            title: {
                                display: true,
                                text: `Weight (${weightUnit})`
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Date'
                            },
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45,
                                autoSkip: true,
                                maxTicksLimit: 15
                            }
                        }
                    },
                    plugins: {
                        tooltip: {
                            callbacks: {
                                title: function(tooltipItems) {
                                    const index = tooltipItems[0].dataIndex;
                                    return filteredData.weightDates[index];
                                }
                            }
                        },
                        decimation: {
                            enabled: true,
                            algorithm: 'min-max',
                            samples: 50
                        }
                    }
                }
            });
        }
    }

    // Time range selector event listener
    if (timeRangeSelector) {
        timeRangeSelector.addEventListener('change', function() {
            // Get the selected time range
            const selectedDays = this.value;
            
            // Filter data based on selected time range
            filteredData = filterDataByDays(selectedDays);
            
            // Update summary statistics
            updateSummaryStats(filteredData);
            
            // Update calorie chart
            if (calorieChart) {
                calorieChart.data.labels = formatDates(filteredData.dates);
                calorieChart.data.datasets[0].data = filteredData.calories;
                calorieChart.data.datasets[1].data = filteredData.calorieGoals;
                calorieChart.update();
            }
            
            // Update protein chart
            if (proteinChart) {
                proteinChart.data.labels = formatDates(filteredData.dates);
                proteinChart.data.datasets[0].data = filteredData.proteins;
                proteinChart.data.datasets[1].data = filteredData.proteinGoals;
                proteinChart.update();
            }
            
            // Update weight chart if it exists
            if (weightChart) {
                const weightGoalArray = Array(filteredData.weights.length).fill(weightGoal);
                weightChart.data.labels = formatDates(filteredData.weightDates);
                weightChart.data.datasets[0].data = filteredData.weights;
                
                if (weightGoal && weightChart.data.datasets.length > 1) {
                    weightChart.data.datasets[1].data = weightGoalArray;
                }
                
                weightChart.update();
            }
        });
    }

    // Update export and edit history links in HTML
    document.querySelectorAll('a[href]').forEach(link => {
        if (link.getAttribute('href').includes('export_csv')) {
            link.href = URLS.exportCsv;
        } else if (link.getAttribute('href').includes('edit_history')) {
            link.href = URLS.editHistory;
        }
    });
});
