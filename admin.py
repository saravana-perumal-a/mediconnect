from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.db import mongo
from bson import ObjectId
import bcrypt
from functools import wraps
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ── Hardcoded Admin Credentials ──────────────────────────────
ADMIN_EMAIL    = 'admin@mediconnect.com'
ADMIN_PASSWORD = 'Admin@1234'

# ── Auth Guard ────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated

# ── Admin Login ───────────────────────────────────────────────
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('role') == 'admin':
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        # Check Hardcoded Admin
        if email == ADMIN_EMAIL.lower() and password == ADMIN_PASSWORD:
            session['role']       = 'admin'
            session['email']      = email
            session['user_id']    = 'admin'
            flash('Welcome, Admin!', 'success')
            return redirect(url_for('admin.dashboard'))
        
        # Check Database for Registered Admins
        user = mongo.db.users.find_one({'email': email, 'role': 'admin'})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['role']       = 'admin'
            session['email']      = email
            session['user_id']    = str(user['_id'])
            flash('Welcome, Admin!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid admin credentials.', 'danger')

    return render_template('admin_login.html')

# ── Admin Logout ──────────────────────────────────────────────
@admin_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('admin.login'))

# ── Dashboard ─────────────────────────────────────────────────
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    total_patients     = mongo.db.users.count_documents({'role': 'patient'})
    total_doctors      = mongo.db.users.count_documents({'role': 'doctor'})
    total_appointments = mongo.db.appointments.count_documents({})
    booked             = mongo.db.appointments.count_documents({'status': 'booked'})
    cancelled          = mongo.db.appointments.count_documents({'status': 'cancelled'})
    completed          = mongo.db.appointments.count_documents({'status': 'completed'})

    # Recent 5 appointments
    recent_appts = list(mongo.db.appointments.find().sort('_id', -1).limit(5))
    for a in recent_appts:
        doc = mongo.db.doctors.find_one({'_id': a.get('doctor_id')})
        pat = mongo.db.users.find_one({'_id': a.get('patient_id')})
        a['doctor_name']  = doc['name']  if doc else 'Unknown'
        a['patient_email'] = pat['email'] if pat else 'Unknown'

    return render_template('admin_dashboard.html',
        total_patients=total_patients,
        total_doctors=total_doctors,
        total_appointments=total_appointments,
        booked=booked,
        cancelled=cancelled,
        completed=completed,
        recent_appts=recent_appts
    )

# ── Manage Patients ───────────────────────────────────────────
@admin_bp.route('/patients')
@admin_required
def patients():
    patients = list(mongo.db.users.find({'role': 'patient'}))
    for p in patients:
        p['appt_count'] = mongo.db.appointments.count_documents({'patient_id': p['_id']})
    return render_template('admin_patients.html', patients=patients)

@admin_bp.route('/patients/delete/<patient_id>', methods=['POST'])
@admin_required
def delete_patient(patient_id):
    mongo.db.users.delete_one({'_id': ObjectId(patient_id)})
    mongo.db.appointments.delete_many({'patient_id': ObjectId(patient_id)})
    flash('Patient deleted successfully.', 'success')
    return redirect(url_for('admin.patients'))

# ── Manage Doctors ────────────────────────────────────────────
@admin_bp.route('/doctors')
@admin_required
def doctors():
    doctors = list(mongo.db.doctors.find())
    for d in doctors:
        d['appt_count'] = mongo.db.appointments.count_documents({'doctor_id': d['_id']})
        user = mongo.db.users.find_one({'_id': d['_id']})
        d['email'] = user['email'] if user else 'N/A'
    return render_template('admin_doctors.html', doctors=doctors)

@admin_bp.route('/doctors/delete/<doctor_id>', methods=['POST'])
@admin_required
def delete_doctor(doctor_id):
    mongo.db.doctors.delete_one({'_id': ObjectId(doctor_id)})
    mongo.db.users.delete_one({'_id': ObjectId(doctor_id)})
    mongo.db.slots.delete_many({'doctor_id': ObjectId(doctor_id)})
    mongo.db.appointments.delete_many({'doctor_id': ObjectId(doctor_id)})
    flash('Doctor deleted successfully.', 'success')
    return redirect(url_for('admin.doctors'))

@admin_bp.route('/doctors/edit/<doctor_id>', methods=['GET', 'POST'])
@admin_required
def edit_doctor(doctor_id):
    doctor = mongo.db.doctors.find_one({'_id': ObjectId(doctor_id)})
    if not doctor:
        flash('Doctor not found.', 'danger')
        return redirect(url_for('admin.doctors'))

    if request.method == 'POST':
        mongo.db.doctors.update_one({'_id': ObjectId(doctor_id)}, {'$set': {
            'name':           request.form.get('name'),
            'specialization': request.form.get('specialization'),
            'hospital':       request.form.get('hospital'),
            'location':       request.form.get('location'),
            'experience':     int(request.form.get('experience', 0)),
        }})
        flash('Doctor profile updated.', 'success')
        return redirect(url_for('admin.doctors'))

    return render_template('admin_edit_doctor.html', doctor=doctor)

@admin_bp.route('/doctors/add', methods=['GET', 'POST'])
@admin_required
def add_doctor():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        name     = request.form.get('name')
        spec     = request.form.get('specialization')
        hosp     = request.form.get('hospital')
        loc      = request.form.get('location')
        exp      = int(request.form.get('experience', 0))

        if mongo.db.users.find_one({'email': email}):
            flash('Email already registered.', 'danger')
            return redirect(url_for('admin.add_doctor'))

        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        user_id = mongo.db.users.insert_one({
            'email': email,
            'password': hashed_pw,
            'role': 'doctor',
            'is_verified': True,
            'created_at': datetime.utcnow()
        }).inserted_id

        mongo.db.doctors.insert_one({
            '_id': user_id,
            'name': name,
            'specialization': spec,
            'hospital': hosp,
            'location': loc,
            'experience': exp,
            'reviews': [],
            'rating': 0
        })

        flash(f'Dr. {name} added successfully.', 'success')
        return redirect(url_for('admin.doctors'))

    return render_template('admin_add_doctor.html')
