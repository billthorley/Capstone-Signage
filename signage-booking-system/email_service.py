import smtplib
from email.message import EmailMessage


def send_booking_confirmation(app, booking, booking_item) -> None:
    subject = f"New signage booking request: {booking.event_name}"
    body = "\n".join(
        [
            "A new signage booking request has been submitted.",
            "",
            f"Event name: {booking.event_name}",
            f"Contact name: {booking.contact_name}",
            f"Email: {booking.email}",
            f"Phone number: {booking.phone_number}",
            f"Pickup date: {booking.pickup_date.strftime('%d %b %Y')}",
            f"Return date: {booking.return_date.strftime('%d %b %Y')}",
            f"Signage type: {booking_item.sign.name}",
            f"Quantity: {booking_item.quantity}",
            f"Notes: {booking.notes or 'None'}",
            f"Status: {booking.status}",
        ]
    )

    if not app.config.get("MAIL_SERVER") or not app.config.get("ADMIN_EMAIL"):
        app.logger.warning("Email settings are incomplete. Booking email not sent.\n%s", body)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = app.config["MAIL_SENDER"]
    message["To"] = app.config["ADMIN_EMAIL"]
    message.set_content(body)

    with smtplib.SMTP(app.config["MAIL_SERVER"], app.config["MAIL_PORT"]) as server:
        if app.config["MAIL_USE_TLS"]:
            server.starttls()
        if app.config.get("MAIL_USERNAME") and app.config.get("MAIL_PASSWORD"):
            server.login(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])
        server.send_message(message)
