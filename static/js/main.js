// Polling interval (1 minute)
const POLL_INTERVAL = 60000;

// Track if we're currently polling
let pollInterval;

// Function to fetch fresh data
async function fetchFreshData() {
  console.log('Fetching fresh data...');
  try {
    const response = await fetch('/dashboard');
    const html = await response.text();
    
    // Parse the HTML response
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    
    // Update the food log section only (without totals)
    const foodLog = doc.querySelector('#todaysLogSection');
    if (foodLog) {
      console.log('Found food log section in response');
      // Get the table body content only
      const tableBody = foodLog.querySelector('#daily-log');
      if (tableBody) {
        console.log('Found table body in response');
        const currentTableBody = document.querySelector('#daily-log');
        if (currentTableBody) {
          console.log('Updating table body with new content');
          currentTableBody.innerHTML = tableBody.innerHTML;
        } else {
          console.warn('Could not find current table body in DOM');
        }
      } else {
        console.warn('Could not find table body in response');
      }
    } else {
      console.warn('Could not find food log section in response');
    }

    // Extract totals from the response
    const totalCalories = parseInt(doc.querySelector('#total-calories')?.textContent || '0');
    const totalProtein = parseInt(doc.querySelector('#total-protein')?.textContent || '0');
    const calorieGoal = parseInt(doc.querySelector('#calorie-goal')?.textContent || '0');
    const proteinGoal = parseInt(doc.querySelector('#protein-goal')?.textContent || '0');

    console.log('Extracted totals from response:', {
      totalCalories,
      totalProtein,
      calorieGoal,
      proteinGoal
    });

    // Update navbar stats
    const updateNavbarStats = (totalCalories, totalProtein, calorieGoal, proteinGoal) => {
      console.log('Current DOM state before navbar update:', {
        headerCalories: document.querySelector('#header-calories')?.textContent,
        headerProtein: document.querySelector('#header-protein')?.textContent,
        totalCalories: document.querySelector('#total-calories')?.textContent,
        totalProtein: document.querySelector('#total-protein')?.textContent
      });

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

      console.log('DOM state after navbar update:', {
        headerCalories: document.querySelector('#header-calories')?.textContent,
        headerProtein: document.querySelector('#header-protein')?.textContent,
        totalCalories: document.querySelector('#total-calories')?.textContent,
        totalProtein: document.querySelector('#total-protein')?.textContent
      });
    };

    // Update navbar stats
    updateNavbarStats(totalCalories, totalProtein, calorieGoal, proteinGoal);

  } catch (error) {
    console.error('Error fetching fresh data:', error);
  }
}

// Start polling when the page loads
function startPolling() {
  console.log('Starting polling...');
  // Initial fetch
  fetchFreshData();
  
  // Set up polling interval
  pollInterval = setInterval(fetchFreshData, POLL_INTERVAL);
  console.log('Polling interval set to:', POLL_INTERVAL, 'ms');
}

// Stop polling when the page is hidden
function stopPolling() {
  if (pollInterval) {
    console.log('Stopping polling...');
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

// Handle visibility changes
document.addEventListener('visibilitychange', () => {
  console.log('Visibility changed:', document.visibilityState);
  if (document.visibilityState === 'visible') {
    // App came into focus, fetch fresh data immediately
    console.log('Page became visible, fetching fresh data...');
    fetchFreshData();
    // Restart polling
    startPolling();
  } else {
    // App went to background, stop polling
    console.log('Page hidden, stopping polling...');
    stopPolling();
  }
});

// Start polling when the page loads
document.addEventListener('DOMContentLoaded', startPolling);