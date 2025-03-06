import os
import sys
import tempfile
import pytest
import sqlite3
import logging
from werkzeug.security import generate_password_hash
from flask import session
from app import app as flask_app

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    logger.debug("Setting up test app...")
    
    # Create a temporary database
    db_fd, db_path = tempfile.mkstemp()
    
    # Create a database connection
    conn = sqlite3.connect(db_path, check_same_thread=False)
    
    # Reset the app configuration for each test
    flask_app.config.update({
        'TESTING': True,
        'DB_PATH': db_path,
        'DB_CONNECTION': conn,  # Add the connection to the config
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost',
    })

    logger.debug(f"Database path set to: {flask_app.config['DB_PATH']}")
    
    # Patch the DB_PATH in the app module to use our test database
    import app as app_module
    original_db_path = app_module.DB_PATH
    app_module.DB_PATH = db_path
    
    # Initialize the database
    with flask_app.app_context():
        init_db(db_path)

    yield flask_app

    # Clean up after the test
    conn.close()
    os.close(db_fd)
    os.unlink(db_path)
    
    # Restore the original DB_PATH
    app_module.DB_PATH = original_db_path


def init_db(db_path):
    """Initialize the test database with the required tables."""
    logger.debug("Initializing test database...")
    
    # Connect to the database
    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
    
    # Drop existing tables if they exist
    c.executescript('''
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS foods;
        DROP TABLE IF EXISTS daily_log;
        DROP TABLE IF EXISTS daily_summary;
        DROP TABLE IF EXISTS quick_foods;
        DROP TABLE IF EXISTS weight_logs;
    ''')
    
    # Create tables
    logger.debug("Creating tables...")
    
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
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS foods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        calories INTEGER NOT NULL,
        protein INTEGER NOT NULL,
        user_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS daily_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        food_name TEXT NOT NULL,
        calories INTEGER NOT NULL,
        protein INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS daily_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        total_calories INTEGER NOT NULL,
        total_protein INTEGER NOT NULL,
        summary TEXT,
        user_id INTEGER NOT NULL,
        calorie_goal INTEGER,
        protein_goal INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(date, user_id)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS quick_foods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        food_name TEXT NOT NULL,
        calories INTEGER NOT NULL,
        protein INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS weight_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        weight REAL NOT NULL,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    # Insert test user
    test_password = generate_password_hash('password')
    c.execute("INSERT INTO users (username, password, calorie_goal, protein_goal) VALUES (?, ?, ?, ?)",
              ('testuser', test_password, 2000, 100))
    
    logger.debug("Test user inserted...")
    
    # Get the list of tables to verify
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    logger.debug(f"Created tables: {tables}")
    
    conn.commit()
    return conn


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
            # Make sure we're always sending as AJAX request
            headers = {'X-Requested-With': 'XMLHttpRequest'}
            response = client.post(
                '/login',
                data={'username': username, 'password': password},
                headers=headers,
                follow_redirects=follow_redirects
            )
            logger.debug(f"Login response status: {response.status_code}")
            logger.debug(f"Login response data: {response.get_data(as_text=True)}")
            return response
            
        def logout(self):
            logger.debug("Attempting logout")
            response = client.get('/logout', follow_redirects=True)
            logger.debug(f"Logout response status: {response.status_code}")
            logger.debug(f"Login response data: {response.get_data(as_text=True)}")
            return response
    
    return AuthActions()


@pytest.fixture(autouse=True)
def logout_after_test(client):
    """Ensure user is logged out after each test."""
    yield
    # Force logout by clearing the session
    with client.session_transaction() as session:
        session.clear() 