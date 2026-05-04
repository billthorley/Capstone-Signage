from app import app
from database import db
from models import Sign


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
        "name": "Feathes",
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


def seed_signs() -> None:
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


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_signs()
        print("signage.db created and seed inventory inserted.")
