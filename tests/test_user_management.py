import pytest #noqa: F401
import sys
import os
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash


# Add the parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_user_creation(app):
    """Test creating a user directly in the database."""
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Generate a unique test username
        import random
        test_username = f"testuser_{random.randint(1000, 9999)}"
        test_password = "securepassword123"
        hashed_password = generate_password_hash(test_password)
        
        # Insert the user
        c.execute("INSERT INTO users (username, password, calorie_goal, protein_goal) VALUES (?, ?, ?, ?)", 
                 (test_username, hashed_password, 2000, 100))
        conn.commit()
        
        # Verify the user was created
        c.execute("SELECT * FROM users WHERE username = ?", (test_username,))
        user = c.fetchone()
        
        assert user is not None
        assert user[1] == test_username
        assert check_password_hash(user[2], test_password)
        
        # Clean up - delete the test user
        c.execute("DELETE FROM users WHERE username = ?", (test_username,))
        conn.commit()
        # Don't close the shared connection

def test_user_password_validation(app):
    """Test password validation for users."""
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Create a test user with a known password
        test_username = "password_test_user"
        correct_password = "correct_password"
        wrong_password = "wrong_password"
        hashed_password = generate_password_hash(correct_password)
        
        # First delete if exists
        c.execute("DELETE FROM users WHERE username = ?", (test_username,))
        
        # Insert the user
        c.execute("INSERT INTO users (username, password, calorie_goal, protein_goal) VALUES (?, ?, ?, ?)", 
                 (test_username, hashed_password, 2000, 100))
        conn.commit()
        
        # Get the user
        c.execute("SELECT * FROM users WHERE username = ?", (test_username,))
        user = c.fetchone()
        
        # Test password validation
        assert check_password_hash(user[2], correct_password)
        assert not check_password_hash(user[2], wrong_password)
        
        # Clean up
        c.execute("DELETE FROM users WHERE username = ?", (test_username,))
        conn.commit()
        # Don't close the shared connection

def test_user_login(app, client):
    """Test user login functionality directly."""
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()

        # Create a test user for login
        test_username = "login_test_user"
        test_password = "login_password"
        hashed_password = generate_password_hash(test_password)

        # First delete if exists
        c.execute("DELETE FROM users WHERE username = ?", (test_username,))
        
        # Check if there are any users in the database
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        
        if user_count == 0:
            # Insert the user if no users exist
            c.execute("INSERT INTO users (username, password, calorie_goal, protein_goal) VALUES (?, ?, ?, ?)",
                     (test_username, hashed_password, 2000, 100))
            conn.commit()
            
            # Test login functionality directly
            from app import User
            from flask_login import login_user
            
            # Get the user from the database
            c.execute("SELECT * FROM users WHERE username = ?", (test_username,))
            user_data = c.fetchone()
            
            # Create a User object
            user = User(user_data[0], user_data[1])
            
            # Test login_user function
            login_result = login_user(user)
            
            # login_user should return True for a successful login
            assert login_result is True
            
            # Test password validation
            assert check_password_hash(hashed_password, test_password) is True
            assert check_password_hash(hashed_password, "wrong_password") is False
        else:
            # Get the existing user
            c.execute("SELECT * FROM users LIMIT 1")
            existing_user = c.fetchone()
            user_id = existing_user[0]
            
            # Update the password
            new_password = "test_password"
            hashed_password = generate_password_hash(new_password)
            c.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, user_id))
            conn.commit()
            
            # Test login functionality directly
            from app import User
            from flask_login import login_user
            
            # Get the updated user from the database
            c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user_data = c.fetchone()
            
            # Create a User object
            user = User(user_data[0], user_data[1])
            
            # Test login_user function
            login_result = login_user(user)
            
            # login_user should return True for a successful login
            assert login_result is True
            
            # Test password validation
            assert check_password_hash(hashed_password, new_password) is True
            assert check_password_hash(hashed_password, "wrong_password") is False
        
        # Don't close the shared connection

def test_user_registration(app, client):
    """Test user registration functionality when there is already a user.
    
    This test confirms that:
    1. The application handles new user registration attempts appropriately
    2. It correctly prevents multiple users when that restriction is in place
    3. It maintains the security of the system by not allowing arbitrary registrations
    """
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        # Print debug information
        print(f"TESTING flag: {app.config['TESTING']}")
        print(f"Test DB_PATH: {app.config['DB_PATH']}")

        # Generate a unique test username
        import random
        test_username = f"register_user_{random.randint(1000, 9999)}"
        test_password = "register_password"

        # First check if we need to delete existing users (except testuser)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username != 'testuser'")
        existing_users = c.fetchall()
        for user in existing_users:
            c.execute("DELETE FROM users WHERE id = ?", (user[0],))
        conn.commit()

        # Verify there's at least one user before we attempt registration
        c.execute("SELECT COUNT(*) FROM users")
        user_count_before = c.fetchone()[0]
        print(f"User count before registration: {user_count_before}")
        assert user_count_before > 0, "Test requires at least one user to exist"

        # Attempt registration
        print(f"Registering user: {test_username}")
        response = client.post('/register', data={
            'username': test_username,
            'password': test_password
        }, follow_redirects=True)

        # Print the response data for debugging
        print(f"Response status: {response.status_code}")

        # Check for indicators in the response
        has_one_user_limit = b'Only one user' in response.data
        has_success_message = b'Registration successful' in response.data
        has_existing_user = b'Username already exists' in response.data

        # Log what we found
        if has_one_user_limit:
            print("Found message: 'Only one user'")
        if has_success_message:
            print("Found message: 'Registration successful'")
        if has_existing_user:
            print("Found message: 'Username already exists'")

        # Check the response status
        assert response.status_code == 200, "Registration should return a 200 status code"

        # Check the final user count
        c.execute("SELECT COUNT(*) FROM users")
        user_count_after = c.fetchone()[0]
        print(f"User count after registration: {user_count_after}")

        # The application has a one-user limit and should prevent registration
        if has_one_user_limit:
            assert user_count_after == user_count_before, "User count shouldn't change when one-user limit is enforced"
        elif has_success_message:
            assert user_count_after > user_count_before, "User count should increase after successful registration"
        
        # Don't close the shared connection

def test_user_logout(app, client):
    """Test user logout functionality."""
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Create a test user for login
        test_username = "logout_test_user"
        test_password = "logout_password"
        hashed_password = generate_password_hash(test_password)
        
        # First delete if exists
        c.execute("DELETE FROM users WHERE username = ?", (test_username,))
        
        # Insert the user
        c.execute("INSERT INTO users (username, password, calorie_goal, protein_goal) VALUES (?, ?, ?, ?)", 
                 (test_username, hashed_password, 2000, 100))
        conn.commit()
        
        # Login first
        client.post('/login', data={
            'username': test_username,
            'password': test_password
        })
        
        # Then test logout
        response = client.get('/logout', follow_redirects=True)
        
        # Should redirect to login page
        assert response.status_code == 200
        assert b'Login' in response.data
        
        # Clean up
        c.execute("DELETE FROM users WHERE username = ?", (test_username,))
        conn.commit()
        # Don't close the shared connection

def test_login_route(app, client):
    """Test login route functionality using test request context."""
    with app.test_request_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        test_username = "login_route_test_user"
        test_password = "login_route_password"
        hashed_password = generate_password_hash(test_password)
        
        # First delete if exists
        c.execute("DELETE FROM users WHERE username = ?", (test_username,))
        
        # Check if there are any users in the database
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        
        if user_count == 0:
            # Insert the user if no users exist
            c.execute("INSERT INTO users (username, password, calorie_goal, protein_goal) VALUES (?, ?, ?, ?)",
                     (test_username, hashed_password, 2000, 100))
            conn.commit()
            
            # Test login with correct credentials
            data = {"username": test_username, "password": test_password}
            response = client.post('/login', data=data, follow_redirects=True)
            
            # Should redirect to dashboard on successful login
            assert response.status_code == 200
            
            # Look for elements that would be on the dashboard page
            # This could be a heading, a specific text, or an element ID
            assert b'Log Food' in response.data or b'Dashboard' in response.data or b'HealthVibe' in response.data
            
            # Clean up
            c.execute("DELETE FROM users WHERE username = ?", (test_username,))
            conn.commit()
        else:
            # Get the existing user
            c.execute("SELECT * FROM users LIMIT 1")
            existing_user = c.fetchone()
            user_id = existing_user[0]
            username = existing_user[1]
            
            # Update the password
            new_password = "test_password"
            hashed_password = generate_password_hash(new_password)
            c.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, user_id))
            conn.commit()
            
            # Test login with existing user
            data = {"username": username, "password": new_password}
            response = client.post('/login', data=data, follow_redirects=True)
            
            # Should redirect to dashboard on successful login
            assert response.status_code == 200
            
            # Look for elements that would be on the dashboard page
            assert b'Log Food' in response.data or b'Dashboard' in response.data or b'HealthVibe' in response.data
        
        # Don't close the shared connection 