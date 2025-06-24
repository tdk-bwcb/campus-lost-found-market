import sqlite3
from datetime import datetime
import os
import hashlib
from flask_login import UserMixin
from config import DB_PATH

class User(UserMixin):
    def __init__(self, id):
        self.id = id

def get_db_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys and ensure WAL journal mode for better reliability
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn

def init_db():
    """Initialize the database with tables and default data if they don't exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create tables
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE,
            role TEXT DEFAULT 'student',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_admin INTEGER DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS lost_found_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            status TEXT NOT NULL,
            priority INTEGER DEFAULT 1,
            image_path TEXT,
            date TEXT NOT NULL,
            location TEXT,
            contact_info TEXT,
            latitude REAL,
            longitude REAL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user (id)
        );
        
        CREATE TABLE IF NOT EXISTS marketplace_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT,
            condition TEXT,
            status TEXT NOT NULL,
            image_path TEXT,
            date TEXT NOT NULL,
            location TEXT,
            contact_info TEXT,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user (id)
        );
        
        CREATE TABLE IF NOT EXISTS category (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_type TEXT NOT NULL CHECK(item_type IN ('lost_found', 'marketplace')),
            item_id INTEGER NOT NULL,
            comment TEXT,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user(id)
        );
    ''')
    
    # Check if default users exist
    cur.execute('SELECT COUNT(*) FROM user WHERE username IN (?, ?)', ('admin', 'temp'))
    if cur.fetchone()[0] < 2:
        # Add default admin and temp user if they don't exist
        admin_pass = hashlib.sha256('admin123'.encode()).hexdigest()
        temp_pass = hashlib.sha256('temp123'.encode()).hexdigest()
        
        cur.execute(
            'INSERT OR IGNORE INTO user (username, password, email, role, is_admin) VALUES (?, ?, ?, ?, ?)',
            ('admin', admin_pass, 'admin@campushub.com', 'admin', 1)
        )
        cur.execute(
            'INSERT OR IGNORE INTO user (username, password, email, role, is_admin) VALUES (?, ?, ?, ?, ?)',
            ('temp', temp_pass, 'temp@campushub.com', 'guest', 0)
        )
    
    # Check if existing users need the role field
    try:
        cur.execute('SELECT role FROM user LIMIT 1')
    except sqlite3.OperationalError:
        # role column doesn't exist, add it
        cur.execute('ALTER TABLE user ADD COLUMN role TEXT DEFAULT "student"')
        cur.execute('UPDATE user SET role = "admin" WHERE is_admin = 1')
        cur.execute('UPDATE user SET role = "student" WHERE is_admin = 0 AND username != "temp"')
        cur.execute('UPDATE user SET role = "guest" WHERE username = "temp"')
    
    # Check if existing users need the created_at field
    try:
        cur.execute('SELECT created_at FROM user LIMIT 1')
    except sqlite3.OperationalError:
        # created_at column doesn't exist, add it
        cur.execute('ALTER TABLE user ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP')
    
    # Check if existing users need the is_confirmed field
    try:
        cur.execute('SELECT is_confirmed FROM user LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE user ADD COLUMN is_confirmed INTEGER DEFAULT 0')
        cur.execute('UPDATE user SET is_confirmed = 1 WHERE is_admin = 1')
        cur.execute('UPDATE user SET is_confirmed = 1 WHERE username = "temp"')

    # Check if default categories exist
    cur.execute('SELECT COUNT(*) FROM category')
    if cur.fetchone()[0] == 0:
        # Add default categories for lost & found
        lost_found_categories = [
            ('electronics', 'lost_found'),
            ('clothing', 'lost_found'),
            ('accessories', 'lost_found'),
            ('books', 'lost_found'),
            ('documents', 'lost_found'),
            ('keys', 'lost_found'),
            ('other', 'lost_found')
        ]
        
        # Add default categories for marketplace
        market_categories = [
            ('electronics', 'marketplace'),
            ('textbooks', 'marketplace'),
            ('furniture', 'marketplace'),
            ('clothing', 'marketplace'),
            ('services', 'marketplace'),
            ('tickets', 'marketplace'),
            ('free', 'marketplace'),
            ('other', 'marketplace')
        ]
        
        # Insert all categories
        for name, type in lost_found_categories + market_categories:
            cur.execute('INSERT INTO category (name, type) VALUES (?, ?)', (name, type))

    # Add columns for tracking finder and claimer on lost_found_item
    try:
        cur.execute('SELECT found_by FROM lost_found_item LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE lost_found_item ADD COLUMN found_by INTEGER')
    try:
        cur.execute('SELECT claimed_by FROM lost_found_item LIMIT 1')
    except sqlite3.OperationalError:
        cur.execute('ALTER TABLE lost_found_item ADD COLUMN claimed_by INTEGER')

    conn.commit()
    conn.close()

# User management functions
def create_user(username, email, password):
    """Create a new user in the database."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Hash the password for security
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        cur.execute(
            'INSERT INTO user (username, password, email, role, created_at) VALUES (?, ?, ?, ?, ?)',
            (username, hashed_password, email, 'student', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        # Username or email already exists
        return False
    finally:
        conn.close()

def verify_user(username, password):
    """Verify user credentials and return user data if valid."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Hash the provided password for comparison
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    cur.execute(
        'SELECT * FROM user WHERE username = ? AND password = ?',
        (username, hashed_password)
    )
    user = cur.fetchone()
    conn.close()
    
    return dict(user) if user else None

def get_user_by_id(user_id):
    """Get a user by their ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM user WHERE id = ?', (user_id,))
    user = cur.fetchone()
    conn.close()
    
    return dict(user) if user else None

def get_user_by_username(username):
    """Get a user by their username."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM user WHERE username = ?', (username,))
    user = cur.fetchone()
    conn.close()
    
    return dict(user) if user else None

def get_user_by_email(email):
    """Get a user by their email."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM user WHERE email = ?', (email,))
    user = cur.fetchone()
    conn.close()
    
    return dict(user) if user else None

def confirm_user(user_id):
    """Mark a user's email as confirmed."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE user SET is_confirmed = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

# Category functions
def get_categories(type=None):
    """Get all categories or by type."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if type:
        cur.execute('SELECT * FROM category WHERE type = ?', (type,))
    else:
        cur.execute('SELECT * FROM category')
        
    categories = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    return categories

# Lost & Found item functions
def create_lost_found_item(item_data):
    """Create a new lost & found item."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Add current date if not provided
    if 'date' not in item_data or not item_data['date']:
        item_data['date'] = datetime.now().strftime('%Y-%m-%d')
    
    try:
        cur.execute('''
            INSERT INTO lost_found_item (
                name, description, category, status, priority, image_path, 
                date, location, contact_info, latitude, longitude, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item_data['name'], 
            item_data.get('description'), 
            item_data.get('category'),
            item_data['status'],
            item_data.get('priority', 1),
            item_data.get('image_path'),
            item_data['date'],
            item_data.get('location'),
            item_data.get('contact_info'),
            item_data.get('latitude'),
            item_data.get('longitude'),
            item_data['user_id']
        ))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        print(f"Error creating lost & found item: {e}")
        return False
    finally:
        conn.close()

def get_lost_found_items(order_by=None, filters=None):
    """Get lost & found items with optional ordering and filtering."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = '''
        SELECT i.*, u.username 
        FROM lost_found_item i
        JOIN user u ON i.user_id = u.id
    '''
    
    params = []
    
    if filters:
        conditions = []
        for key, value in filters.items():
            conditions.append(f"i.{key} = ?")
            params.append(value)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
    
    if order_by:
        query += f" ORDER BY i.{order_by}"
    
    cur.execute(query, params)
    items = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    return items

def get_lost_found_item(item_id):
    """Get a specific lost & found item by ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT i.*, u.username 
        FROM lost_found_item i
        JOIN user u ON i.user_id = u.id
        WHERE i.id = ?
    ''', (item_id,))
    
    item = cur.fetchone()
    conn.close()
    
    return dict(item) if item else None

def update_lost_found_item(item_id, item_data):
    """Update an existing lost & found item."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Prepare update fields and values
    update_fields = []
    update_values = []
    
    for key, value in item_data.items():
        update_fields.append(f"{key} = ?")
        update_values.append(value)
    
    # Add item_id to values
    update_values.append(item_id)
    
    try:
        query = f"UPDATE lost_found_item SET {', '.join(update_fields)} WHERE id = ?"
        cur.execute(query, update_values)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating lost & found item: {e}")
        return False
    finally:
        conn.close()

def delete_lost_found_item(item_id):
    """Delete a lost & found item by ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute('DELETE FROM lost_found_item WHERE id = ?', (item_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting lost & found item: {e}")
        return False
    finally:
        conn.close()

# Marketplace item functions
def create_marketplace_item(item_data):
    """Create a new marketplace item."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Add current date if not provided
    if 'date' not in item_data or not item_data['date']:
        item_data['date'] = datetime.now().strftime('%Y-%m-%d')
    
    try:
        print(f"DEBUG - Inserting marketplace item: {item_data['name']}")
        cur.execute('''
            INSERT INTO marketplace_item (
                name, description, price, category, condition, status, 
                image_path, date, location, contact_info, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item_data['name'], 
            item_data.get('description'), 
            item_data['price'],
            item_data.get('category'),
            item_data.get('condition'),
            item_data['status'],
            item_data.get('image_path'),
            item_data['date'],
            item_data.get('location'),
            item_data.get('contact_info'),
            item_data['user_id']
        ))
        conn.commit()
        item_id = cur.lastrowid
        print(f"DEBUG - Marketplace item created with ID: {item_id}")
        
        # Verify insertion
        cur.execute('SELECT * FROM marketplace_item WHERE id = ?', (item_id,))
        item = cur.fetchone()
        if item:
            print(f"DEBUG - Item verification successful: {dict(item)}")
        else:
            print(f"DEBUG - Item verification failed - No item found with ID: {item_id}")
        
        return item_id
    except Exception as e:
        print(f"ERROR creating marketplace item: {e}")
        return False
    finally:
        conn.close()

def get_marketplace_items(order_by=None, filters=None):
    """Get marketplace items with optional ordering and filtering."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = '''
        SELECT i.*, u.username 
        FROM marketplace_item i
        JOIN user u ON i.user_id = u.id
    '''
    
    params = []
    
    if filters:
        conditions = []
        for key, value in filters.items():
            conditions.append(f"i.{key} = ?")
            params.append(value)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
    
    if order_by:
        query += f" ORDER BY i.{order_by}"
    
    print(f"DEBUG - Executing marketplace query: {query}")
    cur.execute(query, params)
    items = [dict(row) for row in cur.fetchall()]
    print(f"DEBUG - Found {len(items)} marketplace items")
    
    # Also check directly using a separate query for verification
    cur.execute("SELECT COUNT(*) FROM marketplace_item")
    count = cur.fetchone()[0]
    print(f"DEBUG - Direct count of marketplace_item table: {count}")
    
    conn.close()
    
    return items

def get_marketplace_item(item_id):
    """Get a specific marketplace item by ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT i.*, u.username 
        FROM marketplace_item i
        JOIN user u ON i.user_id = u.id
        WHERE i.id = ?
    ''', (item_id,))
    
    item = cur.fetchone()
    conn.close()
    
    return dict(item) if item else None

def update_marketplace_item(item_id, item_data):
    """Update an existing marketplace item."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Prepare update fields and values
    update_fields = []
    update_values = []
    
    for key, value in item_data.items():
        update_fields.append(f"{key} = ?")
        update_values.append(value)
    
    # Add item_id to values
    update_values.append(item_id)
    
    try:
        query = f"UPDATE marketplace_item SET {', '.join(update_fields)} WHERE id = ?"
        cur.execute(query, update_values)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating marketplace item: {e}")
        return False
    finally:
        conn.close()

def delete_marketplace_item(item_id):
    """Delete a marketplace item by ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute('DELETE FROM marketplace_item WHERE id = ?', (item_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting marketplace item: {e}")
        return False
    finally:
        conn.close()

def create_feedback(user_id, item_type, item_id, comment):
    """Add a feedback comment for lost_found or marketplace item"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            'INSERT INTO feedback (user_id, item_type, item_id, comment) VALUES (?, ?, ?, ?)',
            (user_id, item_type, item_id, comment)
        )
        conn.commit()
        return cur.lastrowid
    except Exception:
        return False
    finally:
        conn.close()


def get_feedback_for_item(item_type, item_id):
    """Retrieve feedback comments for a specific item"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'SELECT f.*, u.username FROM feedback f JOIN user u ON f.user_id = u.id WHERE f.item_type = ? AND f.item_id = ? ORDER BY date DESC',
        (item_type, item_id)
    )
    feedback = [dict(row) for row in cur.fetchall()]
    conn.close()
    return feedback