from app import app
from models.db import mongo
import bcrypt
from datetime import datetime, timedelta

def seed_db():
    with app.app_context():
        # Clear existing data
        mongo.db.users.delete_many({})
        mongo.db.doctors.delete_many({})
        mongo.db.slots.delete_many({})
        mongo.db.appointments.delete_many({})

        print("Database cleared. Starting seed...")

        # Create dummy patient
        patient_pw = bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt())
        patient_id = mongo.db.users.insert_one({
            'email': 'patient@example.com',
            'password': patient_pw,
            'role': 'patient',
            'is_verified': True,
            'created_at': datetime.utcnow()
        }).inserted_id
        print("Created dummy patient: patient@example.com / password123")

        # Create dummy doctors
        doctors_data = [
            {
                'email': 'doctor1@example.com',
                'password': bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt()),
                'name': 'Dr. Sarah Jenkins',
                'specialization': 'Cardiologist',
                'location': 'New York, NY',
                'hospital': 'Mount Sinai Hospital',
                'experience': 15,
                'qualifications': ['MD', 'FACC'],
                'rating': 4.8,
                'reviews': [
                    {'patient_name': 'John D.', 'rating': 5, 'comment': 'Excellent doctor!', 'date': '2023-10-01'}
                ]
            },
            {
                'email': 'doctor2@example.com',
                'password': bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt()),
                'name': 'Dr. Michael Chen',
                'specialization': 'Dermatologist',
                'location': 'San Francisco, CA',
                'hospital': 'UCSF Medical Center',
                'experience': 8,
                'qualifications': ['MD', 'FAAD'],
                'rating': 4.5,
                'reviews': []
            },
            {
                'email': 'doctor3@example.com',
                'password': bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt()),
                'name': 'Dr. Emily Carter',
                'specialization': 'Pediatrician',
                'location': 'Austin, TX',
                'hospital': 'Dell Children\'s Medical Center',
                'experience': 12,
                'qualifications': ['MD', 'FAAP'],
                'rating': 4.9,
                'reviews': [
                    {'patient_name': 'Sarah W.', 'rating': 5, 'comment': 'Great with kids!', 'date': '2023-11-15'},
                    {'patient_name': 'Mike T.', 'rating': 4, 'comment': 'Very thorough.', 'date': '2023-11-20'}
                ]
            }
        ]

        for doc in doctors_data:
            user_doc = {
                'email': doc['email'],
                'password': doc['password'],
                'role': 'doctor',
                'is_verified': True,
                'created_at': datetime.utcnow()
            }
            user_id = mongo.db.users.insert_one(user_doc).inserted_id

            doctor_profile = {
                '_id': user_id,
                'name': doc['name'],
                'specialization': doc['specialization'],
                'location': doc['location'],
                'hospital': doc['hospital'],
                'experience': doc['experience'],
                'qualifications': doc['qualifications'],
                'rating': doc['rating'],
                'reviews': doc['reviews']
            }
            mongo.db.doctors.insert_one(doctor_profile)
            
            print(f"Created dummy doctor: {doc['email']} / password123")

            # Create some slots for each doctor starting from tomorrow
            tomorrow = datetime.now() + timedelta(days=1)
            day_after = datetime.now() + timedelta(days=2)
            
            slots = [
                {'doctor_id': user_id, 'date': tomorrow.strftime('%Y-%m-%d'), 'time': '09:00', 'is_booked': False},
                {'doctor_id': user_id, 'date': tomorrow.strftime('%Y-%m-%d'), 'time': '10:00', 'is_booked': False},
                {'doctor_id': user_id, 'date': tomorrow.strftime('%Y-%m-%d'), 'time': '14:00', 'is_booked': False},
                {'doctor_id': user_id, 'date': day_after.strftime('%Y-%m-%d'), 'time': '11:00', 'is_booked': False},
                {'doctor_id': user_id, 'date': day_after.strftime('%Y-%m-%d'), 'time': '15:00', 'is_booked': False}
            ]
            mongo.db.slots.insert_many(slots)

        print("Seeding complete! You can now log in with the created accounts.")

if __name__ == '__main__':
    seed_db()
