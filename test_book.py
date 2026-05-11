from app import app
from models.db import mongo
from bson.objectid import ObjectId

def test_booking():
    with app.test_client() as c:
        with app.app_context():
            # Get a patient
            patient = mongo.db.users.find_one({'role': 'patient'})
            if not patient:
                print("No patient found!")
                return
            
            # Login as patient using session transaction
            with c.session_transaction() as sess:
                sess['user_id'] = str(patient['_id'])
                sess['email'] = patient['email']
                sess['role'] = patient['role']
            
            # Find an available slot
            slot = mongo.db.slots.find_one({'is_booked': False})
            if not slot:
                print("No slot found!")
                return
            
            # Book it
            print(f"Booking slot {slot['_id']}...")
            response = c.post(f"/patient/book/{slot['_id']}")
            print("Response Status:", response.status_code)
            print("Response Headers:", response.headers)

if __name__ == '__main__':
    test_booking()
