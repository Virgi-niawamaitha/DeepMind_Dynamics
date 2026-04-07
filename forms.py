from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, SubmitField, SelectField,
                     TextAreaField, FileField, RadioField)
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from models import User, County, db

# Constants
KENYAN_COUNTIES = [
    ('Baringo', 'Baringo'),
    ('Bomet', 'Bomet'),
    ('Bungoma', 'Bungoma'),
    ('Busia', 'Busia'),
    ('Elgeyo-Marakwet', 'Elgeyo-Marakwet'),
    ('Embu', 'Embu'),
    ('Garissa', 'Garissa'),
    ('Homa Bay', 'Homa Bay'),
    ('Isiolo', 'Isiolo'),
    ('Kajiado', 'Kajiado'),
    ('Kakamega', 'Kakamega'),
    ('Kericho', 'Kericho'),
    ('Kiambu', 'Kiambu'),
    ('Kilifi', 'Kilifi'),
    ('Kirinyaga', 'Kirinyaga'),
    ('Kisii', 'Kisii'),
    ('Kisumu', 'Kisumu'),
    ('Kitui', 'Kitui'),
    ('Kwale', 'Kwale'),
    ('Laikipia', 'Laikipia'),
    ('Lamu', 'Lamu'),
    ('Machakos', 'Machakos'),
    ('Makueni', 'Makueni'),
    ('Mandera', 'Mandera'),
    ('Marsabit', 'Marsabit'),
    ('Meru', 'Meru'),
    ('Migori', 'Migori'),
    ('Mombasa', 'Mombasa'),
    ('Murang\'a', 'Murang\'a'),
    ('Nairobi', 'Nairobi'),
    ('Nakuru', 'Nakuru'),
    ('Nandi', 'Nandi'),
    ('Narok', 'Narok'),
    ('Nyamira', 'Nyamira'),
    ('Nyandarua', 'Nyandarua'),
    ('Nyeri', 'Nyeri'),
    ('Samburu', 'Samburu'),
    ('Siaya', 'Siaya'),
    ('Taita-Taveta', 'Taita-Taveta'),
    ('Tana River', 'Tana River'),
    ('Tharaka-Nithi', 'Tharaka-Nithi'),
    ('Trans Nzoia', 'Trans Nzoia'),
    ('Turkana', 'Turkana'),
    ('Uasin Gishu', 'Uasin Gishu'),
    ('Vihiga', 'Vihiga'),
    ('Wajir', 'Wajir'),
    ('West Pokot', 'West Pokot')
]

DISEASE_CHOICES = [
    ('', 'Select disease...'),
    ('Apple Scab', 'Apple Scab'),
    ('Black Rot', 'Black Rot'),
    ('Cedar Apple Rust', 'Cedar Apple Rust'),
    ('Powdery Mildew', 'Powdery Mildew'),
    ('Leaf Spot', 'Leaf Spot'),
    ('Bacterial Spot', 'Bacterial Spot'),
    ('Early Blight', 'Early Blight'),
    ('Late Blight', 'Late Blight'),
    ('Leaf Mold', 'Leaf Mold'),
    ('Other', 'Other')
]

PLANT_CHOICES = [
    ('', 'Select a plant type'),
    ('apple', 'Apple'),
    ('blueberry', 'Blueberry'),
    ('cherry', 'Cherry'),
    ('corn', 'Corn'),
    ('grape', 'Grape'),
    ('orange', 'Orange'),
    ('peach', 'Peach'),
    ('pepper', 'Pepper'),
    ('potato', 'Potato'),
    ('raspberry', 'Raspberry'),
    ('soybean', 'Soybean'),
    ('squash', 'Squash'),
    ('strawberry', 'Strawberry'),
    ('tomato', 'Tomato')
]

def initialize_counties():
    """Initialize counties in the database - must be called within app context"""
    for county_name, _ in KENYAN_COUNTIES:
        if not County.query.filter_by(name=county_name).first():
            county = County(name=county_name, code=None)  # Explicitly set code=None
            db.session.add(county)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing counties: {e}")

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password')]
    )
    county = SelectField('County', choices=KENYAN_COUNTIES, validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')

    verification_code = StringField('Verification Code', validators=[DataRequired()])
class CountyForm(FlaskForm):
    county = SelectField('County', coerce=int, validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super(CountyForm, self).__init__(*args, **kwargs)
        counties = County.query.order_by(County.name).all()
        self.county.choices = [(c.id, c.name) for c in counties]
        self.county.choices.insert(0, (0, 'Select your county'))

class PaymentForm(FlaskForm):
    phone_number = StringField('Phone Number',
                              validators=[
                                  DataRequired(),
                                  Length(min=10, max=12)
                              ])
    payment_plan = SelectField('Payment Plan',
                              choices=[
                                  ('monthly', 'Monthly (ksh 15)'),
                                  ('weekly', 'Weekly (ksh 1)')
                              ],
                              validators=[DataRequired()])
    submit = SubmitField('Pay with M-Pesa')
class PredictionForm(FlaskForm):
    plant_type = SelectField(
        'Plant Type',
        choices=PLANT_CHOICES,
        validators=[DataRequired()]
    )
    submit = SubmitField('Continue to Upload Image')

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired()])
    photo = FileField('Upload Photo')
    submit = SubmitField('Post Comment')


class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    disease = SelectField('Disease', choices=DISEASE_CHOICES, validators=[DataRequired()])
    county = SelectField('County', coerce=int)  # Ensure county is treated as integer

    def __init__(self, *args, **kwargs):
        super(PostForm, self).__init__(*args, **kwargs)
        self.county.choices = [(c.id, c.name) for c in County.query.order_by('name')]

    submit = SubmitField('Create Post')