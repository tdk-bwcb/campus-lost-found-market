from flask import render_template, redirect, url_for, request, flash, make_response
from flask_login import login_required, current_user
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image, ImageStat
import re

from . import marketplace_bp
import models  # Use local models module
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS, MAX_IMAGE_SIZE, QUALITY, allowed_file

@marketplace_bp.route('/')
@login_required
def dashboard():
    # Get all marketplace items
    items = models.get_marketplace_items('date DESC')
    
    # Calculate statistics
    total_items = len(items)
    total_available = sum(1 for i in items if i['status'] == 'available')
    total_sold = sum(1 for i in items if i['status'] == 'sold')
    recent_items = items[:10]
    
    # Get categories for filtering
    categories = models.get_categories('marketplace')
    
    return render_template('marketplace/dashboard.html', 
                           user=models.get_user_by_id(current_user.id),
                           items=items,
                           total_items=total_items, 
                           total_available=total_available,
                           total_sold=total_sold, 
                           recent_items=recent_items,
                           categories=categories)

@marketplace_bp.route('/item/<int:item_id>')
def item_detail(item_id):
    item = models.get_marketplace_item(item_id)
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('marketplace.dashboard'))
    
    # Always supply a user dict for template; default non-admin
    if current_user.is_authenticated:
        user = models.get_user_by_id(current_user.id)
    else:
        user = {'is_admin': 0}

    feedback = models.get_feedback_for_item('marketplace', item_id)
    return render_template('marketplace/detail.html', item=item, feedback=feedback, user=user)

@marketplace_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    # Check if user is temporary
    user = models.get_user_by_id(current_user.id)
    if user and user['username'] == 'temp':
        flash('You need to create an account to list items for sale', 'warning')
        return redirect(url_for('auth.register'))
    
    if request.method == 'POST':
        form = request.form
        file = request.files.get('image')
        
        # Process image upload
        if file and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            dest_folder = UPLOAD_FOLDER
            os.makedirs(dest_folder, exist_ok=True)
            
            # Resize and optimize image
            img = Image.open(file)
            orig_w, orig_h = img.size
            tgt_w, tgt_h = MAX_IMAGE_SIZE
            ratio = min(tgt_w / orig_w, tgt_h / orig_h)
            new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            
            # Create background
            bg_color = tuple(int(c) for c in ImageStat.Stat(img).mean[:3])
            final = Image.new('RGB', (tgt_w, tgt_h), bg_color)
            final.paste(img, ((tgt_w - new_w) // 2, (tgt_h - new_h) // 2))
            
            # Save image
            fullpath = os.path.join(dest_folder, fn)
            final.save(fullpath, quality=QUALITY)
            img_path = f"/images/{fn}"
        else:
            flash('Invalid file format. Only JPG, PNG, JPEG and WEBP are allowed.', 'danger')
            return redirect(url_for('marketplace.create'))
        
        # Create item data
        item_data = {
            'name': form['name'],
            'description': form['description'],
            'price': form['price'],
            'category': form['category'],
            'condition': form['condition'],
            'image_path': img_path,
            'location': form['location'],
            'contact_info': form['contact_info'],
            'user_id': current_user.id,
            'status': 'available'
        }
        
        # Save to database
        item_id = models.create_marketplace_item(item_data)
        if item_id:
            flash('Item listed successfully!', 'success')
            return redirect(url_for('marketplace.dashboard'))
        else:
            flash('Error creating listing. Please try again.', 'danger')
    
    # Get categories for the form
    categories = models.get_categories('marketplace')
    return render_template('marketplace/create.html', categories=categories)

@marketplace_bp.route('/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    # Get the item
    item = models.get_marketplace_item(item_id)
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('marketplace.dashboard'))
    
    # Check if user is authorized
    user = models.get_user_by_id(current_user.id)
    if not (item['user_id'] == current_user.id or user['is_admin']):
        flash('You are not authorized to edit this item', 'danger')
        return redirect(url_for('marketplace.dashboard'))
    
    if request.method == 'POST':
        form = request.form
        file = request.files.get('image_path')
        
        # Process image if provided
        if file and file.filename and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            dest_folder = UPLOAD_FOLDER
            os.makedirs(dest_folder, exist_ok=True)
            
            # Resize and optimize image
            img = Image.open(file)
            orig_w, orig_h = img.size
            tgt_w, tgt_h = MAX_IMAGE_SIZE
            ratio = min(tgt_w / orig_w, tgt_h / orig_h)
            new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            
            # Create background
            bg_color = tuple(int(c) for c in ImageStat.Stat(img).mean[:3])
            final = Image.new('RGB', (tgt_w, tgt_h), bg_color)
            final.paste(img, ((tgt_w - new_w) // 2, (tgt_h - new_h) // 2))
            
            # Save image
            fullpath = os.path.join(dest_folder, fn)
            final.save(fullpath, quality=QUALITY)
            img_path = f"/images/{fn}"
            
            # Remove old image if it exists
            if item['image_path']:
                old_path = os.path.join(UPLOAD_FOLDER, os.path.basename(item['image_path']))
                if os.path.exists(old_path):
                    os.remove(old_path)
        else:
            img_path = item['image_path']
        
        # Create item data
        item_data = {
            'name': form['name'],
            'description': form['description'],
            'price': form['price'],
            'category': form['category'],
            'condition': form['condition'],
            'image_path': img_path,
            'location': form['location'],
            'contact_info': form['contact_info'],
            'status': form['status']
        }
        
        # Update item
        if models.update_marketplace_item(item_id, item_data):
            flash('Item updated successfully!', 'success')
            return redirect(url_for('marketplace.item_detail', item_id=item_id))
        else:
            flash('Error updating item. Please try again.', 'danger')
    
    # Get categories for the form
    categories = models.get_categories('marketplace')
    return render_template('marketplace/edit.html', item=item, categories=categories)

@marketplace_bp.route('/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    # Get the item
    item = models.get_marketplace_item(item_id)
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('marketplace.dashboard'))
    
    # Check if user is authorized
    user = models.get_user_by_id(current_user.id)
    if not (item['user_id'] == current_user.id or user['is_admin']):
        flash('You are not authorized to delete this item', 'danger')
        return redirect(url_for('marketplace.dashboard'))
    
    # Delete item
    if models.delete_marketplace_item(item_id):
        # Remove image if it exists
        if item['image_path']:
            path = os.path.join(UPLOAD_FOLDER, os.path.basename(item['image_path']))
            if os.path.exists(path):
                os.remove(path)
                
        flash('Item deleted successfully!', 'success')
    else:
        flash('Error deleting item. Please try again.', 'danger')
    
    return redirect(url_for('marketplace.dashboard'))

@marketplace_bp.route('/buy/<int:item_id>')
@login_required
def buy_item(item_id):
    # Fetch item and ensure it exists
    item = models.get_marketplace_item(item_id)
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('marketplace.dashboard'))
    # Prevent buying own item
    if item['user_id'] == current_user.id:
        flash('You cannot buy your own item', 'warning')
        return redirect(url_for('marketplace.item_detail', item_id=item_id))
    # Get seller details
    seller = models.get_user_by_id(item['user_id']) or {}
    # Prepare seller info content
    content = []
    content.append(f"Seller Details for Item: {item['name']}")
    content.append(f"Username: {seller.get('username', 'N/A')}")
    content.append(f"Email: {seller.get('email', 'N/A')}")
    content.append(f"Contact: {item.get('contact_info', 'N/A')}")
    text = '\n'.join(content)
    # Mark the item as sold
    models.update_marketplace_item(item_id, {'status': 'sold'})
    # Create response as downloadable text file
    response = make_response(text)
    response.headers.set('Content-Disposition', f'attachment; filename=seller_{item_id}.txt')
    response.mimetype = 'text/plain'
    return response