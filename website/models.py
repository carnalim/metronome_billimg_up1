from datetime import datetime
from . import db

class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(10))
    message = db.Column(db.Text)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(255), unique=True)  # Metronome product ID
    name = db.Column(db.String(255))
    description = db.Column(db.Text)
    archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime)
    last_synced = db.Column(db.DateTime)
    credit_types = db.Column(db.JSON)  # Store credit types as JSON

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    metronome_id = db.Column(db.String(255), unique=True)
    name = db.Column(db.String(255))
    salesforce_id = db.Column(db.String(255))
    rate_card_id = db.Column(db.String(255))
    stripe_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime)
    last_synced = db.Column(db.DateTime)
    status = db.Column(db.String(50))
