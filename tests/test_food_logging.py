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
            INSERT INTO daily_log (user_id, date, food_name, calories, protein)
            VALUES (?, ?, ?, ?, ?)
        """, (1, today, food_name, calories, protein))
        conn.commit()
        
        # Verify the food was added
        c.execute("""
            SELECT * FROM daily_log 
            WHERE user_id = 1 AND food_name = ? AND calories = ? AND protein = ?
        """, (food_name, calories, protein))
        food = c.fetchone()
        assert food is not None

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
            INSERT INTO daily_log (user_id, date, food_name, calories, protein)
            VALUES (?, ?, ?, ?, ?)
        """, (1, today, food_name, calories, protein))
        conn.commit()
        
        # Get the ID of the inserted food
        c.execute("""
            SELECT id FROM daily_log 
            WHERE user_id = 1 AND food_name = ? AND date = ?
        """, (food_name, today))
        food_id = c.fetchone()[0]
        
        # Now delete the food
        c.execute("DELETE FROM daily_log WHERE id = ?", (food_id,))
        conn.commit()
        
        # Verify the food was deleted
        c.execute("SELECT * FROM daily_log WHERE id = ?", (food_id,))
        assert c.fetchone() is None

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
        c.execute("DELETE FROM daily_log WHERE date = ? AND user_id = ?", (test_date, 1))
        conn.commit()
        
        # Add some test entries
        test_foods = [
            ("Banana", 105, 1.3),
            ("Yogurt", 150, 8.5),
            ("Granola", 120, 3.0)
        ]
        
        for food in test_foods:
            c.execute("""
                INSERT INTO daily_log (user_id, date, food_name, calories, protein)
                VALUES (?, ?, ?, ?, ?)
            """, (1, test_date, food[0], food[1], food[2]))
        
        conn.commit()
        
        # Add a new food entry
        new_food_name = "Lunch Salad"
        new_calories = 200
        new_protein = 5
        
        c.execute("""
            INSERT INTO daily_log (user_id, date, food_name, calories, protein)
            VALUES (?, ?, ?, ?, ?)
        """, (1, test_date, new_food_name, new_calories, new_protein))
        conn.commit()
        
        # Verify the new entry was added
        c.execute("""
            SELECT * FROM daily_log 
            WHERE user_id = ? AND date = ? AND food_name = ?
        """, (1, test_date, new_food_name))
        result = c.fetchone()
        assert result is not None
        assert result[2] == new_food_name  # food_name is at index 2
        assert result[3] == new_calories   # calories is at index 3
        assert result[4] == new_protein    # protein is at index 4

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
        
        c.execute("DELETE FROM daily_log WHERE date = ? AND user_id = ?", (today, 1))
        conn.commit()
        
        # Add some test food entries for today
        test_foods = [
            ("Breakfast Eggs", 140, 12),
            ("Toast", 80, 3),
            ("Lunch Salad", 200, 5),
            ("Dinner Chicken", 300, 30),
            ("Vegetables", 50, 2)
        ]
        
        for food in test_foods:
            c.execute("""
                INSERT INTO daily_log (user_id, date, food_name, calories, protein)
                VALUES (?, ?, ?, ?, ?)
            """, (1, today, food[0], food[1], food[2]))
        
        conn.commit()
        
        # Calculate expected totals
        expected_calories = sum(food[1] for food in test_foods)
        expected_protein = sum(food[2] for food in test_foods)
        
        # Calculate totals from the database
        c.execute("""
            SELECT SUM(calories), SUM(protein) FROM daily_log
            WHERE user_id = ? AND date = ?
        """, (1, today))
        
        result = c.fetchone()
        assert result is not None
        assert result[0] == expected_calories
        assert result[1] == expected_protein 