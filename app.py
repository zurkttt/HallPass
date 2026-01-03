from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import MySQLdb.cursors


app = Flask(__name__)

# --- CONFIGURATION ---
app.secret_key = 'facilibook' 
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'     
app.config['MYSQL_PASSWORD'] = ''      
app.config['MYSQL_DB'] = 'facilibook'

mysql = MySQL(app)

# --- HELPER FUNCTIONS ---

def get_facilities():
    """Fetches list of all facilities."""
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM facilities')
    return cursor.fetchall()

def get_user_bookings(user_id):
    """Fetches booking history for a specific user, INCLUDING the approver's name."""
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # We join 'users' table TWICE: 
    # 1. To get the Faculty Name (u.name)
    # 2. To get the Admin Approver's Name (admin_user.name)
    query = """
        SELECT 
            b.id, b.start_time, b.end_time, b.purpose, b.status, 
            f.name as facility_name,
            admin_user.name as approver_name
        FROM bookings b
        JOIN facilities f ON b.facility_id = f.id
        LEFT JOIN users admin_user ON b.approved_by = admin_user.id
        WHERE b.user_id = %s
        ORDER BY b.start_time DESC
    """
    cursor.execute(query, (user_id,))
    return cursor.fetchall()

# --- AUTHENTICATION ROUTES ---

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
        
        # Simple plain-text password check (as requested)
        if account and account['password'] == password:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['role'] = account['role']
            session['name'] = account['name']
            
            if account['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('my_bookings'))
        else:
            return render_template('login.html', error="Incorrect Username or Password")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Allows new Instructors to create an account."""
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Check if username exists
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        if cursor.fetchone():
            return render_template('register.html', error="Username already exists!")
        
        # Create new Faculty User
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

# Feature: CRUD Facilities
@app.route('/admin/facilities', methods=['GET', 'POST'])
def manage_facilities():
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        if request.method == 'POST':
            # Check if this is an Edit (has ID) or New (no ID)
            if 'facility_id' in request.form and request.form['facility_id']:
                # Update
                fid = request.form['facility_id']
                name = request.form['name']
                desc = request.form['description']
                cap = request.form['capacity']
                cursor.execute('UPDATE facilities SET name=%s, description=%s, capacity=%s WHERE id=%s', (name, desc, cap, fid))
            else:
                # Insert
                name = request.form['name']
                desc = request.form['description']
                cap = request.form['capacity']
                cursor.execute('INSERT INTO facilities (name, description, capacity) VALUES (%s, %s, %s)', (name, desc, cap))
            
            mysql.connection.commit()
            return redirect(url_for('manage_facilities'))

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

# Feature: Booking Approvals
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
            WHERE b.status = 'pending'
            ORDER BY b.start_time ASC
        """
        cursor.execute(query)
        bookings = cursor.fetchall()
        return render_template('admin_bookings.html', bookings=bookings)
    return redirect(url_for('login'))

@app.route('/approve_booking/<int:id>')
def approve_booking(id):
    if 'role' in session and session['role'] == 'admin':
        admin_id = session['id'] # Capture who clicked the button
        cursor = mysql.connection.cursor()
        # Set status to Approved AND save the Admin's ID
        cursor.execute("UPDATE bookings SET status = 'approved', approved_by = %s WHERE id = %s", (admin_id, id))
        mysql.connection.commit()
        return redirect(url_for('admin_bookings'))
    return redirect(url_for('login'))

@app.route('/reject_booking/<int:id>')
def reject_booking(id):
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE bookings SET status = 'rejected' WHERE id = %s", (id,))
        mysql.connection.commit()
        return redirect(url_for('admin_bookings'))
    return redirect(url_for('login'))

# Feature: CRUD Users
@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        if request.method == 'POST':
            user_id = request.form['user_id']
            name = request.form['name']
            username = request.form['username']
            password = request.form['password']
            
            # Update password only if provided
            if password:
                cursor.execute('UPDATE users SET name=%s, username=%s, password=%s WHERE id=%s', (name, username, password, user_id))
            else:
                cursor.execute('UPDATE users SET name=%s, username=%s WHERE id=%s', (name, username, user_id))
                
            mysql.connection.commit()
            return redirect(url_for('manage_users'))

        # Show all users except admins
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

# Feature: Reports
@app.route('/admin/reports')
def admin_reports():
    if 'role' in session and session['role'] == 'admin':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # Fetch Approved Bookings History
        query = """
            SELECT b.start_time, b.end_time, b.purpose, f.name AS facility_name, u.name AS faculty_name
            FROM bookings b
            JOIN facilities f ON b.facility_id = f.id
            JOIN users u ON b.user_id = u.id
            WHERE b.status = 'approved'
            ORDER BY b.start_time DESC
        """
        cursor.execute(query)
        reports = cursor.fetchall()
        return render_template('admin_reports.html', reports=reports)
    return redirect(url_for('login'))

# --- FACULTY ROUTES ---

@app.route('/my_bookings')
def my_bookings():
    """Faculty Dashboard: Shows History & Print Permit Button."""
    if 'role' in session and session['role'] == 'faculty':
        user_id = session['id']
        bookings = get_user_bookings(user_id)
        return render_template('my_bookings.html', bookings=bookings)
    return redirect(url_for('login'))

@app.route('/faculty', methods=['GET', 'POST'])
def faculty_booking():
    """Transaction: Booking Form with Conflict Check."""
    if 'role' in session and session['role'] == 'faculty':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        if request.method == 'POST':
            facility_id = request.form['facility_id']
            start_str = request.form['start_time']
            end_str = request.form['end_time']
            purpose = request.form['purpose']
            user_id = session['id']
            
            # 1. Validation: End time must be after Start time
            if start_str >= end_str:
                return render_template('faculty_booking.html', 
                                     facilities=get_facilities(), 
                                     error="End time must be after Start time.")

            # 2. Conflict Detection Logic
            # Check if any APPROVED/PENDING booking overlaps with requested time
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
                # No conflict? Insert the request.
                cursor.execute('INSERT INTO bookings (facility_id, user_id, start_time, end_time, purpose) VALUES (%s, %s, %s, %s, %s)', 
                               (facility_id, user_id, start_str, end_str, purpose))
                mysql.connection.commit()
                return redirect(url_for('my_bookings'))

        return render_template('faculty_booking.html', facilities=get_facilities())
    return redirect(url_for('login'))

# Feature: Print Permit Page
@app.route('/print_permit/<int:id>')
def print_permit(id):
    """Generates the printable permit for an approved booking."""
    if 'role' in session: # Allow Admin or Faculty to see this
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = """
            SELECT 
                b.id, b.start_time, b.end_time, b.purpose, 
                f.name as facility_name,
                u.name as faculty_name,
                admin_user.name as approver_name
            FROM bookings b
            JOIN facilities f ON b.facility_id = f.id
            JOIN users u ON b.user_id = u.id
            LEFT JOIN users admin_user ON b.approved_by = admin_user.id
            WHERE b.id = %s AND b.status = 'approved'
        """
        cursor.execute(query, (id,))
        booking = cursor.fetchone()
        
        if booking:
            return render_template('print_permit.html', booking=booking)
            
    return "Permit not found or not approved."

if __name__ == '__main__':
    app.run(debug=True)