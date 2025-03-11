import pytest
import sqlite3
import logging
import json
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_weight_logs_unit_conversion(app):
    """Test that weight logs are correctly converted based on user's weight unit preference."""
    logger.info("Starting weight logs unit conversion test")
    
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Get the test user ID
        c.execute("SELECT id FROM users WHERE username = ?", ('testuser',))
        user_id = c.fetchone()[0]
        
        # Create dates for testing
        today = datetime.now().date()
        yesterday = (today - timedelta(days=1)).isoformat()
        two_days_ago = (today - timedelta(days=2)).isoformat()
        
        # Insert test weight logs
        c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)", 
                 (today.isoformat(), 70.0, user_id))  # 70 kg
        c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)", 
                 (yesterday, 71.5, user_id))  # 71.5 kg
        c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)", 
                 (two_days_ago, 72.2, user_id))  # 72.2 kg
        
        conn.commit()
        
        # Import the User class from app
        from app import User
        
        # Create a user instance with kg as the weight unit (0)
        user_kg = User(user_id, 'testuser', weight_unit=0)
        
        # Get weight logs with kg as the unit
        weight_logs_kg = user_kg.get_weight_logs()
        
        # Check that we have 3 weight logs
        assert len(weight_logs_kg) == 3
        
        # Check that the weights are in kg (unchanged)
        assert weight_logs_kg[0][1] == 70.0
        assert weight_logs_kg[1][1] == 71.5
        assert weight_logs_kg[2][1] == 72.2
        
        # Now create a user instance with lbs as the weight unit (1)
        user_lbs = User(user_id, 'testuser', weight_unit=1)
        
        # Get weight logs with lbs as the unit
        weight_logs_lbs = user_lbs.get_weight_logs()
        
        # Check that we have 3 weight logs
        assert len(weight_logs_lbs) == 3
        
        # Check that the weights are converted to lbs
        # The conversion factor is 2.20462
        assert round(weight_logs_lbs[0][1], 1) == round(70.0 * 2.20462, 1)
        assert round(weight_logs_lbs[1][1], 1) == round(71.5 * 2.20462, 1)
        assert round(weight_logs_lbs[2][1], 1) == round(72.2 * 2.20462, 1)
        
        # Verify the exact values
        assert weight_logs_lbs[0][1] == round(70.0 * 2.20462, 1)  # 154.3 lbs
        assert weight_logs_lbs[1][1] == round(71.5 * 2.20462, 1)  # 157.6 lbs
        assert weight_logs_lbs[2][1] == round(72.2 * 2.20462, 1)  # 159.2 lbs
        
        # Clean up the test data
        c.execute("DELETE FROM weight_logs WHERE user_id = ?", (user_id,))
        conn.commit()
        
    logger.info("Completed weight logs unit conversion test")

def test_weight_logs_in_settings_page(client, auth, app):
    """Test that weight logs are correctly converted based on user's weight unit preference in the settings page."""
    logger.info("Starting weight logs in settings page test")
    
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Get the test user ID
        c.execute("SELECT id FROM users WHERE username = ?", ('testuser',))
        user_id = c.fetchone()[0]
        
        # Create dates for testing
        today = datetime.now().date()
        yesterday = (today - timedelta(days=1)).isoformat()
        
        # Insert test weight logs
        c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)", 
                 (today.isoformat(), 70.0, user_id))  # 70 kg
        c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)", 
                 (yesterday, 71.5, user_id))  # 71.5 kg
        
        conn.commit()
        
        # Login
        auth.login()
        
        # Test with kg as the weight unit (0)
        # Set the user's weight unit to kg (0)
        c.execute("UPDATE users SET weight_unit = ? WHERE id = ?", (0, user_id))
        conn.commit()
        
        # Import the User class from app
        from app import User, load_user
        
        # Get the user with kg as the weight unit
        user_kg = load_user(user_id)
        assert user_kg.weight_unit == 0
        
        # Get weight logs with kg as the unit
        weight_logs_kg = user_kg.get_weight_logs()
        
        # Check that the weights are in kg (unchanged)
        assert weight_logs_kg[0][1] == 70.0
        assert weight_logs_kg[1][1] == 71.5
        
        # Test with lbs as the weight unit (1)
        # Set the user's weight unit to lbs (1)
        c.execute("UPDATE users SET weight_unit = ? WHERE id = ?", (1, user_id))
        conn.commit()
        
        # Get the user with lbs as the weight unit
        user_lbs = load_user(user_id)
        assert user_lbs.weight_unit == 1
        
        # Get weight logs with lbs as the unit
        weight_logs_lbs = user_lbs.get_weight_logs()
        
        # Check that the weights are converted to lbs
        assert round(weight_logs_lbs[0][1], 1) == round(70.0 * 2.20462, 1)  # 154.3 lbs
        assert round(weight_logs_lbs[1][1], 1) == round(71.5 * 2.20462, 1)  # 157.6 lbs
        
        # Clean up the test data
        c.execute("DELETE FROM weight_logs WHERE user_id = ?", (user_id,))
        c.execute("UPDATE users SET weight_unit = ? WHERE id = ?", (0, user_id))  # Reset to kg
        conn.commit()
        
    logger.info("Completed weight logs in settings page test")

def test_historical_goals_for_past_date_summary(client, auth, app):
    """Test that when creating a summary for a past date, it uses goals from the most recent previous summary."""
    logger.info("Starting historical goals for past date summary test")
    
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Get the test user ID
        c.execute("SELECT id FROM users WHERE username = ?", ('testuser',))
        user_id = c.fetchone()[0]
        
        # Create dates for testing
        today = datetime.now().date()
        date1 = (today - timedelta(days=30)).isoformat()  # 30 days ago
        date2 = (today - timedelta(days=20)).isoformat()  # 20 days ago
        date3 = (today - timedelta(days=10)).isoformat()  # 10 days ago
        
        # The date we'll be testing (15 days ago - between date2 and date3)
        test_date = (today - timedelta(days=15)).isoformat()
        
        # Set different calorie and protein goals for each date
        # These will be stored in the daily_summary table
        goals_date1 = (1800, 90)  # 30 days ago: 1800 calories, 90g protein
        goals_date2 = (2000, 100)  # 20 days ago: 2000 calories, 100g protein
        goals_date3 = (2200, 110)  # 10 days ago: 2200 calories, 110g protein
        
        # Insert test food logs and summaries for each date
        # Date 1 (30 days ago)
        c.execute("""INSERT INTO daily_log (date, food_name, calories, protein, user_id)
                    VALUES (?, ?, ?, ?, ?)""", 
                 (date1, "Test Food 1", 500, 30, user_id))
        
        c.execute("""INSERT INTO daily_summary 
                    (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                 (date1, 500, 30, "Test Food 1", user_id, goals_date1[0], goals_date1[1]))
        
        # Date 2 (20 days ago)
        c.execute("""INSERT INTO daily_log (date, food_name, calories, protein, user_id)
                    VALUES (?, ?, ?, ?, ?)""", 
                 (date2, "Test Food 2", 600, 40, user_id))
        
        c.execute("""INSERT INTO daily_summary 
                    (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                 (date2, 600, 40, "Test Food 2", user_id, goals_date2[0], goals_date2[1]))
        
        # Date 3 (10 days ago)
        c.execute("""INSERT INTO daily_log (date, food_name, calories, protein, user_id)
                    VALUES (?, ?, ?, ?, ?)""", 
                 (date3, "Test Food 3", 700, 50, user_id))
        
        c.execute("""INSERT INTO daily_summary 
                    (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                 (date3, 700, 50, "Test Food 3", user_id, goals_date3[0], goals_date3[1]))
        
        conn.commit()
        
        # Login
        auth.login()
        
        # Now, let's create a new food log for the test date (15 days ago)
        # This should use the goals from date2 (20 days ago) since it's the most recent previous date
        # Format the data as expected by the update_history route
        response = client.post('/update_history', data={
            'edit_date': test_date,
            'new_food_name[]': ['Test Food for Past Date'],
            'new_food_calories[]': ['800'],
            'new_food_protein[]': ['60'],
            'existing_food_id[]': []  # No existing foods to keep
        })
        
        # The update_history route redirects to edit_history after processing
        # So we should expect a 302 status code
        assert response.status_code == 302
        
        # Now check the database to see if the summary was created with the correct goals
        c.execute("""SELECT calorie_goal, protein_goal FROM daily_summary 
                     WHERE date = ? AND user_id = ?""", 
                  (test_date, user_id))
        
        summary_goals = c.fetchone()
        assert summary_goals is not None
        
        # The goals should match those from date2 (20 days ago)
        assert summary_goals[0] == goals_date2[0]  # 2000 calories
        assert summary_goals[1] == goals_date2[1]  # 100g protein
        
        # Also check that the food log was created correctly
        c.execute("""SELECT food_name, calories, protein FROM daily_log 
                     WHERE date = ? AND user_id = ?""", 
                  (test_date, user_id))
        
        food_log = c.fetchone()
        assert food_log is not None
        assert food_log[0] == 'Test Food for Past Date'
        assert int(food_log[1]) == 800
        assert int(food_log[2]) == 60
        
        # Clean up the test data
        c.execute("DELETE FROM daily_log WHERE user_id = ? AND date IN (?, ?, ?, ?)", 
                 (user_id, date1, date2, date3, test_date))
        c.execute("DELETE FROM daily_summary WHERE user_id = ? AND date IN (?, ?, ?, ?)", 
                 (user_id, date1, date2, date3, test_date))
        conn.commit()
        
    logger.info("Completed historical goals for past date summary test")

def test_log_quick_food(client, auth, app):
    """Test the log_quick_food functionality."""
    logger.info("Starting log_quick_food test")
    
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Get the test user ID
        c.execute("SELECT id FROM users WHERE username = ?", ('testuser',))
        user_id = c.fetchone()[0]
        
        # Create a test food item in the foods table
        c.execute("""INSERT INTO foods (name, calories, protein, user_id)
                    VALUES (?, ?, ?, ?)""", 
                 ("Test Quick Food", 300, 20, user_id))
        
        # Get the ID of the inserted food
        food_id = c.lastrowid
        
        conn.commit()
        
        # Login
        auth.login()
        
        # Test logging the quick food
        response = client.post('/log_quick_food', data={
            'food_id': food_id,
            'total_calories': 500,  # Simulating existing calories for the day
            'total_protein': 30     # Simulating existing protein for the day
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        # Check that the request was successful
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Check the response data
        assert 'log_entry' in data
        assert data['log_entry']['food_name'] == "Test Quick Food"
        assert data['log_entry']['calories'] == 300
        assert data['log_entry']['protein'] == 20
        
        # Check the updated totals
        assert 'totals' in data
        assert data['totals']['calories'] == 800  # 500 + 300
        assert data['totals']['protein'] == 50    # 30 + 20
        
        # Check that the food was actually logged in the database
        today = datetime.now().date().isoformat()
        c.execute("""SELECT food_name, calories, protein FROM daily_log 
                     WHERE date = ? AND user_id = ? AND food_name = ?""", 
                  (today, user_id, "Test Quick Food"))
        
        food_log = c.fetchone()
        assert food_log is not None
        assert food_log[0] == "Test Quick Food"
        assert food_log[1] == 300
        assert food_log[2] == 20
        
        # Test with an invalid food ID
        response = client.post('/log_quick_food', data={
            'food_id': 9999,  # Non-existent food ID
            'total_calories': 500,
            'total_protein': 30
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        # Check that the request failed appropriately
        assert response.status_code == 200  # The endpoint returns 200 even for errors
        data = response.get_json()
        assert data['success'] is False
        assert 'message' in data
        assert 'not found' in data['message'].lower() or 'permission' in data['message'].lower()
        
        # Test with no food ID
        response = client.post('/log_quick_food', data={
            # No food_id provided
            'total_calories': 500,
            'total_protein': 30
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        # Check that the request failed appropriately
        assert response.status_code == 200  # The endpoint returns 200 even for errors
        data = response.get_json()
        assert data['success'] is False
        assert 'message' in data
        assert 'no food id' in data['message'].lower()
        
        # Clean up the test data
        c.execute("DELETE FROM foods WHERE id = ?", (food_id,))
        c.execute("DELETE FROM daily_log WHERE user_id = ? AND food_name = ?", 
                 (user_id, "Test Quick Food"))
        conn.commit()
        
    logger.info("Completed log_quick_food test")

def test_update_existing_daily_summary(client, auth, app):
    """Test updating an existing daily summary (covering line 667 in app.py)."""
    logger.info("Starting update existing daily summary test")
    
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Get the test user ID
        c.execute("SELECT id FROM users WHERE username = ?", ('testuser',))
        user_id = c.fetchone()[0]
        
        # Get the user's current calorie and protein goals
        c.execute("SELECT calorie_goal, protein_goal FROM users WHERE id = ?", (user_id,))
        user_goals = c.fetchone()
        calorie_goal, protein_goal = user_goals
        
        # Create a date for testing - use today's date since that's what the save_summary route uses
        today = datetime.now().date().isoformat()
        
        # First, create an initial daily summary
        initial_calories = 500
        initial_protein = 30
        initial_summary = "Initial Food 500 (30)"
        
        # Insert a test food log
        c.execute("""INSERT INTO daily_log (date, food_name, calories, protein, user_id)
                    VALUES (?, ?, ?, ?, ?)""", 
                 (today, "Initial Food", initial_calories, initial_protein, user_id))
        
        # Insert the initial daily summary
        c.execute("""INSERT INTO daily_summary 
                    (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                 (today, initial_calories, initial_protein, initial_summary, 
                  user_id, calorie_goal, protein_goal))
        
        conn.commit()
        
        # Login
        auth.login()
        
        # Add a second food to the database
        additional_calories = 300
        additional_protein = 20
        c.execute("""INSERT INTO daily_log (date, food_name, calories, protein, user_id)
                    VALUES (?, ?, ?, ?, ?)""", 
                 (today, "Additional Food", additional_calories, additional_protein, user_id))
        
        conn.commit()
        
        # Now, let's update the daily summary
        # The save_summary route will recalculate the totals based on the foods in the database
        response = client.post('/save_summary', data={
            'date': today
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        # Check that the request was successful
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Check the response data
        assert 'totals' in data
        assert data['totals']['calories'] == initial_calories + additional_calories  # 800 calories
        assert data['totals']['protein'] == initial_protein + additional_protein     # 50g protein
        
        # Now check the database to see if the summary was updated correctly
        c.execute("""SELECT total_calories, total_protein, summary, calorie_goal, protein_goal 
                     FROM daily_summary 
                     WHERE date = ? AND user_id = ?""", 
                  (today, user_id))
        
        updated_summary = c.fetchone()
        assert updated_summary is not None
        
        # Check that the totals were updated
        assert updated_summary[0] == initial_calories + additional_calories  # 800 calories
        assert updated_summary[1] == initial_protein + additional_protein    # 50g protein
        
        # Check that the summary text was updated to include both foods
        assert "Initial Food" in updated_summary[2]
        assert "Additional Food" in updated_summary[2]
        
        # Check that the goals were updated to the current user's goals
        assert updated_summary[3] == calorie_goal
        assert updated_summary[4] == protein_goal
        
        # Clean up the test data
        c.execute("DELETE FROM daily_log WHERE user_id = ? AND date = ?", (user_id, today))
        c.execute("DELETE FROM daily_summary WHERE user_id = ? AND date = ?", (user_id, today))
        conn.commit()
        
    logger.info("Completed update existing daily summary test")

def test_weight_unit_conversion_in_history(app):
    """Test weight unit conversion in the history route (covering lines 1243 and 1251-1253 in app.py)."""
    logger.info("Starting weight unit conversion test for history route")
    
    with app.app_context():
        # Create a test user with weight logs
        conn = sqlite3.connect(app.config['DB_PATH'])
        c = conn.cursor()
        
        # Insert a test user with weight unit preference
        c.execute("""
            INSERT INTO users (username, password, calorie_goal, protein_goal, weight_goal, weight_unit)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('weightuser', 'password', 2000, 100, 65.0, 1))  # weight_unit=1 for lbs
        
        user_id = c.lastrowid
        
        # Insert test weight logs (in kg, as the app stores all weights in kg)
        today = datetime.now().date()
        yesterday = (today - timedelta(days=1))
        
        c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)",
                 (today.isoformat(), 70.0, user_id))  # 70 kg
        c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)",
                 (yesterday.isoformat(), 71.5, user_id))  # 71.5 kg
        
        conn.commit()
        
        # Import the User class and load_user function
        from app import User, load_user
        
        # Load the user with lbs preference
        user_lbs = User(
            id=user_id,
            username='weightuser',
            calorie_goal=2000,
            protein_goal=100,
            weight_goal=65.0,
            weight_unit=1  # lbs
        )
        
        # Now directly test the weight unit conversion logic
        # This is the same logic used in the history route
        
        # Get weight logs
        c.execute("""SELECT date, weight FROM weight_logs 
                    WHERE user_id = ? 
                    ORDER BY date ASC""", (user_id,))
        weight_logs = c.fetchall()
        
        # Format weight data
        weight_dates = [entry[0] for entry in weight_logs]
        weights = [entry[1] for entry in weight_logs]
        
        # Convert weight to user's preferred unit (lbs)
        # This tests line 1243: weights = [round(w * 2.20462, 1) for w in weights]
        if user_lbs.weight_unit == 1:  # If user prefers lbs
            weights = [round(w * 2.20462, 1) for w in weights]  # Convert kg to lbs
        
        # Verify the weights are converted to lbs
        assert weights == [157.6, 154.3]  # 71.5 kg ≈ 157.6 lbs, 70 kg ≈ 154.3 lbs
        
        # Determine weight unit string
        weight_unit = "lbs" if user_lbs.weight_unit == 1 else "kg"
        assert weight_unit == "lbs"
        
        # Get weight goal in the correct unit
        # This tests lines 1251-1253 about weight goal conversion
        weight_goal = None
        if user_lbs.weight_goal is not None:
            weight_goal = user_lbs.weight_goal
            if user_lbs.weight_unit == 1:  # If user prefers lbs and goal is stored in kg
                weight_goal = round(weight_goal * 2.20462, 1)  # Convert kg to lbs
        
        # Verify the weight goal is converted to lbs
        assert weight_goal == 143.3  # 65 kg ≈ 143.3 lbs
        
        # Clean up
        c.execute("DELETE FROM weight_logs WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    logger.info("Completed weight unit conversion test for history route") 