from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pytz import UTC

db = SQLAlchemy()

class LogEntry(db.Model):
    __tablename__ = 'logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC))
    level = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    def __repr__(self):
        return f'<LogEntry {self.timestamp} {self.level}: {self.message[:50]}...>'

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    metronome_id = db.Column(db.String(255), unique=True, nullable=False)
    stripe_id = db.Column(db.String(100))  # Removed unique constraint since it's optional
    name = db.Column(db.String(255), nullable=False)
    external_id = db.Column(db.String(100), unique=True)
    salesforce_id = db.Column(db.String(255))
    rate_card_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC))
    status = db.Column(db.String(50))  # Add status field
    last_synced = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_modified = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    def __repr__(self):
        return f'<Customer {self.name}>'
