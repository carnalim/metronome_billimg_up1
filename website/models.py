from datetime import datetime
from . import db

class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(10))
    message = db.Column(db.Text)

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
