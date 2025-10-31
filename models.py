from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    events = db.relationship('Event', backref='organizer', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    venue = db.Column(db.String(200), nullable=False)
    max_tickets = db.Column(db.Integer, nullable=False)
    ticket_price = db.Column(db.Integer, default=0)
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    tickets = db.relationship('Ticket', backref='event', lazy=True, cascade='all, delete-orphan')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    attendee_name = db.Column(db.String(100), nullable=False)
    attendee_phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, used
    payment_reference = db.Column(db.String(100))
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
    checked_in_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)