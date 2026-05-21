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
    "wyt001@student.usc.edu.au": {
        "password": "admin1",
        "label": "Admin 3",
    },
    "ccs017@student.usc.edu.au": {
        "password": "admin2",
        "label": "Admin 4",
    },
    "admintest": {
        "password": "admin 3",
        "label": "Admin Test",
    },
}

CLIENT_USERS = {
    "user1": {
        "password": "user123",
        "label": "User 1",
    },
    "user2": {
        "password": "user456",
        "label": "User 2",
    },
}


def parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def get_safe_next_url(next_url: Optional[str]) -> str:
    if next_url and next_url.startswith("/"):
        return next_url
    return url_for("index")


def is_admin_logged_in() -> bool:
    return session.get("admin_username") in ADMIN_USERS


def is_user_logged_in() -> bool:
    return session.get("client_username") in CLIENT_USERS


def has_site_access() -> bool:
    return is_admin_logged_in() or is_user_logged_in()


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not is_admin_logged_in():
            flash("Please sign in to access the admin area.", "error")
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


def user_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not has_site_access():
            flash("Please sign in to access the booking system.", "error")
            return redirect(url_for("index"))
        return view_func(*args, **kwargs)

    return wrapped_view


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "capstone-mvp-secret")
    app.config["ADMIN_EMAIL"] = os.environ.get("ADMIN_EMAIL", "wyt001@student.usc.edu.au")
    app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER")
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_SENDER"] = os.environ.get("MAIL_SENDER", app.config["ADMIN_EMAIL"])
    app.config.setdefault("SEED_DEMO_DATA", True)

    if config_overrides:
        app.config.update(config_overrides)

    init_app(app)

    with app.app_context():
        db.create_all()
        ensure_schema_updates()
        from seed_data import seed_demo_bookings, seed_signs

        seed_signs()
        if app.config.get("SEED_DEMO_DATA"):
            seed_demo_bookings()

    @app.context_processor
    def inject_auth_state():
        admin_username = session.get("admin_username")
        client_username = session.get("client_username")
        return {
            "is_admin_logged_in": admin_username in ADMIN_USERS,
            "is_user_logged_in": client_username in CLIENT_USERS,
            "has_site_access": has_site_access(),
            "admin_display_name": ADMIN_USERS.get(admin_username, {}).get("label"),
            "client_display_name": CLIENT_USERS.get(client_username, {}).get("label"),
            "current_role": "admin" if admin_username in ADMIN_USERS else ("user" if client_username in CLIENT_USERS else None),
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


def can_adjust_booking_stock(booking_record, booking_item_payload):
    for sign_id, quantity in booking_item_payload:
        sign = db.session.get(Sign, sign_id)
        if sign is None:
            return False, "One of the selected signage items no longer exists."
        if quantity <= 0:
            return False, f"Quantity for {sign.name} must be at least 1."
        if quantity > sign.total_quantity:
            return False, f"Quantity for {sign.name} cannot exceed {sign.total_quantity}."

        available = get_available_stock(sign, booking_record.pickup_date, booking_record.return_date, booking_record.id)
        if quantity > available:
            return False, f"Only {available} {sign.name} signs are available for those dates."

    return True, None


def parse_booking_items(form):
    sign_ids = form.getlist("sign_id[]")
    quantities = form.getlist("quantity[]")
    parsed_items = []

    for sign_id, quantity in zip(sign_ids, quantities):
        if not sign_id and not quantity:
            continue

        if not sign_id or not quantity:
            raise ValueError("Each booking item must include both a signage type and quantity.")

        try:
            parsed_items.append((int(sign_id), int(quantity)))
        except ValueError as exc:
            raise ValueError("Booking item values must be valid numbers.") from exc

    if not parsed_items:
        raise ValueError("Please add at least one signage item to the booking.")

    return parsed_items


def register_routes(app):
    @app.route("/")
    def index():
        if is_admin_logged_in():
            return redirect(url_for("admin_dashboard"))
        if is_user_logged_in():
            return redirect(url_for("booking"))
        return render_template("index.html")

    @app.route("/admin-login", methods=["GET", "POST"])
    def admin_login():
        first_username = next(iter(ADMIN_USERS))
        first_password = ADMIN_USERS[first_username]["password"]
        if request.method == "POST":
            username = request.form["username"].strip().lower()
            password = request.form["password"]
            next_url = get_safe_next_url(request.form.get("next"))
            user = ADMIN_USERS.get(username)

            if user and user["password"] == password:
                session.pop("client_username", None)
                session["admin_username"] = username
                flash(f"Signed in as {user['label']}.", "success")
                return redirect(next_url)

            flash("Invalid username or password.", "error")

        next_url = get_safe_next_url(request.args.get("next") or request.form.get("next"))
        return render_template(
            "login.html",
            next_url=next_url,
            login_type="admin",
            login_title="Admin login",
            login_heading="Sign in to the admin dashboard",
            login_description="Admins can review bookings, manage inventory, and monitor current and future bookings.",
            demo_users=ADMIN_USERS,
            placeholder_username=first_username,
            placeholder_password=first_password,
        )

    @app.route("/user-login", methods=["GET", "POST"])
    def user_login():
        first_username = next(iter(CLIENT_USERS))
        first_password = CLIENT_USERS[first_username]["password"]
        if request.method == "POST":
            username = request.form["username"].strip().lower()
            password = request.form["password"]
            next_url = get_safe_next_url(request.form.get("next")) or url_for("booking")
            user = CLIENT_USERS.get(username)

            if user and user["password"] == password:
                session.pop("admin_username", None)
                session["client_username"] = username
                flash(f"Signed in as {user['label']}.", "success")
                return redirect(next_url if next_url != url_for("index") else url_for("booking"))

            flash("Invalid username or password.", "error")

        next_url = get_safe_next_url(request.args.get("next") or request.form.get("next"))
        return render_template(
            "login.html",
            next_url=next_url,
            login_type="user",
            login_title="User login",
            login_heading="Sign in to the booking system",
            login_description="Users can access the signage booking calendar, submit requests, and view inventory after logging in.",
            demo_users=CLIENT_USERS,
            placeholder_username=first_username,
            placeholder_password=first_password,
        )

    @app.route("/booking")
    @user_required
    def booking():
        signs = Sign.query.order_by(Sign.category.asc(), Sign.name.asc()).all()
        return render_template("booking.html", signs_by_category=group_signs_by_category(signs), today=date.today())

    @app.route("/logout", methods=["POST"])
    def logout():
        session.pop("admin_username", None)
        session.pop("client_username", None)
        flash("You have been signed out.", "success")
        return redirect(url_for("index"))

    @app.route("/bookings", methods=["POST"])
    @user_required
    def create_booking_request():
        form = request.form
        pickup_date = parse_date(form["pickup_date"])
        return_date = parse_date(form["return_date"])
        try:
            requested_items = parse_booking_items(form)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("booking"))

        if return_date < pickup_date:
            flash("Return date must be on or after the pickup date.", "error")
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

        consolidated_items = {}
        for sign_id, quantity in requested_items:
            sign = Sign.query.get_or_404(sign_id)
            if quantity <= 0 or quantity > sign.total_quantity:
                flash(f"Quantity for {sign.name} must be between 1 and {sign.total_quantity}.", "error")
                return redirect(url_for("booking"))

            consolidated_items.setdefault(sign.id, {"sign": sign, "quantity": 0})
            consolidated_items[sign.id]["quantity"] += quantity

        for item_data in consolidated_items.values():
            if item_data["quantity"] > item_data["sign"].total_quantity:
                flash(
                    f"Combined quantity for {item_data['sign'].name} cannot exceed {item_data['sign'].total_quantity}.",
                    "error",
                )
                return redirect(url_for("booking"))

            booking_record.items.append(BookingItem(sign=item_data["sign"], quantity=item_data["quantity"]))

        db.session.add(booking_record)
        db.session.commit()

        try:
            send_booking_confirmation(app, booking_record)
        except Exception as exc:  # pragma: no cover
            app.logger.warning("Booking email failed: %s", exc)

        return redirect(url_for("confirmation", booking_id=booking_record.id))

    @app.route("/confirmation/<int:booking_id>")
    @user_required
    def confirmation(booking_id: int):
        booking_record = Booking.query.get_or_404(booking_id)
        return render_template("confirmation.html", booking=booking_record)

    @app.route("/inventory")
    @user_required
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
    @user_required
    def calendar_events():
        active_bookings = (
            Booking.query.filter(Booking.status.in_(ACTIVE_STATUSES))
            .order_by(Booking.pickup_date.asc(), Booking.created_at.asc())
            .all()
        )
        return jsonify([build_calendar_event(booking_record) for booking_record in active_bookings])

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        signs = Sign.query.order_by(Sign.category.asc(), Sign.name.asc()).all()
        today = date.today()
        future_stock = get_future_stock_summary()

        total_inventory = sum(sign.total_quantity for sign in signs)
        available_stock = sum(get_available_stock(sign, today, today) for sign in signs)
        booked_stock = get_reserved_total_for_day(today)

        sign_cards = []
        category_totals = {}
        category_available = {}
        for sign in signs:
            available_today = get_available_stock(sign, today, today)
            category = sign.category or "General"
            category_totals[category] = category_totals.get(category, 0) + sign.total_quantity
            category_available[category] = category_available.get(category, 0) + available_today
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

        stock_trend_labels = []
        stock_trend_values = []
        for offset in range(8):
            target_day = today + timedelta(days=offset * 4)
            reserved = get_reserved_total_for_day(target_day)
            stock_trend_labels.append(target_day.strftime("%d %b"))
            stock_trend_values.append(max(total_inventory - reserved, 0))

        top_stock_cards = sorted(sign_cards, key=lambda item: item["booked_today"], reverse=True)[:6]

        return render_template(
            "admin_dashboard.html",
            total_inventory=total_inventory,
            available_stock=available_stock,
            booked_stock=booked_stock,
            future_stock=future_stock,
            sign_cards=sign_cards,
            chart_category_labels=list(category_totals.keys()),
            chart_category_totals=list(category_totals.values()),
            chart_category_available=[category_available[label] for label in category_totals.keys()],
            chart_overview_labels=["Available", "Booked"],
            chart_overview_values=[available_stock, booked_stock],
            chart_top_item_labels=[item["sign"].name for item in top_stock_cards],
            chart_top_item_booked=[item["booked_today"] for item in top_stock_cards],
            chart_top_item_available=[item["available_today"] for item in top_stock_cards],
            chart_trend_labels=stock_trend_labels,
            chart_trend_values=stock_trend_values,
        )

    @app.route("/admin/bookings")
    @admin_required
    def admin_bookings():
        booking_records = Booking.query.order_by(Booking.created_at.desc()).all()
        return render_template("admin_bookings.html", booking_records=booking_records)

    @app.route("/admin/bookings/manage")
    @admin_required
    def manage_booking_stock():
        booking_records = Booking.query.order_by(Booking.created_at.desc()).all()
        signs = Sign.query.order_by(Sign.category.asc(), Sign.name.asc()).all()
        return render_template(
            "admin_booking_stock.html",
            booking_records=booking_records,
            signs_by_category=group_signs_by_category(signs),
        )

    @app.route("/admin/bookings/<int:booking_id>/edit", methods=["POST"])
    @admin_required
    def edit_booking_stock(booking_id: int):
        booking_record = Booking.query.get_or_404(booking_id)

        raw_sign_ids = request.form.getlist("sign_id[]")
        raw_quantities = request.form.getlist("quantity[]")
        updated_items = []

        for sign_id, quantity in zip(raw_sign_ids, raw_quantities):
            if not sign_id and not quantity:
                continue
            if not sign_id or not quantity:
                flash("Each booking row must include both a signage type and quantity.", "error")
                return redirect(url_for("manage_booking_stock"))

            try:
                updated_items.append((int(sign_id), int(quantity)))
            except ValueError:
                flash("Booking changes must use valid signage and quantity values.", "error")
                return redirect(url_for("manage_booking_stock"))

        if not updated_items:
            flash("A booking must contain at least one signage item.", "error")
            return redirect(url_for("manage_booking_stock"))

        consolidated_items = {}
        for sign_id, quantity in updated_items:
            consolidated_items[sign_id] = consolidated_items.get(sign_id, 0) + quantity

        payload = [(sign_id, quantity) for sign_id, quantity in consolidated_items.items()]

        if booking_record.status in {"APPROVED", "COLLECTED"}:
            is_valid, error_message = can_adjust_booking_stock(booking_record, payload)
            if not is_valid:
                flash(error_message, "error")
                return redirect(url_for("manage_booking_stock"))
        else:
            for sign_id, quantity in payload:
                sign = db.session.get(Sign, sign_id)
                if sign is None:
                    flash("One of the selected signage items no longer exists.", "error")
                    return redirect(url_for("manage_booking_stock"))
                if quantity <= 0 or quantity > sign.total_quantity:
                    flash(f"Quantity for {sign.name} must be between 1 and {sign.total_quantity}.", "error")
                    return redirect(url_for("manage_booking_stock"))

        booking_record.items.clear()
        for sign_id, quantity in payload:
            sign = db.session.get(Sign, sign_id)
            booking_record.items.append(BookingItem(sign=sign, quantity=quantity))

        db.session.commit()
        flash(f"Booking stock updated for {booking_record.event_name}.", "success")
        return redirect(url_for("manage_booking_stock"))

    @app.route("/admin/bookings/<int:booking_id>/cancel", methods=["POST"])
    @admin_required
    def cancel_booking(booking_id: int):
        booking_record = Booking.query.get_or_404(booking_id)
        booking_record.status = "CANCELLED"
        db.session.commit()
        flash(f"Booking cancelled for {booking_record.event_name}.", "success")
        return redirect(url_for("manage_booking_stock"))

    @app.route("/admin/bookings/<int:booking_id>/status", methods=["POST"])
    @admin_required
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
            "CANCELLED": set(),
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
    @admin_required
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
