import pytest
from flask import session, url_for
import logging

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