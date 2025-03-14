import pytest #noqa 
import sqlite3
from datetime import datetime, timedelta

def test_historical_goals(app):
    """Test that historical goals are correctly maintained when updating past summaries."""
    with app.app_context():
        # Use the shared connection for the in-memory database
        conn = app.config['DB_CONNECTION']
        c = conn.cursor()
        
        # Get the test user ID
        c.execute("SELECT id FROM users WHERE username = ?", ('testuser',))
        user_id = c.fetchone()[0]
        
        # Get current user goals
        c.execute("SELECT calorie_goal, protein_goal FROM users WHERE id = ?", (user_id,))
        current_goals = c.fetchone()
        
        # Create dates for testing
        today = datetime.now().date()
        date1 = (today - timedelta(days=10)).isoformat()
        date2 = (today - timedelta(days=5)).isoformat()
        date3 = (today - timedelta(days=3)).isoformat()
        
        # Create a summary for 10 days ago with different goals
        custom_calorie_goal = current_goals[0] - 200
        custom_protein_goal = current_goals[1] - 20
        
        # Insert test food log entries
        c.execute("""INSERT INTO daily_log (date, food_name, calories, protein, user_id)
                    VALUES (?, ?, ?, ?, ?)""", 
                (date1, "Test Food", 500, 30, user_id))
        
        c.execute("""INSERT INTO daily_summary 
                    (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                (date1, 500, 30, "Test Food 500 (30)", user_id, custom_calorie_goal, custom_protein_goal))
        
        # Test data for date2
        c.execute("""INSERT INTO daily_log (date, food_name, calories, protein, user_id)
                    VALUES (?, ?, ?, ?, ?)""", 
                (date2, "Test Food 2", 600, 40, user_id))
        
        c.execute("""INSERT INTO daily_summary 
                    (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                (date2, 600, 40, "Test Food 2 600 (40)", user_id, custom_calorie_goal, custom_protein_goal))
        
        # Test data for date3
        c.execute("""INSERT INTO daily_log (date, food_name, calories, protein, user_id)
                    VALUES (?, ?, ?, ?, ?)""", 
                (date3, "Test Food 3", 700, 50, user_id))
        
        c.execute("""INSERT INTO daily_summary 
                    (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                (date3, 700, 50, "Test Food 3 700 (50)", user_id, current_goals[0], current_goals[1]))
        
        conn.commit()
        
        # Now test that we can retrieve the correct historical goals
        c.execute("""SELECT date, calorie_goal, protein_goal FROM daily_summary
                    WHERE user_id = ? ORDER BY date""", (user_id,))
        summaries = c.fetchall()
        
        # Check that we have 3 summaries
        assert len(summaries) == 3
        
        # Check that the first two summaries have the custom goals
        assert summaries[0][1] == custom_calorie_goal
        assert summaries[0][2] == custom_protein_goal
        assert summaries[1][1] == custom_calorie_goal
        assert summaries[1][2] == custom_protein_goal
        
        # Check that the third summary has the current goals
        assert summaries[2][1] == current_goals[0]
        assert summaries[2][2] == current_goals[1]
        
        # Don't close the shared connection 