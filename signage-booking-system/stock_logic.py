from datetime import date, timedelta

from sqlalchemy import func

from database import db
from models import Booking, BookingItem, Sign


ACTIVE_STATUSES = {"APPROVED", "COLLECTED"}
WARNING_STATUSES = {"PENDING", "APPROVED", "COLLECTED"}
FORECAST_STATUSES = {"PENDING", "APPROVED", "COLLECTED"}


def get_overlapping_quantity(
    sign_id: int,
    requested_pickup: date,
    requested_return: date,
    exclude_booking_id=None,
    statuses=None,
) -> int:
    booking_statuses = statuses or ACTIVE_STATUSES
    query = (
        db.session.query(func.coalesce(func.sum(BookingItem.quantity), 0))
        .join(Booking)
        .filter(BookingItem.sign_id == sign_id)
        .filter(Booking.status.in_(booking_statuses))
        .filter(Booking.pickup_date <= requested_return)
        .filter(Booking.return_date >= requested_pickup)
    )

    if exclude_booking_id is not None:
        query = query.filter(Booking.id != exclude_booking_id)

    return int(query.scalar() or 0)


def get_available_stock(sign: Sign, requested_pickup: date, requested_return: date, exclude_booking_id=None) -> int:
    booked_quantity = get_overlapping_quantity(sign.id, requested_pickup, requested_return, exclude_booking_id)
    return max(sign.total_quantity - booked_quantity, 0)


def get_projected_available_stock(
    sign: Sign,
    requested_pickup: date,
    requested_return: date,
    exclude_booking_id=None,
) -> int:
    booked_quantity = get_overlapping_quantity(
        sign.id,
        requested_pickup,
        requested_return,
        exclude_booking_id=exclude_booking_id,
        statuses=FORECAST_STATUSES,
    )
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


def get_total_available_for_day(target_day: date, signs=None) -> int:
    sign_records = signs or Sign.query.order_by(Sign.name.asc()).all()
    return sum(get_available_stock(sign, target_day, target_day) for sign in sign_records)


def get_projected_total_available_for_day(target_day: date, signs=None) -> int:
    sign_records = signs or Sign.query.order_by(Sign.name.asc()).all()
    return sum(get_projected_available_stock(sign, target_day, target_day) for sign in sign_records)


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
    today = date.today()

    lowest_available = get_projected_total_available_for_day(today, signs)
    peak_date = today
    for offset in range(days_ahead + 1):
        target_day = today + timedelta(days=offset)
        available = get_projected_total_available_for_day(target_day, signs)
        if available < lowest_available:
            lowest_available = available
            peak_date = target_day

    return {
        "projected_available": lowest_available,
        "peak_date": peak_date,
    }


def get_sign_projection(sign: Sign, days_ahead: int = 30) -> int:
    today = date.today()
    return min(
        get_projected_available_stock(sign, today + timedelta(days=offset), today + timedelta(days=offset))
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


def get_stock_split_recommendations(days_ahead: int = 180) -> dict[int, list[dict]]:
    today = date.today()
    horizon_end = today + timedelta(days=days_ahead)
    recommendations_by_booking = {}

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
                    "booking_item": booking_item,
                    "quantity": booking_item.quantity,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

        if not relevant_items:
            continue

        relevant_items.sort(key=lambda item: (item["start_date"], item["end_date"], item["booking"].id))

        clusters = []
        current_cluster = []
        cluster_end = None
        for item in relevant_items:
            if not current_cluster:
                current_cluster = [item]
                cluster_end = item["end_date"]
                continue

            if item["start_date"] <= cluster_end:
                current_cluster.append(item)
                cluster_end = max(cluster_end, item["end_date"])
            else:
                clusters.append(current_cluster)
                current_cluster = [item]
                cluster_end = item["end_date"]

        if current_cluster:
            clusters.append(current_cluster)

        for cluster in clusters:
            total_requested = sum(item["quantity"] for item in cluster)
            if total_requested <= sign.total_quantity:
                continue

            exact_shares = []
            for item in cluster:
                exact_share = sign.total_quantity * (item["quantity"] / total_requested)
                base_share = min(int(exact_share), item["quantity"])
                exact_shares.append(
                    {
                        "item": item,
                        "exact_share": exact_share,
                        "recommended": base_share,
                        "remainder": exact_share - base_share,
                    }
                )

            allocated = sum(share["recommended"] for share in exact_shares)
            remaining_units = sign.total_quantity - allocated

            for share in sorted(exact_shares, key=lambda item: item["remainder"], reverse=True):
                if remaining_units <= 0:
                    break
                if share["recommended"] < share["item"]["quantity"]:
                    share["recommended"] += 1
                    remaining_units -= 1

            for share in exact_shares:
                item = share["item"]
                if share["recommended"] >= item["quantity"]:
                    continue

                booking = item["booking"]
                recommendations_by_booking.setdefault(booking.id, []).append(
                    {
                        "sign_name": sign.name,
                        "requested_quantity": item["quantity"],
                        "recommended_quantity": share["recommended"],
                        "date_range": f"{item['start_date'].strftime('%d %b')} to {item['end_date'].strftime('%d %b')}",
                    }
                )

    return recommendations_by_booking
