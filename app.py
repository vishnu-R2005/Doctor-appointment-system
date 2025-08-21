from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# ----------------------
# App & Config
# ----------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key_change_me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///doctor_appointment.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ----------------------
# Models
# ----------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="patient")  # patient/doctor
    specialization = db.Column(db.String(120), nullable=True)  # only for doctors

    appointments_as_patient = db.relationship(
        "Appointment", back_populates="patient", foreign_keys="Appointment.patient_id"
    )
    appointments_as_doctor = db.relationship(
        "Appointment", back_populates="doctor", foreign_keys="Appointment.doctor_id"
    )

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending/approved/rejected/cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship("User", foreign_keys=[patient_id], back_populates="appointments_as_patient")
    doctor = db.relationship("User", foreign_keys=[doctor_id], back_populates="appointments_as_doctor")


# ----------------------
# Login manager
# ----------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ----------------------
# Utilities
# ----------------------
def require_role(role):
    from functools import wraps
    def wrapper(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role != role:
                abort(403)
            return fn(*args, **kwargs)
        return inner
    return wrapper


def is_timeslot_taken(doctor_id, date, time):
    return db.session.query(Appointment).filter_by(
        doctor_id=doctor_id, date=date, time=time
    ).filter(Appointment.status != "rejected").first() is not None


# ----------------------
# Routes - Public
# ----------------------
@app.route("/")
def home():
    return render_template("home.html")


@app.route('/index')
def index():
    doctors = User.query.filter_by(role='doctor').all()
    specs = sorted(set(d.specialization for d in doctors if d.specialization))
    return render_template('index.html', specs=specs, doctors=doctors)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'patient')  # ✅ dropdown role (patient/doctor/admin)
        specialization = request.form.get('specialization') if role == 'doctor' else None

        # Validation
        if not name or not email or not password:
            flash('Please fill all required fields.', 'warning')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'danger')
            return redirect(url_for('register'))

        # Create user
        user = User(name=name, email=email, role=role, specialization=specialization)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'{role.capitalize()} account created successfully. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')

            # Redirect based on role
            if user.role == "admin":
                return redirect(url_for('admin_dashboard'))
            elif user.role == "doctor":
                return redirect(url_for('doctor_dashboard'))
            else:  # patient
                return redirect(url_for('patient_dashboard'))

        flash('Invalid credentials.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')



@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('index'))


# ----------------------
# Routes - Common
# ----------------------
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'doctor':
        return redirect(url_for('doctor_dashboard'))
    return redirect(url_for('patient_dashboard'))


# ----------------------
# Patient
# ----------------------
@app.route('/patient/dashboard')
@login_required
@require_role('patient')
def patient_dashboard():
    my_appts = Appointment.query.filter_by(patient_id=current_user.id).order_by(
        Appointment.date.desc(), Appointment.time.desc()
    ).all()
    return render_template('patient_dashboard.html', appts=my_appts)


@app.route('/patient/book', methods=['GET', 'POST'])
@login_required
@require_role('patient')
def book_appointment():
    doctors = User.query.filter_by(role='doctor').order_by(User.name).all()
    if request.method == 'POST':
        doctor_id = int(request.form.get('doctor_id'))
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        reason = request.form.get('reason', '').strip()

        if not date_str or not time_str:
            flash('Please choose date and time.', 'warning')
            return redirect(url_for('book_appointment'))

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            time_obj = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            flash('Invalid date/time format.', 'danger')
            return redirect(url_for('book_appointment'))

        if is_timeslot_taken(doctor_id, date_obj, time_obj):
            flash('Selected timeslot is not available. Please choose another.', 'danger')
            return redirect(url_for('book_appointment'))

        appt = Appointment(
            patient_id=current_user.id,
            doctor_id=doctor_id,
            date=date_obj,
            time=time_obj,
            reason=reason,
            status='pending'
        )
        db.session.add(appt)
        db.session.commit()

        flash('Appointment requested. Awaiting doctor approval.', 'success')
        return redirect(url_for('patient_dashboard'))

    return render_template('book_appointment.html', doctors=doctors)


@app.route('/patient/cancel/<int:appt_id>', methods=['POST'])
@login_required
@require_role('patient')
def cancel_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.patient_id != current_user.id:
        abort(403)
    if appt.status in ('approved', 'pending'):
        appt.status = 'cancelled'
        db.session.commit()
        flash('Appointment cancelled.', 'info')
    return redirect(url_for('patient_dashboard'))


# ----------------------
# Doctor
# ----------------------
@app.route('/doctor/dashboard')
@login_required
@require_role('doctor')
def doctor_dashboard():
    incoming = Appointment.query.filter_by(doctor_id=current_user.id).order_by(
        Appointment.date.asc(), Appointment.time.asc()
    ).all()
    return render_template('doctor_dashboard.html', appts=incoming)


@app.route('/doctor/approve/<int:appt_id>', methods=['POST'])
@login_required
@require_role('doctor')
def approve_appt(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.doctor_id != current_user.id:
        abort(403)
    appt.status = 'approved'
    db.session.commit()
    flash('Appointment approved.', 'success')
    return redirect(url_for('doctor_dashboard'))


@app.route('/doctor/reject/<int:appt_id>', methods=['POST'])
@login_required
@require_role('doctor')
def reject_appt(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.doctor_id != current_user.id:
        abort(403)
    appt.status = 'rejected'
    db.session.commit()
    flash('Appointment rejected.', 'warning')
    return redirect(url_for('doctor_dashboard'))


# ----------------------
# CLI for setup
# ----------------------
@app.cli.command('init-db')
def init_db():
    """Initialize database and create sample users (doctor + patient)."""
    db.create_all()
    created = []

    def ensure_user(name, email, role, pwd='password', spec=None):
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(name=name, email=email, role=role, specialization=spec)
            u.set_password(pwd)
            db.session.add(u)
            db.session.commit()
            created.append(email)
        return u

    ensure_user('Dr. Asha Rao', 'doc1@example.com', 'doctor', spec='Cardiology')
    ensure_user('Dr. Kiran Patel', 'doc2@example.com', 'doctor', spec='Dermatology')
    ensure_user('Vishnu Patient', 'patient@example.com', 'patient')

    print('Initialized DB. Created users:', created)





# ----------------------
# Admin
# ----------------------
@app.route("/admin/dashboard")
@login_required
@require_role("admin")
def admin_dashboard():
    doctor_count = User.query.filter_by(role="doctor").count()
    patient_count = User.query.filter_by(role="patient").count()
    return render_template("admin_dashboard.html",
                           doctor_count=doctor_count,
                           patient_count=patient_count)


@app.route("/admin/manage/<user_type>")
@login_required
@require_role("admin")
def admin_manage(user_type):
    if user_type == "doctor":
        users = User.query.filter_by(role="doctor").all()
    elif user_type == "patient":
        users = User.query.filter_by(role="patient").all()
    else:
        abort(400)
    return render_template("admin_manage.html", users=users, user_type=user_type)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
