from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image, ImageStat
import re
from flask_mail import Message
from extensions import mail
from config import MAIL_USERNAME

from . import lost_and_found_bp
import models
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS, MAX_IMAGE_SIZE, QUALITY, allowed_file

@lost_and_found_bp.route('/')
@login_required
def dashboard():
    # Get all lost and found items
    items = models.get_lost_found_items('date DESC')
    # Attach finder/claimer usernames
    for item in items:
        if item.get('found_by'):
            item['found_by_user'] = models.get_user_by_id(item['found_by'])['username']
        else:
            item['found_by_user'] = None
        if item.get('claimed_by'):
            item['claimed_by_user'] = models.get_user_by_id(item['claimed_by'])['username']
        else:
            item['claimed_by_user'] = None
    items_prior = models.get_lost_found_items('priority DESC')
    
    # Calculate statistics
    total_items = len(items)
    total_lost = sum(1 for i in items if i['status'] == 'lost')
    total_found = sum(1 for i in items if i['status'] == 'found')
    recent_items = items_prior[:10]
    
    # Get categories for filtering
    categories = models.get_categories('lost_found')
    
    return render_template('lost_and_found/dashboard.html', 
                           user=models.get_user_by_id(current_user.id),
                           items=items,
                           total_items=total_items, 
                           total_lost=total_lost,
                           total_found=total_found, 
                           recent_items=recent_items,
                           categories=categories)

@lost_and_found_bp.route('/item/<int:item_id>')
@login_required
def item_detail(item_id):
    # Fetch item and current user info
    item = models.get_lost_found_item(item_id)
    feedback = models.get_feedback_for_item('lost_found', item_id)
    user = models.get_user_by_id(current_user.id)
    # Track who found or claimed
    found_by_user = None
    claimed_by_user = None
    if item.get('found_by'):
        found_by_user = models.get_user_by_id(item['found_by'])['username']
    if item.get('claimed_by'):
        claimed_by_user = models.get_user_by_id(item['claimed_by'])['username']
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('lost_and_found.dashboard'))
    return render_template('lost_and_found/detail.html', item=item, feedback=feedback, user=user, found_by_user=found_by_user, claimed_by_user=claimed_by_user)

@lost_and_found_bp.route('/new', methods=['GET', 'POST'])
@login_required
def report():
    # Check if user is temporary
    user = models.get_user_by_id(current_user.id)
    if user and user['username'] == 'temp':
        flash('You need to create an account to report items', 'warning')
        return redirect(url_for('auth.register'))
    
    if request.method == 'POST':
        form = request.form
        # Validate phone number contact
        contact = form.get('contact_info', '').strip()
        if not re.fullmatch(r"\d{10}", contact):
            flash('Contact info must be a 10-digit phone number', 'danger')
            return redirect(url_for('lost_and_found.report'))
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
            return redirect(url_for('lost_and_found.report'))
        
        # Create item data
        item_data = {
            'priority': form['priority'],
            'name': form['name'],
            'description': form['description'],
            'category': form['category'],
            'status': form['status'],
            'image_path': img_path,
            'date': form['date'],
            'location': form['location'],
            'contact_info': form['contact_info'],
            'latitude': form.get('latitude'),
            'longitude': form.get('longitude'),
            'user_id': current_user.id
        }
        
        # Save to database
        item_id = models.create_lost_found_item(item_data)
        if item_id:
            flash('Report submitted successfully!', 'success')
            return redirect(url_for('lost_and_found.dashboard'))
        else:
            flash('Error creating report. Please try again.', 'danger')
    
    # Get categories for the form
    categories = models.get_categories('lost_found')
    return render_template('lost_and_found/report.html', categories=categories)

@lost_and_found_bp.route('/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    # Get the item
    item = models.get_lost_found_item(item_id)
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('lost_and_found.dashboard'))
    
    # Check if user is authorized
    user = models.get_user_by_id(current_user.id)
    if not (item['user_id'] == current_user.id or user['is_admin']):
        flash('You are not authorized to edit this item', 'danger')
        return redirect(url_for('lost_and_found.dashboard'))
    
    if request.method == 'POST':
        form = request.form
        # Validate phone number contact
        contact = form.get('contact_info', '').strip()
        if not re.fullmatch(r"\d{10}", contact):
            flash('Contact info must be a 10-digit phone number', 'danger')
            return redirect(url_for('lost_and_found.edit_item', item_id=item_id))
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
            'priority': form['priority'],
            'name': form['name'],
            'description': form['description'],
            'category': form['category'],
            'status': form['status'],
            'image_path': img_path,
            'location': form['location'],
            'contact_info': form['contact_info']
        }
        # Clear tags if status changed
        if form['status'] != 'found':
            item_data['found_by'] = None
        if form['status'] != 'claimed':
            item_data['claimed_by'] = None
        # Update item
        if models.update_lost_found_item(item_id, item_data):
            flash('Item updated successfully!', 'success')
            return redirect(url_for('lost_and_found.item_detail', item_id=item_id))
        else:
            flash('Error updating item. Please try again.', 'danger')
    
    # Get categories for the form
    categories = models.get_categories('lost_found')
    return render_template('lost_and_found/edit.html', item=item, categories=categories)

@lost_and_found_bp.route('/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    # Get the item
    item = models.get_lost_found_item(item_id)
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('lost_and_found.dashboard'))
    
    # Check if user is authorized
    user = models.get_user_by_id(current_user.id)
    if not (item['user_id'] == current_user.id or user['is_admin']):
        flash('You are not authorized to delete this item', 'danger')
        return redirect(url_for('lost_and_found.dashboard'))
    
    # Delete item
    if models.delete_lost_found_item(item_id):
        # Remove image if it exists
        if item['image_path']:
            path = os.path.join(UPLOAD_FOLDER, os.path.basename(item['image_path']))
            if os.path.exists(path):
                os.remove(path)
                
        flash('Item deleted successfully!', 'success')
    else:
        flash('Error deleting item. Please try again.', 'danger')
    
    return redirect(url_for('lost_and_found.dashboard'))

# Claim a found item and notify owner
@lost_and_found_bp.route('/item/<int:item_id>/claim', methods=['POST'])
@login_required
def claim_item(item_id):
    item = models.get_lost_found_item(item_id)
    if not item or item['status'] != 'found':
        flash('Invalid operation.', 'danger')
        return redirect(url_for('lost_and_found.item_detail', item_id=item_id))
    if item['user_id'] == current_user.id:
        flash('Cannot claim your own item.', 'warning')
        return redirect(url_for('lost_and_found.item_detail', item_id=item_id))
    # Update status, record who claimed, preserve category
    update_data = {'status': 'claimed', 'claimed_by': current_user.id, 'category': item['category']}
    if models.update_lost_found_item(item_id, update_data):
        owner = models.get_user_by_id(item['user_id'])
        claimer = models.get_user_by_id(current_user.id)
        msg = Message('Your item has been claimed', sender=MAIL_USERNAME, recipients=[owner['email']])
        msg.body = f"{claimer['username']} has claimed your item '{item['name']}'."
        try:
            mail.send(msg)
            flash('Item claimed and email sent!', 'success')
        except Exception:
            flash(f"Item claimed. Could not send email automatically. Owner: {owner['email']}", 'warning')
    else:
        flash('Error claiming item.', 'danger')
    return redirect(url_for('lost_and_found.item_detail', item_id=item_id))

# Notify owner that lost item is found
@lost_and_found_bp.route('/item/<int:item_id>/found_user', methods=['POST'])
@login_required
def found_user(item_id):
    item = models.get_lost_found_item(item_id)
    if not item or item['status'] != 'lost':
        flash('Invalid operation.', 'danger')
        return redirect(url_for('lost_and_found.item_detail', item_id=item_id))
    if item['user_id'] == current_user.id:
        flash('Cannot mark your own item as found.', 'warning')
        return redirect(url_for('lost_and_found.item_detail', item_id=item_id))
    # Record who found the lost item and preserve category/status
    update_data = {
        'found_by': current_user.id,
        'category': item['category']
    }
    models.update_lost_found_item(item_id, update_data)
    owner = models.get_user_by_id(item['user_id'])
    finder = models.get_user_by_id(current_user.id)
    msg = Message('Your lost item has been found', sender=MAIL_USERNAME, recipients=[owner['email']])
    msg.body = f"{finder['username']} has found your lost item '{item['name']}'."
    try:
        mail.send(msg)
        flash('Notification email sent to owner!', 'success')
    except Exception:
        flash(f"Could not send email automatically. Owner: {owner['email']}", 'warning')
    return redirect(url_for('lost_and_found.item_detail', item_id=item_id))

# Route to remove a claim on a found item
@lost_and_found_bp.route('/item/<int:item_id>/remove_claim', methods=['POST'])
@login_required
def remove_claim(item_id):
    item = models.get_lost_found_item(item_id)
    user = models.get_user_by_id(current_user.id)
    # Only owner or admin can remove claim
    if not item or not (item['user_id'] == current_user.id or user['is_admin']):
        flash('Not authorized to remove claim.', 'danger')
        return redirect(url_for('lost_and_found.dashboard'))
    # Only remove for claimed items
    if item['status'] != 'claimed':
        flash('Item is not claimed.', 'warning')
        return redirect(url_for('lost_and_found.dashboard'))
    # Reset status and clear claimer
    if models.update_lost_found_item(item_id, {'status': 'found', 'claimed_by': None}):
        flash('Claim removed; item status set back to Found.', 'success')
    else:
        flash('Error removing claim.', 'danger')
    return redirect(url_for('lost_and_found.dashboard'))

# Route to remove the 'found by' tag and revert to lost
@lost_and_found_bp.route('/item/<int:item_id>/remove_found', methods=['POST'])
@login_required
def remove_found(item_id):
    item = models.get_lost_found_item(item_id)
    user = models.get_user_by_id(current_user.id)
    # Only owner or admin can remove found tag
    if not item or not (item['user_id'] == current_user.id or user['is_admin']):
        flash('Not authorized to remove found tag.', 'danger')
        return redirect(url_for('lost_and_found.dashboard'))
    # Only if a found_by tag exists
    if not item.get('found_by'):
        flash('No found tag to remove.', 'warning')
        return redirect(url_for('lost_and_found.item_detail', item_id=item_id))
    # Clear found_by tag but keep status and category unchanged
    update_data = {'found_by': None, 'status': item['status'], 'category': item['category']}
    if models.update_lost_found_item(item_id, update_data):
        flash('Found tag removed.', 'success')
    else:
        flash('Error removing found tag.', 'danger')
    # Redirect back to whatever page the form was submitted from
    return redirect(request.referrer or url_for('lost_and_found.dashboard'))