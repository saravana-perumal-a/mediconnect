from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.db import mongo
from bson.objectid import ObjectId
from datetime import datetime
from utils.decorators import doctor_required

doctor_bp = Blueprint('doctor', __name__)

@doctor_bp.route('/dashboard', methods=['GET', 'POST'])
@doctor_required
def dashboard():
    doctor_id = ObjectId(session['user_id'])
    
    if request.method == 'POST':
        # Update doctor profile
        name = request.form.get('name')
        specialization = request.form.get('specialization')
        location = request.form.get('location')
        hospital = request.form.get('hospital')
        experience = request.form.get('experience')
        qualifications = request.form.get('qualifications') # Expecting comma separated

        update_data = {}
        if name: update_data['name'] = name
        if specialization: update_data['specialization'] = specialization
        if location: update_data['location'] = location
        if hospital: update_data['hospital'] = hospital
        if experience: update_data['experience'] = int(experience)
        if qualifications:
            update_data['qualifications'] = [q.strip() for q in qualifications.split(',')]

        if update_data:
            mongo.db.doctors.update_one({'_id': doctor_id}, {'$set': update_data})
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('doctor.dashboard'))

    doctor = mongo.db.doctors.find_one({'_id': doctor_id})
    return render_template('doctor_dashboard.html', doctor=doctor)

@doctor_bp.route('/manage-slots', methods=['GET', 'POST'])
@doctor_required
def manage_slots():
    doctor_id = ObjectId(session['user_id'])

    if request.method == 'POST':
        # Add new slot
        date = request.form.get('date')
        time = request.form.get('time')

        if not date or not time:
            flash('Date and time are required.', 'danger')
            return redirect(url_for('doctor.manage_slots'))

        # Check if slot already exists
        existing_slot = mongo.db.slots.find_one({
            'doctor_id': doctor_id,
            'date': date,
            'time': time
        })

        if existing_slot:
            flash('A slot already exists for this date and time.', 'warning')
        else:
            mongo.db.slots.insert_one({
                'doctor_id': doctor_id,
                'date': date,
                'time': time,
                'is_booked': False
            })
            flash('Slot added successfully.', 'success')

        return redirect(url_for('doctor.manage_slots'))

    # GET request: view slots
    today = datetime.now().strftime('%Y-%m-%d')
    slots = list(mongo.db.slots.find({'doctor_id': doctor_id, 'date': {'$gte': today}}).sort([('date', 1), ('time', 1)]))
    
    return render_template('manage_slots.html', slots=slots)

@doctor_bp.route('/delete-slot/<slot_id>', methods=['POST'])
@doctor_required
def delete_slot(slot_id):
    try:
        slot = mongo.db.slots.find_one({'_id': ObjectId(slot_id), 'doctor_id': ObjectId(session['user_id'])})
        if not slot:
            flash('Slot not found.', 'danger')
        elif slot['is_booked']:
            flash('Cannot delete a booked slot. Please cancel the appointment instead.', 'danger')
        else:
            mongo.db.slots.delete_one({'_id': ObjectId(slot_id)})
            flash('Slot deleted successfully.', 'success')
            
        return redirect(url_for('doctor.manage_slots'))
    except Exception as e:
        flash('Error deleting slot.', 'danger')
        return redirect(url_for('doctor.manage_slots'))

@doctor_bp.route('/appointments')
@doctor_required
def appointments():
    doctor_id = ObjectId(session['user_id'])
    
    # Get today's and upcoming appointments
    today = datetime.now().strftime('%Y-%m-%d')
    
    appointments_cursor = mongo.db.appointments.aggregate([
        {'$match': {'doctor_id': doctor_id, 'date': {'$gte': today}}},
        {'$lookup': {
            'from': 'users',
            'localField': 'patient_id',
            'foreignField': '_id',
            'as': 'patient'
        }},
        {'$unwind': '$patient'},
        {'$sort': {'date': 1, 'time': 1}}
    ])
    
    appointments = list(appointments_cursor)
    
    return render_template('doctor_appointments.html', appointments=appointments)
