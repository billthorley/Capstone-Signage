# Troubleshooting

## Common checks

- Confirm dependencies are installed with `pip install -r requirements.txt`
- Confirm the database has seed data with `python seed_data.py`
- Confirm the app starts locally before testing deployment

## Login problems

- If user pages redirect back to the portal, confirm a valid user account was entered
- If admin pages redirect back to login, confirm an admin account was used instead of a user account

## Booking form problems

- If a booking will not submit, confirm each booking row has both a signage type and quantity
- If quantity validation fails, check that the requested quantity is not greater than the total stock for that item
- If approval fails, check whether another approved booking already overlaps those dates

## Email problems

- If email notifications do not send, confirm `ADMIN_EMAIL`, `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_USE_TLS`, and `MAIL_SENDER` are set
- If using Gmail or Outlook, an app password may be required instead of the normal mailbox password

## Render problems

- If Render fails to start, confirm the root directory is `signage-booking-system`
- Confirm the start command is `gunicorn app:app`
- Confirm `gunicorn` is present in `requirements.txt`
- If data resets unexpectedly, remember the app currently uses SQLite and will need persistent storage or a hosted database for reliable production use

## Internal test command

Run the internal tests with:

```bash
pytest
```
