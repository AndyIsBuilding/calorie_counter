import pytest
import sys
import os
from werkzeug.security import generate_password_hash
from app import load_user, User
import sqlite3

# Add the parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_load_user_existing(app, auth):
    """Test that load_user correctly loads an existing user."""
    with app.app_context():
        print(f"\nTest using database: {app.config['DB_PATH']}")
        
        # Use the shared connection
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Check what tables exist
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = c.fetchall()
        print(f"Tables in database: {tables}")
        
        # Check users in the database
        try:
            c.execute("SELECT id, username FROM users")
            users = c.fetchall()
            print(f"Users in database: {users}")
        except sqlite3.OperationalError as e:
            print(f"Error querying users: {e}")
        
        # Don't close the connection since it's shared
        
        # Now test the load_user function
        user = load_user('1')
        
        assert user is not None
        assert user.username == 'testuser'
        assert isinstance(user, User)

def test_load_user_nonexistent(app):
    """Test that load_user returns None for a non-existent user."""
    with app.app_context():
        user = load_user('999')
        assert user is None

def test_user_class():
    """Test the User class functionality."""
    user = User(1, 'testuser')
    
    assert user.id == 1
    assert user.username == 'testuser'
    assert user.is_authenticated
    assert user.is_active
    assert not user.is_anonymous

def test_user_authentication(app, client, auth):
    """Test user authentication process."""
    with app.app_context():
        # Verify database is properly set up before testing
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Check if test user exists (should always exist due to init_test_db)
        c.execute("SELECT * FROM users WHERE username = ?", ('testuser',))
        user = c.fetchone()
        if not user:
            print("Test user not found in database!")
            test_password = generate_password_hash('password')
            c.execute(
                "INSERT INTO users (username, password, calorie_goal, protein_goal) VALUES (?, ?, ?, ?)",
                ('testuser', test_password, 2000, 100)
            )
            conn.commit()
        else:
            print(f"Found existing test user: {user}")
        
        # Make sure we're logged out before testing login
        with client.session_transaction() as session:
            session.clear()
        
        # Test successful login
        response = auth.login()
        print(f"Successful login response: {response.status_code}")
        print(f"Response data: {response.get_data(as_text=True)}")
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'redirect_url' in data
        
        # Logout before testing failed login
        auth.logout()
        
        # Test failed login
        response = auth.login(username='testuser', password='wrongpassword')
        print(f"Failed login response: {response.status_code}")
        print(f"Response data: {response.get_data(as_text=True)}")
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert 'message' in data
        
        # Test logout
        # First login again
        auth.login()
        # Then logout
        response = auth.logout()
        assert response.status_code == 200
        assert b'Login' in response.data

@pytest.mark.parametrize('route', [
    '/dashboard',
    '/settings',
    '/history',
])
def test_protected_routes(client, route):
    """Test that protected routes require authentication."""
    response = client.get(route, follow_redirects=True)
    assert response.status_code == 200
    assert b'Login' in response.data

def test_login_page_render(client):
    """Test that the login page renders correctly."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Login' in response.data 