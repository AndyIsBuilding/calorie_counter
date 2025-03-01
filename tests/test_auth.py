import pytest
import sqlite3
import sys
import os
from unittest.mock import patch

# Add the parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import load_user, User

def test_load_user_existing(app):
    """Test that load_user correctly loads an existing user."""
    with app.app_context():
        db_path = app.config['DB_PATH']
        
        # Insert a test user directly into the test database
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE username = 'testuser'")
        user_data = c.fetchone()
        conn.close()
        
        if not user_data:
            pytest.skip("Test user not found in the database")
        
        expected_id, expected_username = user_data
        
        # Patch the DB_PATH in the load_user function
        with patch('app.DB_PATH', db_path):
            # Now test the load_user function
            user = load_user(str(expected_id))
            
            # Verify the user was loaded correctly
            assert user is not None
            assert user.id == expected_id
            assert user.username == expected_username
            assert isinstance(user, User)

def test_load_user_nonexistent(app):
    """Test that load_user returns None for a non-existent user."""
    with app.app_context():
        db_path = app.config['DB_PATH']
        
        # Patch the DB_PATH in the load_user function
        with patch('app.DB_PATH', db_path):
            # Try to load a user that doesn't exist
            user = load_user('999')
            
            # Verify that None is returned
            assert user is None

def test_user_class(app):
    """Test the User class functionality."""
    # Create a user instance
    user = User(1, 'testuser')
    
    # Test the properties
    assert user.id == 1
    assert user.username == 'testuser'
    assert user.is_authenticated
    assert user.is_active
    assert not user.is_anonymous 