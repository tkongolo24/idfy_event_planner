from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Event, Ticket
from config import Config
import secrets
import qrcode
import io
import base64
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Helper function
def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode()

# ============= PUBLIC ROUTES =============
@app.route('/')
def index():
    return render_template('index.html')

# ============= AUTH ROUTES =============
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        user = User(
            email=email,
            password=generate_password_hash(password),
            phone=phone
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'error')
    
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

# ============= ORGANIZER ROUTES =============
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    events = Event.query.filter_by(organizer_id=user.id).order_by(Event.created_at.desc()).all()
    
    return render_template('organizer/dashboard.html', user=user, events=events)

@app.route('/create-event', methods=['GET', 'POST'])
def create_event():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        event = Event(
            code=secrets.token_urlsafe(6).upper()[:8],
            name=request.form['name'],
            date=request.form['date'],
            venue=request.form['venue'],
            max_tickets=int(request.form['max_tickets']),
            ticket_price=int(request.form.get('ticket_price', 0)),
            organizer_id=session['user_id']
        )
        db.session.add(event)
        db.session.commit()
        flash(f'Event "{event.name}" created successfully!', 'success')
        return redirect(url_for('event_details', event_id=event.id))
    
    return render_template('organizer/create_event.html')

@app.route('/event/<int:event_id>')
def event_details(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    event = Event.query.get_or_404(event_id)
    if event.organizer_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('dashboard'))
    
    pending = Ticket.query.filter_by(event_id=event_id, status='pending').order_by(Ticket.created_at.desc()).all()
    approved = Ticket.query.filter_by(event_id=event_id, status='approved').order_by(Ticket.created_at.desc()).all()
    used = Ticket.query.filter_by(event_id=event_id, status='used').order_by(Ticket.checked_in_at.desc()).all()
    
    registration_url = url_for('register_attendee', event_code=event.code, _external=True)
    
    return render_template('organizer/event_details.html', 
                           event=event, 
                           pending=pending,
                           approved=approved,
                           used=used,
                           registration_url=registration_url)

@app.route('/approve-ticket/<int:ticket_id>')
def approve_ticket(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    ticket = Ticket.query.get_or_404(ticket_id)
    event = Event.query.get(ticket.event_id)
    
    if event.organizer_id != session['user_id']:
        flash('Unauthorized', 'error')
        return redirect(url_for('dashboard'))
    
    ticket.status = 'approved'
    db.session.commit()
    flash(f'✅ Ticket approved for {ticket.attendee_name}', 'success')
    return redirect(url_for('event_details', event_id=event.id))

@app.route('/reject-ticket/<int:ticket_id>')
def reject_ticket(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    ticket = Ticket.query.get_or_404(ticket_id)
    event = Event.query.get(ticket.event_id)
    
    if event.organizer_id != session['user_id']:
        flash('Unauthorized', 'error')
        return redirect(url_for('dashboard'))
    
    name = ticket.attendee_name
    db.session.delete(ticket)
    db.session.commit()
    flash(f'❌ Ticket rejected for {name}', 'warning')
    return redirect(url_for('event_details', event_id=event.id))

# ============= ATTENDEE ROUTES =============
@app.route('/register/<event_code>', methods=['GET', 'POST'])
def register_attendee(event_code):
    event = Event.query.filter_by(code=event_code).first_or_404()
    
    if request.method == 'POST':
        # Check capacity
        ticket_count = Ticket.query.filter_by(event_id=event.id).count()
        if ticket_count >= event.max_tickets:
            flash('Sorry, event is full!', 'error')
            return redirect(url_for('register_attendee', event_code=event_code))
        
        ticket = Ticket(
            code=f"{event.code}-{secrets.token_hex(4).upper()}",
            attendee_name=request.form['name'],
            attendee_phone=request.form['phone'],
            payment_reference=request.form.get('payment_ref', ''),
            event_id=event.id,
            status='pending'
        )
        db.session.add(ticket)
        db.session.commit()
        
        return redirect(url_for('ticket_pending', ticket_id=ticket.id))
    
    organizer = User.query.get(event.organizer_id)
    tickets_remaining = event.max_tickets - Ticket.query.filter_by(event_id=event.id).count()
    
    return render_template('attendee/register.html', 
                           event=event, 
                           organizer=organizer,
                           tickets_remaining=tickets_remaining)

@app.route('/ticket/pending/<int:ticket_id>')
def ticket_pending(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    event = Event.query.get(ticket.event_id)
    organizer = User.query.get(event.organizer_id)
    
    return render_template('attendee/ticket_pending.html', 
                           ticket=ticket, 
                           event=event, 
                           organizer=organizer)

@app.route('/ticket/<int:ticket_id>')
def view_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    if ticket.status == 'pending':
        return redirect(url_for('ticket_pending', ticket_id=ticket_id))
    
    event = Event.query.get(ticket.event_id)
    qr_data = url_for('verify_ticket', ticket_code=ticket.code, _external=True)
    qr_image = generate_qr_code(qr_data)
    
    return render_template('attendee/ticket.html', 
                           ticket=ticket, 
                           event=event, 
                           qr_image=qr_image)

# ============= VERIFICATION ROUTES =============
@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        ticket_code = request.form['ticket_code'].strip().upper()
        return redirect(url_for('verify_ticket', ticket_code=ticket_code))
    
    return render_template('verify/verify_form.html')

@app.route('/verify/<ticket_code>')
def verify_ticket(ticket_code):
    ticket = Ticket.query.filter_by(code=ticket_code).first()
    
    if not ticket:
        return render_template('verify/verify_result.html', 
                               status='invalid', 
                               message='Ticket not found')
    
    event = Event.query.get(ticket.event_id)
    
    if ticket.status == 'pending':
        return render_template('verify/verify_result.html', 
                               status='pending', 
                               message='Payment not confirmed yet',
                               ticket=ticket,
                               event=event)
    
    if ticket.status == 'used':
        return render_template('verify/verify_result.html', 
                               status='used', 
                               message=f'Already used at {ticket.checked_in_at.strftime("%I:%M %p")}',
                               ticket=ticket,
                               event=event)
    
    # Valid ticket - mark as used
    ticket.status = 'used'
    ticket.checked_in_at = datetime.utcnow()
    db.session.commit()
    
    return render_template('verify/verify_result.html', 
                           status='valid', 
                           message='Entry Approved!',
                           ticket=ticket,
                           event=event)

# ============= INITIALIZATION =============
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)