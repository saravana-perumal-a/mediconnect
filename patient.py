from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.db import mongo
from bson.objectid import ObjectId
from datetime import datetime
from utils.decorators import patient_required
from utils.notifications import send_appointment_confirmation, send_appointment_cancellation

patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/dashboard')
@patient_required
def dashboard():
    return render_template('dashboard.html')

@patient_bp.route('/search-doctors', methods=['GET'])
@patient_required
def search_doctors():
    query = {}
    specialization = request.args.get('specialization')
    location = request.args.get('location')
    name = request.args.get('name')

    if specialization:
        query['specialization'] = {'$regex': specialization, '$options': 'i'}
    if location:
        query['location'] = {'$regex': location, '$options': 'i'}
    if name:
        query['name'] = {'$regex': name, '$options': 'i'}

    doctors = list(mongo.db.doctors.find(query))
    return render_template('search.html', doctors=doctors)

@patient_bp.route('/doctor/<doctor_id>')
@patient_required
def doctor_profile(doctor_id):
    try:
        doctor = mongo.db.doctors.find_one({'_id': ObjectId(doctor_id)})
        if not doctor:
            flash('Doctor not found', 'danger')
            return redirect(url_for('patient.search_doctors'))
            
        slots_cursor = list(mongo.db.slots.find({
            'doctor_id': ObjectId(doctor_id),
            'is_booked': False,
            'date': {'$gte': datetime.now().strftime('%Y-%m-%d')}
        }).sort([('date', 1), ('time', 1)]))

        from collections import defaultdict
        grouped_slots = defaultdict(list)
        for slot in slots_cursor:
            dt = datetime.strptime(slot['date'], '%Y-%m-%d')
            date_label = dt.strftime('%A, %d %b')
            grouped_slots[date_label].append(slot)
        
        return render_template('doctor_profile.html', doctor=doctor, grouped_slots=grouped_slots)
    except:
        flash('Invalid doctor ID', 'danger')
        return redirect(url_for('patient.search_doctors'))

@patient_bp.route('/book/<slot_id>', methods=['POST'])
@patient_required
def book_appointment(slot_id):
    try:
        slot = mongo.db.slots.find_one({'_id': ObjectId(slot_id)})
        if not slot or slot['is_booked']:
            flash('Slot is no longer available.', 'danger')
            return redirect(request.referrer or url_for('patient.dashboard'))

        # Check for double booking
        existing_appointment = mongo.db.appointments.find_one({
            'patient_id': ObjectId(session['user_id']),
            'date': slot['date'],
            'time': slot['time'],
            'status': 'booked'
        })
        if existing_appointment:
            flash('You already have an appointment at this time.', 'danger')
            return redirect(request.referrer)

        # Mark slot as booked
        mongo.db.slots.update_one({'_id': ObjectId(slot_id)}, {'$set': {'is_booked': True}})

        # Create appointment
        appointment = {
            'patient_id': ObjectId(session['user_id']),
            'doctor_id': slot['doctor_id'],
            'slot_id': ObjectId(slot_id),
            'date': slot['date'],
            'time': slot['time'],
            'status': 'booked',
            'created_at': datetime.utcnow()
        }
        appointment_id = mongo.db.appointments.insert_one(appointment).inserted_id

        # Send confirmation email
        patient_user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
        doctor = mongo.db.doctors.find_one({'_id': slot['doctor_id']})
        if patient_user and doctor:
            send_appointment_confirmation(patient_user['email'], doctor['name'], slot['date'], slot['time'])

        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('patient.confirmation', appt_id=str(appointment_id)))
    except Exception as e:
        print("BOOKING ERROR:", str(e))
        import traceback
        traceback.print_exc()
        flash('Error booking appointment.', 'danger')
        return redirect(request.referrer)

@patient_bp.route('/confirmation/<appt_id>')
@patient_required
def confirmation(appt_id):
    try:
        appointment = mongo.db.appointments.find_one({'_id': ObjectId(appt_id)})
        if not appointment or str(appointment['patient_id']) != session['user_id']:
            flash('Appointment not found.', 'danger')
            return redirect(url_for('patient.my_appointments'))
            
        doctor = mongo.db.doctors.find_one({'_id': appointment['doctor_id']})
        return render_template('confirmation.html', appointment=appointment, doctor=doctor)
    except:
        return redirect(url_for('patient.my_appointments'))

@patient_bp.route('/my-appointments')
@patient_required
def my_appointments():
    appointments = list(mongo.db.appointments.aggregate([
        {'$match': {'patient_id': ObjectId(session['user_id'])}},
        {'$lookup': {
            'from': 'doctors',
            'localField': 'doctor_id',
            'foreignField': '_id',
            'as': 'doctor'
        }},
        {'$unwind': '$doctor'},
        {'$sort': {'date': 1, 'time': 1}}
    ]))
    return render_template('my_appointments.html', appointments=appointments)

@patient_bp.route('/cancel/<appt_id>', methods=['POST'])
@patient_required
def cancel_appointment(appt_id):
    try:
        appointment = mongo.db.appointments.find_one({'_id': ObjectId(appt_id), 'patient_id': ObjectId(session['user_id'])})
        if not appointment:
            flash('Appointment not found.', 'danger')
            return redirect(url_for('patient.my_appointments'))

        # Update appointment status
        mongo.db.appointments.update_one({'_id': ObjectId(appt_id)}, {'$set': {'status': 'cancelled'}})

        # Free the slot
        mongo.db.slots.update_one({'_id': appointment['slot_id']}, {'$set': {'is_booked': False}})

        # Send cancellation email
        patient_user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
        doctor = mongo.db.doctors.find_one({'_id': appointment['doctor_id']})
        if patient_user and doctor:
            send_appointment_cancellation(patient_user['email'], doctor['name'], appointment['date'], appointment['time'])

        flash('Appointment cancelled successfully.', 'success')
        return redirect(url_for('patient.my_appointments'))
    except Exception as e:
        flash('Error cancelling appointment.', 'danger')
        return redirect(url_for('patient.my_appointments'))

@patient_bp.route('/reschedule/<appt_id>', methods=['GET', 'POST'])
@patient_required
def reschedule_appointment(appt_id):
    try:
        appointment = mongo.db.appointments.find_one({'_id': ObjectId(appt_id), 'patient_id': ObjectId(session['user_id'])})
        if not appointment or appointment['status'] == 'cancelled':
            flash('Invalid appointment for rescheduling.', 'danger')
            return redirect(url_for('patient.my_appointments'))

        doctor = mongo.db.doctors.find_one({'_id': appointment['doctor_id']})

        if request.method == 'POST':
            new_slot_id = request.form.get('new_slot_id')
            new_slot = mongo.db.slots.find_one({'_id': ObjectId(new_slot_id)})
            
            if not new_slot or new_slot['is_booked']:
                flash('Selected slot is no longer available.', 'danger')
                return redirect(url_for('patient.reschedule_appointment', appt_id=appt_id))

            # Free old slot
            mongo.db.slots.update_one({'_id': appointment['slot_id']}, {'$set': {'is_booked': False}})
            
            # Book new slot
            mongo.db.slots.update_one({'_id': ObjectId(new_slot_id)}, {'$set': {'is_booked': True}})

            # Update appointment
            mongo.db.appointments.update_one({'_id': ObjectId(appt_id)}, {
                '$set': {
                    'slot_id': ObjectId(new_slot_id),
                    'date': new_slot['date'],
                    'time': new_slot['time']
                }
            })

            # Send notification
            patient_user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
            if patient_user and doctor:
                # Cancel old notification
                send_appointment_cancellation(patient_user['email'], doctor['name'], appointment['date'], appointment['time'])
                # Confirm new notification
                send_appointment_confirmation(patient_user['email'], doctor['name'], new_slot['date'], new_slot['time'])

            flash('Appointment rescheduled successfully.', 'success')
            return redirect(url_for('patient.confirmation', appt_id=str(appt_id)))

        # GET request: show available slots for this doctor
        slots_cursor = list(mongo.db.slots.find({
            'doctor_id': appointment['doctor_id'],
            'is_booked': False,
            'date': {'$gte': datetime.now().strftime('%Y-%m-%d')}
        }).sort([('date', 1), ('time', 1)]))

        from collections import defaultdict
        grouped_slots = defaultdict(list)
        for slot in slots_cursor:
            dt = datetime.strptime(slot['date'], '%Y-%m-%d')
            date_label = dt.strftime('%A, %d %b')
            grouped_slots[date_label].append(slot)

        return render_template('reschedule.html', appointment=appointment, doctor=doctor, grouped_slots=grouped_slots)
    except Exception as e:
        flash('Error rescheduling appointment.', 'danger')
        return redirect(url_for('patient.my_appointments'))

@patient_bp.route('/add-review/<doctor_id>', methods=['POST'])
@patient_required
def add_review(doctor_id):
    try:
        rating = int(request.form.get('rating', 5))
        comment = request.form.get('comment', '')
        
        # Verify the patient has had a completed/booked appointment with this doctor
        has_appointment = mongo.db.appointments.find_one({
            'patient_id': ObjectId(session['user_id']),
            'doctor_id': ObjectId(doctor_id),
            'status': {'$in': ['booked', 'completed']}
        })
        
        if not has_appointment:
            flash('You can only review doctors you have booked appointments with.', 'danger')
            return redirect(url_for('patient.doctor_profile', doctor_id=doctor_id))

        patient = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
        review = {
            'patient_name': patient['email'].split('@')[0], # Simplified name
            'rating': rating,
            'comment': comment,
            'date': datetime.now().strftime('%Y-%m-%d')
        }

        # Calculate new average rating
        doctor = mongo.db.doctors.find_one({'_id': ObjectId(doctor_id)})
        current_reviews = doctor.get('reviews', [])
        current_reviews.append(review)
        
        new_avg = sum(r['rating'] for r in current_reviews) / len(current_reviews)

        mongo.db.doctors.update_one({'_id': ObjectId(doctor_id)}, {
            '$push': {'reviews': review},
            '$set': {'rating': round(new_avg, 1)}
        })

        flash('Review added successfully!', 'success')
        return redirect(url_for('patient.doctor_profile', doctor_id=doctor_id))
    except Exception as e:
        flash('Error adding review.', 'danger')
        return redirect(url_for('patient.doctor_profile', doctor_id=doctor_id))
