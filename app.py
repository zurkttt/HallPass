from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors

app = Flask(__name__)

# --- CONFIGURATION ---
app.secret_key = 'your_secret_key'  # Change to a random secret word
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'      # Your MariaDB username
app.config['MYSQL_PASSWORD'] = ''      # Your MariaDB password
app.config['MYSQL_DB'] = 'booking_system'

mysql = MySQL(app)

# --- HELPER FUNCTIONS (Must be defined BEFORE routes use them) ---
def get_facilities():
    """Helper function to fetch all facilities for dropdowns."""
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM facilities')
    return cursor.fetchall()

# --- AUTH ROUTES ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()
        
        # Simple Password Check
        if account and account['password'] == password:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['role'] = account['role']
            session['name'] = account.get('name', username)
            
            if account['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('faculty_booking'))
        else:
            return render_template('login.html', error="Incorrect Username or Password")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Check if username exists
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()
        
        if account:
            return render_template('register.html', error="Username already exists!")
        
        # Insert new Faculty
        cursor.execute('INSERT INTO users (name, username, password, role) VALUES (%s, %s, %s, "faculty")', 
                       (name, username, password))
        mysql.connection.commit()
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ADMIN ROUTES ---

@app.route('/admin')
def admin_dashboard():
    """Main Menu for Admin"""
    if 'role' in session and session['role'] == 'admin':
        return render_template('admin_dashboard.html')
    return redirect(url_for('login'))

# 1. MANAGE FACILITIES PAGE
@app.route('/admin/facilities', methods=['GET', 'POST'])
def manage_facilities():
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Handle Add Facility
        if request.method == 'POST':
            # Check if this is an Edit or Add (Hidden ID field)
            if 'facility_id' in request.form and request.form['facility_id']:
                # UPDATE LOGIC
                fid = request.form['facility_id']
                name = request.form['name']
                desc = request.form['description']
                cap = request.form['capacity']
                cursor.execute('UPDATE facilities SET name=%s, description=%s, capacity=%s WHERE id=%s', (name, desc, cap, fid))
            else:
                # INSERT LOGIC
                name = request.form['name']
                desc = request.form['description']
                cap = request.form['capacity']
                cursor.execute('INSERT INTO facilities (name, description, capacity) VALUES (%s, %s, %s)', (name, desc, cap))
            
            mysql.connection.commit()
            return redirect(url_for('manage_facilities'))

        # List all
        facilities = get_facilities()
        return render_template('manage_facilities.html', facilities=facilities)
    return redirect(url_for('login'))

@app.route('/delete_facility/<int:id>')
def delete_facility(id):
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor()
        cursor.execute('DELETE FROM facilities WHERE id = %s', (id,))
        mysql.connection.commit()
    return redirect(url_for('manage_facilities'))

# 2. BOOKING APPROVALS PAGE
@app.route('/admin/bookings')
def admin_bookings():
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = """
            SELECT b.id AS booking_id, b.start_time, b.end_time, b.purpose, b.status, 
                   f.name AS facility_name, u.name AS faculty_name
            FROM bookings b
            JOIN facilities f ON b.facility_id = f.id
            JOIN users u ON b.user_id = u.id
            ORDER BY b.start_time DESC
        """
        cursor.execute(query)
        bookings = cursor.fetchall()
        return render_template('admin_bookings.html', bookings=bookings)
    return redirect(url_for('login'))

# --- MISSING APPROVAL ROUTES ---

@app.route('/approve_booking/<int:id>')
def approve_booking(id):
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE bookings SET status = 'approved' WHERE id = %s", (id,))
        mysql.connection.commit()
        # Redirect back to the bookings list
        return redirect(url_for('admin_bookings'))
    return redirect(url_for('login'))

@app.route('/reject_booking/<int:id>')
def reject_booking(id):
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE bookings SET status = 'rejected' WHERE id = %s", (id,))
        mysql.connection.commit()
        # Redirect back to the bookings list
        return redirect(url_for('admin_bookings'))
    return redirect(url_for('login'))


# 3. MANAGE USERS PAGE
@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Handle User Update
        if request.method == 'POST':
            user_id = request.form['user_id']
            name = request.form['name']
            username = request.form['username']
            # Optional: Password reset if field is not empty
            password = request.form['password']
            
            if password:
                cursor.execute('UPDATE users SET name=%s, username=%s, password=%s WHERE id=%s', (name, username, password, user_id))
            else:
                cursor.execute('UPDATE users SET name=%s, username=%s WHERE id=%s', (name, username, user_id))
                
            mysql.connection.commit()
            return redirect(url_for('manage_users'))

        # Fetch all users (excluding admin usually, or show all)
        cursor.execute("SELECT * FROM users WHERE role != 'admin'")
        users = cursor.fetchall()
        return render_template('manage_users.html', users=users)
    return redirect(url_for('login'))

@app.route('/delete_user/<int:id>')
def delete_user(id):
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor()
        cursor.execute('DELETE FROM users WHERE id = %s', (id,))
        mysql.connection.commit()
    return redirect(url_for('manage_users'))

# --- FACULTY BOOKING (FORM ONLY) ---
@app.route('/faculty', methods=['GET', 'POST'])
def faculty_booking():
    if 'role' in session and session['role'] == 'faculty':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # --- HANDLE BOOKING SUBMISSION ---
        if request.method == 'POST':
            facility_id = request.form['facility_id']
            start_str = request.form['start_time']
            end_str = request.form['end_time']
            purpose = request.form['purpose']
            user_id = session['id']
            
            # Validation: End time after Start time
            if start_str >= end_str:
                return render_template('faculty_booking.html', 
                                     facilities=get_facilities(), 
                                     error="End time must be after Start time.")

            # CONFLICT CHECK
            query = """
                SELECT * FROM bookings 
                WHERE facility_id = %s 
                AND status != 'rejected'
                AND start_time < %s 
                AND end_time > %s
            """
            cursor.execute(query, (facility_id, end_str, start_str))
            conflict = cursor.fetchone()
            
            if conflict:
                return render_template('faculty_booking.html', 
                                     facilities=get_facilities(), 
                                     error=f"Conflict! Facility is busy from {conflict['start_time']} to {conflict['end_time']}")
            else:
                cursor.execute('INSERT INTO bookings (facility_id, user_id, start_time, end_time, purpose) VALUES (%s, %s, %s, %s, %s)', 
                               (facility_id, user_id, start_str, end_str, purpose))
                mysql.connection.commit()
                # SUCCESS: Redirect to the Dashboard/History page
                return redirect(url_for('my_bookings'))

        # --- LOAD PAGE (GET) ---
        # Only fetch facilities, no history needed here
        facilities = get_facilities()
        return render_template('faculty_booking.html', facilities=facilities)
    return redirect(url_for('login'))

# Helper function to get history (Cleaner code)
def get_user_bookings(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    query = """
        SELECT b.start_time, b.end_time, b.purpose, b.status, f.name as facility_name
        FROM bookings b
        JOIN facilities f ON b.facility_id = f.id
        WHERE b.user_id = %s
        ORDER BY b.start_time DESC
    """
    cursor.execute(query, (user_id,))
    return cursor.fetchall()

@app.route('/my_bookings')
def my_bookings():
    if 'role' in session and session['role'] == 'faculty':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        user_id = session['id']
        
        query = """
            SELECT b.start_time, b.end_time, b.purpose, b.status, f.name as facility_name
            FROM bookings b
            JOIN facilities f ON b.facility_id = f.id
            WHERE b.user_id = %s
            ORDER BY b.start_time DESC
        """
        cursor.execute(query, (user_id,))
        bookings = cursor.fetchall()
        return render_template('my_bookings.html', bookings=bookings)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)