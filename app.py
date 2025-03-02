from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify, get_flashed_messages
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
import pytz
import csv
import io
import os
from typing import NamedTuple

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # Change this to a random secret key
app.config['TIMEZONE'] = os.getenv('TIMEZONE') 
app.config['TESTING'] = False  # Default to False, will be set to True in test environment

# Remove global constants
# CALORIE_GOAL = 2000 
# PROTEIN_GOAL = 220 

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
        
        # Check if weight_unit column exists
        try:
            c.execute("SELECT weight_unit FROM users WHERE id = ?", (self.id,))
            # If we get here, the column exists
            c.execute("""UPDATE users SET 
                        calorie_goal = ?, 
                        protein_goal = ?, 
                        weight_goal = ?,
                        weight_unit = ? 
                        WHERE id = ?""", 
                    (calorie_goal, protein_goal, weight_goal, weight_unit, self.id))
        except sqlite3.OperationalError:
            # Column doesn't exist, just update the other fields
            c.execute("""UPDATE users SET 
                        calorie_goal = ?, 
                        protein_goal = ?, 
                        weight_goal = ?
                        WHERE id = ?""", 
                    (calorie_goal, protein_goal, weight_goal, self.id))
            
        conn.commit()
        conn.close()
        
        return True
    
    def log_weight(self, weight, date=None):
        """Log the user's weight for a specific date"""
        if date is None:
            date = get_local_date().isoformat()
            
        # Convert weight to kg for storage if user preference is lbs
        stored_weight = weight
        if self.weight_unit == 1:  # If user prefers lbs
            # Convert lbs to kg for storage (1 lb = 0.45359237 kg)
            stored_weight = weight * 0.45359237
            
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if there's already a weight log for this date
        c.execute("SELECT id FROM weight_logs WHERE date = ? AND user_id = ?", (date, self.id))
        existing_log = c.fetchone()
        
        if existing_log:
            # Update existing log
            c.execute("UPDATE weight_logs SET weight = ? WHERE id = ?", (stored_weight, existing_log[0]))
        else:
            # Insert new log
            c.execute("INSERT INTO weight_logs (date, weight, user_id) VALUES (?, ?, ?)", 
                     (date, stored_weight, self.id))
        
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
        
        conn.close()
        
        # Convert weights to user's preferred unit
        converted_logs = []
        for date, weight in logs:
            if self.weight_unit == 1:  # If user prefers lbs
                # Convert kg to lbs (1 kg = 2.20462 lbs)
                weight = round(weight * 2.20462, 1)
            converted_logs.append((date, weight))
            
        return converted_logs

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        # Check if weight_goal column exists in the result
        weight_goal = user[5] if len(user) > 5 else None
        # Check if weight_unit column exists in the result
        weight_unit = user[6] if len(user) > 6 else 0  # Default to kg (0)
        return User(user[0], user[1], user[3], user[4], weight_goal, weight_unit)
    return None

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, calorie_goal INTEGER DEFAULT 2000, protein_goal INTEGER DEFAULT 100, weight_goal REAL DEFAULT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS foods
                 (id INTEGER PRIMARY KEY, name TEXT, calories INTEGER, protein INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_log
                 (id INTEGER PRIMARY KEY, date TEXT, food_name TEXT, calories INTEGER, protein INTEGER, user_id INTEGER,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute("""CREATE TABLE IF NOT EXISTS daily_summary
                 (id INTEGER PRIMARY KEY, date TEXT, total_calories INTEGER, total_protein INTEGER, summary TEXT, user_id INTEGER,
                  calorie_goal INTEGER DEFAULT 2000, protein_goal INTEGER DEFAULT 100,
                  FOREIGN KEY(user_id) REFERENCES users(id))""")
    
    # Add weight_logs table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS weight_logs
                 (id INTEGER PRIMARY KEY, date TEXT, weight REAL, user_id INTEGER,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    # Add weight_goal column to users table if it doesn't exist
    try:
        c.execute("SELECT weight_goal FROM users LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE users ADD COLUMN weight_goal REAL DEFAULT NULL")
    
    # Add weight_unit column to users table if it doesn't exist
    try:
        c.execute("SELECT weight_unit FROM users LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE users ADD COLUMN weight_unit INTEGER DEFAULT 0")  # Default to kg (0)
    
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
    c.execute("SELECT * FROM foods ORDER BY name")  # Order foods alphabetically
    foods = c.fetchall()
    
    today = get_local_date().isoformat()
    
    # Check if there's a daily summary for today
    c.execute("SELECT id FROM daily_summary WHERE date = ? AND user_id = ?", (today, current_user.id))
    summary_exists = c.fetchone()
    
    if summary_exists:
        # If summary exists, set daily_log to empty list
        daily_log = []
        total_calories = 0
        total_protein = 0
    else:
        # If no summary, fetch the daily log as before
        c.execute("""SELECT id, food_name, calories, protein 
                     FROM daily_log
                     WHERE date = ? AND user_id = ?""", (today, current_user.id))
        daily_log = c.fetchall()
        total_calories = sum(food[2] for food in daily_log)
        total_protein = sum(food[3] for food in daily_log)
    
    conn.close()
    return render_template('dashboard.html', foods=foods, daily_log=daily_log, 
                           total_calories=total_calories, total_protein=total_protein)

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
    
    # Fetch all foods
    c.execute("SELECT * FROM foods ORDER BY name")
    foods = c.fetchall()
    
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
                           foods=foods, 
                           daily_log=daily_log, 
                           summary=summary)


@app.route('/update_history', methods=['POST'])
@login_required
def update_history():
    edit_date = request.form['edit_date']
    print(f"Edit date: {edit_date}")
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

    # Fetch all foods for the day after updates
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

    flash(f'Daily log for {edit_date} updated successfully!', 'success')
    return redirect(url_for('edit_history'))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/quick_add_food', methods=['POST'])
@login_required
def quick_add_food():
    name = request.form['name']
    calories = int(request.form['calories'])
    protein = int(request.form['protein'])
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO foods (name, calories, protein) VALUES (?, ?, ?)", (name, calories, protein))
    food_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
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
    
    return jsonify({
        'success': True,
        'log_entry': {
            'id': log_id,
            'food_name': name,
            'calories': total_calories,
            'protein': total_protein
        },
        'totals': {
            'calories': total_calories_sum,
            'protein': total_protein_sum
        }
    })


@app.route('/log_quick_food', methods=['POST'])
@login_required
def log_quick_food():
    food_id = request.form['food_id']
    today = get_local_date().isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT name, calories, protein FROM foods WHERE id = ?", (food_id,))
    food = c.fetchone()
    
    if food:
        food_name, calories, protein = food
        c.execute("INSERT INTO daily_log (date, food_name, calories, protein, user_id) VALUES (?, ?, ?, ?, ?)", 
                  (today, food_name, calories, protein, current_user.id))
        log_id = c.lastrowid
        conn.commit()
        
        # Calculate new totals
        c.execute("SELECT SUM(calories), SUM(protein) FROM daily_log WHERE date = ? AND user_id = ?", (today, current_user.id))
        total_calories, total_protein = c.fetchone()
        
        conn.close()
        return jsonify({
            'success': True,
            'log_entry': {
                'id': log_id,
                'food_name': food_name,
                'calories': calories,
                'protein': protein
            },
            'totals': {
                'calories': total_calories,
                'protein': total_protein
            }
        })
    else:
        conn.close()
        return jsonify({
            'success': False,
            'message': 'Food not found!'
        }), 404
    

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
        'success': True,
        'totals': {
            'calories': total_calories or 0,
            'protein': total_protein or 0
        }
    })

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
    
    # Update the daily_summary table with the user's current goals
    c.execute("""INSERT OR REPLACE INTO daily_summary (date, total_calories, total_protein, summary, user_id, calorie_goal, protein_goal)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                (today, total_calories, total_protein, summary, current_user.id, current_user.calorie_goal, current_user.protein_goal))
    
    conn.commit()
    conn.close()
    
    flash('Daily summary saved successfully!', 'success')
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
        return redirect(url_for('dashboard')) 

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            # Get weight_goal and weight_unit if they exist
            weight_goal = user[5] if len(user) > 5 else None
            weight_unit = user[6] if len(user) > 6 else 0  # Default to kg (0)
            user_obj = User(user[0], user[1], user[3], user[4], weight_goal, weight_unit)
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
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
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            user_count = c.fetchone()[0]
            conn.close()

            if user_count > 0:
                flash('Only one user (the creator) is allowed in this application.', 'error')
                return redirect(url_for('index'))
        
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        
        conn = sqlite3.connect(app.config['DB_PATH'])
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, calorie_goal, protein_goal, weight_goal, weight_unit) VALUES (?, ?, ?, ?, ?, ?)", 
                     (username, hashed_password, DEFAULT_CALORIE_GOAL, DEFAULT_PROTEIN_GOAL, None, 0))
            conn.commit()
            conn.close()
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as e:
            conn.close()
            flash('Username already exists. Please choose a different one.', 'error')
        except Exception as e:
            conn.close()
            flash(f'An error occurred: {e}', 'error')
    
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


    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get today's date
    today = get_local_date().isoformat()

    # Fetch foods eaten today from the daily log
    c.execute("SELECT DISTINCT food_name FROM daily_log WHERE date = ? AND user_id = ?", (today, current_user.id))
    eaten_foods = [row[0] for row in c.fetchall()] # a list of tuples in fetchall, extract the food name into list

    # Fetch all foods and filter out the ones eaten today
    foods = c.execute("SELECT * FROM foods").fetchall()
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
            "quote": "Calorie Counter has made it so easy for me to keep on top of my nutrition. I've never felt better!",
            "author": "Sarah L.",
            "role": "Fitness Enthusiast",
        },
        {
            "quote": "As a nutritionist, I recommend Calorie Counter to all my clients. It's user-friendly and accurate.",
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
def settings(): 
    # Get success message from flash if it exists
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
    
    if current_user.is_authenticated:
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
        
        conn.close()
    else:
        weight_logs = []
    
    # No need to fetch weekly summaries anymore as they're now in the history page
    return render_template('settings.html', 
                          calorie_goal=current_user.calorie_goal, 
                          protein_goal=current_user.protein_goal,
                          today_calories=today_calories,
                          today_protein=today_protein,
                          weight_logs=weight_logs,
                          success_message=success_message)

@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    # Get the new calorie and protein goals from the form
    calorie_goal = request.form.get('calorie_goal', type=int)
    protein_goal = request.form.get('protein_goal', type=int)
    weight_goal = request.form.get('weight_goal', type=float)
    current_weight = request.form.get('current_weight', type=float)
    weight_unit = request.form.get('weight_unit', type=int, default=0)  # Default to kg (0)
    
    # Validate the input
    if calorie_goal is None or protein_goal is None:
        flash('Invalid input. Please enter valid numbers for calorie and protein goals.', 'error')
        return redirect(url_for('settings'))
    
    if calorie_goal <= 0 or protein_goal <= 0:
        flash('Calorie and protein goals must be positive numbers.', 'error')
        return redirect(url_for('settings'))
    
    # Update the user's goals using the User class method
    current_user.update_goals(calorie_goal, protein_goal, weight_goal, weight_unit)
    
    # Log the current weight if provided
    if current_weight is not None and current_weight > 0:
        current_user.log_weight(current_weight)
        flash_message = 'Settings updated and weight logged successfully!'
    else:
        flash_message = 'Settings updated successfully!'
    
    # Redirect back to the settings page with a success message
    flash(flash_message, 'success')
    return redirect(url_for('settings'))

@app.route('/history')
@login_required
def history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get data for the last 90 days (3 months) instead of just 30 days
    ninety_days_ago = (get_local_date() - timedelta(days=90)).isoformat()
    c.execute("""SELECT date, total_calories, total_protein, summary, calorie_goal, protein_goal 
                 FROM daily_summary 
                 WHERE date >= ? AND user_id = ? 
                 ORDER BY date ASC""", (ninety_days_ago, current_user.id))
    summaries = c.fetchall()
    
    # Get weight logs for the same period
    c.execute("""SELECT date, weight FROM weight_logs 
                 WHERE date >= ? AND user_id = ? 
                 ORDER BY date ASC""", (ninety_days_ago, current_user.id))
    weight_logs = c.fetchall()
    
    # Format data for charts
    dates = [entry[0] for entry in summaries]
    calories = [entry[1] for entry in summaries]
    proteins = [entry[2] for entry in summaries]
    calorie_goals = [entry[4] for entry in summaries]
    protein_goals = [entry[5] for entry in summaries]
    
    # Format weight data
    weight_dates = [entry[0] for entry in weight_logs]
    weights = [entry[1] for entry in weight_logs]
    
    # Convert weight to user's preferred unit
    if current_user.weight_unit == 1:  # If user prefers lbs
        weights = [round(w * 2.20462, 1) for w in weights]  # Convert kg to lbs
    
    conn.close()
    return render_template('history.html', 
                          weekly_summaries=summaries,
                          chart_dates=dates,
                          chart_calories=calories,
                          chart_proteins=proteins,
                          chart_calorie_goals=calorie_goals,
                          chart_protein_goals=protein_goals,
                          weight_dates=weight_dates,
                          weights=weights,
                          weight_goal=current_user.weight_goal,
                          weight_unit="lbs" if current_user.weight_unit == 1 else "kg")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)

