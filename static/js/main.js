// Polling interval (1 minute)
const POLL_INTERVAL = 60000;

// Track if we're currently polling
let pollInterval;

// Function to fetch fresh data
async function fetchFreshData() {
  try {
    const response = await fetch('/api/dashboard-stats');
    
    // Check if the response is ok
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Validate the response data structure
    if (!data || !data.daily_log || !data.stats || 
        !('total_calories' in data.stats) || 
        !('total_protein' in data.stats) || 
        !('calorie_goal' in data.stats) || 
        !('protein_goal' in data.stats)) {
      throw new Error('Invalid response data structure');
    }
    
    // Update the food log section
    const tableBody = document.querySelector('#daily-log');
    if (tableBody) {
      tableBody.innerHTML = data.daily_log.map(entry => {
        // Validate each entry has required fields
        if (!entry || !entry.id || !entry.food_name || 
            typeof entry.calories !== 'number' || 
            typeof entry.protein !== 'number') {
          console.warn('Invalid entry in daily log:', entry);
          return ''; // Skip invalid entries
        }
        
        return `
          <tr data-log-id="${entry.id}">
            <td class="p-2">${entry.food_name}</td>
            <td class="p-2">${entry.calories}</td>
            <td class="p-2">${entry.protein}g</td>
            <td class="p-2">
              <span class="material-symbols-outlined text-[#1F3C5E] cursor-pointer delete-icon" data-log-id="${entry.id}">delete</span>
            </td>
          </tr>
        `;
      }).join('');
    } else {
      console.warn('Could not find table body in DOM');
    }

    // Update navbar stats with the new data
    const { total_calories, total_protein, calorie_goal, protein_goal } = data.stats;
    updateNavbarStats(total_calories, total_protein, calorie_goal, protein_goal);

  } catch (error) {
    console.error('Error fetching fresh data:', error);
    // Don't update the UI if there was an error
    // This keeps the existing data on the page
    
    // Optionally show a toast message to the user
    if (typeof showToast === 'function') {  // Check if toast function exists
      showToast({
        message: 'Failed to refresh data. Will try again later.',
        category: 'error'
      });
    }
  }
}

// Update navbar stats
const updateNavbarStats = (totalCalories, totalProtein, calorieGoal, proteinGoal) => {
  try {
    // Validate inputs
    if (typeof totalCalories !== 'number' || 
        typeof totalProtein !== 'number' || 
        typeof calorieGoal !== 'number' || 
        typeof proteinGoal !== 'number') {
      throw new Error('Invalid input types for updateNavbarStats');
    }

    // Update desktop header
    const headerCalories = document.querySelector('#header-calories');
    const headerProtein = document.querySelector('#header-protein');
    const mobileHeaderCalories = document.querySelector('#mobile-header-calories');
    const mobileHeaderProtein = document.querySelector('#mobile-header-protein');

    if (headerCalories) headerCalories.textContent = totalCalories;
    if (headerProtein) headerProtein.textContent = totalProtein;
    if (mobileHeaderCalories) mobileHeaderCalories.textContent = totalCalories;
    if (mobileHeaderProtein) mobileHeaderProtein.textContent = totalProtein;

    // Calculate and update percentages
    const caloriePercentage = Math.min((totalCalories / calorieGoal) * 100, 100);
    const proteinPercentage = Math.min((totalProtein / proteinGoal) * 100, 100);

    // Update percentage text
    const caloriePercentageText = Math.round((totalCalories / calorieGoal) * 100) + '%';
    const proteinPercentageText = Math.round((totalProtein / proteinGoal) * 100) + '%';

    // Update desktop percentages
    const headerCaloriesPercentage = document.querySelector('#header-calories-percentage');
    const headerProteinPercentage = document.querySelector('#header-protein-percentage');
    const mobileHeaderCaloriesPercentage = document.querySelector('#mobile-header-calories-percentage');
    const mobileHeaderProteinPercentage = document.querySelector('#mobile-header-protein-percentage');

    if (headerCaloriesPercentage) headerCaloriesPercentage.textContent = caloriePercentageText;
    if (headerProteinPercentage) headerProteinPercentage.textContent = proteinPercentageText;
    if (mobileHeaderCaloriesPercentage) mobileHeaderCaloriesPercentage.textContent = caloriePercentageText;
    if (mobileHeaderProteinPercentage) mobileHeaderProteinPercentage.textContent = proteinPercentageText;

    // Update progress bars
    const updateProgressBar = (id, percentage, colorClass) => {
      const progressBar = document.querySelector(id);
      if (progressBar) {
        progressBar.style.width = percentage + '%';
        progressBar.className = `h-full rounded-full transition-all duration-300 ${colorClass}`;
      }
    };

    // Update calorie progress bars
    updateProgressBar('#calorie-progress', caloriePercentage, 
      caloriePercentage > 100 ? 'bg-red-500' : 'bg-blue-500');
    updateProgressBar('#mobile-calorie-progress', caloriePercentage,
      caloriePercentage > 100 ? 'bg-red-500' : 'bg-blue-500');

    // Update protein progress bars
    updateProgressBar('#protein-progress', proteinPercentage,
      proteinPercentage > 100 ? 'bg-yellow-500' : 'bg-green-500');
    updateProgressBar('#mobile-protein-progress', proteinPercentage,
      proteinPercentage > 100 ? 'bg-yellow-500' : 'bg-green-500');

    // Update the totals display in the food log section
    const totalCaloriesElement = document.querySelector('#total-calories');
    const totalProteinElement = document.querySelector('#total-protein');
    if (totalCaloriesElement) totalCaloriesElement.textContent = totalCalories;
    if (totalProteinElement) totalProteinElement.textContent = totalProtein + 'g';

  } catch (error) {
    console.error('Error updating navbar stats:', error);
    // Don't update anything if there was an error
    // This keeps the existing stats on the page
  }
};

// Start polling when the page loads
function startPolling() {
  // Initial fetch
  fetchFreshData();
  
  // Set up polling interval
  pollInterval = setInterval(fetchFreshData, POLL_INTERVAL);
}

// Stop polling when the page is hidden
function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

// Handle visibility changes
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    // App came into focus, fetch fresh data immediately
    fetchFreshData();
    // Restart polling
    startPolling();
  } else {
    // App went to background, stop polling
    stopPolling();
  }
});

// Start polling when the page loads
document.addEventListener('DOMContentLoaded', startPolling);