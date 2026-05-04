import os
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Optional

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from database import db, ensure_schema_updates, init_app
from email_service import send_booking_confirmation
from models import Booking, BookingItem, Sign
from stock_logic import (
    ACTIVE_STATUSES,
    get_available_stock,
    get_future_stock_summary,
    get_peak_reserved_for_sign,
    get_reserved_total_for_day,
)

ADMIN_USERS = {
    "admin1": {
        "password": "admin123",
        "label": "Admin 1",
    },
    "admin2": {
        "password": "admin456",
        "label": "Admin 2",
    },
}


def parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def get_safe_next_url(next_url: Optional[str]) -> str:
    if next_url and next_url.startswith("/"):
        return next_url
    return url_for("admin_dashboard")


def is_admin_logged_in() -> bool:
    return session.get("admin_username") in ADMIN_USERS


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not is_admin_logged_in():
            flash("Please sign in to access the admin area.", "error")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "capstone-mvp-secret")
    app.config["ADMIN_EMAIL"] = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER")
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_SENDER"] = os.environ.get("MAIL_SENDER", app.config["ADMIN_EMAIL"])

    init_app(app)

    with app.app_context():
        db.create_all()
        ensure_schema_updates()

    @app.context_processor
    def inject_auth_state():
        username = session.get("admin_username")
        return {
            "is_admin_logged_in": username in ADMIN_USERS,
            "admin_display_name": ADMIN_USERS.get(username, {}).get("label"),
        }

    register_routes(app)
    return app


def build_calendar_event(booking: Booking) -> dict:
    item_summary = ", ".join(f"{item.sign.name} x{item.quantity}" for item in booking.items)
    return {
        "title": f"{booking.event_name} ({item_summary})",
        "start": booking.pickup_date.isoformat(),
        "end": (booking.return_date + timedelta(days=1)).isoformat(),
        "color": "#157347" if booking.status == "APPROVED" else "#0d6efd",
    }


def group_signs_by_category(signs):
    grouped = {}
    for sign in signs:
        category = sign.category or "General"
        grouped.setdefault(category, []).append(sign)
    return grouped


def register_routes(app):
    @app.route("/")
    def index():
        signs = Sign.query.order_by(Sign.category.asc(), Sign.name.asc()).limit(6).all()
        approved_count = Booking.query.filter(Booking.status == "APPROVED").count()
        return render_template("index.html", signs=signs, approved_count=approved_count)

    @app.route("/booking")
    def booking():
        signs = Sign.query.order_by(Sign.category.asc(), Sign.name.asc()).all()
        return render_template("booking.html", signs_by_category=group_signs_by_category(signs), today=date.today())

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["username"].strip().lower()
            password = request.form["password"]
            next_url = get_safe_next_url(request.form.get("next"))
            user = ADMIN_USERS.get(username)

            if user and user["password"] == password:
                session["admin_username"] = username
                flash(f"Signed in as {user['label']}.", "success")
                return redirect(next_url)

            flash("Invalid username or password.", "error")

        next_url = get_safe_next_url(request.args.get("next") or request.form.get("next"))
        return render_template("login.html", next_url=next_url, demo_users=ADMIN_USERS)

    @app.route("/logout", methods=["POST"])
    def logout():
        session.pop("admin_username", None)
        flash("You have been signed out.", "success")
        return redirect(url_for("login"))

    @app.route("/bookings", methods=["POST"])
    def create_booking_request():
        form = request.form
        sign = Sign.query.get_or_404(int(form["sign_id"]))
        pickup_date = parse_date(form["pickup_date"])
        return_date = parse_date(form["return_date"])
        quantity = int(form["quantity"])

        if return_date < pickup_date:
            flash("Return date must be on or after the pickup date.", "error")
            return redirect(url_for("booking"))

        if quantity <= 0 or quantity > sign.total_quantity:
            flash("Quantity must be between 1 and the total inventory for this sign.", "error")
            return redirect(url_for("booking"))

        booking_record = Booking(
            event_name=form["event_name"].strip(),
            contact_name=form["contact_name"].strip(),
            email=form["email"].strip(),
            phone_number=form["phone_number"].strip(),
            pickup_date=pickup_date,
            return_date=return_date,
            notes=form.get("notes", "").strip(),
            status="PENDING",
        )
        booking_item = BookingItem(sign=sign, quantity=quantity)
        booking_record.items.append(booking_item)

        db.session.add(booking_record)
        db.session.commit()

        try:
            send_booking_confirmation(app, booking_record, booking_item)
        except Exception as exc:  # pragma: no cover
            app.logger.warning("Booking email failed: %s", exc)

        return redirect(url_for("confirmation", booking_id=booking_record.id))

    @app.route("/confirmation/<int:booking_id>")
    def confirmation(booking_id: int):
        booking_record = Booking.query.get_or_404(booking_id)
        return render_template("confirmation.html", booking=booking_record)

    @app.route("/inventory")
    def inventory():
        signs = Sign.query.order_by(Sign.category.asc(), Sign.name.asc()).all()
        today = date.today()
        inventory_rows_by_category = {}

        for sign in signs:
            available_today = get_available_stock(sign, today, today)
            category = sign.category or "General"
            inventory_rows_by_category.setdefault(category, []).append(
                {
                    "sign": sign,
                    "available_today": available_today,
                    "booked_today": sign.total_quantity - available_today,
                }
            )

        return render_template("inventory.html", inventory_rows_by_category=inventory_rows_by_category)

    @app.route("/calendar-events")
    def calendar_events():
        active_bookings = (
            Booking.query.filter(Booking.status.in_(ACTIVE_STATUSES))
            .order_by(Booking.pickup_date.asc(), Booking.created_at.asc())
            .all()
        )
        return jsonify([build_calendar_event(booking_record) for booking_record in active_bookings])

    @app.route("/admin")
    @login_required
    def admin_dashboard():
        signs = Sign.query.order_by(Sign.category.asc(), Sign.name.asc()).all()
        today = date.today()
        future_stock = get_future_stock_summary()
        upcoming_bookings = (
            Booking.query.filter(Booking.return_date >= today)
            .order_by(Booking.pickup_date.asc(), Booking.created_at.desc())
            .limit(8)
            .all()
        )

        total_inventory = sum(sign.total_quantity for sign in signs)
        available_stock = sum(get_available_stock(sign, today, today) for sign in signs)
        booked_stock = get_reserved_total_for_day(today)

        sign_cards = []
        for sign in signs:
            available_today = get_available_stock(sign, today, today)
            sign_cards.append(
                {
                    "sign": sign,
                    "available_today": available_today,
                    "booked_today": sign.total_quantity - available_today,
                    "predicted_future_stock": min(
                        get_available_stock(sign, today + timedelta(days=offset), today + timedelta(days=offset))
                        for offset in range(31)
                    ),
                }
            )

        return render_template(
            "admin_dashboard.html",
            total_inventory=total_inventory,
            available_stock=available_stock,
            booked_stock=booked_stock,
            future_stock=future_stock,
            upcoming_bookings=upcoming_bookings,
            sign_cards=sign_cards,
        )

    @app.route("/admin/bookings")
    @login_required
    def admin_bookings():
        booking_records = Booking.query.order_by(Booking.created_at.desc()).all()
        return render_template("admin_bookings.html", booking_records=booking_records)

    @app.route("/admin/bookings/<int:booking_id>/status", methods=["POST"])
    @login_required
    def update_booking_status(booking_id: int):
        booking_record = Booking.query.get_or_404(booking_id)
        action = request.form["action"]

        transitions = {
            "approve": "APPROVED",
            "reject": "REJECTED",
            "collect": "COLLECTED",
            "return": "RETURNED",
        }
        allowed_actions = {
            "PENDING": {"approve", "reject"},
            "APPROVED": {"reject", "collect"},
            "COLLECTED": {"return"},
            "REJECTED": set(),
            "RETURNED": set(),
        }

        if action not in transitions:
            flash("Unknown booking action.", "error")
            return redirect(url_for("admin_bookings"))

        if action not in allowed_actions.get(booking_record.status, set()):
            flash(f"{action.title()} is not allowed when a booking is {booking_record.status}.", "error")
            return redirect(url_for("admin_bookings"))

        if action == "approve":
            for item in booking_record.items:
                available = get_available_stock(item.sign, booking_record.pickup_date, booking_record.return_date, booking_record.id)
                if item.quantity > available:
                    flash(
                        f"Cannot approve this request. Only {available} {item.sign.name} signs are available for those dates.",
                        "error",
                    )
                    return redirect(url_for("admin_bookings"))

        booking_record.status = transitions[action]
        db.session.commit()
        flash(f"Booking updated to {booking_record.status}.", "success")
        return redirect(url_for("admin_bookings"))

    @app.route("/admin/inventory/<int:sign_id>", methods=["POST"])
    @login_required
    def update_inventory(sign_id: int):
        sign = Sign.query.get_or_404(sign_id)
        total_quantity = int(request.form["total_quantity"])

        if total_quantity < 0:
            flash("Inventory quantity cannot be negative.", "error")
            return redirect(url_for("admin_dashboard"))

        peak_reserved = get_peak_reserved_for_sign(sign)
        if total_quantity < peak_reserved:
            flash(
                f"Inventory for {sign.name} cannot be reduced below {peak_reserved} because that stock is already reserved.",
                "error",
            )
            return redirect(url_for("admin_dashboard"))

        sign.total_quantity = total_quantity
        sign.description = request.form.get("description", "").strip()
        db.session.commit()
        flash(f"Inventory updated for {sign.name}.", "success")
        return redirect(url_for("admin_dashboard"))


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
