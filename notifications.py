from flask_mail import Mail, Message
from flask_apscheduler import APScheduler
from flask import current_app
from datetime import datetime, timedelta
from bson.objectid import ObjectId

mail = Mail()
scheduler = APScheduler()

def send_email(subject, recipient, body):
    try:
        msg = Message(subject, recipients=[recipient])
        msg.body = body
        mail.send(msg)
        print(f"Email sent to {recipient}: {subject}")
    except Exception as e:
        print(f"Failed to send email to {recipient}: {e}")


def send_appointment_confirmation(recipient, doctor_name, date, time):
    subject = "Appointment Confirmation - MediConnect"
    body = f"Your appointment with Dr. {doctor_name} is confirmed for {date} at {time}."
    send_email(subject, recipient, body)

def send_appointment_cancellation(recipient, doctor_name, date, time):
    subject = "Appointment Cancellation - MediConnect"
    body = f"Your appointment with Dr. {doctor_name} on {date} at {time} has been cancelled."
    send_email(subject, recipient, body)

# Background job for reminders
def check_upcoming_appointments(app):
    with app.app_context():
        from models.db import mongo
        # Find appointments starting tomorrow
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        appointments = mongo.db.appointments.find({"date": tomorrow, "status": "booked"})
        
        for appt in appointments:
            patient = mongo.db.users.find_one({"_id": appt["patient_id"]})
            doctor = mongo.db.doctors.find_one({"_id": appt["doctor_id"]})
            
            if patient and doctor and patient.get('email'):
                subject = "Reminder: Upcoming Appointment Tomorrow"
                body = f"Dear Patient,\nThis is a reminder for your appointment with Dr. {doctor['name']} tomorrow at {appt['time']}."
                send_email(subject, patient['email'], body)

# We will add this job to the scheduler in app.py after registering routes
# scheduler.add_job(id='reminder_job', func=check_upcoming_appointments, args=[app], trigger='cron', hour=8)
