from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.db import mongo
import bcrypt
import random
from datetime import datetime


auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        role = request.form.get('role', 'patient')

        # Basic validation
        if not email or not password:
            flash('Email and password are required', 'danger')
            return redirect(url_for('auth.register'))

        # Check if user exists
        existing_user = mongo.db.users.find_one({'email': email})
        if existing_user:
            flash('Email already registered', 'danger')
            return redirect(url_for('auth.login'))

        # Hash password
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Create user document
        new_user = {
            'email': email,
            'password': hashed_pw,
            'role': role,
            'is_verified': True,
            'created_at': datetime.utcnow()
        }

        user_id = mongo.db.users.insert_one(new_user).inserted_id

        # If registering as a doctor, create an empty doctor profile
        if role == 'doctor':
            name = request.form.get('name', 'Dr. Name')
            specialization = request.form.get('specialization', 'General')
            location = request.form.get('location', 'Location')
            hospital = request.form.get('hospital', 'Hospital')
            
            mongo.db.doctors.insert_one({
                '_id': user_id,
                'name': name,
                'specialization': specialization,
                'location': location,
                'hospital': hospital,
                'qualifications': [],
                'experience': 0,
                'reviews': [],
                'rating': 0
            })

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')



@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        user = mongo.db.users.find_one({'email': email})

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['user_id'] = str(user['_id'])
            session['email'] = user['email']
            session['role'] = user['role']

            flash('Logged in successfully.', 'success')
            if user['role'] == 'doctor':
                return redirect(url_for('doctor.dashboard'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('patient.dashboard'))
        else:
            flash('Invalid email or password', 'danger')

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
