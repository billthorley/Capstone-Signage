from datetime import date

from database import db
from models import Booking, BookingItem, Sign


def login_user(client):
    return client.post(
        "/user-login",
        data={"username": "user1", "password": "user123"},
        follow_redirects=True,
    )


def login_admin(client):
    return client.post(
        "/admin-login",
        data={"username": "admin1", "password": "admin123"},
        follow_redirects=True,
    )


def test_home_page_shows_portal_selection(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Select your portal" in response.data


def test_user_login_opens_booking_system(client):
    response = login_user(client)
    assert response.status_code == 200
    assert b"Booking request form" in response.data


def test_admin_login_opens_stock_dashboard(client):
    response = login_admin(client)
    assert response.status_code == 200
    assert b"Stock overview" in response.data
    assert b"Future availability trend" in response.data


def test_booking_route_requires_login(client):
    response = client.get("/booking", follow_redirects=True)
    assert response.status_code == 200
    assert b"Select your portal" in response.data


def test_admin_cannot_access_public_booking_portal(client):
    login_admin(client)

    response = client.get("/booking", follow_redirects=True)

    assert response.status_code == 200
    assert b"Admin dashboard" in response.data
    assert b"public booking portal is available to signed-in users only" in response.data


def test_multi_item_booking_creates_multiple_booking_items(app, client):
    login_user(client)

    with app.app_context():
        signs = {sign.name: sign.id for sign in Sign.query.all()}

    response = client.post(
        "/bookings",
        data={
            "event_name": "Sunshine Expo",
            "contact_name": "Casey",
            "email": "casey@example.com",
            "phone_number": "0400000000",
            "pickup_date": "2026-05-20",
            "return_date": "2026-05-22",
            "sign_id[]": [str(signs["Events.SC"]), str(signs["Corflute"])],
            "quantity[]": ["2", "3"],
            "notes": "Test booking",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Booking request received" in response.data

    with app.app_context():
        booking = Booking.query.one()
        assert booking.status == "PENDING"
        assert BookingItem.query.count() == 2
        quantities = sorted(item.quantity for item in booking.items)
        assert quantities == [2, 3]


def test_admin_cannot_approve_overlapping_booking_without_stock(app, client):
    with app.app_context():
        sign = Sign.query.filter_by(name="Marquee 3x3").first()

        approved_booking = Booking(
            event_name="Existing Event",
            contact_name="Admin",
            email="admin@example.com",
            phone_number="0400000001",
            pickup_date=date(2026, 5, 20),
            return_date=date(2026, 5, 21),
            status="APPROVED",
        )
        approved_booking.items.append(BookingItem(sign=sign, quantity=2))

        pending_booking = Booking(
            event_name="Overlap Event",
            contact_name="Jordan",
            email="jordan@example.com",
            phone_number="0400000002",
            pickup_date=date(2026, 5, 20),
            return_date=date(2026, 5, 21),
            status="PENDING",
        )
        pending_booking.items.append(BookingItem(sign=sign, quantity=1))

        db.session.add_all([approved_booking, pending_booking])
        db.session.commit()
        pending_id = pending_booking.id

    login_admin(client)
    response = client.post(
        f"/admin/bookings/{pending_id}/status",
        data={"action": "approve"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Cannot approve this request" in response.data

    with app.app_context():
        refreshed = Booking.query.get(pending_id)
        assert refreshed.status == "PENDING"


def test_admin_pages_show_overbooking_warnings(app, client):
    today = date.today()

    with app.app_context():
        sign = Sign.query.filter_by(name="Marquee 3x3").first()

        booking_one = Booking(
            event_name="Company One",
            contact_name="Alex",
            email="alex@example.com",
            phone_number="0400000003",
            pickup_date=today,
            return_date=today,
            status="APPROVED",
        )
        booking_one.items.append(BookingItem(sign=sign, quantity=2))

        booking_two = Booking(
            event_name="Company Two",
            contact_name="Riley",
            email="riley@example.com",
            phone_number="0400000004",
            pickup_date=today,
            return_date=today,
            status="PENDING",
        )
        booking_two.items.append(BookingItem(sign=sign, quantity=1))

        db.session.add_all([booking_one, booking_two])
        db.session.commit()

    login_admin(client)

    dashboard_response = client.get("/admin")
    manage_response = client.get("/admin/bookings/manage")

    assert dashboard_response.status_code == 200
    assert b"Overbooking warnings" in dashboard_response.data
    assert b"Marquee 3x3 is overbooked by 1" in dashboard_response.data
    assert b"Company One, Company Two" in dashboard_response.data

    assert manage_response.status_code == 200
    assert b"Overbooking warnings" in manage_response.data
    assert b"Marquee 3x3 is overbooked by 1" in manage_response.data


def test_manage_stock_table_shows_available_stock_and_overbooked_rows(app, client):
    today = date.today()

    with app.app_context():
        sign = Sign.query.filter_by(name="Marquee 3x3").first()

        booking_one = Booking(
            event_name="Company One",
            contact_name="Alex",
            email="alex@example.com",
            phone_number="0400000003",
            pickup_date=today,
            return_date=today,
            status="APPROVED",
        )
        booking_one.items.append(BookingItem(sign=sign, quantity=2))

        booking_two = Booking(
            event_name="Company Two",
            contact_name="Riley",
            email="riley@example.com",
            phone_number="0400000004",
            pickup_date=today,
            return_date=today,
            status="PENDING",
        )
        booking_two.items.append(BookingItem(sign=sign, quantity=1))

        db.session.add_all([booking_one, booking_two])
        db.session.commit()

    login_admin(client)
    response = client.get("/admin/bookings/manage")

    assert response.status_code == 200
    assert b"Total stock" in response.data
    assert b"Remaining available" in response.data
    assert b"booking-row-overbooked" in response.data
    assert b"stock-line-overbooked" in response.data
    assert b"Recommended split" in response.data
    assert b"Marquee 3x3:" in response.data
