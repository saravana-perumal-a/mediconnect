from flask_pymongo import PyMongo

mongo = PyMongo()

def init_db(app):
    mongo.init_app(app)

# We can access collections directly like:
# mongo.db.users
# mongo.db.doctors
# mongo.db.slots
# mongo.db.appointments
