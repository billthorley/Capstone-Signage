from datetime import date

from database import db
from models import Booking, BookingItem, Sign


INITIAL_SIGNS = [
    {
        "category": "Mesh Short",
        "name": "Events.SC",
        "total_quantity": 10,
        "description": "Short mesh sign for Events.SC branding.",
    },
    {
        "category": "Mesh Short",
        "name": "Short Single",
        "total_quantity": 14,
        "description": "Single short mesh signage unit.",
    },
    {
        "category": "Mesh Short",
        "name": "Short Multi",
        "total_quantity": 16,
        "description": "Multi-panel short mesh signage set.",
    },
    {
        "category": "Mesh Tall",
        "name": "Tall Single",
        "total_quantity": 19,
        "description": "Single tall mesh signage unit.",
    },
    {
        "category": "Mesh Tall",
        "name": "Tall Multi (4)",
        "total_quantity": 14,
        "description": "Tall mesh signage set with 4-panel format.",
    },
    {
        "category": "Mesh Tall",
        "name": "Tall Multi (5)",
        "total_quantity": 5,
        "description": "Tall mesh signage set with 5-panel format.",
    },
    {
        "category": "Mesh Tall",
        "name": "Tall Multi (10)",
        "total_quantity": 2,
        "description": "Tall mesh signage set with 10-panel format.",
    },
    {
        "category": "Equipment",
        "name": "Feathers",
        "total_quantity": 22,
        "description": "Feather flag inventory as listed in the provided stock sheet.",
    },
    {
        "category": "Equipment",
        "name": "Marquee 3x3",
        "total_quantity": 2,
        "description": "3x3 marquee equipment.",
    },
    {
        "category": "Equipment",
        "name": "Marquee 6x3",
        "total_quantity": 2,
        "description": "6x3 marquee equipment.",
    },
    {
        "category": "Equipment",
        "name": "Feather Bases",
        "total_quantity": 10,
        "description": "Bases used with feather signage.",
    },
    {
        "category": "Equipment",
        "name": "Marquee weights",
        "total_quantity": 8,
        "description": "Weights used to secure marquees.",
    },
    {
        "category": "Vinyl & Corflutes",
        "name": "Vinyl Short",
        "total_quantity": 1,
        "description": "Short vinyl signage.",
    },
    {
        "category": "Vinyl & Corflutes",
        "name": "Vinyl Tall",
        "total_quantity": 3,
        "description": "Tall vinyl signage.",
    },
    {
        "category": "Vinyl & Corflutes",
        "name": "Corflute",
        "total_quantity": 13,
        "description": "Corflute signage stock.",
    },
]

DEMO_BOOKINGS = [
    {
        "event_name": "Queensland Garden Show",
        "contact_name": "Nursery and Garden Industry Qld / TLC Events Co",
        "email": "gardenshow.demo@example.com",
        "phone_number": "0400 000 101",
        "pickup_date": date(2026, 7, 7),
        "return_date": date(2026, 7, 14),
        "notes": "Dummy booking loaded from Signage Order Form - City Hall 2026 Garden Show Uni project.docx. Collection time 9am-12pm. Return time 9am-12pm.",
        "status": "PENDING",
        "items": {
            "Short Single": 14,
            "Feathers": 8,
            "Marquee 3x3": 2,
            "Marquee 6x3": 2,
            "Feather Bases": 2,
            "Marquee weights": 8,
            "Vinyl Tall": 1,
        },
    },
    {
        "event_name": "Oz Tag",
        "contact_name": "NRL",
        "email": "oztag.demo@example.com",
        "phone_number": "0400 000 202",
        "pickup_date": date(2026, 7, 8),
        "return_date": date(2026, 7, 14),
        "notes": "Dummy booking loaded from Signage Order Form - City Hall 2026 Uni Students 2.docx. Collection time 10am. Return time 12pm.",
        "status": "PENDING",
        "items": {
            "Short Single": 5,
            "Short Multi": 5,
            "Tall Single": 10,
            "Tall Multi (5)": 5,
            "Feathers": 20,
            "Marquee 3x3": 2,
            "Marquee 6x3": 1,
            "Marquee weights": 4,
            "Vinyl Tall": 1,
        },
    },
]


def seed_signs() -> None:
    legacy_sign = Sign.query.filter_by(name="Feathes").first()
    corrected_sign = Sign.query.filter_by(name="Feathers").first()
    if legacy_sign and corrected_sign is None:
        legacy_sign.name = "Feathers"

    valid_names = {item["name"] for item in INITIAL_SIGNS}

    for item in INITIAL_SIGNS:
        existing_sign = Sign.query.filter_by(name=item["name"]).first()
        if existing_sign:
            existing_sign.category = item["category"]
            existing_sign.total_quantity = item["total_quantity"]
            existing_sign.description = item["description"]
        else:
            db.session.add(Sign(**item))

    for existing_sign in Sign.query.all():
        if existing_sign.name not in valid_names and not existing_sign.booking_items:
            db.session.delete(existing_sign)

    db.session.commit()


def seed_demo_bookings() -> None:
    signs = {sign.name: sign for sign in Sign.query.all()}

    for booking_data in DEMO_BOOKINGS:
        booking = Booking.query.filter_by(event_name=booking_data["event_name"]).first()
        if booking is None:
            booking = Booking(event_name=booking_data["event_name"])
            db.session.add(booking)

        booking.contact_name = booking_data["contact_name"]
        booking.email = booking_data["email"]
        booking.phone_number = booking_data["phone_number"]
        booking.pickup_date = booking_data["pickup_date"]
        booking.return_date = booking_data["return_date"]
        booking.notes = booking_data["notes"]
        booking.status = booking_data["status"]
        booking.items.clear()

        for sign_name, quantity in booking_data["items"].items():
            sign = signs.get(sign_name)
            if sign is None:
                raise RuntimeError(f"Missing sign mapping for demo booking item: {sign_name}")
            booking.items.append(BookingItem(sign=sign, quantity=quantity))

    db.session.commit()


if __name__ == "__main__":
    from app import app

    with app.app_context():
        db.create_all()
        seed_signs()
        seed_demo_bookings()
        print("signage.db created and seed inventory/bookings inserted.")
