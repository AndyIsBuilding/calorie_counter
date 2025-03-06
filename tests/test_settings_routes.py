import pytest #noqa
from datetime import datetime, timedelta
import pytz
import logging
import sqlite3


# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_settings_route(client, auth):
    """Test the settings route functionality."""
    with client.application.app_context():
        # Login first
        response = auth.login()
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Now test the settings route
        response = client.get('/settings')
        assert response.status_code == 200
        assert b'Settings' in response.data
        assert b'Calorie Goal' in response.data
        assert b'Protein Goal' in response.data
        assert b'Weight Goal' in response.data

def test_update_settings(client, auth):
    """Test updating user settings."""
    with client.application.app_context():
        # Login first
        response = auth.login()
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Test updating settings
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
        
        # Verify settings were updated
        response = client.get('/settings')
        assert response.status_code == 200
        assert b'2500' in response.data  # calorie goal
        assert b'150' in response.data   # protein goal
        assert b'75' in response.data    # weight goal
        assert b'80' in response.data    # current weight

def test_update_settings_validation(client, auth):
    """Test settings validation."""
    with client.application.app_context():
        # Login first
        response = auth.login()
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Test invalid calorie goal
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
        assert 'Calorie and protein goals must be positive numbers' in data['toast']['message']
        
        # Test invalid protein goal
        response = client.post('/update_settings', data={
            'calorie_goal': '2500',
            'protein_goal': '-50',
            'weight_goal': '75',
            'current_weight': '80',
            'weight_unit': '0'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert 'Calorie and protein goals must be positive numbers' in data['toast']['message']

def test_history_route(client, auth):
    """Test the history route functionality."""
    with client.application.app_context():
        # Login first
        response = auth.login()
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Test history page access
        response = client.get('/history')
        assert response.status_code == 200
        assert b'History' in response.data
        
        # Add test data
        response = client.post('/quick_add_food', data={
            'name': 'Test Food',
            'calories': '100',
            'protein': '10'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        response = client.post('/log_food', data={
            'name': 'Test Food',
            'calories': '100',
            'protein': '10',
            'servings': '1'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Save summary
        response = client.post('/save_summary', 
                             headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Verify data in history
        response = client.get('/history')
        assert response.status_code == 200
        assert b'Test Food' in response.data

def test_remove_quick_add_food(client, auth, app):
    """Test removing quick add food functionality."""
    # Login first
    response = auth.login()
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    
    # First, clear any existing "Test Food" entries to avoid conflicts
    with app.app_context():
        conn = app.config['DB_CONNECTION']
        cursor = conn.cursor()
        cursor.execute("DELETE FROM foods WHERE name = 'Test Food'")
        conn.commit()
    
    # Add a test food
    response = client.post('/quick_add_food', data={
        'name': 'Test Food',
        'calories': '100',
        'protein': '10'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    food_id = data['food']['id']
    
    # Verify the food was added to the database
    with app.app_context():
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM foods WHERE id = ?", (food_id,))
        food = cursor.fetchone()
        assert food is not None
    
    # Now remove the food
    response = client.post('/remove_quick_add_food', data={
        'food_id': food_id
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    
    # Verify the food was removed from the database
    with app.app_context():
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM foods WHERE id = ?", (food_id,))
        food = cursor.fetchone()
        assert food is None
    
    # Also verify the UI doesn't contain our specific food ID
    response = client.get('/settings')
    assert response.status_code == 200
    assert f'data-food-id="{food_id}"'.encode() not in response.data 