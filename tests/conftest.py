import os
import sys
import tempfile
import pytest
import sqlite3
import logging
from werkzeug.security import generate_password_hash
from flask import session

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app as flask_app


@pytest.fixture(scope="session")
def db_connection():
    """Create a single database connection for the test session."""
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    yield conn
    conn.close()


@pytest.fixture
def app(db_connection):
    """Create and configure a Flask app for testing."""
    logger.debug("Setting up test app...")
    
    # Reset the app configuration for each test
    flask_app.config.update({
        'TESTING': True,
        'DB_CONNECTION': db_connection,  # Store the connection object
        'DB_PATH': ':memory:',
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost',
    })

    logger.debug(f"Database path set to: {flask_app.config['DB_PATH']}")

    # Create fresh database tables for each test
    with flask_app.app_context():
        logger.debug("Initializing test database...")
        init_test_db(db_connection)
        
        # Verify tables were created
        c = db_connection.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = c.fetchall()
        logger.debug(f"Created tables: {tables}")

    yield flask_app

    # Clean up after the test
    with flask_app.app_context():
        # Reset database state if needed
        pass


def init_test_db(conn):
    """Initialize the test database with schema and test data."""
    logger.debug("Running init_test_db...")
    
    c = conn.cursor()
    
    # Drop existing tables if they exist
    c.executescript('''
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS foods;
        DROP TABLE IF EXISTS food_log;
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
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        calories INTEGER NOT NULL,
        protein INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
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
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS weight_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        weight REAL NOT NULL,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Insert test user
    test_password = generate_password_hash('password')
    c.execute("INSERT INTO users (username, password, calorie_goal, protein_goal) VALUES (?, ?, ?, ?)",
              ('testuser', test_password, 2000, 100))
    
    logger.debug("Test user inserted...")
    
    conn.commit()


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