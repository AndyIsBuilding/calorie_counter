document.addEventListener('DOMContentLoaded', function() {
    const foodTable = document.getElementById('food-table').getElementsByTagName('tbody')[0];
    const addFoodButton = document.getElementById('add-food');
    const dateInput = document.getElementById('date');
    const dateDisplay = document.getElementById('date-display');
    
    function clearTable() {
        foodTable.innerHTML = '';
    }

    function fetchDailyLog(date) {
        fetch(`${URLS.editHistory}?date=${date}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            populateExistingFoods(data.daily_log);
        });
    }

    function updateDateDisplay(date) {
        const options = { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' };
        const formattedDate = new Date(date + 'T00:00:00Z').toLocaleDateString('en-US', options);
        dateDisplay.textContent = `Foods for ${formattedDate}`;
    }
    
    dateInput.addEventListener('change', function() {
        fetchDailyLog(this.value);
        updateDateDisplay(this.value);
    });
    
    function createExistingFoodRow(food) {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-100 border-t transition-colors';
        row.innerHTML = `
            <td class="p-2">${food.name}</td>
            <td class="p-2">${food.calories}</td>
            <td class="p-2">${food.protein}</td>
            <td class="p-2">
                <input type="hidden" name="existing_food_id[]" value="${food.id}">
                <button type="button" class="bg-red-500 hover:bg-red-600 text-white py-1 px-2 rounded-md transition-colors">Remove</button>
            </td>
        `;
        return row;
    }

    function createNewFoodRow() {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-100 border-t transition-colors';
        row.innerHTML = `
            <td class="p-2"><input type="text" name="new_food_name[]" required class="w-full px-2 py-1 border rounded-md"></td>
            <td class="p-2"><input type="number" name="new_food_calories[]" required class="w-full px-2 py-1 border rounded-md"></td>
            <td class="p-2"><input type="number" name="new_food_protein[]" required class="w-full px-2 py-1 border rounded-md"></td>
            <td class="p-2"><button type="button" class="bg-red-500 hover:bg-red-600 text-white py-1 px-2 rounded-md transition-colors">Remove</button></td>
        `;
        return row;
    }

    function populateExistingFoods(foods) {
        clearTable();
        foods.forEach(food => {
            foodTable.appendChild(createExistingFoodRow(food));
        });
    }

    addFoodButton.addEventListener('click', function() {
        foodTable.appendChild(createNewFoodRow());
    });
    
    foodTable.addEventListener('click', function(e) {
        if (e.target.tagName === 'BUTTON' && 
            (e.target.classList.contains('bg-red-500') || 
             e.target.classList.contains('remove-food') || 
             e.target.classList.contains('button-remove') || 
             e.target.classList.contains('delete-button'))) {
            e.target.closest('tr').remove();
        }
    });

    // Initialize the table with the initial state data
    clearTable();
    populateExistingFoods(INITIAL_STATE.dailyLog);
});
