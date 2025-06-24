from flask import render_template, redirect, url_for, request, flash, make_response
from flask_login import login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import hashlib
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_mail import Message
from extensions import mail
from config import SECRET_KEY, MAIL_USERNAME

from . import auth_bp
import models

serializer = URLSafeTimedSerializer(SECRET_KEY)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('lost_and_found.dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = models.verify_user(username, password)
        # Prevent login if email not confirmed
        if user and not user.get('is_confirmed', 0):
            flash('Please confirm your email before logging in.', 'warning')
            return redirect(url_for('auth.login'))
        if user:
            login_user(models.User(user['id']))
            next_page = request.args.get('next')
            return redirect(next_page or url_for('lost_and_found.dashboard'))
        
        flash('Invalid username or password', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/continue_without_login')
def continue_without_login():
    user = models.get_user_by_username('temp')
    if user:
        login_user(models.User(user['id']))
        return redirect(url_for('lost_and_found.dashboard'))
    
    flash('Temporary user does not exist!', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('lost_and_found.dashboard'))
    
    cookie = request.cookies.get('rate_limit')
    if request.method == 'POST' and cookie:
        last = datetime.strptime(cookie, '%Y-%m-%d %H:%M:%S')
        if datetime.now() - last < timedelta(seconds=60):
            flash('Rate-limited. Wait a minute.', 'warning')
            return redirect(url_for('auth.register'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash("Passwords don't match.", 'danger')
            return redirect(url_for('auth.register'))
        
        user_id = models.create_user(username, email, password)
        if user_id:
            # Send confirmation email
            token = serializer.dumps(email, salt='email-confirm')
            confirm_url = url_for('auth.confirm_email', token=token, _external=True)
            # Log confirmation URL for offline testing
            print(f'Confirmation URL: {confirm_url}')
            msg = Message('Confirm Your Email', sender=MAIL_USERNAME, recipients=[email])
            msg.body = f'Please click the link to confirm your email: {confirm_url}'
            try:
                mail.send(msg)
                flash('A confirmation email has been sent. Please check your inbox.', 'info')
            except Exception:
                # Fallback: show confirmation link to user
                flash(f'Registration successful. Please confirm using this link: {confirm_url}', 'warning')
            # Ensure no user remains logged in until confirmation
            logout_user()
            resp = make_response(redirect(url_for('auth.login')))
            resp.set_cookie('rate_limit', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            return resp
        else:
            flash('Username or email already exists.', 'warning')
    
    return render_template('auth/register.html')

@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    # Ensure no one is auto-logged in before confirmation
    logout_user()
    try:
        email = serializer.loads(token, salt='email-confirm', max_age=3600)
    except SignatureExpired:
        flash('The confirmation link has expired.', 'danger')
        return redirect(url_for('auth.register'))
    except BadSignature:
        flash('Invalid confirmation token.', 'danger')
        return redirect(url_for('auth.register'))
    user = models.get_user_by_email(email)
    if not user:
        flash('User not found.', 'danger')
    elif user.get('is_confirmed'):
        flash('Account already confirmed.', 'info')
    else:
        models.confirm_user(user['id'])
        flash('Your email has been confirmed! You can now log in.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = models.get_user_by_id(current_user.id)
    
    # Add created_at and role for the template
    if user and 'created_at' not in user:
        user['created_at'] = datetime.now().strftime('%B %Y')  # Default value
    if user and 'role' not in user:
        user['role'] = 'student'  # Default value
    
    # Get all lost and found items posted by this user
    lost_found_items = models.get_lost_found_items(filters={'user_id': current_user.id})
    
    # Get all marketplace items posted by this user
    marketplace_items = models.get_marketplace_items(filters={'user_id': current_user.id})
    
    # Get recent items for the dashboard tab
    recent_items = []
    # Add lost and found items with type indicator
    for item in lost_found_items[:5]:
        item['type'] = 'lost_found'
        recent_items.append(item)
    
    # Add marketplace items with type indicator
    for item in marketplace_items[:5]:
        item['type'] = 'marketplace'
        recent_items.append(item)
    
    # Sort by date (newest first)
    recent_items.sort(key=lambda x: x['date'], reverse=True)
    recent_items = recent_items[:10]  # Limit to 10 items
    
    if request.method == 'POST':
        # Handle deletion of lost and found items
        if request.form.get('lost_found_id'):
            item_id = request.form.get('lost_found_id')
            item = models.get_lost_found_item(item_id)
            
            if item and (item['user_id'] == current_user.id or user['is_admin']):
                if models.delete_lost_found_item(item_id):
                    flash('Item deleted successfully.', 'success')
                else:
                    flash('Failed to delete item.', 'danger')
            else:
                flash('You are not authorized to delete this item.', 'danger')
                
            return redirect(url_for('auth.profile'))
            
        # Handle deletion of marketplace items
        if request.form.get('market_id'):
            item_id = request.form.get('market_id')
            item = models.get_marketplace_item(item_id)
            
            if item and (item['user_id'] == current_user.id or user['is_admin']):
                if models.delete_marketplace_item(item_id):
                    flash('Item deleted successfully.', 'success')
                else:
                    flash('Failed to delete item.', 'danger')
            else:
                flash('You are not authorized to delete this item.', 'danger')
                
            return redirect(url_for('auth.profile'))
    
    return render_template('auth/profile.html', user=user, 
                          lost_found_items=lost_found_items, 
                          marketplace_items=marketplace_items,
                          recent_items=recent_items)

@auth_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user = models.get_user_by_id(current_user.id)
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('auth.profile'))
    
    # Get form data
    username = request.form.get('username')
    email = request.form.get('email')
    role = request.form.get('role')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Prepare update data
    update_data = {}
    
    # Update username if changed and not already taken
    if username != user['username']:
        existing_user = models.get_user_by_username(username)
        if existing_user and existing_user['id'] != user['id']:
            flash('Username already taken', 'danger')
            return redirect(url_for('auth.profile'))
        update_data['username'] = username
    
    # Update email if changed
    if email != user['email']:
        update_data['email'] = email
    
    # Update role if provided
    if role:
        update_data['role'] = role
    
    # Update password if provided
    if current_password and new_password:
        if new_password != confirm_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('auth.profile'))
        
        # Verify current password
        hashed_current = hashlib.sha256(current_password.encode()).hexdigest()
        if hashed_current != user['password']:
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('auth.profile'))
        
        # Update password
        hashed_new = hashlib.sha256(new_password.encode()).hexdigest()
        update_data['password'] = hashed_new
    
    # Update user in database if there are changes
    if update_data:
        if update_user_profile(user['id'], update_data):
            flash('Profile updated successfully', 'success')
        else:
            flash('Error updating profile', 'danger')
    else:
        flash('No changes made', 'info')
    
    return redirect(url_for('auth.profile'))

def update_user_profile(user_id, update_data):
    """Update user profile in database."""
    conn = models.get_db_connection()
    cur = conn.cursor()
    
    # Prepare update fields and values
    update_fields = []
    update_values = []
    
    for key, value in update_data.items():
        update_fields.append(f"{key} = ?")
        update_values.append(value)
    
    # Add user_id to values
    update_values.append(user_id)
    
    try:
        query = f"UPDATE user SET {', '.join(update_fields)} WHERE id = ?"
        cur.execute(query, update_values)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating user profile: {e}")
        return False
    finally:
        conn.close()