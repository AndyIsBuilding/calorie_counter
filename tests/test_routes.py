import pytest
from flask import session, url_for
import logging
import sqlite3

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_index_page(client):
    """Test that the index page loads correctly."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'HealthVibe' in response.data

def test_login_page(client):
    """Test that the login page loads correctly."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Login' in response.data

def test_register_page(client):
    """Test that the register page loads correctly."""
    response = client.get('/register')
    assert response.status_code == 200
    assert b'Register' in response.data

def test_login_functionality(client, auth, app):
    """Test login functionality."""
    logger.info("Starting login functionality test")
    with app.app_context():
        # Make sure we're logged out before we start
        with client.session_transaction() as session:
            session.clear()
        
        # Test login with correct credentials
        logger.debug("Attempting login with correct credentials")
        response = auth.login()
        logger.debug(f"Login response status: {response.status_code}")
        logger.debug(f"Login response data: {response.get_data(as_text=True)}")
        assert response.status_code == 200
        data = response.get_json()
        logger.debug(f"Parsed JSON data: {data}")
        assert data['success'] is True
        assert 'redirect_url' in data
        assert 'user' in data
        assert data['user']['username'] == 'testuser'
        assert data['user']['calorie_goal'] == 2000
        assert data['user']['protein_goal'] == 100

        # Make sure we're logged out before testing invalid credentials
        auth.logout()
        
        # Test login with incorrect credentials
        logger.debug("Attempting login with incorrect credentials")
        response = auth.login(username='testuser', password='wrongpassword', follow_redirects=False)
        logger.debug(f"Failed login response status: {response.status_code}")
        logger.debug(f"Failed login response data: {response.get_data(as_text=True)}")
        assert response.status_code == 401
        data = response.get_json()
        logger.debug(f"Parsed JSON data from failed login: {data}")
        assert data['success'] is False
        assert 'message' in data
        assert data['message'] == 'Invalid username or password'

        # Test login with follow_redirects - not using auth fixture for this special case
        logger.debug("Attempting login with follow_redirects")
        response = client.post('/login', data={
            'username': 'testuser', 
            'password': 'password'
        }, follow_redirects=True)
        logger.debug(f"Follow redirects response status: {response.status_code}")
        logger.debug(f"Follow redirects response data: {response.get_data(as_text=True)}")
        assert response.status_code == 200
        assert b'Dashboard' in response.data or b'HealthVibe' in response.data
    logger.info("Completed login functionality test")

def test_logout(client, auth):
    """Test logout functionality."""
    # First login
    auth.login()
    
    # Then logout
    response = auth.logout()
    assert response.status_code == 200
    assert b'Login' in response.data

def test_protected_routes_redirect(client):
    """Test that protected routes redirect to login when not authenticated."""
    routes = [
        '/dashboard',
        '/edit_history',
        '/export_csv'
    ]
    
    for route in routes:
        response = client.get(route, follow_redirects=True)
        assert response.status_code == 200  # Should redirect to login page
        assert b'Login' in response.data 

def test_update_settings(client, auth, app):
    """Test updating user settings."""
    logger.info("Starting update_settings test")
    with app.app_context():
        # Login first
        response = auth.login()
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Test updating settings with valid data
        response = client.post('/update_settings', data={
            'calorie_goal': '2500',
            'protein_goal': '150',
            'weight_goal': '75',
            'current_weight': '80',
            'weight_unit': '0'  # kg
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'toast' in data
        assert 'Settings updated' in data['toast']['message']
        
        # Test with invalid data (negative values)
        response = client.post('/update_settings', data={
            'calorie_goal': '-100',
            'protein_goal': '150',
            'weight_goal': '75',
            'current_weight': '80',
            'weight_unit': '0'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'toast' in data
        assert 'Calorie and protein goals must be positive numbers' in data['toast']['message']
    logger.info("Completed update_settings test")

def test_update_settings_weight_unit_conversion(client, auth, app):
    """Test weight unit conversion in settings.
    
    The expected behavior is:
    - All weights should be stored in kg in the database
    - When weight_unit is 0, input values are in kg and should be stored as-is
    - When weight_unit is 1, input values are in lbs and should be converted to kg
    - Weight unit changes are now handled separately from other settings
    """
    logger.info("Starting update_settings weight unit conversion test")
    with app.app_context():
        # Login first
        response = auth.login()
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # First, set initial settings with kg as the unit
        response = client.post('/update_settings', data={
            'calorie_goal': '2000',
            'protein_goal': '100',
            'weight_goal': '70',  # 70 kg
            'current_weight': '75',  # 75 kg
            'weight_unit': '0',  # kg
            'update_unit_only': 'false'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Verify the settings were saved correctly in kg
        conn = sqlite3.connect(app.config['DB_PATH'])
        c = conn.cursor()
        c.execute("SELECT weight_goal, weight_unit FROM users WHERE username = 'testuser'")
        user_data = c.fetchone()
        assert user_data[0] == 70.0  # weight_goal in kg
        assert user_data[1] == 0     # weight_unit is kg (0)
        
        # Check weight log was created
        c.execute("SELECT weight FROM weight_logs WHERE user_id = 1 ORDER BY id DESC LIMIT 1")
        weight_log = c.fetchone()
        assert weight_log[0] == 75.0  # weight in kg
        
        # Test Case 1: Change weight unit from kg to lbs using the dedicated endpoint
        response = client.post('/update_weight_unit', data={
            'weight_unit': '1'  # lbs
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Verify only the weight unit was updated
        c.execute("SELECT weight_goal, weight_unit FROM users WHERE username = 'testuser'")
        user_data = c.fetchone()
        assert user_data[0] == 70.0  # weight_goal still in kg
        assert user_data[1] == 1     # weight_unit is now lbs (1)
        
        # Test Case 2: Update settings with lbs as the unit
        # When using lbs, input values should be converted to kg for storage
        response = client.post('/update_settings', data={
            'calorie_goal': '2000',
            'protein_goal': '100',
            'weight_goal': '165',  # 165 lbs
            'current_weight': '170',  # 170 lbs
            'weight_unit': '1',  # still lbs
            'update_unit_only': 'false'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Verify the settings were saved correctly
        c.execute("SELECT weight_goal, weight_unit FROM users WHERE username = 'testuser'")
        user_data = c.fetchone()
        assert round(user_data[0], 1) == round(165 / 2.20462, 1)  # weight_goal correctly converted to kg
        assert user_data[1] == 1     # weight_unit is still lbs (1)
        
        # Check weight log was created with converted value
        c.execute("SELECT weight FROM weight_logs WHERE user_id = 1 ORDER BY id DESC LIMIT 1")
        weight_log = c.fetchone()
        assert round(weight_log[0], 1) == round(170 / 2.20462, 1)  # weight correctly converted to kg
        
        # Test Case 3: Change weight unit back to kg
        response = client.post('/update_weight_unit', data={
            'weight_unit': '0'  # back to kg
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Verify only the weight unit was updated
        c.execute("SELECT weight_goal, weight_unit FROM users WHERE username = 'testuser'")
        user_data = c.fetchone()
        # Weight goal should still be the same value in kg
        assert round(user_data[0], 1) == round(165 / 2.20462, 1)
        assert user_data[1] == 0     # weight_unit is kg (0)
        
        # Test Case 4: Update settings with kg as the unit
        response = client.post('/update_settings', data={
            'calorie_goal': '2000',
            'protein_goal': '100',
            'weight_goal': '65',  # 65 kg
            'current_weight': '70',  # 70 kg
            'weight_unit': '0',  # kg
            'update_unit_only': 'false'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Verify the settings were saved
        c.execute("SELECT weight_goal, weight_unit FROM users WHERE username = 'testuser'")
        user_data = c.fetchone()
        assert user_data[0] == 65.0  # weight_goal in kg
        assert user_data[1] == 0     # weight_unit is kg (0)
        
        # Check weight log was created
        c.execute("SELECT weight FROM weight_logs WHERE user_id = 1 ORDER BY id DESC LIMIT 1")
        weight_log = c.fetchone()
        assert weight_log[0] == 70.0  # weight in kg is correct
        
        # Test Case 5: No weight goal provided
        response = client.post('/update_settings', data={
            'calorie_goal': '2000',
            'protein_goal': '100',
            # No weight_goal provided
            'current_weight': '72',  # 72 kg
            'weight_unit': '0',  # kg
            'update_unit_only': 'false'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Verify the settings were saved
        c.execute("SELECT weight_goal, weight_unit FROM users WHERE username = 'testuser'")
        user_data = c.fetchone()
        # When no weight_goal is provided, it should maintain the previous value
        assert user_data[0] == 65.0  # weight_goal should remain unchanged
        assert user_data[1] == 0     # weight_unit is kg (0)
        
        # Check weight log was created
        c.execute("SELECT weight FROM weight_logs WHERE user_id = 1 ORDER BY id DESC LIMIT 1")
        weight_log = c.fetchone()
        assert weight_log[0] == 72.0  # weight in kg is correct
        
        conn.close()
    logger.info("Completed update_settings weight unit conversion test")

def test_history_route(client, auth, app):
    """Test the history route functionality."""
    logger.info("Starting history route test")
    with app.app_context():
        # Login first
        response = auth.login()
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Test history page access
        response = client.get('/history')
        assert response.status_code == 200
        assert b'History' in response.data
        
        # Add a food entry to create history
        response = client.post('/log_food', data={
            'name': 'Test Food',
            'calories': '100',
            'protein': '10',
            'servings': '1'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Save summary to create a history entry
        response = client.post('/save_summary', 
                             headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Check history page again to verify data is displayed
        response = client.get('/history')
        assert response.status_code == 200
        assert b'Test Food' in response.data
    logger.info("Completed history route test")

def test_history_route_weight_unit_conversion(client, auth, app):
    """Test weight unit conversion in the history route (covering lines 1243 and 1251-1253 in app.py)."""
    logger.info("Starting history route weight unit conversion test")

    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = sqlite3.connect(app.config['DB_PATH'])
        c = conn.cursor()

        # Get the test user ID
        c.execute("SELECT id FROM users WHERE username = ?", ('testuser',))
        user_id = c.fetchone()[0]

        # Login first
        response = auth.login()
        assert response.status_code == 200
        assert response.get_json()['success'] is True

        # Create test weight logs
        from datetime import datetime, timedelta
        today = datetime.now().date()
        yesterday = (today - timedelta(days=1))

        # Insert test weight logs (in kg)
        c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)",
                 (today.isoformat(), 70.0, user_id))  # 70 kg
        c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)",
                 (yesterday.isoformat(), 71.5, user_id))  # 71.5 kg

        # Set a weight goal (in kg)
        weight_goal_kg = 65.0  # 65 kg
        c.execute("UPDATE users SET weight_goal = ? WHERE id = ?", (weight_goal_kg, user_id))

        # First test with kg as the weight unit (0)
        c.execute("UPDATE users SET weight_unit = ? WHERE id = ?", (0, user_id))
        conn.commit()
        
        # Debug: Check the user's weight unit in the database
        c.execute("SELECT weight_unit FROM users WHERE id = ?", (user_id,))
        weight_unit_kg = c.fetchone()[0]
        logger.info(f"Weight unit in database (kg): {weight_unit_kg}")

        # Access the history page
        response = client.get('/history')
        assert response.status_code == 200

        # Check that the weights are in kg in the JavaScript INITIAL_STATE
        response_data = response.data.decode('utf-8')
        assert 'weightUnit: "kg"' in response_data
        assert 'weights: [71.5, 70.0]' in response_data

        # Now test with lbs as the weight unit (1)
        c.execute("UPDATE users SET weight_unit = ? WHERE id = ?", (1, user_id))
        conn.commit()
        
        # Debug: Check the user's weight unit in the database
        c.execute("SELECT weight_unit FROM users WHERE id = ?", (user_id,))
        weight_unit_lbs = c.fetchone()[0]
        logger.info(f"Weight unit in database (lbs): {weight_unit_lbs}")
        
        # We need to logout and login again to refresh the user object
        client.get('/logout')
        auth.login()
        
        # Access the history page again
        response = client.get('/history')
        assert response.status_code == 200
        
        # Check that the weights are converted to lbs in the JavaScript INITIAL_STATE
        # This tests line 1243: weights = [round(w * 2.20462, 1) for w in weights]
        response_data = response.data.decode('utf-8')
        logger.info(f"Response data contains 'weightUnit': {'weightUnit' in response_data}")
        logger.info(f"Response data contains 'weightUnit: \"kg\"': {'weightUnit: \"kg\"' in response_data}")
        logger.info(f"Response data contains 'weightUnit: \"lbs\"': {'weightUnit: \"lbs\"' in response_data}")
        
        assert 'weightUnit: "lbs"' in response_data
        
        # Check for converted weights (71.5 kg ≈ 157.6 lbs, 70 kg ≈ 154.3 lbs)
        # The values should be rounded to 1 decimal place
        expected_weights = [round(71.5 * 2.20462, 1), round(70.0 * 2.20462, 1)]
        logger.info(f"Expected weights: {expected_weights}")
        logger.info(f"Expected weights string: weights: [{expected_weights[0]}, {expected_weights[1]}]")
        
        # Log the actual response data for debugging
        logger.info(f"Response data snippet around weights: {response_data[response_data.find('weights:') - 20:response_data.find('weights:') + 100]}")
        
        assert f'weights: [{expected_weights[0]}, {expected_weights[1]}]' in response_data
        
        # Check that the weight goal is also converted (65 kg ≈ 143.3 lbs)
        # This tests lines 1251-1253 about weight goal conversion
        expected_weight_goal = round(65.0 * 2.20462, 1)
        logger.info(f"Expected weight goal: {expected_weight_goal}")
        logger.info(f"Expected weight goal string: weightGoal: {expected_weight_goal}")
        
        # Log the actual response data for debugging
        logger.info(f"Response data snippet around weightGoal: {response_data[response_data.find('weightGoal:') - 20:response_data.find('weightGoal:') + 50]}")
        
        assert f'weightGoal: {expected_weight_goal}' in response_data

        # Clean up
        c.execute("DELETE FROM weight_logs WHERE user_id = ?", (user_id,))
        c.execute("UPDATE users SET weight_goal = NULL, weight_unit = 0 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

    logger.info("Completed history route weight unit conversion test")

def test_remove_quick_add_food(client, auth, app):
    """Test removing a quick add food item."""
    logger.info("Starting remove_quick_add_food test")
    with app.app_context():
        # Login first
        response = auth.login()
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Add a quick add food first
        response = client.post('/quick_add_food', data={
            'name': 'Test Quick Food',
            'calories': '200',
            'protein': '20'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        food_id = data['food']['id']
        
        # Now test removing it
        response = client.post('/remove_quick_add_food', data={
            'food_id': food_id
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'toast' in data
        assert 'Food removed' in data['toast']['message']
        
        # Test with invalid food ID
        response = client.post('/remove_quick_add_food', data={
            'food_id': '9999'  # Non-existent ID
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
    logger.info("Completed remove_quick_add_food test")

def test_edit_history_route(client, auth, app):
    """Test the edit_history route functionality."""
    logger.info("Starting edit_history route test")
    with app.app_context():
        # Login first
        response = auth.login()
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Add a food entry and save summary to create history
        response = client.post('/log_food', data={
            'name': 'Edit History Test Food',
            'calories': '300',
            'protein': '30',
            'servings': '1'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        response = client.post('/save_summary', 
                             headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Test edit_history page access
        response = client.get('/edit_history')
        assert response.status_code == 200
        assert b'Edit History' in response.data
        
        # Test with a specific date parameter
        import datetime
        today = datetime.date.today().isoformat()
        response = client.get(f'/edit_history?date={today}')
        assert response.status_code == 200
        assert b'Edit History' in response.data
        assert b'Edit History Test Food' in response.data
    logger.info("Completed edit_history route test")

def test_update_history(client, auth, app):
    """Test the update_history route functionality."""
    logger.info("Starting update_history route test")
    with app.app_context():
        # Login first
        response = auth.login()
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Add a food entry and save summary to create history
        response = client.post('/log_food', data={
            'name': 'Update History Test Food',
            'calories': '400',
            'protein': '40',
            'servings': '1'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        food_id = data['log_entry']['id']
        
        response = client.post('/save_summary', 
                             headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Now test updating the history
        import datetime
        today = datetime.date.today().isoformat()
        
        response = client.post('/update_history', data={
            'edit_date': today,
            'existing_food_id[]': [food_id],
            'new_food_name[]': ['New Test Food'],
            'new_food_calories[]': ['500'],
            'new_food_protein[]': ['50']
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Edit History' in response.data
        assert b'Daily log for' in response.data
        assert b'updated' in response.data
        
        # Verify the update worked by checking edit_history
        response = client.get(f'/edit_history?date={today}')
        assert response.status_code == 200
        assert b'New Test Food' in response.data
        assert b'500' in response.data
        assert b'50' in response.data 