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

// Initialize charts with default data (30 days)
let filteredData = filterDataByDays('30');
updateSummaryStats(filteredData);

// Calorie Chart
const calorieCtx = document.getElementById('calorieChart').getContext('2d');
const calorieChart = new Chart(calorieCtx, {
    type: 'bar',
    data: {
        labels: formatDates(filteredData.dates),
        datasets: [
            {
                label: 'Calories',
                data: filteredData.calories,
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            },
            {
                label: 'Calorie Goal',
                data: filteredData.calorieGoals,
                type: 'line',
                fill: false,
                borderColor: 'rgba(255, 99, 132, 1)',
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

// Protein Chart
const proteinCtx = document.getElementById('proteinChart').getContext('2d');
const proteinChart = new Chart(proteinCtx, {
    type: 'bar',
    data: {
        labels: formatDates(filteredData.dates),
        datasets: [
            {
                label: 'Protein (g)',
                data: filteredData.proteins,
                backgroundColor: 'rgba(75, 192, 192, 0.5)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            },
            {
                label: 'Protein Goal (g)',
                data: filteredData.proteinGoals,
                type: 'line',
                fill: false,
                borderColor: 'rgba(153, 102, 255, 1)',
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

// Weight Chart (replace Jinja conditional)
if (allWeights.length > 0) {
    const weightCtx = document.getElementById('weightChart').getContext('2d');

    // Create an array of the weight goal for each date point
    let weightGoalArray = Array(filteredData.weights.length).fill(weightGoal);

    const weightChart = new Chart(weightCtx, {
        type: 'line',
        data: {
            labels: formatDates(filteredData.weightDates),
            datasets: [
                {
                    label: `Weight (${weightUnit})`,
                    data: filteredData.weights,
                    backgroundColor: 'rgba(255, 159, 64, 0.5)',
                    borderColor: 'rgba(255, 159, 64, 1)',
                    borderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.1
                },
                // Replace Jinja weight_goal conditional
                ...(weightGoal ? [{
                    label: `Weight Goal (${weightUnit})`,
                    data: weightGoalArray,
                    backgroundColor: 'rgba(201, 203, 207, 0.5)',
                    borderColor: 'rgba(201, 203, 207, 1)',
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

    // Time range selector event listener
    document.getElementById('timeRangeSelector').addEventListener('change', function() {
        // ... existing update code ...
        
        // Update weight chart (replace Jinja conditional)
        weightGoalArray = Array(filteredData.weights.length).fill(weightGoal);
        weightChart.data.labels = formatDates(filteredData.weightDates);
        weightChart.data.datasets[0].data = filteredData.weights;
        weightChart.data.datasets[0].label = `Weight (${weightUnit})`;
        
        if (weightGoal) {
            weightChart.data.datasets[1].data = weightGoalArray;
            weightChart.data.datasets[1].label = `Weight Goal (${weightUnit})`;
        }
        
        // Update y-axis title
        weightChart.options.scales.y.title.text = `Weight (${weightUnit})`;
        
        weightChart.update();
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
