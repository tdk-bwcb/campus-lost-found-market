from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, make_response
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import sqlite3
import os
from werkzeug.utils import secure_filename
from PIL import Image, ImageStat
import logging

# Import configuration
from config import SECRET_KEY, UPLOAD_FOLDER, DB_PATH, ALLOWED_EXTENSIONS, MAX_IMAGE_SIZE, QUALITY, MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_USE_TLS, MAIL_USE_SSL, SESSION_TYPE, SESSION_FILE_DIR, SESSION_PERMANENT

# Import models
import models

# Configuration
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)
# Mail configuration
app.config.update(
    MAIL_SERVER=MAIL_SERVER,
    MAIL_PORT=MAIL_PORT,
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=MAIL_PASSWORD,
    MAIL_USE_TLS=MAIL_USE_TLS,
    MAIL_USE_SSL=MAIL_USE_SSL
)
# Initialize Flask-Mail via extensions
from extensions import mail
mail.init_app(app)

# Configure Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

# Initialize session support
from flask_session import Session
sess = Session()
app.config['SESSION_TYPE'] = SESSION_TYPE
app.config['SESSION_FILE_DIR'] = SESSION_FILE_DIR
app.config['SESSION_PERMANENT'] = SESSION_PERMANENT
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
sess.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    user = models.get_user_by_id(user_id)
    if user:
        return models.User(user['id'])
    return None

# Import blueprints after app creation to avoid circular imports
from blueprints.auth import auth_bp
from blueprints.lost_and_found import lost_and_found_bp
from blueprints.marketplace import marketplace_bp

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(lost_and_found_bp)
app.register_blueprint(marketplace_bp)

@app.route('/')
def index():
    """Redirect to the most appropriate page based on login status"""
    if current_user.is_authenticated:
        return redirect(url_for('lost_and_found.dashboard'))
    return redirect(url_for('auth.login'))

# Context processor to inject user info into templates
@app.context_processor
def inject_user_info():
    if current_user.is_authenticated:
        user = models.get_user_by_id(current_user.id)
        if user:
            return {'get_user_info': lambda: user}
    return {'get_user_info': lambda: None}

# Handle 404 errors
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Handle 500 errors
@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Ensure database is initialized
    models.init_db()
    
    # Create upload folder if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    app.run(debug=True)
