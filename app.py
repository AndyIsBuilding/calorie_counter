from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify, get_flashed_messages, current_app
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import pytz
import csv
import io
import os
from typing import NamedTuple

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # Change this to a random secret key
app.config['TIMEZONE'] = os.getenv('TIMEZONE') 
app.config['TESTING'] = False  # Default to False, will be set to True in test environment


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
            login_user(user_obj)
            
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
                    'category': 'success'
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
    
    # Handle weight goal conversion based on whether the weight unit is being updated
    # or based on the current user's weight unit preference
    if weight_goal is not None:
        # If weight_unit is provided in the form (e.g., from a test or API call),
        # use it to determine the conversion
        form_weight_unit = request.form.get('weight_unit', type=int)
        
        # If form_weight_unit is provided and it's pounds (1), convert from pounds to kg
        if form_weight_unit is not None and form_weight_unit == 1:
            # Convert from lbs to kg for storage
            weight_goal = weight_goal / 2.20462
        # If no weight_unit in the form, use the current user's preference
        elif form_weight_unit is None and current_user.weight_unit == 1:
            # In the UI, the JavaScript already converts to kg, but for API calls
            # or tests that don't use the UI, we need to convert here
            # Check if this is an AJAX request from the UI
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # From UI, already converted in JavaScript
                pass
            else:
                # Direct API call or test, convert from lbs to kg
                weight_goal = weight_goal / 2.20462

    # Convert current weight if provided
    if current_weight is not None and current_weight > 0:
        # Similar logic for current_weight
        form_weight_unit = request.form.get('weight_unit', type=int)
        
        if form_weight_unit is not None and form_weight_unit == 1:
            # Convert from lbs to kg for storage
            current_weight = current_weight / 2.20462
        elif form_weight_unit is None and current_user.weight_unit == 1:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # From UI, already converted in JavaScript
                pass
            else:
                # Direct API call or test, convert from lbs to kg
                current_weight = current_weight / 2.20462
    
    # Update the user's goals with the converted weights
    # If weight_unit is provided in the form, use it, otherwise don't change it
    form_weight_unit = request.form.get('weight_unit', type=int)
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
                'message': 'Settings updated and weight logged!',
                'category': 'success'
            },
            'redirect': url_for('settings')
        })
    
    # For non-AJAX requests, use flash and redirect
    flash('Settings updated and weight logged!', 'success')
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

    
    # Redirect to the index page to see the flashed messages
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

