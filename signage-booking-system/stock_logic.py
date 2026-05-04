from datetime import date, timedelta

from sqlalchemy import func

from database import db
from models import Booking, BookingItem, Sign


ACTIVE_STATUSES = {"APPROVED", "COLLECTED"}


def get_overlapping_quantity(sign_id: int, requested_pickup: date, requested_return: date, exclude_booking_id=None) -> int:
    query = (
        db.session.query(func.coalesce(func.sum(BookingItem.quantity), 0))
        .join(Booking)
        .filter(BookingItem.sign_id == sign_id)
        .filter(Booking.status.in_(ACTIVE_STATUSES))
        .filter(Booking.pickup_date <= requested_return)
        .filter(Booking.return_date >= requested_pickup)
    )

    if exclude_booking_id is not None:
        query = query.filter(Booking.id != exclude_booking_id)

    return int(query.scalar() or 0)


def get_available_stock(sign: Sign, requested_pickup: date, requested_return: date, exclude_booking_id=None) -> int:
    booked_quantity = get_overlapping_quantity(sign.id, requested_pickup, requested_return, exclude_booking_id)
    return max(sign.total_quantity - booked_quantity, 0)


def get_reserved_total_for_day(target_day: date) -> int:
    reserved = (
        db.session.query(func.coalesce(func.sum(BookingItem.quantity), 0))
        .join(Booking)
        .filter(Booking.status.in_(ACTIVE_STATUSES))
        .filter(Booking.pickup_date <= target_day)
        .filter(Booking.return_date >= target_day)
        .scalar()
    )
    return int(reserved or 0)


def get_peak_reserved_for_sign(sign: Sign) -> int:
    bookings = (
        Booking.query.join(BookingItem)
        .filter(BookingItem.sign_id == sign.id)
        .filter(Booking.status.in_(ACTIVE_STATUSES))
        .all()
    )
    if not bookings:
        return 0

    start_day = min(booking.pickup_date for booking in bookings)
    end_day = max(booking.return_date for booking in bookings)
    peak_reserved = 0

    for offset in range((end_day - start_day).days + 1):
        target_day = start_day + timedelta(days=offset)
        reserved = get_overlapping_quantity(sign.id, target_day, target_day)
        peak_reserved = max(peak_reserved, reserved)

    return peak_reserved


def get_future_stock_summary(days_ahead: int = 30) -> dict:
    signs = Sign.query.order_by(Sign.name.asc()).all()
    total_inventory = sum(sign.total_quantity for sign in signs)
    today = date.today()

    peak_reserved = 0
    peak_date = today
    for offset in range(days_ahead + 1):
        target_day = today + timedelta(days=offset)
        reserved = get_reserved_total_for_day(target_day)
        if reserved > peak_reserved:
            peak_reserved = reserved
            peak_date = target_day

    return {
        "projected_available": max(total_inventory - peak_reserved, 0),
        "peak_reserved": peak_reserved,
        "peak_date": peak_date,
    }


def get_sign_projection(sign: Sign, days_ahead: int = 30) -> int:
    today = date.today()
    return min(
        get_available_stock(sign, today + timedelta(days=offset), today + timedelta(days=offset))
        for offset in range(days_ahead + 1)
    )
