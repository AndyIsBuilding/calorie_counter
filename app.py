from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
import pytz
import csv
import io
import os
from typing import NamedTuple

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # Change this to a random secret key
app.config['TIMEZONE'] = os.getenv('TIMEZONE') 

CALORIE_GOAL = 2900 
PROTEIN_GOAL = 220 

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
    DB_PATH = 'food_tracker.db'

# Update app configuration
app.config['DB_PATH'] = DB_PATH



login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(app.config['DB_PATH'])
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1])
    return None

def init_db():
    conn = sqlite3.connect(app.config['DB_PATH'])
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS foods
                 (id INTEGER PRIMARY KEY, name TEXT, calories INTEGER, protein INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_log
                 (id INTEGER PRIMARY KEY, date TEXT, food_name TEXT, calories INTEGER, protein INTEGER, user_id INTEGER,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute("""CREATE TABLE IF NOT EXISTS daily_summary
                 (id INTEGER PRIMARY KEY, date TEXT, total_calories INTEGER, total_protein INTEGER, summary TEXT, user_id INTEGER,
                  FOREIGN KEY(user_id) REFERENCES users(id))""")
    conn.commit()
    conn.close()


def get_local_date():
    tz = pytz.timezone(os.environ.get('TIMEZONE', 'UTC'))
    return datetime.now(tz).date()

@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect(app.config['DB_PATH'])
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
    
    # Fetch weekly summaries for the last 7 days
    seven_days_ago = (get_local_date() - timedelta(days=7)).isoformat()
    c.execute("""SELECT date, total_calories, total_protein, summary 
                 FROM daily_summary 
                 WHERE date >= ? AND user_id = ? 
                 ORDER BY date DESC""", (seven_days_ago, current_user.id))
    weekly_summaries = c.fetchall()
    
    conn.close()
    return render_template('dashboard.html', foods=foods, daily_log=daily_log, 
                           total_calories=total_calories, total_protein=total_protein,
                           weekly_summaries=weekly_summaries)


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
    
    conn = sqlite3.connect(app.config['DB_PATH'])
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
    
    conn = sqlite3.connect(app.config['DB_PATH'])
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
    
    conn = sqlite3.connect(app.config['DB_PATH'])
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
    conn = sqlite3.connect(app.config['DB_PATH'])
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
    
    conn = sqlite3.connect(app.config['DB_PATH'])
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
    
    # Update the daily_summary table
    c.execute("""INSERT OR REPLACE INTO daily_summary (date, total_calories, total_protein, summary, user_id)
                 VALUES (?, ?, ?, ?, ?)""", (today, total_calories, total_protein, summary, current_user.id))
    
    conn.commit()
    conn.close()
    
    flash('Daily summary saved successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/export_csv')
@login_required
def export_csv():
    conn = sqlite3.connect(app.config['DB_PATH'])
    c = conn.cursor()
    c.execute("""SELECT date, summary, total_calories, total_protein 
                 FROM daily_summary
                 WHERE user_id = ?
                 ORDER BY date""", (current_user.id,))
    data = c.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Food Summary', 'Total Calories', 'Total Protein'])
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
        conn = sqlite3.connect(app.config['DB_PATH'])
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            user_obj = User(user[0], user[1])
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
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            conn.close()
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            flash('Username already exists. Please choose a different one.', 'error')
    
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
    
    conn = sqlite3.connect(app.config['DB_PATH'])
    c = conn.cursor()
    
    c.execute("SELECT SUM(calories) FROM daily_log WHERE date = ? AND user_id = ?", (today, current_user.id))
    total_calories = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(protein) FROM daily_log WHERE date = ? AND user_id = ?", (today, current_user.id))
    total_protein = c.fetchone()[0] or 0
    
    conn.close()
    
    protein_first, calorie_first = food_recommendation(total_calories, total_protein)

    # Calculate sums for protein_first recommendation
    protein_first_foods = protein_first[0] if protein_first else []
    protein_first_calories = sum(food.calories for food in protein_first_foods)
    protein_first_protein = sum(food.protein for food in protein_first_foods)

    # Calculate sums for calorie_first recommendation
    calorie_first_foods = calorie_first[0] if calorie_first else []
    calorie_first_calories = sum(food.calories for food in calorie_first_foods)
    calorie_first_protein = sum(food.protein for food in calorie_first_foods)

    formatted_recommendations = {
        "protein_first": {
            "foods": [
                {"name": food.name, "calories": food.calories, "protein": food.protein}
                for food in protein_first_foods
            ],
            "total_calories": protein_first_calories,
            "total_protein": protein_first_protein,
            "day_total_calories": total_calories + protein_first_calories,
            "day_total_protein": total_protein + protein_first_protein,
        },
        "calorie_first": {
            "foods": [
                {"name": food.name, "calories": food.calories, "protein": food.protein}
                for food in calorie_first_foods
            ],
            "total_calories": calorie_first_calories,
            "total_protein": calorie_first_protein,
            "day_total_calories": total_calories + calorie_first_calories,
            "day_total_protein": total_protein + calorie_first_protein,
        }
    }
    
    return jsonify(formatted_recommendations)

def food_recommendation(total_calories, total_protein): 
    """    Compare to pre-set calorie/protein goals; determine remaining calories/protein for the day 
    Recommend based on remaining calories/protein
    Return a list of recommended foods"""


    conn = sqlite3.connect(app.config['DB_PATH'])
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
    remaining_calories = CALORIE_GOAL - total_calories
    remaining_protein = PROTEIN_GOAL - total_protein

    # Use the remaining calories/protein to recommend foods 
    # 2 recommendations: 
        # 1. hit protein goal, minimize calories
        # 2. stay within calorie goal, maximize protein
    dp = [[[0 for _ in range(remaining_protein + 1)] 
           for _ in range(remaining_calories + 1)] 
           for _ in range(n + 1)]

    # Fill the DP table
    for i in range(1, n + 1):
        for j in range(remaining_calories + 1):
            for k in range(remaining_protein + 1):
                if available_foods[i-1].calories <= j:
                    new_protein = min(k, dp[i-1][j-available_foods[i-1].calories][k] + available_foods[i-1].protein)
                    dp[i][j][k] = max(dp[i-1][j][k], new_protein)
                else:
                    dp[i][j][k] = dp[i-1][j][k]

    def backtrack(i: int, j: int, k: int):
        if i == 0:
            return []
        if dp[i][j][k] > dp[i-1][j][k]:
            return backtrack(i-1, j-available_foods[i-1].calories, max(0, k-available_foods[i-1].protein)) + [available_foods[i-1]]
        return backtrack(i-1, j, k)

    # Generate recommendations
    protein_first = []
    calorie_first = []

    # 1. Hit protein goal, minimize calories
    for j in range(remaining_calories + 1):
        if dp[n][j][remaining_protein] >= remaining_protein:
            protein_first.append(backtrack(n, j, remaining_protein))
            break

    # 2. Stay within calorie goal, maximize protein
    max_protein = dp[n][remaining_calories][remaining_protein]
    calorie_first.append(backtrack(n, remaining_calories, max_protein))

    # Sort recommendations
    protein_first.sort(key=lambda x: sum(food.calories for food in x))
    calorie_first.sort(key=lambda x: sum(food.protein for food in x), reverse=True)

    return protein_first, calorie_first

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)