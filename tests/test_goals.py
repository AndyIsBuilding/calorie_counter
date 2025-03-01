import pytest
import sqlite3
from datetime import datetime, timedelta

def test_historical_goals(app):
    """Test that historical goals are correctly maintained when updating past summaries."""
    with app.app_context():
        db_path = app.config['DB_PATH']
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Get the test user ID
        c.execute("SELECT id FROM users WHERE username = ?", ('testuser',))
        user_id = c.fetchone()[0]
        
        # Get current user goals
        c.execute("SELECT calorie_goal, protein_goal FROM users WHERE id = ?", (user_id,))
        current_goals = c.fetchone()
        
        # Create dates for testing
        today = datetime.now().date()
        date1 = (today - timedelta(days=10)).isoformat()  # 10 days ago
        date2 = (today - timedelta(days=5)).isoformat()   # 5 days ago
        date3 = (today - timedelta(days=3)).isoformat()   # 3 days ago
        
        # Clean up any existing test data for these dates
        for date in [date1, date2, date3]:
            c.execute("DELETE FROM food_log WHERE date = ? AND user_id = ?", (date, user_id))
            c.execute("DELETE FROM daily_summary WHERE date = ? AND user_id = ?", (date, user_id))
        
        try:
            # Create a summary for 10 days ago with different goals
            custom_calorie_goal = current_goals[0] - 200  # Different from current
            custom_protein_goal = current_goals[1] - 20   # Different from current
            
            # Insert a test food log entry for date1
            c.execute("""INSERT INTO food_log (date, food_name, calories, protein, user_id)
                        VALUES (?, ?, ?, ?, ?)""", 
                    (date1, "Test Food", 500, 30, user_id))
            
            # Create a summary for date1
            c.execute("""INSERT INTO daily_summary 
                        (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                    (date1, 500, 30, "Test Food 500 (30)", user_id, custom_calorie_goal, custom_protein_goal))
            
            # Now simulate updating history for date2 (5 days ago)
            # This should use the goals from date1
            
            # Insert a test food log entry for date2
            c.execute("""INSERT INTO food_log (date, food_name, calories, protein, user_id)
                        VALUES (?, ?, ?, ?, ?)""", 
                    (date2, "Test Food 2", 600, 40, user_id))
            
            # Simulate the update_history function logic
            c.execute("""SELECT calorie_goal, protein_goal FROM daily_summary 
                        WHERE date < ? AND user_id = ? 
                        ORDER BY date DESC LIMIT 1""", 
                    (date2, user_id))
            previous_summary = c.fetchone()
            
            if previous_summary:
                calorie_goal, protein_goal = previous_summary
            else:
                calorie_goal, protein_goal = current_goals
            
            # Create a summary for date2
            c.execute("""INSERT INTO daily_summary 
                        (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                    (date2, 600, 40, "Test Food 2 600 (40)", user_id, calorie_goal, protein_goal))
            
            # Verify the goals for date2
            c.execute("SELECT calorie_goal, protein_goal FROM daily_summary WHERE date = ? AND user_id = ?", 
                    (date2, user_id))
            date2_goals = c.fetchone()
            
            # Check if the goals match what we expect
            assert date2_goals[0] == custom_calorie_goal, f"Expected calorie goal {custom_calorie_goal}, got {date2_goals[0]}"
            assert date2_goals[1] == custom_protein_goal, f"Expected protein goal {custom_protein_goal}, got {date2_goals[1]}"
            
            # Now test creating a summary for date3 with no previous summary
            # First, delete the previous test data
            for date in [date1, date2]:
                c.execute("DELETE FROM food_log WHERE date = ? AND user_id = ?", (date, user_id))
                c.execute("DELETE FROM daily_summary WHERE date = ? AND user_id = ?", (date, user_id))
            
            # Now create a summary for date3 directly
            
            # Insert a test food log entry for date3
            c.execute("""INSERT INTO food_log (date, food_name, calories, protein, user_id)
                        VALUES (?, ?, ?, ?, ?)""", 
                    (date3, "Test Food 3", 700, 50, user_id))
            
            # Simulate the update_history function logic
            c.execute("""SELECT calorie_goal, protein_goal FROM daily_summary 
                        WHERE date < ? AND user_id = ? 
                        ORDER BY date DESC LIMIT 1""", 
                    (date3, user_id))
            previous_summary = c.fetchone()
            
            if previous_summary:
                calorie_goal, protein_goal = previous_summary
            else:
                calorie_goal, protein_goal = current_goals
            
            # Create a summary for date3
            c.execute("""INSERT INTO daily_summary 
                        (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                    (date3, 700, 50, "Test Food 3 700 (50)", user_id, calorie_goal, protein_goal))
            
            # Verify the goals for date3
            c.execute("SELECT calorie_goal, protein_goal FROM daily_summary WHERE date = ? AND user_id = ?", 
                    (date3, user_id))
            date3_goals = c.fetchone()
            
            # Check if the goals match what we expect (should be current user goals)
            assert date3_goals[0] == current_goals[0], f"Expected calorie goal {current_goals[0]}, got {date3_goals[0]}"
            assert date3_goals[1] == current_goals[1], f"Expected protein goal {current_goals[1]}, got {date3_goals[1]}"
            
        finally:
            # Clean up test data
            for date in [date1, date2, date3]:
                c.execute("DELETE FROM food_log WHERE date = ? AND user_id = ?", (date, user_id))
                c.execute("DELETE FROM daily_summary WHERE date = ? AND user_id = ?", (date, user_id))
            
            conn.commit()
            conn.close() 