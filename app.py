from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify, get_flashed_messages, current_app, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
import pytz
import csv
import io
import os
import logging
from typing import NamedTuple

# Configure logging
logging.basicConfig(level=logging.DEBUG if os.environ.get('DEBUG') else logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # Change this to a random secret key
app.config['TIMEZONE'] = os.getenv('TIMEZONE') 
app.config['TESTING'] = False  # Default to False, will be set to True in test environment
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)


class Food(NamedTuple):
    id: int
    name: str = ''
    calories: int = 0
    protein: int = 0


# Set the database path based on the environment
if 'PYTHONANYWHERE_SITE' in os.environ:
    # We're on PythonAnywhere (production)
    DB_PATH = os.getenv('DB_PATH')
else:
    # We're in local development
    DB_PATH = 'instance/food_tracker.db'

# Update app configuration
app.config['DB_PATH'] = DB_PATH

# Default goals for new users
DEFAULT_CALORIE_GOAL = 2000
DEFAULT_PROTEIN_GOAL = 100

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, calorie_goal=DEFAULT_CALORIE_GOAL, protein_goal=DEFAULT_PROTEIN_GOAL, weight_goal=None, weight_unit=0):
        self.id = id
        self.username = username
        self.calorie_goal = calorie_goal
        self.protein_goal = protein_goal
        self.weight_goal = weight_goal
        self.weight_unit = weight_unit  # 0 for kg, 1 for lbs
    
    def update_goals(self, calorie_goal, protein_goal, weight_goal=None, weight_unit=None):
        """Update the user's calorie, protein, weight goals and weight unit preference"""
        self.calorie_goal = calorie_goal
        self.protein_goal = protein_goal
        
        # Update weight_goal and weight_unit if provided
        if weight_goal is not None:
            self.weight_goal = weight_goal
        
        if weight_unit is not None:
            self.weight_unit = weight_unit
            
        # Update the database with all settings
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Build the SQL query and parameters based on what was provided
        sql_parts = ["calorie_goal = ?", "protein_goal = ?"]
        params = [calorie_goal, protein_goal]
        
        if weight_goal is not None:
            sql_parts.append("weight_goal = ?")
            params.append(weight_goal)
        
        if weight_unit is not None:
            sql_parts.append("weight_unit = ?")
            params.append(weight_unit)
        
        # Complete the SQL query
        sql = f"UPDATE users SET {', '.join(sql_parts)} WHERE id = ?"
        params.append(self.id)
        
        # Execute the query
        c.execute(sql, params)
        conn.commit()
        conn.close()
        
        return True
    
    def log_weight(self, weight, date=None):
        """Log the user's weight for a specific date"""
        
        if date is None:
            date = get_local_date().isoformat()
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if there's already a weight log for this date
        c.execute("SELECT id, weight FROM weight_logs WHERE date = ? AND user_id = ?", (date, self.id))
        existing_log = c.fetchone()
        
        if existing_log:
            # Update existing log
            c.execute("UPDATE weight_logs SET weight = ? WHERE id = ?", (weight, existing_log[0]))
        else:
            # Insert new log
            c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)", 
                     (date, weight, self.id))
        
        conn.commit()
        conn.close()
        
        return True
    
    def get_weight_logs(self, limit=30):
        """Get the user's weight logs, limited to the most recent entries"""
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("""SELECT date, weight FROM weight_logs 
                     WHERE user_id = ? 
                     ORDER BY date DESC LIMIT ?""", 
                  (self.id, limit))
        logs = c.fetchall()
                
        # Convert weights to user's preferred unit
        converted_logs = []
        for date, weight in logs:
            if self.weight_unit == 1:  # If user prefers lbs
                converted_weight = round(weight * 2.20462, 1)
                converted_logs.append((date, converted_weight))
            else:
                converted_logs.append((date, weight))
        
        conn.close()
        return converted_logs

@login_manager.user_loader
def load_user(user_id):
    from flask import current_app
    # Use the shared connection if in testing mode
    if current_app.config['TESTING']:
        conn = current_app.config['DB_CONNECTION']
    else:
        conn = sqlite3.connect(current_app.config['DB_PATH'])
        
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    
    if not current_app.config['TESTING']:
        conn.close()
    
    if user:
        # Explicitly map the database columns to User constructor arguments
        return User(
            id=user[0],
            username=user[1],
            calorie_goal=user[3],
            protein_goal=user[4],
            weight_goal=user[5],
            weight_unit=user[6]
        )
    return None

def init_db():
    """Initialize the database with the required tables."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create users table
    c.execute(f'''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  calorie_goal INTEGER DEFAULT {DEFAULT_CALORIE_GOAL},
                  protein_goal INTEGER DEFAULT {DEFAULT_PROTEIN_GOAL},
                  weight_goal REAL,
                  weight_unit INTEGER DEFAULT 0)''')
    
    # Create foods table with user_id column
    c.execute('''CREATE TABLE IF NOT EXISTS foods
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  calories INTEGER NOT NULL,
                  protein INTEGER NOT NULL,
                  user_id INTEGER,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Create daily_log table
    c.execute('''CREATE TABLE IF NOT EXISTS daily_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  food_name TEXT NOT NULL,
                  calories INTEGER NOT NULL,
                  protein INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Create daily_summary table with unique constraint on date and user_id
    c.execute('''CREATE TABLE IF NOT EXISTS daily_summary
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  total_calories INTEGER NOT NULL,
                  total_protein INTEGER NOT NULL,
                  summary TEXT,
                  user_id INTEGER NOT NULL,
                  calorie_goal INTEGER,
                  protein_goal INTEGER,
                  FOREIGN KEY (user_id) REFERENCES users(id),
                  UNIQUE(date, user_id))''')
    
    # Create weight_logs table
    c.execute('''CREATE TABLE IF NOT EXISTS weight_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  weight REAL NOT NULL,
                  user_id INTEGER NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Create poker_players table
    c.execute('''CREATE TABLE IF NOT EXISTS poker_players
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  player_name TEXT NOT NULL,
                  player_notes TEXT,
                  total_hands INTEGER DEFAULT 0,
                  total_vpip INTEGER DEFAULT 0,
                  total_pfr INTEGER DEFAULT 0,
                  last_played TEXT,
                  is_hero INTEGER DEFAULT 0,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Create poker_sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS poker_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  session_date TEXT NOT NULL,
                  is_active INTEGER DEFAULT 1,
                  button_position INTEGER NOT NULL,
                  hand_count INTEGER DEFAULT 0,
                  created_at TEXT NOT NULL,
                  ended_at TEXT,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Create poker_session_players table (junction table)
    c.execute('''CREATE TABLE IF NOT EXISTS poker_session_players
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id INTEGER NOT NULL,
                  player_id INTEGER,
                  seat_number INTEGER NOT NULL,
                  session_hands INTEGER DEFAULT 0,
                  session_vpip INTEGER DEFAULT 0,
                  session_pfr INTEGER DEFAULT 0,
                  is_sitting_out INTEGER DEFAULT 0,
                  player_display_name TEXT NOT NULL,
                  joined_at TEXT,
                  FOREIGN KEY (session_id) REFERENCES poker_sessions(id),
                  FOREIGN KEY (player_id) REFERENCES poker_players(id))''')

    # Create poker_hand_tracking table (temporary hand state)
    c.execute('''CREATE TABLE IF NOT EXISTS poker_hand_tracking
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id INTEGER NOT NULL,
                  hand_number INTEGER NOT NULL,
                  button_position INTEGER NOT NULL,
                  has_btn_straddle INTEGER DEFAULT 0,
                  has_utg_straddle INTEGER DEFAULT 0,
                  actions TEXT,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY (session_id) REFERENCES poker_sessions(id))''')

    # Create poker_session_appearances table (permanent per-occupancy history).
    # One row per stint a player spent in a seat. Captured when a player leaves
    # a seat or when the session ends, so seat swaps are preserved.
    c.execute('''CREATE TABLE IF NOT EXISTS poker_session_appearances
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id INTEGER NOT NULL,
                  seat_number INTEGER NOT NULL,
                  player_id INTEGER,
                  player_display_name TEXT NOT NULL,
                  session_hands INTEGER DEFAULT 0,
                  session_vpip INTEGER DEFAULT 0,
                  session_pfr INTEGER DEFAULT 0,
                  joined_at TEXT,
                  left_at TEXT,
                  FOREIGN KEY (session_id) REFERENCES poker_sessions(id),
                  FOREIGN KEY (player_id) REFERENCES poker_players(id))''')

    # Create poker_hands table (permanent raw hand history).
    # One row per completed hand. dealt_in and actions are JSON, with each
    # action attributed to a player_id, so any preflop stat (VPIP, PFR, limp,
    # 3bet, steal, ...) can be derived now or in the future.
    c.execute('''CREATE TABLE IF NOT EXISTS poker_hands
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id INTEGER NOT NULL,
                  hand_number INTEGER,
                  button_position INTEGER,
                  has_btn_straddle INTEGER DEFAULT 0,
                  has_utg_straddle INTEGER DEFAULT 0,
                  dealt_in TEXT,
                  actions TEXT,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY (session_id) REFERENCES poker_sessions(id))''')

    conn.commit()
    conn.close()


def get_local_date():
    tz = pytz.timezone(os.environ.get('TIMEZONE', 'UTC'))
    return datetime.now(tz).date()

@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get today's date in the user's timezone
    today = get_local_date().isoformat()
    
    # Check if a summary exists for today
    c.execute("""SELECT id FROM daily_summary 
                 WHERE date = ? AND user_id = ?""", 
              (today, current_user.id))
    has_summary = c.fetchone() is not None
    
    # Get today's log
    c.execute("""SELECT id, food_name, calories, protein 
                 FROM daily_log 
                 WHERE date = ? AND user_id = ?""", 
              (today, current_user.id))
    daily_log = c.fetchall()
    
    # Calculate totals
    total_calories = sum(log[2] for log in daily_log)
    total_protein = sum(log[3] for log in daily_log)
    
    # Get quick add foods for the current user
    c.execute("SELECT id, name, calories, protein FROM foods WHERE user_id = ? ORDER BY name", (current_user.id,))
    foods = c.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                          daily_log=daily_log,
                          total_calories=total_calories,
                          total_protein=total_protein,
                          foods=foods,
                          calorie_goal=current_user.calorie_goal,
                          protein_goal=current_user.protein_goal,
                          has_summary=has_summary)

@app.route('/api/dashboard-stats')
@login_required
def dashboard_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get today's date in the user's timezone
    today = get_local_date().isoformat()
    
    # Get today's log
    c.execute("""SELECT id, food_name, calories, protein 
                 FROM daily_log 
                 WHERE date = ? AND user_id = ?""", 
              (today, current_user.id))
    daily_log = c.fetchall()
    
    # Format the daily log for JSON
    formatted_log = [
        {
            'id': entry[0],
            'food_name': entry[1],
            'calories': entry[2],
            'protein': entry[3]
        }
        for entry in daily_log
    ]
    
    # Calculate totals
    total_calories = sum(log[2] for log in daily_log)
    total_protein = sum(log[3] for log in daily_log)
    
    conn.close()
    
    return jsonify({
        'daily_log': formatted_log,
        'stats': {
            'total_calories': total_calories,
            'total_protein': total_protein,
            'calorie_goal': current_user.calorie_goal,
            'protein_goal': current_user.protein_goal
        }
    })

@app.route('/edit_history')
@login_required
def edit_history():
    # Get the date from the query parameter, or use today's date if not provided
    date_str = request.args.get('date', get_local_date().isoformat())
    
    try:
        # Parse the date string into a datetime object
        edit_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Fetch the daily log for the selected date
    c.execute("""SELECT id, food_name, calories, protein 
                 FROM daily_log
                 WHERE date = ? AND user_id = ?""", (date_str, current_user.id))
    daily_log = [{"id": row[0], "name": row[1], "calories": row[2], "protein": row[3]} for row in c.fetchall()]
    
    # Fetch the daily summary for the selected date
    c.execute("""SELECT total_calories, total_protein, summary, calorie_goal, protein_goal 
                 FROM daily_summary
                 WHERE date = ? AND user_id = ?""", (date_str, current_user.id))
    summary = c.fetchone()
    
    conn.close()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'daily_log': daily_log,
            'summary': summary
        })
    
    return render_template('edit_history.html', 
                           edit_date=edit_date, 
                           daily_log=daily_log, 
                           summary=summary)


@app.route('/update_history', methods=['POST'])
@login_required
def update_history():
    edit_date = request.form['edit_date']
    
    existing_food_ids = request.form.getlist('existing_food_id[]')
    new_food_names = request.form.getlist('new_food_name[]')
    new_food_calories = request.form.getlist('new_food_calories[]')
    new_food_protein = request.form.getlist('new_food_protein[]')

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Remove foods that were deleted on the edit page
    c.execute("""DELETE FROM daily_log 
                 WHERE date = ? AND user_id = ? AND id NOT IN ({})""".format(','.join(['?']*len(existing_food_ids))), 
              [edit_date, current_user.id] + existing_food_ids)

    # Add new foods
    for name, calories, protein in zip(new_food_names, new_food_calories, new_food_protein):
        c.execute("""INSERT INTO daily_log (date, food_name, calories, protein, user_id)
                     VALUES (?, ?, ?, ?, ?)""", 
                  (edit_date, name, calories, protein, current_user.id))

    # Fetch all foods for the day after updating
    c.execute("""SELECT food_name, calories, protein
                 FROM daily_log
                 WHERE date = ? AND user_id = ?
                 ORDER BY id""", (edit_date, current_user.id))
    foods = c.fetchall()

    # Create the summary string
    summary = ", ".join([f"{name} {calories} ({protein})" for name, calories, protein in foods])

    # Calculate total calories and protein
    total_calories = sum(int(food[1]) for food in foods)
    total_protein = sum(int(food[2]) for food in foods)

    # Check if there's a daily summary for the current date
    c.execute("""SELECT id, calorie_goal, protein_goal FROM daily_summary 
                 WHERE date = ? AND user_id = ?""", 
              (edit_date, current_user.id))
    existing_summary = c.fetchone()

    if existing_summary:
        # Update the existing summary, preserving the calorie_goal and protein_goal
        c.execute("""UPDATE daily_summary 
                     SET total_calories = ?, total_protein = ?, summary = ?
                     WHERE date = ? AND user_id = ?""", 
                  (total_calories, total_protein, summary, edit_date, current_user.id))
    else:
        # For a new summary of a past date, find the most recent previous summary
        # and use its goal values
        calorie_goal = current_user.calorie_goal
        protein_goal = current_user.protein_goal
        
        # Find the most recent summary before the edit date
        c.execute("""SELECT calorie_goal, protein_goal FROM daily_summary 
                     WHERE date < ? AND user_id = ? 
                     ORDER BY date DESC LIMIT 1""", 
                  (edit_date, current_user.id))
        previous_summary = c.fetchone()
        
        if previous_summary:
            # Use the goals from the previous summary
            calorie_goal, protein_goal = previous_summary
        
        # Insert a new summary with the determined goal values
        c.execute("""INSERT INTO daily_summary 
                     (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                  (edit_date, total_calories, total_protein, summary, current_user.id, calorie_goal, protein_goal))

    conn.commit()
    conn.close()

    flash(f'Daily log for {edit_date} updated!', 'success')
    return redirect(url_for('edit_history'))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/quick_add_food', methods=['POST'])
@login_required
def quick_add_food():
    name = request.form.get('name')
    calories = request.form.get('calories', type=int)
    protein = request.form.get('protein', type=int)
    
    if not name or not calories or not protein:
        return jsonify({
            'success': False,
            'toast': {
                'message': 'Missing required fields',
                'category': 'error'
            }
        })
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Insert the food with the current user's ID
    c.execute("INSERT INTO foods (name, calories, protein, user_id) VALUES (?, ?, ?, ?)", 
              (name, calories, protein, current_user.id))
    
    # Get the ID of the newly inserted food
    food_id = c.lastrowid
    
    conn.commit()
    conn.close()
    
    # Return the food data including the ID
    return jsonify({
        'success': True,
        'toast': {
            'message': 'Food added to your quick add list',
            'category': 'success'
        },
        'food': {
            'id': food_id,
            'name': name,
            'calories': calories,
            'protein': protein
        }
    })


@app.route('/log_food', methods=['POST'])
@login_required
def log_food():
    name = request.form['name']
    calories = int(request.form['calories'])
    protein = int(request.form['protein'])
    servings = float(request.form['servings'])
    
    total_calories = int(calories * servings)
    total_protein = int(protein * servings)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    today = get_local_date().isoformat()
    c.execute("INSERT INTO daily_log (date, food_name, calories, protein, user_id) VALUES (?, ?, ?, ?, ?)", 
              (today, name, total_calories, total_protein, current_user.id))
    log_id = c.lastrowid
    
    # Calculate new totals
    c.execute("SELECT SUM(calories), SUM(protein) FROM daily_log WHERE date = ? AND user_id = ?", (today, current_user.id))
    total_calories_sum, total_protein_sum = c.fetchone()
    
    conn.commit()
    conn.close()
    
    # Return a standard JSON response with toast data
    return jsonify({
        "success": True,
        "toast": {
            "message": f"Added {name} to your log",
            "category": "success"
        },
        "log_entry": {
            "id": log_id,
            "food_name": name,
            "calories": total_calories,
            "protein": total_protein
        },
        "totals": {
            "calories": total_calories_sum,
            "protein": total_protein_sum
        }
    })


@app.route('/log_quick_food', methods=['POST'])
@login_required
def log_quick_food():
    food_id = request.form.get('food_id')
    
    if not food_id:
        return jsonify({'success': False, 'message': 'No food ID provided'})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get the food details, ensuring it belongs to the current user
    c.execute("SELECT name, calories, protein FROM foods WHERE id = ? AND user_id = ?", (food_id, current_user.id))
    food = c.fetchone()
    
    if not food:
        conn.close()
        return jsonify({'success': False, 'message': 'Food not found or you do not have permission to log it'})
    
    name, calories, protein = food
    today = get_local_date().isoformat()
    
    # Insert into daily log
    c.execute("INSERT INTO daily_log (date, food_name, calories, protein, user_id) VALUES (?, ?, ?, ?, ?)",
             (today, name, calories, protein, current_user.id))
    log_id = c.lastrowid
    
    conn.commit()
    conn.close()
    
    # Return the log entry and updated totals
    return jsonify({
        'success': True,
        "toast": {
            "message": f"Added {name} to your log",
            "category": "success"
        },
        'log_entry': {
            'id': log_id,
            'food_name': name,
            'calories': calories,
            'protein': protein
        },
        'totals': {
            'calories': request.form.get('total_calories', type=int, default=0) + calories,
            'protein': request.form.get('total_protein', type=int, default=0) + protein
        }
    })


@app.route('/remove_food/<int:log_id>', methods=['POST'])
@login_required
def remove_food(log_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Delete the log entry
    c.execute("DELETE FROM daily_log WHERE id = ? AND user_id = ?", (log_id, current_user.id))
    
    # Calculate new totals
    today = get_local_date().isoformat()
    c.execute("SELECT SUM(calories), SUM(protein) FROM daily_log WHERE date = ? AND user_id = ?", (today, current_user.id))
    total_calories, total_protein = c.fetchone()
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "toast": {
            "message": "Food removed",
            "category": "success"
        },
        "totals": {
            "calories": total_calories or 0,
            "protein": total_protein or 0
        }
    })

@app.route('/remove_quick_add_food', methods=['POST'])
@login_required
def remove_quick_add_food():
    food_id = request.form.get('food_id')
    
    if not food_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'toast': {
                    'message': 'No food ID provided',
                    'category': 'error'
                }
            })
        flash('No food ID provided', 'error')
        return redirect(url_for('settings'))
    
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        # First check if the food belongs to the current user
        c.execute("SELECT id FROM foods WHERE id = ? AND user_id = ?", (food_id, current_user.id))
        if not c.fetchone():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'toast': {
                        'message': 'Food not found or unauthorized',
                        'category': 'error'
                    }
                })
            flash('Food not found or unauthorized', 'error')
            return redirect(url_for('settings'))
        
        # Delete the food
        c.execute("DELETE FROM foods WHERE id = ? AND user_id = ?", (food_id, current_user.id))
        conn.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'toast': {
                    'message': 'Food removed!',
                    'category': 'success'
                }
            })
        
        flash('Food removed!', 'success')
        return redirect(url_for('settings'))
    except sqlite3.Error:
        conn.rollback()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'toast': {
                    'message': 'Database error occurred',
                    'category': 'error'
                }
            })
        flash('Database error occurred', 'error')
        return redirect(url_for('settings'))
    finally:
        conn.close()

@app.route('/save_summary', methods=['POST'])
@login_required
def save_summary():
    today = get_local_date().isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Fetch all foods logged for today
    c.execute("""SELECT food_name, calories, protein
                 FROM daily_log
                 WHERE date = ? AND user_id = ?
                 ORDER BY id""", (today, current_user.id))
    foods = c.fetchall()
    
    # Create the summary string
    summary = ", ".join([f"{name} {calories} ({protein})" for name, calories, protein in foods])
    
    # Calculate total calories and protein
    total_calories = sum(food[1] for food in foods)
    total_protein = sum(food[2] for food in foods)
    
    # Check if a summary already exists for today
    c.execute("""SELECT id FROM daily_summary 
                 WHERE date = ? AND user_id = ?""", 
              (today, current_user.id))
    existing_summary = c.fetchone()
    
    if existing_summary:
        # Update existing summary
        c.execute("""UPDATE daily_summary 
                     SET total_calories = ?, total_protein = ?, summary = ?, 
                         calorie_goal = ?, protein_goal = ?
                     WHERE date = ? AND user_id = ?""", 
                  (total_calories, total_protein, summary, 
                   current_user.calorie_goal, current_user.protein_goal,
                   today, current_user.id))
    else:
        # Insert new summary
        c.execute("""INSERT INTO daily_summary 
                     (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                  (today, total_calories, total_protein, summary, 
                   current_user.id, current_user.calorie_goal, current_user.protein_goal))
    
    conn.commit()
    conn.close()
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': 'Daily summary updated!',
            'totals': {
                'calories': total_calories,
                'protein': total_protein
            }
        })
    
    # For non-AJAX requests, use flash and redirect
    flash('Daily summary updated!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/export_csv')
@login_required
def export_csv():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT date, summary, total_calories, total_protein, calorie_goal, protein_goal 
                 FROM daily_summary
                 WHERE user_id = ?
                 ORDER BY date""", (current_user.id,))
    data = c.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Food Summary', 'Total Calories', 'Total Protein', 'Calorie Goal', 'Protein Goal'])
    writer.writerows(data)
    
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='daily_summary.csv'
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'redirect_url': url_for('dashboard')})
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = current_app.config['DB_CONNECTION'] if current_app.config.get('TESTING') else sqlite3.connect(current_app.config['DB_PATH'])
        
        try:
            c = conn.cursor()
            # Use COLLATE NOCASE to make the username search case-insensitive
            c.execute("SELECT * FROM users WHERE username COLLATE NOCASE = ?", (username,))
            user = c.fetchone()
            
            # First check if user exists and password matches
            if user is None or not check_password_hash(user[2], password):
                # Failed login - wrong username or password
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': False,
                        'message': 'Invalid username or password'
                    }), 401
                flash('Invalid username or password', 'error')
                return render_template('login.html'), 401

            # If we get here, login is successful
            # Create user object with all attributes
            user_obj = User(
                id=user[0],
                username=user[1],
                calorie_goal=user[3],
                protein_goal=user[4],
                weight_goal=user[5],
                weight_unit=user[6]
            )
            # Make the session permanent to last for PERMANENT_SESSION_LIFETIME
            session.permanent = True
            login_user(user_obj, remember=True)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'redirect_url': url_for('dashboard'),
                    'user': {
                        'username': user_obj.username,
                        'calorie_goal': user_obj.calorie_goal,
                        'protein_goal': user_obj.protein_goal,
                        'weight_goal': user_obj.weight_goal,
                        'weight_unit': user_obj.weight_unit
                    }
                })
            return redirect(url_for('dashboard'))
            
        finally:
            if not current_app.config.get('TESTING'):
                conn.close()
    
    # GET request
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: 
        return redirect(url_for('dashboard')) 

    if request.method == 'POST':
        # Check if there's already a user in the database
        # Skip this check if we're in testing mode
        if not app.config['TESTING']:
            conn = sqlite3.connect(app.config['DB_PATH'])
            try:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM users")
                user_count = c.fetchone()[0]
                if user_count > 1:
                    flash('Only one user (the creator) is allowed in this application.', 'error')
                    return redirect(url_for('index'))
            finally:
                conn.close()
        
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        
        conn = sqlite3.connect(app.config['DB_PATH'])
        try:
            c = conn.cursor()
            # First check if username exists
            c.execute("SELECT username FROM users WHERE username = ?", (username,))
            if c.fetchone():
                flash('Username already exists.', 'error')
                return redirect(url_for('register'))
            
            # If username doesn't exist, proceed with insertion
            c.execute("INSERT INTO users (username, password, calorie_goal, protein_goal, weight_goal, weight_unit) VALUES (?, ?, ?, ?, ?, ?)", 
                     (username, hashed_password, DEFAULT_CALORIE_GOAL, DEFAULT_PROTEIN_GOAL, None, 0))
            conn.commit()
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.Error:
            conn.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            return redirect(url_for('register'))
        finally:
            conn.close()

    return render_template('register.html')

@app.errorhandler(400)
def bad_request_error(error):
    return render_template('errors.html', error_code=400, error_message="Bad Request"), 400

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors.html', error_code=403, error_message="Forbidden"), 403

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors.html', error_code=404, error_message="Page Not Found"), 404

@app.errorhandler(500)
def internal_server_error(error):
    return render_template('errors.html', error_code=500, error_message="Internal Server Error"), 500

@app.route('/get_recommendations', methods=['POST'])
@login_required
def get_recommendations():
    today = get_local_date().isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # First check if user has at least 5 foods in their Quick Add section
    c.execute("SELECT COUNT(*) FROM foods WHERE user_id = ?", (current_user.id,))
    food_count = c.fetchone()[0]
    
    if food_count < 5:
        conn.close()
        return jsonify({
            'insufficient_foods': True,
            'message': f'Please add at least 5 foods to your Quick Add section to get recommendations. You currently have {food_count} food{"s" if food_count != 1 else ""}.'
        })
    
    c.execute("SELECT SUM(calories) FROM daily_log WHERE date = ? AND user_id = ?", (today, current_user.id))
    total_calories = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(protein) FROM daily_log WHERE date = ? AND user_id = ?", (today, current_user.id))
    total_protein = c.fetchone()[0] or 0
    
    conn.close()
    
    recommendations = food_recommendation(total_calories, total_protein)

    formatted_recommendations = {}

    for key, foods in recommendations.items():
        if foods:
            total_calories_rec = sum(food.calories for food in foods)
            total_protein_rec = sum(food.protein for food in foods)
            formatted_recommendations[key] = {
                "foods": [
                    {"name": food.name, "calories": food.calories, "protein": food.protein}
                    for food in foods
                ],
                "total_calories": total_calories_rec,
                "total_protein": total_protein_rec,
                "day_total_calories": total_calories + total_calories_rec,
                "day_total_protein": total_protein + total_protein_rec,
            }
        else:
            formatted_recommendations[key] = None

    return jsonify(formatted_recommendations)

def food_recommendation(total_calories, total_protein): 
    """    Compare to pre-set calorie/protein goals; determine remaining calories/protein for the day 
    Recommend based on remaining calories/protein
    Return a list of recommended foods"""
    # TODO: update this algorithm 

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get today's date
    today = get_local_date().isoformat()

    # Fetch foods eaten today from the daily log
    c.execute("SELECT DISTINCT food_name FROM daily_log WHERE date = ? AND user_id = ?", (today, current_user.id))
    eaten_foods = [row[0] for row in c.fetchall()] # a list of tuples in fetchall, extract the food name into list

    # Fetch all foods and filter out the ones eaten today
    foods = c.execute("SELECT * FROM foods WHERE user_id = ?", (current_user.id,)).fetchall()
    available_foods = [Food(id=row[0], name=row[1], calories=row[2], protein=row[3]) for row in foods if row[1] not in eaten_foods]  # row[1] is the food name
    n = len(available_foods)

    conn.close()

    # Calculate remaining calories/protein for the day 
    remaining_calories = max(0, current_user.calorie_goal - total_calories)
    remaining_protein = max(0, current_user.protein_goal - total_protein)

    def knapsack(n, W, wt, val):
        K = [[0 for _ in range(W + 1)] for _ in range(n + 1)]
        for i in range(n + 1):
            for w in range(W + 1):
                if i == 0 or w == 0:
                    K[i][w] = 0
                elif wt[i-1] <= w:
                    K[i][w] = max(val[i-1] + K[i-1][w-wt[i-1]], K[i-1][w])
                else:
                    K[i][w] = K[i-1][w]
        return K

    def backtrack(K, wt, val, n, W):
        res = []
        w = W
        for i in range(n, 0, -1):
            if K[i][w] != K[i-1][w]:
                res.append(available_foods[i-1])
                w -= wt[i-1]
        return res

    weights = [food.calories for food in available_foods]
    values = [food.protein for food in available_foods]
    n = len(available_foods)

    hit_both = None
    prioritize_protein = None
    prioritize_calories = None

    # Priority 1: hit_both
    K = knapsack(n, remaining_calories, weights, values)
    if K[n][remaining_calories] >= remaining_protein:
        hit_both = backtrack(K, weights, values, n, remaining_calories)

    # Priority 2: prioritize_protein (protein_first)
    max_calories = sum(weights)
    K = knapsack(n, max_calories, weights, values)
    for cal in range(remaining_calories, max_calories + 1):
        if K[n][cal] >= remaining_protein:
            prioritize_protein = backtrack(K, weights, values, n, cal)
            break

    # Priority 3: prioritize_calories (calorie_first)
    K = knapsack(n, remaining_calories, weights, values)
    prioritize_calories = backtrack(K, weights, values, n, remaining_calories)

    return {
        "hit_both": hit_both,
        "protein_first": prioritize_protein,
        "calorie_first": prioritize_calories
    }

@app.route('/api/testimonials')
def get_testimonials():
    testimonials = [
        {
            "quote": "HealthVibe has made it so easy for me to keep on top of my nutrition. I've never felt better!",
            "author": "Sarah L.",
            "role": "Fitness Enthusiast",
        },
        {
            "quote": "As a nutritionist, I recommend HealthVibe to all my clients. It's user-friendly and accurate.",
            "author": "Dr. Michael Chen",
            "role": "Registered Dietitian",
        },
        {
            "quote": "This app has been a game-changer in my weight loss journey. The insights are invaluable.",
            "author": "Chris Thompson",
            "role": "User since 2022",
        },
    ]
    return jsonify(testimonials)

@app.route('/settings') 
@login_required
def settings(): 
    # Get success message from flash if it exists
    # TODO: why is this here? 
    success_message = None
    flashed_messages = get_flashed_messages(with_categories=True)
    for category, message in flashed_messages:
        if category == 'success':
            success_message = message
        else:
            flash(message, category)  # Re-flash non-success messages
    
    # Get today's calorie and protein data
    today_calories = 0
    today_protein = 0
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = get_local_date().isoformat()
    
    # First check if there's a daily summary for today
    c.execute("""SELECT total_calories, total_protein 
                 FROM daily_summary 
                 WHERE date = ? AND user_id = ?""", 
              (today, current_user.id))
    summary = c.fetchone()
    
    if summary:
        today_calories, today_protein = summary
    else:
        # If no summary, calculate from daily log
        c.execute("""SELECT SUM(calories), SUM(protein) 
                     FROM daily_log 
                     WHERE date = ? AND user_id = ?""", 
                  (today, current_user.id))
        log_totals = c.fetchone()
        
        if log_totals[0] is not None:
            today_calories, today_protein = log_totals
    
    # Get weight logs
    weight_logs = current_user.get_weight_logs(limit=10)
    
    # Fetch all foods (quick add foods) for the current user
    c.execute("SELECT id, name, calories, protein FROM foods WHERE user_id = ? ORDER BY name", (current_user.id,))
    foods = c.fetchall()
    
    conn.close()
    
    # If this is an AJAX request, return only the quick add foods section
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('settings.html', 
                             foods=foods,
                             success_message=success_message,
                             today_calories=today_calories,
                             today_protein=today_protein,
                             weight_logs=weight_logs,
                             ajax_only=True,
                             calorie_goal=current_user.calorie_goal,
                             protein_goal=current_user.protein_goal)
    
    # For regular requests, return the full page
    return render_template('settings.html', 
                         foods=foods,
                         success_message=success_message,
                         today_calories=today_calories,
                         today_protein=today_protein,
                         weight_logs=weight_logs,
                         calorie_goal=current_user.calorie_goal,
                         protein_goal=current_user.protein_goal)

@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    # Check if this is a unit preference update only
    update_unit_only = request.form.get('update_unit_only') == 'true'
    
    # Get the weight unit preference
    weight_unit = request.form.get('weight_unit', type=int, default=0)  # Default to kg (0)
    
    if update_unit_only:
        # Only update the weight unit preference
        # No need to validate or convert any weight values
        current_user.update_goals(
            current_user.calorie_goal, 
            current_user.protein_goal, 
            weight_goal=None,  # Don't change the weight goal
            weight_unit=weight_unit
        )
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'toast': {
                    'message': 'Display unit updated!',
                    'category': 'success',
                    'skipDisplay': True  # Tell the JavaScript not to show this toast
                },
                'redirect': url_for('settings')
            })
        
        # For non-AJAX requests, use flash and redirect
        flash('Display unit updated!', 'success')
        return redirect(url_for('settings'))
    
    # If not updating only the unit, proceed with full settings update
    # Get the new calorie and protein goals from the form
    calorie_goal = request.form.get('calorie_goal', type=int)
    protein_goal = request.form.get('protein_goal', type=int)
    weight_goal = request.form.get('weight_goal', type=float)
    current_weight = request.form.get('current_weight', type=float)
    
    # Validate the input
    if calorie_goal is None or protein_goal is None:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'toast': {
                    'message': 'Invalid input. Please enter valid numbers for calorie and protein goals.',
                    'category': 'error'
                }
            })
        flash('Invalid input. Please enter valid numbers for calorie and protein goals.', 'error')
        return redirect(url_for('settings'))
    
    if calorie_goal <= 0 or protein_goal <= 0:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'toast': {
                    'message': 'Calorie and protein goals must be positive numbers.',
                    'category': 'error'
                }
            })
        flash('Calorie and protein goals must be positive numbers.', 'error')
        return redirect(url_for('settings'))
    
    # Handle weight goal conversion - the frontend now sends the raw input value
    # and a display unit indicator, so we always need to convert if the unit is pounds
    if weight_goal is not None:
        # Get the current display unit from the form
        display_unit = request.form.get('current_display_unit', type=int, default=current_user.weight_unit)
        
        # Convert to kg if the display unit is pounds (1)
        if display_unit == 1:
            weight_goal = weight_goal / 2.20462
            logger.debug(f"Converting weight goal from lbs to kg: {weight_goal}")

    # Convert current weight if provided
    if current_weight is not None and current_weight > 0:
        # Get the current display unit from the form
        display_unit = request.form.get('current_display_unit', type=int, default=current_user.weight_unit)
        
        # Convert to kg if the display unit is pounds (1)
        if display_unit == 1:
            current_weight = current_weight / 2.20462
            logger.debug(f"Converting current weight from lbs to kg: {current_weight}")
    
    # Update the user's goals with the converted weights
    # If weight_unit is provided in the form, use it, otherwise don't change it
    form_weight_unit = request.form.get('weight_unit', type=int)
    
    # Debug the final values before updating
    logger.debug(f"Updating user goals: calorie_goal={calorie_goal}, protein_goal={protein_goal}, " +
                f"weight_goal={weight_goal}, weight_unit={form_weight_unit}")
    
    current_user.update_goals(
        calorie_goal, 
        protein_goal, 
        weight_goal=weight_goal, 
        weight_unit=form_weight_unit  # This will be None if not provided in the form
    )
    
    # Log the current weight if provided (now in kg)
    if current_weight is not None and current_weight > 0:
        current_user.log_weight(current_weight)
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'toast': {
                'message': 'Settings updated!',
                'category': 'success',
                'skipDisplay': True  # Tell the JavaScript not to show this toast
            },
            'redirect': url_for('settings')
        })
    
    # For non-AJAX requests, use flash and redirect
    flash('Settings updated (flash)!', 'success')
    return redirect(url_for('settings'))

@app.route('/history')
@login_required
def history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get all data for the user for charts (ascending order for proper timeline)
    c.execute("""SELECT date, total_calories, total_protein, summary, calorie_goal, protein_goal 
                 FROM daily_summary 
                 WHERE user_id = ? 
                 ORDER BY date ASC""", (current_user.id,))
    all_summaries = c.fetchall()
    
    # Get the same data but in descending order for the table display (most recent first)
    c.execute("""SELECT date, total_calories, total_protein, summary, calorie_goal, protein_goal 
                 FROM daily_summary 
                 WHERE user_id = ? 
                 ORDER BY date DESC""", (current_user.id,))
    weekly_summaries = c.fetchall()
    
    # Get all weight logs for the user
    c.execute("""SELECT date, weight FROM weight_logs 
                 WHERE user_id = ? 
                 ORDER BY date ASC""", (current_user.id,))
    weight_logs = c.fetchall()
    
    # Format data for charts (using the ascending order data)
    dates = [entry[0] for entry in all_summaries]
    calories = [entry[1] for entry in all_summaries]
    proteins = [entry[2] for entry in all_summaries]
    calorie_goals = [entry[4] for entry in all_summaries]
    protein_goals = [entry[5] for entry in all_summaries]
    
    # Format weight data
    weight_dates = [entry[0] for entry in weight_logs]
    weights = [entry[1] for entry in weight_logs]
    
    # Convert weight to user's preferred unit
    if current_user.weight_unit == 1:  # If user prefers lbs
        weights = [round(w * 2.20462, 1) for w in weights]  # Convert kg to lbs
    
    # Determine weight unit string
    weight_unit = "lbs" if current_user.weight_unit == 1 else "kg"
    
    # Get weight goal in the correct unit
    weight_goal = None
    if current_user.weight_goal is not None:
        weight_goal = current_user.weight_goal
        if current_user.weight_unit == 1:  # If user prefers lbs and goal is stored in kg
            weight_goal = round(weight_goal * 2.20462, 1)  # Convert kg to lbs
    
    conn.close()
    
    return render_template('history.html', 
                          weekly_summaries=weekly_summaries,  # This is now in descending order
                          chart_dates=dates,
                          chart_calories=calories,
                          chart_proteins=proteins,
                          chart_calorie_goals=calorie_goals,
                          chart_protein_goals=protein_goals,
                          weight_dates=weight_dates,
                          weights=weights,
                          weight_goal=weight_goal,
                          weight_unit=weight_unit)

@app.route('/update_weight_unit', methods=['POST'])
@login_required
def update_weight_unit():
    try:
        weight_unit = int(request.form.get('weight_unit', 0))  # Default to kg (0)
        
        # Update only the weight unit preference
        current_user.update_goals(
            current_user.calorie_goal, 
            current_user.protein_goal, 
            weight_goal=None,  # Don't change the weight goal
            weight_unit=weight_unit
        )
        
        return jsonify({
            'success': True,
            'message': 'Weight unit preference updated successfully!'
        })
    except Exception as e:
        app.logger.error(f"Error updating weight unit: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to update weight unit preference.'
        }), 400

# TODO
@app.after_request
def add_header(response):
    # Add headers to prevent caching of dynamic content
    if request.path.startswith('/dashboard') or request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

def get_db_connection():
    """Get a database connection - uses test connection if available"""
    # Check if we're in a test environment with a pre-configured connection
    if current_app.config.get('TESTING') and 'DB_CONNECTION' in current_app.config:
        return current_app.config['DB_CONNECTION']
        
    # Normal database connection logic for production/development
    conn = sqlite3.connect(current_app.config['DB_PATH'])
    conn.row_factory = sqlite3.Row
    return conn

# ==================== POKER ROUTES ====================

def next_occupied_seat(current_pos, cursor, session_id):
    """Find the next occupied, non-sitting-out seat clockwise from current_pos."""
    cursor.execute("""SELECT seat_number FROM poker_session_players
                      WHERE session_id = ? AND is_sitting_out = 0
                      ORDER BY seat_number""", (session_id,))
    occupied = [row[0] for row in cursor.fetchall()]
    if not occupied:
        return (current_pos % 9) + 1
    # Find the first occupied seat after current_pos (wrapping around)
    for seat in occupied:
        if seat > current_pos:
            return seat
    return occupied[0]  # Wrap around to lowest seat


def _archive_appearance(c, session_id, seat_number, player_id, display_name,
                        hands, vpip, pfr, joined_at, left_at, roll_up=True):
    """Record a completed seat occupancy (a "stint") into the permanent
    appearances archive, and optionally roll its stats into the player's
    lifetime totals. Each stint is archived exactly once, so rolling up here
    keeps lifetime stats correct even when a player leaves mid-session."""
    c.execute("""INSERT INTO poker_session_appearances
                 (session_id, seat_number, player_id, player_display_name,
                  session_hands, session_vpip, session_pfr, joined_at, left_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (session_id, seat_number, player_id, display_name,
               hands, vpip, pfr, joined_at, left_at))
    if roll_up and player_id is not None:
        c.execute("""UPDATE poker_players
                     SET total_hands = total_hands + ?,
                         total_vpip = total_vpip + ?,
                         total_pfr = total_pfr + ?,
                         last_played = ?
                     WHERE id = ?""",
                  (hands, vpip, pfr, get_local_date().isoformat(), player_id))


@app.route('/poker')
@login_required
def poker():
    """Main poker page - load active session or show start session screen"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check for active session
    c.execute("""SELECT id, button_position, hand_count, created_at 
                 FROM poker_sessions 
                 WHERE user_id = ? AND is_active = 1 
                 ORDER BY created_at DESC LIMIT 1""", 
              (current_user.id,))
    session = c.fetchone()
    
    session_data = None
    if session:
        session_id, button_pos, hand_count, created_at = session

        # Get all players in this session
        c.execute("""SELECT psp.id, psp.seat_number, psp.player_display_name,
                            psp.session_hands, psp.session_vpip, psp.session_pfr,
                            psp.is_sitting_out, psp.player_id,
                            pp.total_hands, pp.total_vpip, pp.total_pfr, pp.is_hero
                     FROM poker_session_players psp
                     LEFT JOIN poker_players pp ON psp.player_id = pp.id
                     WHERE psp.session_id = ?
                     ORDER BY psp.seat_number""",
                  (session_id,))
        players_raw = c.fetchall()
        players = []
        for p in players_raw:
            players.append({
                'id': p[0],
                'seat_number': p[1],
                'name': p[2],
                'session_hands': p[3],
                'session_vpip': p[4],
                'session_pfr': p[5],
                'sitting_out': p[6] == 1,
                'player_id': p[7],
                'total_hands': p[8],
                'total_vpip': p[9],
                'total_pfr': p[10],
                'is_hero': p[11] == 1
            })

        # Check for active hand
        c.execute("""SELECT id, hand_number, button_position, has_btn_straddle,
                            has_utg_straddle, actions
                     FROM poker_hand_tracking
                     WHERE session_id = ?
                     ORDER BY created_at DESC LIMIT 1""",
                  (session_id,))
        hand_raw = c.fetchone()
        active_hand = None
        if hand_raw:
            import json as _json
            actions = _json.loads(hand_raw[5]) if hand_raw[5] else []
            active_hand = {
                'id': hand_raw[0],
                'hand_number': hand_raw[1],
                'button_position': hand_raw[2],
                'has_btn_straddle': hand_raw[3] == 1,
                'has_utg_straddle': hand_raw[4] == 1,
                'actions': actions
            }

        # The user's own "hero" player name, if they've designated one before
        c.execute("""SELECT player_name FROM poker_players
                     WHERE user_id = ? AND is_hero = 1 LIMIT 1""", (current_user.id,))
        hero_row = c.fetchone()

        session_data = {
            'session_id': session_id,
            'button_position': button_pos,
            'hand_count': hand_count,
            'created_at': created_at,
            'players': players,
            'active_hand': active_hand,
            'hero_name': hero_row[0] if hero_row else ''
        }

    conn.close()

    return render_template('poker.html', session=session_data)

@app.route('/poker/start_session', methods=['POST'])
@login_required
def start_poker_session():
    """Initialize a new poker session"""
    button_position = request.form.get('button_position', type=int)
    
    if not button_position or button_position < 1 or button_position > 9:
        return jsonify({
            'success': False,
            'toast': {'message': 'Invalid button position', 'category': 'error'}
        })
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # End any existing active sessions (safety check)
    c.execute("""UPDATE poker_sessions SET is_active = 0, ended_at = ? 
                 WHERE user_id = ? AND is_active = 1""", 
              (datetime.now().isoformat(), current_user.id))
    
    # Create new session
    now = datetime.now().isoformat()
    c.execute("""INSERT INTO poker_sessions 
                 (user_id, session_date, is_active, button_position, hand_count, created_at)
                 VALUES (?, ?, 1, ?, 0, ?)""", 
              (current_user.id, get_local_date().isoformat(), button_position, now))
    session_id = c.lastrowid
    
    # Pre-populate all 9 seats with placeholder players
    # Using generic placeholder names that make it clear they need to be updated
    placeholder_names = [
        "Player 1", "Player 2", "Player 3", "Player 4", "Player 5",
        "Player 6", "Player 7", "Player 8", "Player 9"
    ]
    
    for seat_num in range(1, 10):
        c.execute("""INSERT INTO poker_session_players
                     (session_id, player_id, seat_number, player_display_name,
                      session_hands, session_vpip, session_pfr, is_sitting_out, joined_at)
                     VALUES (?, NULL, ?, ?, 0, 0, 0, 0, ?)""",
                  (session_id, seat_num, placeholder_names[seat_num - 1], now))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'toast': {'message': 'Session started! Remove empty seats or update player names.', 'category': 'success'}
    })

@app.route('/poker/end_session', methods=['POST'])
@login_required
def end_poker_session():
    """End current session and update cumulative stats"""
    session_id = request.form.get('session_id', type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Verify session belongs to user
    c.execute("SELECT id FROM poker_sessions WHERE id = ? AND user_id = ?", 
              (session_id, current_user.id))
    if not c.fetchone():
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Session not found', 'category': 'error'}
        })
    
    # Archive every current occupant who played hands (preserving their stint
    # in history) and roll their stats into lifetime totals if they're tracked.
    # Players who already left mid-session were archived + rolled up at that
    # time, so they're no longer here — no double counting.
    now = datetime.now().isoformat()
    c.execute("""SELECT seat_number, player_id, player_display_name,
                        session_hands, session_vpip, session_pfr, joined_at
                 FROM poker_session_players
                 WHERE session_id = ?""",
              (session_id,))
    for seat_number, player_id, display_name, hands, vpip, pfr, joined_at in c.fetchall():
        if hands and hands > 0:
            _archive_appearance(c, session_id, seat_number, player_id,
                                display_name, hands, vpip, pfr,
                                joined_at, now, roll_up=True)

    # Mark session as ended
    c.execute("""UPDATE poker_sessions
                 SET is_active = 0, ended_at = ?
                 WHERE id = ?""",
              (now, session_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'toast': {'message': 'Session ended. Stats saved!', 'category': 'success'}
    })

@app.route('/poker/session_state')
@login_required
def poker_session_state():
    """Get current session state"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get active session
    c.execute("""SELECT id, button_position, hand_count, created_at 
                 FROM poker_sessions 
                 WHERE user_id = ? AND is_active = 1 
                 ORDER BY created_at DESC LIMIT 1""", 
              (current_user.id,))
    session = c.fetchone()
    
    if not session:
        conn.close()
        return jsonify({'success': False, 'message': 'No active session'})
    
    session_id, button_pos, hand_count, created_at = session
    
    # Get all players
    c.execute("""SELECT psp.id, psp.seat_number, psp.player_display_name,
                        psp.session_hands, psp.session_vpip, psp.session_pfr,
                        psp.is_sitting_out, psp.player_id,
                        pp.total_hands, pp.total_vpip, pp.total_pfr, pp.is_hero
                 FROM poker_session_players psp
                 LEFT JOIN poker_players pp ON psp.player_id = pp.id
                 WHERE psp.session_id = ?
                 ORDER BY psp.seat_number""",
              (session_id,))
    players_raw = c.fetchall()

    players = []
    for p in players_raw:
        players.append({
            'id': p[0],
            'seat_number': p[1],
            'name': p[2],
            'session_hands': p[3],
            'session_vpip': p[4],
            'session_pfr': p[5],
            'sitting_out': p[6] == 1,
            'player_id': p[7],
            'total_hands': p[8],
            'total_vpip': p[9],
            'total_pfr': p[10],
            'is_hero': p[11] == 1
        })
    
    # Check for active hand
    c.execute("""SELECT id, hand_number, button_position, has_btn_straddle, 
                        has_utg_straddle, actions
                 FROM poker_hand_tracking 
                 WHERE session_id = ? 
                 ORDER BY created_at DESC LIMIT 1""", 
              (session_id,))
    hand_raw = c.fetchone()
    
    active_hand = None
    if hand_raw:
        import json
        actions = json.loads(hand_raw[5]) if hand_raw[5] else []
        active_hand = {
            'id': hand_raw[0],
            'hand_number': hand_raw[1],
            'button_position': hand_raw[2],
            'has_btn_straddle': hand_raw[3] == 1,
            'has_utg_straddle': hand_raw[4] == 1,
            'actions': actions
        }
    
    conn.close()
    
    return jsonify({
        'success': True,
        'session': {
            'id': session_id,
            'button_position': button_pos,
            'hand_count': hand_count,
            'created_at': created_at
        },
        'players': players,
        'active_hand': active_hand
    })

@app.route('/poker/add_player', methods=['POST'])
@login_required
def add_poker_player():
    """Add player to a seat"""
    session_id = request.form.get('session_id', type=int)
    seat_number = request.form.get('seat_number', type=int)
    player_name = request.form.get('player_name', '').strip()
    player_id = request.form.get('player_id', type=int)  # Optional: existing player
    
    if not session_id or not seat_number or seat_number < 1 or seat_number > 9:
        return jsonify({
            'success': False,
            'toast': {'message': 'Invalid request', 'category': 'error'}
        })
    
    if not player_name and not player_id:
        player_name = f"Player {seat_number}"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Verify session belongs to user
    c.execute("SELECT id FROM poker_sessions WHERE id = ? AND user_id = ? AND is_active = 1", 
              (session_id, current_user.id))
    if not c.fetchone():
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Session not found', 'category': 'error'}
        })
    
    # Check if seat is occupied
    c.execute("SELECT id FROM poker_session_players WHERE session_id = ? AND seat_number = ?", 
              (session_id, seat_number))
    if c.fetchone():
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Seat already occupied', 'category': 'error'}
        })
    
    # If player_id provided, get their name
    if player_id:
        c.execute("SELECT player_name FROM poker_players WHERE id = ? AND user_id = ?", 
                  (player_id, current_user.id))
        result = c.fetchone()
        if result:
            player_name = result[0]
        else:
            player_id = None
    
    # Add player to session
    c.execute("""INSERT INTO poker_session_players
                 (session_id, player_id, seat_number, player_display_name,
                  session_hands, session_vpip, session_pfr, is_sitting_out, joined_at)
                 VALUES (?, ?, ?, ?, 0, 0, 0, 0, ?)""",
              (session_id, player_id, seat_number, player_name, datetime.now().isoformat()))
    
    session_player_id = c.lastrowid
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'session_player_id': session_player_id,
        'toast': {'message': f'{player_name} added to seat {seat_number}', 'category': 'success'}
    })

@app.route('/poker/remove_player', methods=['POST'])
@login_required
def remove_poker_player():
    """Remove player from seat"""
    session_id = request.form.get('session_id', type=int)
    seat_number = request.form.get('seat_number', type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Verify session belongs to user
    c.execute("SELECT id FROM poker_sessions WHERE id = ? AND user_id = ? AND is_active = 1", 
              (session_id, current_user.id))
    if not c.fetchone():
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Session not found', 'category': 'error'}
        })
    
    # Look at the current occupant: if they've played hands this session,
    # preserve their stint in the appearances archive (and roll up lifetime
    # stats if they're a tracked player) before clearing the seat.
    c.execute("""SELECT player_id, player_display_name, session_hands,
                        session_vpip, session_pfr, joined_at
                 FROM poker_session_players
                 WHERE session_id = ? AND seat_number = ?""",
              (session_id, seat_number))
    occupant = c.fetchone()

    archived = False
    if occupant:
        player_id, display_name, hands, vpip, pfr, joined_at = occupant
        if hands and hands > 0:
            _archive_appearance(c, session_id, seat_number, player_id,
                                display_name, hands, vpip, pfr,
                                joined_at, datetime.now().isoformat(),
                                roll_up=True)
            archived = True

    c.execute("""DELETE FROM poker_session_players
                 WHERE session_id = ? AND seat_number = ?""",
              (session_id, seat_number))

    conn.commit()
    conn.close()

    message = 'Player left — stats saved to history' if archived else 'Player removed'
    return jsonify({
        'success': True,
        'toast': {'message': message, 'category': 'success'}
    })

@app.route('/poker/switch_seats', methods=['POST'])
@login_required
def switch_poker_seats():
    """Move player to different seat"""
    session_id = request.form.get('session_id', type=int)
    from_seat = request.form.get('from_seat', type=int)
    to_seat = request.form.get('to_seat', type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Verify session
    c.execute("SELECT id FROM poker_sessions WHERE id = ? AND user_id = ? AND is_active = 1", 
              (session_id, current_user.id))
    if not c.fetchone():
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Session not found', 'category': 'error'}
        })
    
    # Check destination is empty
    c.execute("SELECT id FROM poker_session_players WHERE session_id = ? AND seat_number = ?", 
              (session_id, to_seat))
    if c.fetchone():
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Destination seat occupied', 'category': 'error'}
        })
    
    # Move player
    c.execute("""UPDATE poker_session_players 
                 SET seat_number = ? 
                 WHERE session_id = ? AND seat_number = ?""", 
              (to_seat, session_id, from_seat))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'toast': {'message': f'Player moved to seat {to_seat}', 'category': 'success'}
    })

@app.route('/poker/name_player', methods=['POST'])
@login_required
def name_poker_player():
    """Save player name and notes to database"""
    session_id = request.form.get('session_id', type=int)
    seat_number = request.form.get('seat_number', type=int)
    player_name = request.form.get('player_name', '').strip()
    player_notes = request.form.get('player_notes', '').strip()
    is_hero = request.form.get('is_hero', type=int, default=0)

    if not player_name:
        return jsonify({
            'success': False,
            'toast': {'message': 'Player name required', 'category': 'error'}
        })
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get session player
    c.execute("""SELECT id, player_id, session_hands, session_vpip, session_pfr
                 FROM poker_session_players 
                 WHERE session_id = ? AND seat_number = ?""", 
              (session_id, seat_number))
    session_player = c.fetchone()
    
    if not session_player:
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Player not found', 'category': 'error'}
        })
    
    session_player_id, existing_player_id, session_hands, session_vpip, session_pfr = session_player
    
    # Check if player already exists in database with this name
    c.execute("""SELECT id FROM poker_players 
                 WHERE user_id = ? AND player_name = ?""", 
              (current_user.id, player_name))
    existing = c.fetchone()
    
    name_taken = existing and existing[0] != existing_player_id

    if name_taken and not is_hero:
        # Different player with same name exists (blocked for villains to avoid
        # accidental duplicates; allowed for the hero so you can re-seat yourself).
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'A player with this name already exists', 'category': 'error'}
        })

    if name_taken and is_hero:
        # Re-seat your existing identity: link this seat to the existing player.
        player_id = existing[0]
        if player_notes:
            c.execute("UPDATE poker_players SET player_notes = ? WHERE id = ?",
                      (player_notes, player_id))
        c.execute("""UPDATE poker_session_players
                     SET player_id = ?, player_display_name = ?
                     WHERE id = ?""",
                  (player_id, player_name, session_player_id))
    elif existing_player_id:
        # Update existing player
        c.execute("""UPDATE poker_players
                     SET player_name = ?, player_notes = ?
                     WHERE id = ?""",
                  (player_name, player_notes, existing_player_id))
        player_id = existing_player_id

        # Also update display name in session
        c.execute("""UPDATE poker_session_players
                     SET player_display_name = ?
                     WHERE id = ?""",
                  (player_name, session_player_id))
    else:
        # Create new player record
        now = datetime.now().isoformat()
        c.execute("""INSERT INTO poker_players 
                     (user_id, player_name, player_notes, total_hands, 
                      total_vpip, total_pfr, created_at)
                     VALUES (?, ?, ?, 0, 0, 0, ?)""", 
                  (current_user.id, player_name, player_notes, now))
        player_id = c.lastrowid
        
        # Link to session player
        c.execute("""UPDATE poker_session_players
                     SET player_id = ?, player_display_name = ?
                     WHERE id = ?""",
                  (player_id, player_name, session_player_id))

    # Hero designation: at most one "this is me" player per user.
    if is_hero:
        c.execute("UPDATE poker_players SET is_hero = 0 WHERE user_id = ? AND id != ?",
                  (current_user.id, player_id))
        c.execute("UPDATE poker_players SET is_hero = 1 WHERE id = ?", (player_id,))

    conn.commit()
    conn.close()

    message = "That's you — saved" if is_hero else f'Player "{player_name}" saved'
    return jsonify({
        'success': True,
        'player_id': player_id,
        'toast': {'message': message, 'category': 'success'}
    })

@app.route('/poker/toggle_sitting_out', methods=['POST'])
@login_required
def toggle_sitting_out():
    """Mark player as sitting out or back in"""
    session_id = request.form.get('session_id', type=int)
    seat_number = request.form.get('seat_number', type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get current state
    c.execute("""SELECT is_sitting_out FROM poker_session_players 
                 WHERE session_id = ? AND seat_number = ?""", 
              (session_id, seat_number))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Player not found', 'category': 'error'}
        })
    
    new_state = 0 if result[0] == 1 else 1
    
    c.execute("""UPDATE poker_session_players 
                 SET is_sitting_out = ? 
                 WHERE session_id = ? AND seat_number = ?""", 
              (new_state, session_id, seat_number))
    
    conn.commit()
    conn.close()
    
    status_text = "sitting out" if new_state == 1 else "back in"
    
    return jsonify({
        'success': True,
        'is_sitting_out': new_state == 1,
        'toast': {'message': f'Player marked {status_text}', 'category': 'success'}
    })

@app.route('/poker/search_players')
@login_required
def search_poker_players():
    """Search existing players for quick add"""
    query = request.args.get('q', '').strip()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""SELECT id, player_name, total_hands, total_vpip, total_pfr, last_played
                 FROM poker_players 
                 WHERE user_id = ? AND player_name LIKE ?
                 ORDER BY last_played DESC, player_name
                 LIMIT 20""", 
              (current_user.id, f'%{query}%'))
    
    players = []
    for row in c.fetchall():
        vpip_pct = (row[3] / row[2] * 100) if row[2] > 0 else 0
        pfr_pct = (row[4] / row[2] * 100) if row[2] > 0 else 0
        players.append({
            'id': row[0],
            'name': row[1],
            'total_hands': row[2],
            'vpip': round(vpip_pct, 1),
            'pfr': round(pfr_pct, 1),
            'last_played': row[5]
        })
    
    conn.close()
    
    return jsonify({'success': True, 'players': players})

@app.route('/poker/start_hand', methods=['POST'])
@login_required
def start_poker_hand():
    """Initialize new hand tracking"""
    import json
    
    session_id = request.form.get('session_id', type=int)
    has_btn_straddle = request.form.get('has_btn_straddle', type=int, default=0)
    has_utg_straddle = request.form.get('has_utg_straddle', type=int, default=0)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get session
    c.execute("""SELECT button_position, hand_count FROM poker_sessions 
                 WHERE id = ? AND user_id = ? AND is_active = 1""", 
              (session_id, current_user.id))
    session = c.fetchone()
    
    if not session:
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Session not found', 'category': 'error'}
        })
    
    button_pos, hand_count = session
    
    # Count active players (not sitting out)
    c.execute("""SELECT COUNT(*) FROM poker_session_players 
                 WHERE session_id = ? AND is_sitting_out = 0""", 
              (session_id,))
    active_count = c.fetchone()[0]
    
    if active_count < 2:
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Need at least 2 active players', 'category': 'error'}
        })
    
    # Delete any existing incomplete hands
    c.execute("DELETE FROM poker_hand_tracking WHERE session_id = ?", (session_id,))
    
    # Create new hand
    now = datetime.now().isoformat()
    new_hand_number = hand_count + 1
    
    c.execute("""INSERT INTO poker_hand_tracking 
                 (session_id, hand_number, button_position, has_btn_straddle, 
                  has_utg_straddle, actions, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""", 
              (session_id, new_hand_number, button_pos, has_btn_straddle, 
               has_utg_straddle, json.dumps([]), now))
    
    hand_id = c.lastrowid
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'hand_id': hand_id,
        'hand_number': new_hand_number,
        'toast': {'message': f'Hand #{new_hand_number} started', 'category': 'success'}
    })

@app.route('/poker/record_action', methods=['POST'])
@login_required
def record_poker_action():
    """Record player action (fold/call/raise/skip)"""
    import json
    
    session_id = request.form.get('session_id', type=int)
    seat_number = request.form.get('seat_number', type=int)
    action = request.form.get('action', '').lower()  # fold, call, raise, skip
    
    if action not in ['fold', 'call', 'raise', 'skip', 'check']:
        return jsonify({
            'success': False,
            'toast': {'message': 'Invalid action', 'category': 'error'}
        })
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get active hand
    c.execute("""SELECT id, actions FROM poker_hand_tracking 
                 WHERE session_id = ? 
                 ORDER BY created_at DESC LIMIT 1""", 
              (session_id,))
    hand = c.fetchone()
    
    if not hand:
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'No active hand', 'category': 'error'}
        })
    
    hand_id, actions_json = hand
    actions = json.loads(actions_json) if actions_json else []
    
    # Add new action
    actions.append({
        'seat': seat_number,
        'action': action,
        'timestamp': datetime.now().isoformat()
    })
    
    # Update hand tracking
    c.execute("""UPDATE poker_hand_tracking 
                 SET actions = ? 
                 WHERE id = ?""", 
              (json.dumps(actions), hand_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'action_count': len(actions)
    })

@app.route('/poker/complete_hand', methods=['POST'])
@login_required
def complete_poker_hand():
    """Finalize hand and update statistics"""
    import json
    
    session_id = request.form.get('session_id', type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get active hand
    c.execute("""SELECT id, actions, button_position, hand_number,
                        has_btn_straddle, has_utg_straddle
                 FROM poker_hand_tracking
                 WHERE session_id = ?
                 ORDER BY created_at DESC LIMIT 1""",
              (session_id,))
    hand = c.fetchone()

    if not hand:
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'No active hand', 'category': 'error'}
        })

    hand_id, actions_json, button_position, hand_number, has_btn_straddle, has_utg_straddle = hand
    actions = json.loads(actions_json) if actions_json else []

    # Get all active players (seat -> session_player_id and seat -> player_id)
    c.execute("""SELECT seat_number, id, player_id FROM poker_session_players
                 WHERE session_id = ? AND is_sitting_out = 0""",
              (session_id,))
    active_players = {}
    seat_player_id = {}
    for seat_n, sp_id, p_id in c.fetchall():
        active_players[seat_n] = sp_id
        seat_player_id[seat_n] = p_id
    
    # Calculate VPIP and PFR for each player
    player_stats = {}
    for seat in active_players:
        player_stats[seat] = {'vpip': False, 'pfr': False, 'participated': False}
    
    # Check if any raise happened
    has_raise = any(a['action'] == 'raise' for a in actions)
    
    for action in actions:
        seat = action['seat']
        action_type = action['action']
        
        if seat in player_stats and action_type != 'skip':
            player_stats[seat]['participated'] = True
            
            if action_type in ['call', 'raise']:
                player_stats[seat]['vpip'] = True
            
            if action_type == 'raise':
                player_stats[seat]['pfr'] = True
    
    # Update player statistics for ALL active players (they were all dealt in)
    for seat, session_player_id in active_players.items():
        stats = player_stats[seat]
        vpip_inc = 1 if stats['vpip'] else 0
        pfr_inc = 1 if stats['pfr'] else 0

        c.execute("""UPDATE poker_session_players
                     SET session_hands = session_hands + 1,
                         session_vpip = session_vpip + ?,
                         session_pfr = session_pfr + ?
                     WHERE id = ?""",
                  (vpip_inc, pfr_inc, session_player_id))
    
    # Move button position (clockwise, skip empty/sitting-out seats)
    new_button = next_occupied_seat(button_position, c, session_id)

    # Update session
    c.execute("""UPDATE poker_sessions
                 SET button_position = ?, hand_count = hand_count + 1
                 WHERE id = ?""",
              (new_button, session_id))
    
    # Get updated hand count
    c.execute("SELECT hand_count FROM poker_sessions WHERE id = ?", (session_id,))
    hand_count = c.fetchone()[0]

    # Persist the raw hand permanently so any preflop stat can be derived later.
    # Attribute every dealt-in seat and every action to its player_id.
    dealt_in = [{'seat': s, 'player_id': seat_player_id.get(s)}
                for s in sorted(active_players)]
    enriched_actions = [{'seat': a['seat'],
                         'player_id': seat_player_id.get(a['seat']),
                         'action': a['action']}
                        for a in actions]
    c.execute("""INSERT INTO poker_hands
                 (session_id, hand_number, button_position, has_btn_straddle,
                  has_utg_straddle, dealt_in, actions, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (session_id, hand_number, button_position, has_btn_straddle,
               has_utg_straddle, json.dumps(dealt_in), json.dumps(enriched_actions),
               datetime.now().isoformat()))

    # Delete the temporary in-progress hand record
    c.execute("DELETE FROM poker_hand_tracking WHERE id = ?", (hand_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'new_button_position': new_button,
        'hand_count': hand_count,
        'toast': {'message': 'Hand completed', 'category': 'success'}
    })

@app.route('/poker/skip_hand', methods=['POST'])
@login_required
def skip_poker_hand():
    """Skip hand - moves button, no stats recorded"""
    session_id = request.form.get('session_id', type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get current button position
    c.execute("""SELECT button_position FROM poker_sessions 
                 WHERE id = ? AND user_id = ? AND is_active = 1""", 
              (session_id, current_user.id))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'Session not found', 'category': 'error'}
        })
    
    button_position = result[0]
    new_button = next_occupied_seat(button_position, c, session_id)

    # Update button position
    c.execute("""UPDATE poker_sessions
                 SET button_position = ?
                 WHERE id = ?""",
              (new_button, session_id))
    
    # Delete any active hand
    c.execute("DELETE FROM poker_hand_tracking WHERE session_id = ?", (session_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'new_button_position': new_button,
        'toast': {'message': 'Hand skipped', 'category': 'success'}
    })

@app.route('/poker/undo_action', methods=['POST'])
@login_required
def undo_poker_action():
    """Undo last action in current hand"""
    import json
    
    session_id = request.form.get('session_id', type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get active hand
    c.execute("""SELECT id, actions FROM poker_hand_tracking 
                 WHERE session_id = ? 
                 ORDER BY created_at DESC LIMIT 1""", 
              (session_id,))
    hand = c.fetchone()
    
    if not hand:
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'No active hand', 'category': 'error'}
        })
    
    hand_id, actions_json = hand
    actions = json.loads(actions_json) if actions_json else []
    
    if not actions:
        conn.close()
        return jsonify({
            'success': False,
            'toast': {'message': 'No actions to undo', 'category': 'error'}
        })
    
    # Remove last action
    undone_action = actions.pop()
    
    # Update hand
    c.execute("""UPDATE poker_hand_tracking 
                 SET actions = ? 
                 WHERE id = ?""", 
              (json.dumps(actions), hand_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'undone_action': undone_action,
        'toast': {'message': 'Action undone', 'category': 'success'}
    })

def _format_duration(start_iso, end_iso):
    """Return a human duration like '2h 14m' between two ISO timestamps."""
    if not start_iso or not end_iso:
        return None
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
    except (ValueError, TypeError):
        return None
    total_minutes = int((end - start).total_seconds() // 60)
    if total_minutes < 0:
        return None
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _pct(numerator, denominator):
    return round((numerator / denominator) * 100) if denominator else 0


def _compute_preflop_reads(c, player_id, user_id):
    """Derive preflop read stats for a player from the raw poker_hands archive.
    Replays each recorded hand the player was dealt into. Because the raw hands
    are stored permanently, any new stat can be added here without a migration."""
    import json as _json
    c.execute("""SELECT h.dealt_in, h.actions
                 FROM poker_hands h
                 JOIN poker_sessions ps ON h.session_id = ps.id
                 WHERE ps.user_id = ?""", (user_id,))

    hands = vpip = pfr = limp = limp_call = limp_rr = 0
    three_bet = three_bet_opp = 0
    for dealt_in_json, actions_json in c.fetchall():
        dealt_in = _json.loads(dealt_in_json) if dealt_in_json else []
        if not any(d.get('player_id') == player_id for d in dealt_in):
            continue
        hands += 1

        acts = _json.loads(actions_json) if actions_json else []
        raise_count = 0     # number of raises so far this hand (any player)
        limped = v = p = lc = lr = False
        tb = tb_opp = False
        for a in acts:
            is_me = a.get('player_id') == player_id
            act = a.get('action')
            if is_me and act != 'skip':
                if act in ('call', 'raise'):
                    v = True
                # A 3-bet spot = acting while facing exactly one prior raise (the open)
                if raise_count == 1:
                    tb_opp = True
                    if act == 'raise':
                        tb = True
                if act == 'raise':
                    p = True
                    if limped:
                        lr = True          # limped, then re-raised
                elif act == 'call':
                    if raise_count == 0 and not limped:
                        limped = True      # first voluntary money in is a call = limp
                    elif raise_count > 0 and limped:
                        lc = True          # limped, then called a raise
            if act == 'raise':
                raise_count += 1
        vpip += 1 if v else 0
        pfr += 1 if p else 0
        limp += 1 if limped else 0
        limp_call += 1 if lc else 0
        limp_rr += 1 if lr else 0
        three_bet += 1 if tb else 0
        three_bet_opp += 1 if tb_opp else 0

    return {
        'hands': hands,
        'vpip': _pct(vpip, hands),
        'pfr': _pct(pfr, hands),
        'limp': _pct(limp, hands),
        'limp_ct': limp,
        'limp_call_ct': limp_call,
        'limp_rr_ct': limp_rr,
        'limp_call_pct': _pct(limp_call, limp),
        'limp_rr_pct': _pct(limp_rr, limp),
        'three_bet_ct': three_bet,
        'three_bet_opp': three_bet_opp,
        'three_bet_pct': _pct(three_bet, three_bet_opp),
    }


@app.route('/poker/history')
@login_required
def poker_history():
    """History page: past sessions + tracked-player directory."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ended sessions, newest first
    c.execute("""SELECT id, session_date, created_at, ended_at, hand_count
                 FROM poker_sessions
                 WHERE user_id = ? AND is_active = 0
                 ORDER BY created_at DESC""",
              (current_user.id,))
    sessions = []
    for sid, sdate, created_at, ended_at, hand_count in c.fetchall():
        c.execute("""SELECT COUNT(*) FROM poker_session_appearances
                     WHERE session_id = ? AND player_id IS NOT NULL""", (sid,))
        named_count = c.fetchone()[0]
        sessions.append({
            'id': sid,
            'date': sdate,
            'hand_count': hand_count,
            'named_count': named_count,
            'duration': _format_duration(created_at, ended_at)
        })

    # Tracked players directory
    c.execute("""SELECT id, player_name, player_notes, total_hands,
                        total_vpip, total_pfr, last_played, is_hero
                 FROM poker_players
                 WHERE user_id = ?
                 ORDER BY is_hero DESC, last_played DESC, player_name""",
              (current_user.id,))
    players = []
    for row in c.fetchall():
        players.append({
            'id': row[0],
            'name': row[1],
            'notes': row[2] or '',
            'total_hands': row[3],
            'vpip': _pct(row[4], row[3]),
            'pfr': _pct(row[5], row[3]),
            'last_played': row[6],
            'is_hero': row[7] == 1
        })

    conn.close()
    return render_template('poker_history.html', sessions=sessions, players=players)


@app.route('/poker/session_detail/<int:session_id>')
@login_required
def poker_session_detail(session_id):
    """Per-seat stats for one past session."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""SELECT id, session_date, hand_count FROM poker_sessions
                 WHERE id = ? AND user_id = ?""", (session_id, current_user.id))
    session_row = c.fetchone()
    if not session_row:
        conn.close()
        return jsonify({'success': False, 'toast': {'message': 'Session not found', 'category': 'error'}}), 404

    c.execute("""SELECT seat_number, player_display_name, player_id,
                        session_hands, session_vpip, session_pfr, joined_at, left_at
                 FROM poker_session_appearances
                 WHERE session_id = ?
                 ORDER BY seat_number, id""", (session_id,))
    players = []
    for seat, name, player_id, hands, vpip, pfr, joined_at, left_at in c.fetchall():
        players.append({
            'seat': seat,
            'name': name,
            'player_id': player_id,
            'is_named': player_id is not None,
            'hands': hands,
            'vpip': _pct(vpip, hands),
            'pfr': _pct(pfr, hands),
            'duration': _format_duration(joined_at, left_at)
        })

    conn.close()
    return jsonify({
        'success': True,
        'session': {'id': session_row[0], 'date': session_row[1], 'hand_count': session_row[2]},
        'players': players
    })


@app.route('/poker/player_detail/<int:player_id>')
@login_required
def poker_player_detail(player_id):
    """Lifetime stats, notes, and session appearances for one player."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""SELECT player_name, player_notes, total_hands,
                        total_vpip, total_pfr, last_played
                 FROM poker_players
                 WHERE id = ? AND user_id = ?""", (player_id, current_user.id))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'toast': {'message': 'Player not found', 'category': 'error'}}), 404

    c.execute("""SELECT ps.session_date, a.session_hands, a.session_vpip, a.session_pfr,
                        a.joined_at, a.left_at
                 FROM poker_session_appearances a
                 JOIN poker_sessions ps ON a.session_id = ps.id
                 WHERE a.player_id = ? AND ps.user_id = ?
                 ORDER BY ps.created_at DESC""", (player_id, current_user.id))
    appearances = []
    for sdate, hands, vpip, pfr, joined_at, left_at in c.fetchall():
        appearances.append({
            'date': sdate,
            'hands': hands,
            'vpip': _pct(vpip, hands),
            'pfr': _pct(pfr, hands),
            'duration': _format_duration(joined_at, left_at)
        })

    preflop = _compute_preflop_reads(c, player_id, current_user.id)

    conn.close()
    return jsonify({
        'success': True,
        'player': {
            'id': player_id,
            'name': row[0],
            'notes': row[1] or '',
            'total_hands': row[2],
            'vpip': _pct(row[3], row[2]),
            'pfr': _pct(row[4], row[2]),
            'last_played': row[5]
        },
        'appearances': appearances,
        'preflop': preflop
    })


@app.route('/poker/update_player_notes', methods=['POST'])
@login_required
def update_poker_player_notes():
    """Update notes for a tracked player (by player_id)."""
    player_id = request.form.get('player_id', type=int)
    notes = request.form.get('notes', '').strip()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT id FROM poker_players WHERE id = ? AND user_id = ?",
              (player_id, current_user.id))
    if not c.fetchone():
        conn.close()
        return jsonify({'success': False, 'toast': {'message': 'Player not found', 'category': 'error'}}), 404

    c.execute("UPDATE poker_players SET player_notes = ? WHERE id = ?", (notes, player_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'toast': {'message': 'Notes saved', 'category': 'success'}})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5009)

