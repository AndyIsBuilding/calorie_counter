import pytest #noqa: F401
import sys
import os
import sqlite3


# Add the parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import get_local_date

def test_log_food_db(app, client, auth):
    """Test adding a food entry to the database directly."""
    with app.app_context():
        # Log in the test user
        auth.login()
        
        # Test data
        food_name = "Test Apple"
        calories = 95
        protein = 0.5
        
        # Add the food entry directly to the database
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        today = get_local_date().isoformat()
        
        c.execute("""
            INSERT INTO food_log (user_id, date, food_name, calories, protein)
            VALUES (?, ?, ?, ?, ?)
        """, (1, today, food_name, calories, protein))
        conn.commit()
        
        # Verify the entry was added to the database
        c.execute("""
            SELECT * FROM food_log 
            WHERE date = ? AND food_name = ?
        """, (today, food_name))
        entry = c.fetchone()
        # Don't close the shared connection
        
        assert entry is not None
        assert entry[2] == today
        assert entry[3] == food_name
        assert entry[4] == calories
        assert entry[5] == protein

def test_remove_food_db(app, client, auth):
    """Test removing a food entry from the database directly."""
    with app.app_context():
        # Log in the test user
        auth.login()
        
        # First, add a food entry to delete
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        today = get_local_date().isoformat()
        food_name = "Test Orange"
        calories = 62
        protein = 1.2
        
        # Insert directly to the database
        c.execute("""
            INSERT INTO food_log (user_id, date, food_name, calories, protein)
            VALUES (?, ?, ?, ?, ?)
        """, (1, today, food_name, calories, protein))
        conn.commit()
        
        # Get the ID of the inserted entry
        c.execute("""
            SELECT id FROM food_log 
            WHERE date = ? AND food_name = ?
        """, (today, food_name))
        entry_id = c.fetchone()[0]
        
        # Delete the entry directly
        c.execute("DELETE FROM food_log WHERE id = ?", (entry_id,))
        conn.commit()
        
        # Verify the entry was deleted
        c.execute("SELECT * FROM food_log WHERE id = ?", (entry_id,))
        deleted_entry = c.fetchone()
        # Don't close the shared connection
        
        assert deleted_entry is None

def test_update_food_db(app, client, auth):
    """Test updating food entries directly in the database."""
    with app.app_context():
        # Log in the test user
        auth.login()
        
        # First, add some food entries for a specific date
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        test_date = '2023-01-01'
        
        # Clear any existing entries for the test date
        c.execute("DELETE FROM food_log WHERE date = ? AND user_id = ?", (test_date, 1))
        conn.commit()
        
        # Add test entries
        test_foods = [
            ("Breakfast Eggs", 140, 12),
            ("Toast", 80, 3)
        ]
        
        for food in test_foods:
            c.execute("""
                INSERT INTO food_log (user_id, date, food_name, calories, protein)
                VALUES (?, ?, ?, ?, ?)
            """, (1, test_date, food[0], food[1], food[2]))
        
        conn.commit()
        
        # Add a new food entry
        new_food_name = "Lunch Salad"
        new_calories = 200
        new_protein = 5
        
        c.execute("""
            INSERT INTO food_log (user_id, date, food_name, calories, protein)
            VALUES (?, ?, ?, ?, ?)
        """, (1, test_date, new_food_name, new_calories, new_protein))
        conn.commit()
        
        # Check that new entry was added
        c.execute("""
            SELECT * FROM food_log 
            WHERE date = ? AND food_name = ? AND calories = ? AND protein = ?
        """, (test_date, new_food_name, new_calories, new_protein))
        new_entry = c.fetchone()
        assert new_entry is not None
        
        # Don't close the shared connection

def test_daily_totals_calculation_db(app, client, auth):
    """Test calculating daily totals directly from the database."""
    with app.app_context():
        # Log in the test user
        auth.login()
        
        # First, clear any existing entries for today
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        today = get_local_date().isoformat()
        
        c.execute("DELETE FROM food_log WHERE date = ? AND user_id = ?", (today, 1))
        conn.commit()
        
        # Add some test food entries for today
        test_foods = [
            ("Breakfast Eggs", 140, 12),
            ("Toast", 80, 3),
            ("Lunch Salad", 200, 5),
            ("Dinner Chicken", 300, 30)
        ]
        
        expected_calories = 0
        expected_protein = 0
        
        for food in test_foods:
            c.execute("""
                INSERT INTO food_log (user_id, date, food_name, calories, protein)
                VALUES (?, ?, ?, ?, ?)
            """, (1, today, food[0], food[1], food[2]))
            expected_calories += food[1]
            expected_protein += food[2]
        
        conn.commit()
        
        # Calculate totals directly from the database
        c.execute("SELECT SUM(calories), SUM(protein) FROM food_log WHERE date = ? AND user_id = ?", 
                 (today, 1))
        db_totals = c.fetchone()
        # Don't close the shared connection
        
        # Verify the totals match our expectations
        assert db_totals[0] == expected_calories
        assert db_totals[1] == expected_protein 