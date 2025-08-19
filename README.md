# Doctor Appointment System (Flask) — Admin + Email

A complete, ready-to-run doctor appointment system built with Flask + SQLite, now with:
- Admin panel (manage users & appointments)
- Email notifications on booking/approval/rejection/cancellation

## Quick Start
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

# Option A: Use local debug SMTP (prints emails to console)
python -m smtpd -c DebuggingServer -n localhost:8025

# Initialize DB with sample users (incl. admin)
flask --app app.py init-db

# Run the app
flask --app app.py run
```

Open http://127.0.0.1:5000

### Sample Accounts
- Admin: `admin@example.com` / `password`
- Patient: `patient@example.com` / `password`
- Doctor 1: `doc1@example.com` / `password` (Cardiology)
- Doctor 2: `doc2@example.com` / `password` (Dermatology)

## Real SMTP (optional)
Set environment variables:
```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=your@gmail.com
```
# Doctor-appointment-system
