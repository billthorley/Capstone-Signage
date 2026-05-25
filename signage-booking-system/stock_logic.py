from datetime import date, timedelta

from sqlalchemy import func

from database import db
from models import Booking, BookingItem, Sign


ACTIVE_STATUSES = {"APPROVED", "COLLECTED"}
WARNING_STATUSES = {"PENDING", "APPROVED", "COLLECTED"}


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


def get_overbooking_warnings(days_ahead: int = 180) -> list[dict]:
    today = date.today()
    horizon_end = today + timedelta(days=days_ahead)
    warnings = []

    signs = Sign.query.order_by(Sign.category.asc(), Sign.name.asc()).all()
    for sign in signs:
        relevant_items = []
        for booking_item in sign.booking_items:
            booking = booking_item.booking
            if booking.status not in WARNING_STATUSES:
                continue

            start_date = max(booking.pickup_date, today)
            end_date = min(booking.return_date, horizon_end)
            if end_date < today or start_date > horizon_end:
                continue

            relevant_items.append(
                {
                    "booking": booking,
                    "quantity": booking_item.quantity,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

        if not relevant_items:
            continue

        active_warning = None
        for offset in range(days_ahead + 1):
            target_day = today + timedelta(days=offset)
            overlapping_items = [
                item
                for item in relevant_items
                if item["start_date"] <= target_day <= item["end_date"]
            ]
            reserved_quantity = sum(item["quantity"] for item in overlapping_items)

            if reserved_quantity <= sign.total_quantity:
                if active_warning:
                    warnings.append(active_warning)
                    active_warning = None
                continue

            booking_names = tuple(sorted({item["booking"].event_name for item in overlapping_items}))
            statuses = tuple(sorted({item["booking"].status for item in overlapping_items}))
            overbooked_by = reserved_quantity - sign.total_quantity

            if (
                active_warning
                and target_day == active_warning["end_date"] + timedelta(days=1)
                and active_warning["reserved_quantity"] == reserved_quantity
                and active_warning["booking_names"] == booking_names
                and active_warning["statuses"] == statuses
            ):
                active_warning["end_date"] = target_day
                active_warning["overbooked_by"] = overbooked_by
                continue

            if active_warning:
                warnings.append(active_warning)

            active_warning = {
                "sign": sign,
                "total_quantity": sign.total_quantity,
                "reserved_quantity": reserved_quantity,
                "overbooked_by": overbooked_by,
                "start_date": target_day,
                "end_date": target_day,
                "booking_names": booking_names,
                "statuses": statuses,
            }

        if active_warning:
            warnings.append(active_warning)

    return warnings
