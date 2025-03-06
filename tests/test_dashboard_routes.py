import pytest
from datetime import datetime, timedelta
import pytz

def test_dashboard_route(client, auth):
    """Test the dashboard route functionality."""
    # Login first
    response = auth.login()
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # Now test the dashboard route
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert b'Dashboard' in response.data
    assert b'Daily Summary' in response.data
    assert b'Quick Add' in response.data

def test_quick_add_food(client, auth, app):
    """Test quick add food functionality."""
    # Login first
    response = auth.login()
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    
    # Test adding a new food
    response = client.post('/quick_add_food', data={
        'name': 'Test Food',
        'calories': '100',
        'protein': '10'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['food']['name'] == 'Test Food'
    assert data['food']['calories'] == 100
    assert data['food']['protein'] == 10

def test_log_food(client, auth, app):
    """Test food logging functionality."""
    # Login first
    response = auth.login()
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    
    # Test logging a food
    response = client.post('/log_food', data={
        'name': 'Test Food',
        'calories': '100',
        'protein': '10',
        'servings': '1'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['log_entry']['food_name'] == 'Test Food'
    assert data['log_entry']['calories'] == 100
    assert data['log_entry']['protein'] == 10

def test_remove_food(client, auth, app):
    """Test food removal functionality."""
    # Login first
    response = auth.login()
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    
    # First add a food to log
    response = client.post('/quick_add_food', data={
        'name': 'Test Food',
        'calories': '100',
        'protein': '10'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # Log the food
    response = client.post('/log_food', data={
        'name': 'Test Food',
        'calories': '100',
        'protein': '10',
        'servings': '1'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    log_id = data['log_entry']['id']
    
    # Now test removing it
    response = client.post(f'/remove_food/{log_id}', 
                         headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True

def test_save_summary(client, auth, app):
    """Test saving daily summary functionality."""
    # Login first
    response = auth.login()
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    
    # First add and log some food
    response = client.post('/quick_add_food', data={
        'name': 'Test Food',
        'calories': '100',
        'protein': '10'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    response = client.post('/log_food', data={
        'name': 'Test Food',
        'calories': '100',
        'protein': '10',
        'servings': '1'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # Test saving summary
    response = client.post('/save_summary', 
                         headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True

def test_export_csv(client, auth):
    """Test CSV export functionality."""
    # Login first
    response = auth.login()
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    
    # Test CSV export
    response = client.get('/export_csv')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    assert response.headers['Content-Disposition'].startswith('attachment')

def test_get_recommendations(client, auth, app):
    """Test food recommendations functionality."""
    # Login first
    response = auth.login()
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    
    # Add some test foods
    test_foods = [
        {'name': 'Food 1', 'calories': '100', 'protein': '10'},
        {'name': 'Food 2', 'calories': '200', 'protein': '20'},
        {'name': 'Food 3', 'calories': '300', 'protein': '30'},
        {'name': 'Food 4', 'calories': '400', 'protein': '40'},
        {'name': 'Food 5', 'calories': '500', 'protein': '50'}
    ]
    
    for food in test_foods:
        response = client.post('/quick_add_food', data=food, 
                             headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
    
    # Log one of the foods to make sure it's not recommended
    response = client.post('/log_food', data={
        'name': 'Food 1',
        'calories': '100',
        'protein': '10',
        'servings': '1'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    
    # Test getting recommendations
    response = client.post('/get_recommendations', 
                          headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    data = response.get_json()
    assert 'hit_both' in data
    assert 'protein_first' in data
    assert 'calorie_first' in data

def test_get_testimonials(client):
    """Test testimonials API endpoint."""
    response = client.get('/api/testimonials')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert all('quote' in testimonial for testimonial in data)
    assert all('author' in testimonial for testimonial in data)
    assert all('role' in testimonial for testimonial in data) 