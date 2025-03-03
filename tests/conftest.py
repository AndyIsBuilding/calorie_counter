import os
import sys
import tempfile
import pytest
import sqlite3
import logging
from werkzeug.security import generate_password_hash

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app as flask_app


@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    # Create a temporary file to isolate the database for each test
    db_fd, db_path = tempfile.mkstemp()
    
    # Configure the app for testing
    flask_app.config.update({
        'TESTING': True,
        'DB_PATH': db_path,
        'WTF_CSRF_ENABLED': False,  # Disable CSRF protection for testing
        'SERVER_NAME': 'localhost',  # Needed for url_for to work in tests
    })

    # Create the database and tables
    with flask_app.app_context():
        init_test_db(db_path)

    yield flask_app

    # Close and remove the temporary database
    os.close(db_fd)
    os.unlink(db_path)


def init_test_db(db_path):
    """Initialize the test database with schema and test data."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        calorie_goal INTEGER DEFAULT 2000,
        protein_goal INTEGER DEFAULT 100,
        weight_goal REAL,
        weight_unit INTEGER DEFAULT 0
    )
    ''')
    
    # Create foods table
    c.execute('''
    CREATE TABLE IF NOT EXISTS foods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        calories INTEGER NOT NULL,
        protein INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create food_log table
    c.execute('''
    CREATE TABLE IF NOT EXISTS food_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        food_name TEXT NOT NULL,
        calories INTEGER NOT NULL,
        protein INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create daily_summary table
    c.execute('''
    CREATE TABLE IF NOT EXISTS daily_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        notes TEXT,
        total_calories INTEGER,
        total_protein INTEGER,
        summary TEXT,
        calorie_goal INTEGER DEFAULT 2000,
        protein_goal INTEGER DEFAULT 100,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create quick_foods table
    c.execute('''
    CREATE TABLE IF NOT EXISTS quick_foods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        food_name TEXT NOT NULL,
        calories INTEGER NOT NULL,
        protein INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Insert test user with proper password hash
    test_password = generate_password_hash('password')
    c.execute("INSERT INTO users (username, password, calorie_goal, protein_goal) VALUES (?, ?, ?, ?)",
              ('testuser', test_password, 2000, 100))
    
    conn.commit()
    conn.close()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()


@pytest.fixture
def auth(client):
    """Authentication helper for tests."""
    class AuthActions:
        def login(self, username='testuser', password='password', follow_redirects=False):
            logger.debug(f"Attempting login with username: {username}")
            # Always set X-Requested-With header for AJAX requests unless explicitly following redirects
            headers = {'X-Requested-With': 'XMLHttpRequest'} if not follow_redirects else {}
            response = client.post(
                '/login',
                data={'username': username, 'password': password},
                headers=headers,
                follow_redirects=follow_redirects
            )
            logger.debug(f"Login response status: {response.status_code}")
            logger.debug(f"Login response data: {response.get_data(as_text=True)}")
            # For AJAX requests, we want to preserve the original status code
            if not follow_redirects:
                return response
            # For non-AJAX requests, we want to follow redirects and get the final status code
            return response
            
        def logout(self):
            logger.debug("Attempting logout")
            response = client.get('/logout', follow_redirects=True)
            logger.debug(f"Logout response status: {response.status_code}")
            logger.debug(f"Logout response data: {response.get_data(as_text=True)}")
            return response
    
    return AuthActions() 