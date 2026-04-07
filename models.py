from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'users'  # Changed to plural for consistency

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)  # Changed from password to password_hash
    county_id = db.Column(db.Integer, db.ForeignKey('counties.id'))

    # Relationships
    county = db.relationship('County', backref='residents')
    payments = db.relationship('Payment', backref='payer', lazy=True)
    predictions = db.relationship('Prediction', backref='creator', lazy=True)
    calendar_events = db.relationship('UserCalendar', backref='owner', lazy=True)
    authored_posts = db.relationship('ForumPost', back_populates='author')
    post_comments = db.relationship('ForumComment', back_populates='commenter')

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class County(db.Model):
    __tablename__ = 'counties'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    def __repr__(self):
        return f'<County {self.code} - {self.name}>'


class Prediction(db.Model):
    __tablename__ = 'predictions'
    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(200))
    plant_type = db.Column(db.String(50))
    disease = db.Column(db.String(100))
    scientific_name = db.Column(db.String(100))
    phytomedicine = db.Column(db.String(500))
    treatment = db.Column(db.String(500))
    prevention = db.Column(db.String(500))
    confidence = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Fixed to match User.__tablename__
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Prediction {self.id} - {self.plant_type}>'


class Payment(db.Model):
    __tablename__ = 'payments'  # Changed to plural for consistency

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Fixed to match User.__tablename__
    payment_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    mpesa_receipt = db.Column(db.String(50), nullable=True)
    phone_number = db.Column(db.String(15), nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmation_sent = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f'<Payment {self.id} - {self.payment_type}>'


class UserCalendar(db.Model):
    __tablename__ = 'user_calendars'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Fixed to match User.__tablename__
    event_title = db.Column(db.String(100))
    event_date = db.Column(db.DateTime)
    event_type = db.Column(db.String(20))
    completed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<CalendarEvent {self.id} - {self.event_title}>'


class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    disease = db.Column(db.String(100))
    county_id = db.Column(db.Integer, db.ForeignKey('counties.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Fixed to match User.__tablename__
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    county = db.relationship('County', backref='discussions')
    author = db.relationship('User', back_populates='authored_posts')
    comments = db.relationship('ForumComment', back_populates='post', cascade='all, delete-orphan')
    photos = db.relationship('PostPhoto', backref='post', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ForumPost {self.id} - {self.title}>'


class ForumComment(db.Model):
    __tablename__ = 'forum_comments'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Fixed to match User.__tablename__
    post_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    photo = db.Column(db.String(200))

    # Relationships
    commenter = db.relationship('User', back_populates='post_comments')
    post = db.relationship('ForumPost', back_populates='comments')

    def __repr__(self):
        return f'<ForumComment {self.id}>'


class PostPhoto(db.Model):
    __tablename__ = 'post_photos'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    post_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id'))

    def __repr__(self):
        return f'<PostPhoto {self.id}>'