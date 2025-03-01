import pytest
import sqlite3
import sys
import os
from unittest.mock import patch
from flask import g

# Add the parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import init_db

def test_database_connection(app):
    """Test that we can connect to the database."""
    with app.app_context():
        db_path = app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        assert conn is not None
        conn.close()

def test_user_exists(app):
    """Test that the test user exists in the database."""
    with app.app_context():
        db_path = app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", ('testuser',))
        user = c.fetchone()
        assert user is not None
        conn.close()

def test_database_tables(app):
    """Test that all required tables exist in the database."""
    with app.app_context():
        db_path = app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
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
        
        conn.close()

def test_insert_food_log(app):
    """Test inserting data into the food_log table."""
    with app.app_context():
        db_path = app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
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
        
        conn.close()

def test_insert_quick_food(app):
    """Test inserting data into the quick_foods table."""
    with app.app_context():
        db_path = app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
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
        
        conn.close()

def test_init_db():
    """Test that init_db correctly initializes the database schema."""
    # Create a temporary database file
    import tempfile
    db_fd, db_path = tempfile.mkstemp()
    
    try:
        # Patch the DB_PATH to use our temporary database
        with patch('app.DB_PATH', db_path):
            # Call the init_db function
            init_db()
            
            # Verify that the tables were created
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # Check for users table
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            assert c.fetchone() is not None
            
            # Check for foods table
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='foods'")
            assert c.fetchone() is not None
            
            # Check for daily_log table
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_log'")
            assert c.fetchone() is not None
            
            # Check for daily_summary table
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_summary'")
            assert c.fetchone() is not None
            
            # Check table structure
            # Users table should have id, username, and password columns
            c.execute("PRAGMA table_info(users)")
            columns = c.fetchall()
            column_names = [col[1] for col in columns]
            assert 'id' in column_names
            assert 'username' in column_names
            assert 'password' in column_names
            
            # Foods table should have id, name, calories, and protein columns
            c.execute("PRAGMA table_info(foods)")
            columns = c.fetchall()
            column_names = [col[1] for col in columns]
            assert 'id' in column_names
            assert 'name' in column_names
            assert 'calories' in column_names
            assert 'protein' in column_names
            
            # Daily_log table should have the correct columns
            c.execute("PRAGMA table_info(daily_log)")
            columns = c.fetchall()
            column_names = [col[1] for col in columns]
            assert 'id' in column_names
            assert 'date' in column_names
            assert 'food_name' in column_names
            assert 'calories' in column_names
            assert 'protein' in column_names
            assert 'user_id' in column_names
            
            # Daily_summary table should have the correct columns
            c.execute("PRAGMA table_info(daily_summary)")
            columns = c.fetchall()
            column_names = [col[1] for col in columns]
            assert 'id' in column_names
            assert 'date' in column_names
            assert 'total_calories' in column_names
            assert 'total_protein' in column_names
            assert 'summary' in column_names
            assert 'user_id' in column_names
            assert 'calorie_goal' in column_names
            
            conn.close()
    finally:
        # Clean up the temporary file
        os.close(db_fd)
        os.unlink(db_path) 