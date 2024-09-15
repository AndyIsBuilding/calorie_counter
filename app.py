from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
import pytz
import csv
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this to a random secret key
app.config['TIMEZONE'] = '' 

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('food_tracker.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1])
    return None

def init_db():
    conn = sqlite3.connect('food_tracker.db')
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
    tz = pytz.timezone(app.config['TIMEZONE'])
    return datetime.now(tz).date()

@app.route('/')
@login_required
def index():
    conn = sqlite3.connect('food_tracker.db')
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
    return render_template('index.html', foods=foods, daily_log=daily_log, 
                           total_calories=total_calories, total_protein=total_protein,
                           weekly_summaries=weekly_summaries)


@app.route('/home')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('home.html')

@app.route('/quick_add_food', methods=['POST'])
@login_required
def quick_add_food():
    name = request.form['name']
    calories = request.form['calories']
    protein = request.form['protein']
    
    conn = sqlite3.connect('food_tracker.db')
    c = conn.cursor()
    c.execute("INSERT INTO foods (name, calories, protein) VALUES (?, ?, ?)", (name, calories, protein))
    conn.commit()
    conn.close()
    
    flash('Food added successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/log_food', methods=['POST'])
@login_required
def log_food():
    servings = float(request.form.get('servings', 1))
    name = request.form['name']
    calories = int(request.form['calories'])
    protein = int(request.form['protein'])
    
    conn = sqlite3.connect('food_tracker.db')
    c = conn.cursor()

    total_calories = int(calories * servings)
    total_protein = int(protein * servings)
    
    # Log the food for today directly in the daily_log table
    today = get_local_date().isoformat()
    c.execute("INSERT INTO daily_log (date, food_name, calories, protein, user_id) VALUES (?, ?, ?, ?, ?)", 
              (today, name, total_calories, total_protein, current_user.id))
    
    conn.commit()
    conn.close()
    
    flash('Food logged successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/log_quick_food', methods=['POST'])
@login_required
def log_quick_food():
    food_id = request.form['food_id']
    today = get_local_date().isoformat()
    
    conn = sqlite3.connect('food_tracker.db')
    c = conn.cursor()
    
    # Fetch food details from the foods table
    c.execute("SELECT name, calories, protein FROM foods WHERE id = ?", (food_id,))
    food = c.fetchone()
    
    if food:
        food_name, calories, protein = food

        # Insert into daily_log using the calculated values
        c.execute("INSERT INTO daily_log (date, food_name, calories, protein, user_id) VALUES (?, ?, ?, ?, ?)", 
                  (today, food_name, calories, protein, current_user.id))
        conn.commit()
        flash('Food logged successfully!', 'success')
    else:
        flash('Food not found!', 'error')
    
    conn.close()
    return redirect(url_for('index'))

@app.route('/remove_food/<int:log_id>', methods=['POST'])
@login_required
def remove_food(log_id):
    conn = sqlite3.connect('food_tracker.db')
    c = conn.cursor()
    c.execute("DELETE FROM daily_log WHERE id = ? AND user_id = ?", (log_id, current_user.id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))

@app.route('/save_summary', methods=['POST'])
@login_required
def save_summary():
    today = get_local_date().isoformat()
    
    conn = sqlite3.connect('food_tracker.db')
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
    return redirect(url_for('index'))

@app.route('/export_csv')
@login_required
def export_csv():
    conn = sqlite3.connect('food_tracker.db')
    c = conn.cursor()
    c.execute("""SELECT date, food_name, calories, protein 
                 FROM daily_log
                 WHERE user_id = ?
                 ORDER BY date""", (current_user.id,))
    data = c.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Food', 'Calories', 'Protein'])
    writer.writerows(data)
    
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        attachment_filename='food_log.csv'
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('food_tracker.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            user_obj = User(user[0], user[1])
            login_user(user_obj)
            return redirect(url_for('index'))
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
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        
        conn = sqlite3.connect('food_tracker.db')
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)