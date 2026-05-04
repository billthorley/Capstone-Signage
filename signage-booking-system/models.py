from datetime import datetime

from database import db


class Sign(db.Model):
    __tablename__ = "signs"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(120), nullable=True, default="General")
    name = db.Column(db.String(120), nullable=False, unique=True)
    total_quantity = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)

    booking_items = db.relationship("BookingItem", back_populates="sign", cascade="all, delete-orphan")


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(150), nullable=False)
    contact_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(40), nullable=False)
    pickup_date = db.Column(db.Date, nullable=False)
    return_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="PENDING")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    items = db.relationship("BookingItem", back_populates="booking", cascade="all, delete-orphan")


class BookingItem(db.Model):
    __tablename__ = "booking_items"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    sign_id = db.Column(db.Integer, db.ForeignKey("signs.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    booking = db.relationship("Booking", back_populates="items")
    sign = db.relationship("Sign", back_populates="booking_items")
