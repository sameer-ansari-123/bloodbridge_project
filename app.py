from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from flask_bcrypt import Bcrypt
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
import os



def get_db():
    try:
        return mysql.connector.connect(
            host=os.environ.get("MYSQL_HOST", "localhost"),
            port=int(os.environ.get("MYSQL_PORT", 3306)),
            user=os.environ.get("MYSQL_USER", "root"),
            password=os.environ.get("MYSQL_PASSWORD", "Sameer@123"),
            database=os.environ.get("MYSQL_DATABASE", "bloodbridge_db"),
            connection_timeout=5
        )
    except Exception as e:
        print("❌ MySQL connection failed:", e)
        return None


app = Flask(__name__)
app.secret_key = 'bloodbridge_secure_key_999'
bcrypt = Bcrypt(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# db_config = {
#     'host': 'localhost',
#     'user': 'root', 
#     'password': 'Sameer@123', 
#     'database': 'bloodbridge_db'
# }

# def get_db():
#     return mysql.connector.connect(**db_config)

# --- VIEWS ---

# --- CONTEXT PROCESSORS ---
@app.context_processor
def inject_stats():
    try:
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'donor'")
        donors = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_available = 1")
        total_users = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM blood_requests WHERE status = 'Fulfilled'")
        saved = cursor.fetchone()['count']
        db.close()
        return dict(global_donors=donors, global_users=total_users, global_saved=saved)
    except:
        return dict(global_donors=0, global_users=0, global_saved=0)

# --- VIEWS ---

@app.route('/')
def index():
    try:
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'donor'")
        total_donors = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM blood_requests WHERE status = 'Fulfilled'")
        saved_count = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM blood_requests WHERE status = 'Pending'")
        active_reqs = cursor.fetchone()['count']

        cursor.execute("""
            SELECT br.*, u.full_name as requester_name 
            FROM blood_requests br 
            JOIN users u ON br.requester_id = u.id 
            WHERE br.status = 'Pending' 
            ORDER BY br.created_at DESC LIMIT 6
        """)
        urgent_requests = cursor.fetchall()
        
        db.close()
        return render_template('index.html', 
                               donors_count=total_donors, 
                               saved_count=saved_count, 
                               active_reqs=active_reqs,
                               urgent_requests=urgent_requests)
    except Exception as e:
        print(f"Error in index route: {e}")
        return render_template('index.html', donors_count=0, saved_count=0, active_reqs=0, urgent_requests=[])

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    db = get_db()
    if not db:
            raise Exception("Database connection failed")
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    db.close()
    
    print(f"DEBUG LOGIN: Email={email}, FoundUser={user is not None}")
    if user:
        print(f"DEBUG PASSWORD: HashMatch={bcrypt.check_password_hash(user['password_hash'], password)}")
    
    if user and bcrypt.check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['user_name'] = user['full_name']
        session['role'] = user['role']
        return redirect(url_for('dashboard'))
    
    flash('Invalid credentials', 'danger')
    return redirect(url_for('index'))

@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    email = request.form['email']
    pw_raw = request.form['password']
    bg = request.form['blood_group']
    phone = request.form['phone']
    city = request.form['city']
    role = request.form['role']
    latitude = request.form.get('latitude') or None
    longitude = request.form.get('longitude') or None
    
    try:
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor(dictionary=True)
        
        # Check for duplicate email
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            db.close()
            # Render index with error variable to trigger popup
            return render_template('index.html', register_error="User with this email already exists!", page='home')
            
        pw = bcrypt.generate_password_hash(pw_raw).decode('utf-8')
        cursor.execute("INSERT INTO users (full_name, email, password_hash, blood_group, phone, city, role, latitude, longitude) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", 
                       (name, email, pw, bg, phone, city, role, latitude, longitude))
        db.commit()
        
        # Auto-login
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        db.close()
        
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['role'] = user['role']
            flash('Registration successful!', 'success')
            return redirect(url_for('dashboard'))
            
    except Exception as e:
        print(f"Registration Error: {e}")
        flash('Database error during registration.', 'danger')
    
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('index'))
    
    try:
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as count FROM blood_requests WHERE requester_id = %s", (session['user_id'],))
        req_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT * FROM blood_requests WHERE requester_id = %s ORDER BY created_at DESC", (session['user_id'],))
        my_requests = cursor.fetchall()
        
        db.close()
        return render_template('index.html', user=user, my_requests=my_requests, req_count=req_count, page='dashboard')
    except Exception as e:
        print(f"Dashboard Error: {e}")
        return redirect(url_for('index'))

@app.route('/post-request', methods=['POST'])
def post_request():
    if 'user_id' not in session: return redirect(url_for('index'))
    
    bg = request.form['blood_group']
    ct = request.form['city']
    hosp = request.form['hospital']
    urg = request.form['urgency']
    desc = request.form.get('description', '')
    
    try:
        print(f"DEBUG POST: User={session['user_id']}, BG={bg}, City={ct}, Hosp={hosp}, Urg={urg}")
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO blood_requests (requester_id, required_blood_group, city, hospital_name, urgency_level, description) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session['user_id'], bg, ct, hosp, urg, desc))
        db.commit()
        db.close()
        flash('Broadcast sent successfully!', 'success')
        print("DEBUG POST: Success")
    except Exception as e:
        print(f"Post Request Error: {e}")
        flash('Error posting request.', 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/toggle-availability', methods=['POST'])
def toggle_availability():
    if 'user_id' not in session: return redirect(url_for('index'))
    
    try:
        user_id = session['user_id']
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor()
        cursor.execute("UPDATE users SET is_available = NOT is_available WHERE id = %s", (user_id,))
        db.commit()
        db.close()
        flash('Status updated successfully', 'success')
    except Exception as e:
        print(f"Toggle Error: {e}")
        flash('Error updating status', 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/update-profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session: return redirect(url_for('index'))
    
    try:
        db = get_db()
        if not db: raise Exception("Database connection failed")
        cursor = db.cursor()
        
        sql = """
            UPDATE users 
            SET full_name = %s, phone = %s, city = %s, blood_group = %s
            WHERE id = %s
        """
        cursor.execute(sql, (
            request.form['name'],
            request.form['phone'],
            request.form['city'],
            request.form['blood_group'],
            session['user_id']
        ))
        db.commit()
        db.close()
        
        session['user_name'] = request.form['name']  # Update session
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        print(f"Update Profile Error: {e}")
        flash('Error updating profile.', 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/delete-account', methods=['POST'])
def delete_account():
    if 'user_id' not in session: return redirect(url_for('index'))
    
    try:
        user_id = session['user_id']
        db = get_db()
        if not db: raise Exception("Database connection failed")
        cursor = db.cursor()
        
        # Manual Cascade Delete
        cursor.execute("DELETE FROM messages WHERE sender_id = %s OR receiver_id = %s", (user_id, user_id, user_id, user_id))
        cursor.execute("DELETE FROM blood_requests WHERE requester_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        
        db.commit()
        db.close()
        
        session.clear()
        flash('Your account has been permanently deleted.', 'info')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Delete Account Error: {e}")
        flash('Error deleting account.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form['email']
    try:
        db = get_db()
        if not db: raise Exception("Database connection failed")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        db.close()
        
        if user:
            token = serializer.dumps(email, salt='password-reset-salt')
            link = url_for('reset_password', token=token, _external=True)
            # MOCK EMAIL
            flash(f'PASSWORD RESET LINK (Copy this): {link}', 'info') 
        else:
            flash('If that email exists, we sent a reset link.', 'info')
            
    except Exception as e:
        print(f"Forgot Password Error: {e}")
        flash('Error processing request.', 'danger')
        
    return redirect(url_for('index'))

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        password = request.form['password']
        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("UPDATE users SET password_hash = %s WHERE email = %s", (pw_hash, email))
            db.commit()
            db.close()
            flash('Your password has been updated! You can now login.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Reset Password DB Error: {e}")
            flash('Error resetting password.', 'danger')
            
    return render_template('index.html', reset_token=token, page='reset_password')



@app.route('/search')
def search():
    bg = request.args.get('blood_group')
    ct = request.args.get('city')
    
    try:
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor(dictionary=True)
        
        query = "SELECT * FROM users WHERE role = 'donor' AND is_available = 1"
        params = []
        if bg:
            query += " AND blood_group = %s"
            params.append(bg)
        if ct:
            query += " AND city LIKE %s"
            params.append(f"%{ct}%")
        
        cursor.execute(query, params)
        donors = cursor.fetchall()
        db.close()
        return render_template('index.html', donors=donors, page='search')
    except Exception as e:
        print(f"Search Error: {e}")
        return render_template('index.html', donors=[], page='search')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- CHAT API ENDPOINTS ---

@app.route('/api/send-message', methods=['POST'])
def send_message():
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        receiver_id = int(data.get('receiver_id'))
        content = data.get('content')
        
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor()
        cursor.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)",
                       (session['user_id'], receiver_id, content))
        db.commit()
        db.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Send Message Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-messages/<int:partner_id>')
def get_messages(partner_id):
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM messages 
            WHERE (sender_id = %s AND receiver_id = %s) 
               OR (sender_id = %s AND receiver_id = %s)
            ORDER BY timestamp ASC
        """, (session['user_id'], partner_id, partner_id, session['user_id']))
        messages = cursor.fetchall()
        db.close()
        
        # Robust date conversion
        for msg in messages:
            ts = msg.get('timestamp')
            if ts:
                # If it's already a string, keep it. If datetime, format it.
                if isinstance(ts, (datetime,)):
                    msg['timestamp'] = ts.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    msg['timestamp'] = str(ts)
                
        return jsonify(messages)
    except Exception as e:
        print(f"Get Messages Error: {e}")
        # Return empty list instead of erroring out to frontend
        return jsonify([])

@app.route('/api/my-conversations')
def my_conversations():
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        user_id = session['user_id']
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor(dictionary=True)
        
        query = """
            SELECT DISTINCT u.id, u.full_name, u.role, u.is_available
            FROM users u
            JOIN messages m ON (u.id = m.sender_id OR u.id = m.receiver_id)
            WHERE (m.sender_id = %s OR m.receiver_id = %s) AND u.id != %s
        """
        cursor.execute(query, (user_id, user_id, user_id))
        conversations = cursor.fetchall()
        print(f"DEBUG CHAT: UserID={user_id}, FoundConversations={len(conversations)}")
        db.close()
        return jsonify(conversations)
    except Exception as e:
        print(f"Conversations Error: {e}")
        return jsonify([])

@app.route('/api/delete-conversation/<int:partner_id>', methods=['POST'])
def delete_conversation(partner_id):
    if 'user_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        my_id = session['user_id']
        db = get_db()
        if not db:
            raise Exception("Database connection failed")
        cursor = db.cursor()
        cursor.execute("DELETE FROM messages WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s)",
                       (my_id, partner_id, partner_id, my_id))
        db.commit()
        db.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Delete Chat Error: {e}")
        return jsonify({'error': str(e)}), 500

# --- ERROR HANDLERS ---
@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal Server Error', 'details': str(error)}), 500

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Resource Not Found'}), 404

from init_db import init_db

# Initialize DB (Auto-create tables on Gunicorn startup)
try:
    print("Auto-initializing database...")
    init_db()
except Exception as e:
    print(f"Skipping auto-init (likely build step or connection error): {e}")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
