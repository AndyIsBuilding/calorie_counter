import pytest
import sqlite3
import sys
import os
from unittest.mock import patch
from flask import g

# Add the parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_database_connection(app):
    """Test that we can connect to the database."""
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        assert conn is not None
        # Don't close the shared connection

def test_user_exists(app):
    """Test that the test user exists in the database."""
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", ('testuser',))
        user = c.fetchone()
        assert user is not None
        # Don't close the shared connection

def test_database_tables(app):
    """Test that all required tables exist in the database."""
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Check for users table
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        assert c.fetchone() is not None
        
        # Check for food_log table
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='food_log'")
        assert c.fetchone() is not None
        
        # Check for daily_summary table
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_summary'")
        assert c.fetchone() is not None
        
        # Check for quick_foods table
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quick_foods'")
        assert c.fetchone() is not None
        
        # Don't close the shared connection

def test_insert_food_log(app):
    """Test inserting data into the food_log table."""
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Insert a test food log entry
        c.execute("""
            INSERT INTO food_log (user_id, date, food_name, calories, protein)
            VALUES (?, ?, ?, ?, ?)
        """, (1, '2023-01-01', 'Test Food', 100, 10))
        conn.commit()
        
        # Verify the food was added
        c.execute("""
            SELECT * FROM food_log 
            WHERE user_id = 1 AND food_name = ? AND calories = ? AND protein = ?
        """, ('Test Food', 100, 10))
        food = c.fetchone()
        assert food is not None
        # Don't close the shared connection

def test_insert_quick_food(app):
    """Test inserting data into the quick_foods table."""
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Insert a test quick food entry
        c.execute("""
            INSERT INTO quick_foods (user_id, food_name, calories, protein)
            VALUES (?, ?, ?, ?)
        """, (1, 'Quick Test Food', 200, 20))
        conn.commit()
        
        # Verify the quick food was added
        c.execute("""
            SELECT * FROM quick_foods 
            WHERE user_id = 1 AND food_name = ? AND calories = ? AND protein = ?
        """, ('Quick Test Food', 200, 20))
        food = c.fetchone()
        assert food is not None
        # Don't close the shared connection
