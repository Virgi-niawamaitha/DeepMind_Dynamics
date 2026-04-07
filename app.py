import os
import glob
import random

import requests
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy.sql.operators import or_
from sqlalchemy import inspect, text
from werkzeug.utils import secure_filename
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np
from PIL import Image
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email

from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from flask import session
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, current_user
from models import  County
from forms import RegistrationForm, PaymentForm, CommentForm
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db
from forms import RegistrationForm, PaymentForm, CommentForm
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, current_user, login_required
from werkzeug.security import generate_password_hash
from models import db, User, ForumPost, ForumComment
from forms import RegistrationForm
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, current_user, login_required
from werkzeug.security import generate_password_hash
from models import db, User, ForumPost, ForumComment
from forms import RegistrationForm
from models import db
from models import db, User, Prediction, Payment, UserCalendar, ForumPost, ForumComment, PostPhoto
# Remove duplicate imports and keep only:
from forms import LoginForm, RegistrationForm, PredictionForm, CommentForm, PostForm
from forms import PredictionForm
# At the top of app.py with other imports
from forms import CountyForm
from models import ForumComment
from forms import KENYAN_COUNTIES
# Initialize Flask app
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import os
from dotenv import load_dotenv
from forms import initialize_counties


from mpesa import MpesaGateway

# Initialize M-Pesa gateway


app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
load_dotenv()
load_dotenv()
mpesa = MpesaGateway()
print("MAIL_USERNAME loaded:", os.getenv('MAIL_USERNAME') is not None)
print("SECRET_KEY loaded:", os.getenv('SECRET_KEY') is not None)

app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Use absolute path so uploads always work regardless of CWD
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(_BASE_DIR, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # For generating tokens


mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Initialize database

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


def ensure_payment_confirmation_column():
    try:
        inspector = inspect(db.engine)
        payment_columns = {column['name'] for column in inspector.get_columns('payments')}
        if 'confirmation_sent' not in payment_columns:
            db.session.execute(text(
                'ALTER TABLE payments ADD COLUMN confirmation_sent BOOLEAN NOT NULL DEFAULT 0'
            ))
            db.session.commit()
    except Exception as exc:
        app.logger.warning(f'Could not ensure payment confirmation column: {exc}')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    ensure_payment_confirmation_column()


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check verification code
        if (session.get('verification_email') != form.email.data or
                session.get('verification_code') != form.verification_code.data or
                session.get('verification_expires', 0) < datetime.now().timestamp()):
            flash('Invalid or expired verification code', 'danger')
            return redirect(url_for('register'))

        # Proceed with registration
        county = County.query.get(form.county.data)
        user = User(
            username=form.username.data,
            email=form.email.data,
            county=county
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        # Clear verification data
        session.pop('verification_email', None)
        session.pop('verification_code', None)
        session.pop('verification_expires', None)

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)
# --- Database Models ---


# Define User model here to avoid circular imports





from models import User

disease_classes = [
    'Apple___Apple_scab',
    'Apple___Black_rot',
    'Apple___Cedar_apple_rust',
    'Apple___healthy',
    'Blueberry___healthy',
    'Cherry_(including_sour)___Powdery_mildew',
    'Cherry_(including_sour)___healthy',
    'Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot',
    'Corn_(maize)___Common_rust_',
    'Corn_(maize)___Northern_Leaf_Blight',
    'Corn_(maize)___healthy',
    'Grape___Black_rot',
    'Grape___Esca_(Black_Measles)',
    'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)',
    'Grape___healthy',
    'Orange___Haunglongbing_(Citrus_greening)',
    'Peach___Bacterial_spot',
    'Peach___healthy',
    'Pepper,_bell___Bacterial_spot',
    'Pepper,_bell___healthy',
    'Potato___Early_blight',
    'Potato___Late_blight',
    'Potato___healthy',
    'Raspberry___healthy',
    'Soybean___healthy',
    'Squash___Powdery_mildew',
    'Strawberry___Leaf_scorch',
    'Strawberry___healthy',
    'Tomato___Bacterial_spot',
    'Tomato___Early_blight',
    'Tomato___Late_blight',
    'Tomato___Leaf_Mold',
    'Tomato___Septoria_leaf_spot',
    'Tomato___Spider_mites Two-spotted_spider_mite',
    'Tomato___Target_Spot',
    'Tomato___Tomato_Yellow_Leaf_Curl_Virus',
    'Tomato___Tomato_mosaic_virus',
    'Tomato___healthy'
]
disease_info = {
    'Apple___Apple_scab': {
        'scientific_name': 'Venturia inaequalis',
        'treatment': 'Apply copper-based fungicides or sulfur sprays. Prune infected branches and destroy fallen leaves.',
        'agrovet_medications': [
            'Cuprocaffaro 37.5WP (copper oxychloride) – protectant spray at 7-day intervals',
            'Dithane M-45 80WP (mancozeb) – apply at pink/petal fall stage',
            'Score 250EC (difenoconazole) – curative spray at first sign of lesions'
        ],
        'phytomedicine': 'Neem oil (Azadirachta indica) spray every 10 days',
        'prevention': 'Plant resistant varieties, maintain proper tree spacing, remove infected plant debris'
    },
    'Apple___Black_rot': {
        'scientific_name': 'Botryosphaeria obtusa',
        'treatment': 'Remove mummified fruits and infected branches. Apply captan fungicide.',
        'agrovet_medications': [
            'Captan 50WP – apply every 10–14 days from bud break',
            'Mancozeb 80WP (Dithane M-45) – protectant spray during wet periods',
            'Thiophanate-methyl 70WP – systemic fungicide for curative action'
        ],
        'phytomedicine': 'Garlic (Allium sativum) and chili pepper extract spray',
        'prevention': 'Avoid tree wounds, practice good orchard sanitation'
    },
    'Apple___Cedar_apple_rust': {
        'scientific_name': 'Gymnosporangium juniperi-virginianae',
        'treatment': 'Apply fungicides in early spring. Remove nearby juniper plants.',
        'agrovet_medications': [
            'Syllit 400SC (dodine) – apply at pink stage and repeat every 10 days',
            'Score 250EC (difenoconazole) – systemic triazole at first signs',
            'Sulfur 80WP – protective spray from green tip to petal fall'
        ],
        'phytomedicine': 'Baking soda solution (1 tbsp per liter) with horticultural oil',
        'prevention': 'Plant resistant varieties, remove alternate hosts within 2km radius'
    },
    'Apple___healthy': {
        'scientific_name': 'Healthy apple plant',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Preventive neem oil sprays every 2 weeks',
        'prevention': 'Maintain proper nutrition and irrigation, regular pruning'
    },
    'Blueberry___healthy': {
        'scientific_name': 'Healthy blueberry plant',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Aloe vera leaf extract as foliar spray',
        'prevention': 'Maintain acidic soil pH (4.0-5.0), proper mulching'
    },
    'Cherry_(including_sour)___Powdery_mildew': {
        'scientific_name': 'Podosphaera clandestina',
        'treatment': 'Apply sulfur or potassium bicarbonate fungicides',
        'agrovet_medications': [
            'Kumulus DF (sulfur 80%) – apply every 7–10 days in dry weather',
            'Topas 100EC (penconazole) – systemic triazole at first symptoms',
            'Karathane (dinocap) – specific powdery mildew fungicide'
        ],
        'phytomedicine': 'Milk spray (1 part milk to 9 parts water) weekly',
        'prevention': 'Improve air circulation, avoid overhead irrigation'
    },
    'Cherry_(including_sour)___healthy': {
        'scientific_name': 'Healthy cherry plant',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Compost tea as soil drench monthly',
        'prevention': 'Regular pruning, balanced fertilization'
    },
    'Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot': {
        'scientific_name': 'Cercospora zeae-maydis',
        'treatment': 'Apply fungicides containing azoxystrobin or propiconazole',
        'agrovet_medications': [
            'Amistar 250SC (azoxystrobin) – apply at tasseling, repeat after 14 days',
            'Tilt 250EC (propiconazole) – apply at first sign of lesions',
            'Folicur 250EW (tebuconazole) – systemic triazole at early disease onset'
        ],
        'phytomedicine': 'Fermented stinging nettle (Urtica dioica) extract',
        'prevention': 'Crop rotation, resistant varieties, proper plant spacing'
    },
    'Corn_(maize)___Common_rust_': {
        'scientific_name': 'Puccinia sorghi',
        'treatment': 'Apply triazole fungicides at disease onset',
        'agrovet_medications': [
            'Tilt 250EC (propiconazole) – apply at first pustule appearance',
            'Folicur 250EW (tebuconazole) – systemic control of rust',
            'Amistar Top (azoxystrobin + difenoconazole) – broad-spectrum control'
        ],
        'phytomedicine': 'Lantana camara leaf extract spray',
        'prevention': 'Early planting, resistant varieties, balanced fertilization'
    },
    'Corn_(maize)___Northern_Leaf_Blight': {
        'scientific_name': 'Exserohilum turcicum',
        'treatment': 'Apply chlorothalonil or mancozeb fungicides',
        'agrovet_medications': [
            'Dithane M-45 80WP (mancozeb) – apply every 7–10 days during wet periods',
            'Bravo 720SC (chlorothalonil) – protectant spray at tasseling',
            'Headline EC (pyraclostrobin) – systemic strobilurin at early onset'
        ],
        'phytomedicine': 'Tithonia diversifolia (Mexican sunflower) leaf extract',
        'prevention': 'Crop rotation, tillage to bury crop residue'
    },
    'Corn_(maize)___healthy': {
        'scientific_name': 'Healthy maize plant',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Fermented plant extracts for soil health',
        'prevention': 'Proper spacing, timely weeding, crop rotation'
    },
    'Grape___Black_rot': {
        'scientific_name': 'Guignardia bidwellii',
        'treatment': 'Apply fungicides early in season, remove infected material',
        'agrovet_medications': [
            'Mancozeb 80WP (Dithane M-45) – protectant spray every 7–10 days',
            'Topsin M 70WP (thiophanate-methyl) – systemic curative fungicide',
            'Captan 50WP – apply from bud break through berry set'
        ],
        'phytomedicine': 'Fermented pawpaw leaf extract',
        'prevention': 'Proper pruning, canopy management, remove mummified fruits'
    },
    'Grape___Esca_(Black_Measles)': {
        'scientific_name': 'Phaeomoniella spp.',
        'treatment': 'Prune infected wood, no effective chemical control',
        'agrovet_medications': [
            'Trichoderma-based bioagent (e.g. Trichomax) – soil/wound treatment to suppress trunk pathogens',
            'Benlate 50WP (benomyl) – wound-sealing paste after pruning (limited efficacy)',
            'Garlic extract wound sealant – traditional protective measure'
        ],
        'phytomedicine': 'Garlic and ginger rhizome extract',
        'prevention': 'Avoid pruning wounds, use clean pruning tools'
    },
    'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)': {
        'scientific_name': 'Pseudocercospora vitis',
        'treatment': 'Copper-based fungicides during wet periods',
        'agrovet_medications': [
            'Cuprocaffaro 37.5WP (copper oxychloride) – spray every 10–14 days',
            'Dithane M-45 80WP (mancozeb) – protective cover spray',
            'Score 250EC (difenoconazole) – systemic curative at early infection'
        ],
        'phytomedicine': 'Ocimum gratissimum (African basil) leaf extract',
        'prevention': 'Improve air circulation, avoid overhead irrigation'
    },
    'Grape___healthy': {
        'scientific_name': 'Healthy grape vine',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Seaweed extract as foliar spray',
        'prevention': 'Proper trellising, balanced nutrition'
    },
    'Orange___Haunglongbing_(Citrus_greening)': {
        'scientific_name': 'Candidatus Liberibacter asiaticus',
        'treatment': 'Remove infected trees, control psyllid vectors',
        'agrovet_medications': [
            'Actara 25WG (thiamethoxam) – systemic insecticide for psyllid control',
            'Karate Zeon 50CS (lambda-cyhalothrin) – contact insecticide for psyllid',
            'Imidacloprid 200SL (Confidor) – soil drench/foliar for vector management'
        ],
        'phytomedicine': 'Neem oil for psyllid control',
        'prevention': 'Plant disease-free nursery stock, vector monitoring'
    },
    'Peach___Bacterial_spot': {
        'scientific_name': 'Xanthomonas arboricola pv. pruni',
        'treatment': 'Copper sprays during dormancy, streptomycin during growing season',
        'agrovet_medications': [
            'Cuprocaffaro 37.5WP (copper oxychloride) – dormancy and early season sprays',
            'Agrimycin 17 (streptomycin sulfate) – bactericide during growing season',
            'Kocide 2000 (copper hydroxide) – protective copper spray at petal fall'
        ],
        'phytomedicine': 'Horsetail (Equisetum arvense) tea spray',
        'prevention': 'Plant resistant varieties, avoid overhead irrigation'
    },
    'Peach___healthy': {
        'scientific_name': 'Healthy peach tree',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Comfrey leaf tea as foliar feed',
        'prevention': 'Proper pruning, balanced fertilization'
    },
    'Pepper,_bell___Bacterial_spot': {
        'scientific_name': 'Xanthomonas campestris pv. vesicatoria',
        'treatment': 'Copper-based bactericides, avoid working with wet plants',
        'agrovet_medications': [
            'Kocide 2000 (copper hydroxide) – apply every 7–10 days in wet conditions',
            'Cuprocaffaro 37.5WP (copper oxychloride) – protective bactericide spray',
            'Agrimycin 17 (streptomycin) – for severe outbreaks in combination with copper'
        ],
        'phytomedicine': 'Fermented African marigold (Tagetes minuta) extract',
        'prevention': 'Use disease-free seeds, crop rotation'
    },
    'Pepper,_bell___healthy': {
        'scientific_name': 'Healthy bell pepper plant',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Aloe vera gel mixed with water as foliar spray',
        'prevention': 'Proper spacing, mulching, drip irrigation'
    },
    'Potato___Early_blight': {
        'scientific_name': 'Alternaria solani',
        'treatment': 'Apply chlorothalonil or mancozeb fungicides',
        'agrovet_medications': [
            'Dithane M-45 80WP (mancozeb) – apply every 7 days starting at canopy closure',
            'Bravo 720SC (chlorothalonil) – broad-spectrum protectant fungicide',
            'Amistar 250SC (azoxystrobin) – systemic strobilurin for curative action'
        ],
        'phytomedicine': 'Fermented stinging nettle extract',
        'prevention': 'Crop rotation, proper fertilization, remove crop debris'
    },
    'Potato___Late_blight': {
        'scientific_name': 'Phytophthora infestans',
        'treatment': 'Apply metalaxyl or chlorothalonil fungicides',
        'agrovet_medications': [
            'Ridomil Gold MZ 68WG (metalaxyl-M + mancozeb) for curative + protectant control',
            'Dithane M-45 80WP (mancozeb) for protectant sprays every 5-7 days in wet weather',
            'Acrobat MZ 69WP (dimethomorph + mancozeb) where available for resistance rotation'
        ],
        'phytomedicine': 'Horsetail tea spray every 5 days',
        'prevention': 'Plant resistant varieties, avoid overhead irrigation'
    },
    'Potato___healthy': {
        'scientific_name': 'Healthy potato plant',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Compost tea as soil drench',
        'prevention': 'Proper hilling, crop rotation'
    },
    'Raspberry___healthy': {
        'scientific_name': 'Healthy raspberry plant',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Fermented banana peel extract',
        'prevention': 'Proper trellising, regular pruning'
    },
    'Soybean___healthy': {
        'scientific_name': 'Healthy soybean plant',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Rhizobium inoculants for nitrogen fixation',
        'prevention': 'Proper spacing, crop rotation'
    },
    'Squash___Powdery_mildew': {
        'scientific_name': 'Podosphaera xanthii',
        'treatment': 'Apply sulfur or potassium bicarbonate',
        'agrovet_medications': [
            'Kumulus DF (sulfur 80%) – apply every 7–10 days when disease pressure is high',
            'Topas 100EC (penconazole) – systemic triazole at first sign of white powder',
            'Thiovit Jet 80WG (sulfur) – preventive and curative powdery mildew control'
        ],
        'phytomedicine': 'Milk spray (1:9 ratio with water) weekly',
        'prevention': 'Resistant varieties, proper spacing'
    },
    'Strawberry___Leaf_scorch': {
        'scientific_name': 'Diplocarpon earlianum',
        'treatment': 'Apply captan or thiophanate-methyl fungicides',
        'agrovet_medications': [
            'Captan 50WP – apply every 10–14 days during wet weather',
            'Topsin M 70WP (thiophanate-methyl) – systemic fungicide at first symptoms',
            'Mancozeb 80WP (Dithane M-45) – broad-spectrum protective spray'
        ],
        'phytomedicine': 'Fermented comfrey leaf extract',
        'prevention': 'Remove infected leaves, improve air circulation'
    },
    'Strawberry___healthy': {
        'scientific_name': 'Healthy strawberry plant',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Seaweed extract as foliar spray',
        'prevention': 'Proper mulching, drip irrigation'
    },
    'Tomato___Bacterial_spot': {
        'scientific_name': 'Xanthomonas spp.',
        'treatment': 'Copper-based bactericides, avoid working with wet plants',
        'agrovet_medications': [
            'Kocide 2000 (copper hydroxide) – apply every 5–7 days during wet periods',
            'Cuprocaffaro 37.5WP (copper oxychloride) – protectant bactericide spray',
            'Agrimycin 17 (streptomycin + oxytetracycline) – for severe bacterial outbreaks'
        ],
        'phytomedicine': 'Garlic and chili pepper extract spray',
        'prevention': 'Use disease-free seeds, crop rotation'
    },
    'Tomato___Early_blight': {
        'scientific_name': 'Alternaria solani',
        'treatment': 'Apply chlorothalonil, remove lower leaves',
        'agrovet_medications': [
            'Bravo 720SC (chlorothalonil) – apply every 7–10 days from first symptoms',
            'Dithane M-45 80WP (mancozeb) – protectant spray every 7 days',
            'Amistar 250SC (azoxystrobin) – systemic fungicide for curative action'
        ],
        'phytomedicine': 'Fermented stinging nettle extract',
        'prevention': 'Crop rotation, proper plant spacing'
    },
    'Tomato___Late_blight': {
        'scientific_name': 'Phytophthora infestans',
        'treatment': 'Apply chlorothalonil, destroy infected plants',
        'agrovet_medications': [
            'Ridomil Gold MZ 68WG (metalaxyl-M + mancozeb) for early outbreak control',
            'Dithane M-45 / Mancozeb 80WP for preventive cover sprays (5-7 day interval in rainy periods)',
            'Acrobat MZ 69WP (dimethomorph + mancozeb) for follow-up sprays and rotation',
            'Bravo 720SC / chlorothalonil formulations for protectant disease suppression'
        ],
        'phytomedicine': 'Horsetail tea spray every 5 days',
        'prevention': 'Resistant varieties, avoid overhead watering'
    },
    'Tomato___Leaf_Mold': {
        'scientific_name': 'Passalora fulva',
        'treatment': 'Improve air circulation, apply chlorothalonil',
        'agrovet_medications': [
            'Bravo 720SC (chlorothalonil) – apply every 7–10 days in humid conditions',
            'Flint 50WG (trifloxystrobin) – systemic strobilurin for leaf mold control',
            'Dithane M-45 80WP (mancozeb) – protectant spray in high-humidity conditions'
        ],
        'phytomedicine': 'Baking soda solution (1 tbsp per liter)',
        'prevention': 'Proper spacing, greenhouse ventilation'
    },
    'Tomato___Septoria_leaf_spot': {
        'scientific_name': 'Septoria lycopersici',
        'treatment': 'Copper-based fungicides, remove infected leaves',
        'agrovet_medications': [
            'Kocide 2000 (copper hydroxide) – protective spray every 7–10 days',
            'Bravo 720SC (chlorothalonil) – broad-spectrum protectant fungicide',
            'Topsin M 70WP (thiophanate-methyl) – systemic curative fungicide'
        ],
        'phytomedicine': 'Fermented African marigold extract',
        'prevention': 'Crop rotation, avoid overhead irrigation'
    },
    'Tomato___Spider_mites Two-spotted_spider_mite': {
        'scientific_name': 'Tetranychus urticae',
        'treatment': 'Apply miticides or insecticidal soap',
        'agrovet_medications': [
            'Oberon SC (spiromesifen) – miticide specifically for spider mites',
            'Abamectin 1.8EC (Agrimek) – broad-spectrum miticide/insecticide',
            'Envidor 240SC (spirodiclofen) – ovicidal + adulticidal mite control'
        ],
        'phytomedicine': 'Neem oil with liquid soap spray',
        'prevention': 'Maintain humidity, weed control'
    },
    'Tomato___Target_Spot': {
        'scientific_name': 'Corynespora cassiicola',
        'treatment': 'Apply chlorothalonil, remove infected material',
        'agrovet_medications': [
            'Bravo 720SC (chlorothalonil) – apply every 7–10 days from first symptoms',
            'Amistar 250SC (azoxystrobin) – systemic strobilurin for curative action',
            'Mancozeb 80WP (Dithane M-45) – protectant spray every 7 days'
        ],
        'phytomedicine': 'Fermented pawpaw leaf extract',
        'prevention': 'Crop rotation, resistant varieties'
    },
    'Tomato___Tomato_Yellow_Leaf_Curl_Virus': {
        'scientific_name': 'Begomovirus',
        'treatment': 'Control whitefly vectors, remove infected plants',
        'agrovet_medications': [
            'Actara 25WG (thiamethoxam) – systemic insecticide for whitefly control',
            'Confidor 200SL (imidacloprid) – soil drench or foliar for whitefly',
            'Karate Zeon 50CS (lambda-cyhalothrin) – contact insecticide for vectors'
        ],
        'phytomedicine': 'Neem oil for whitefly control',
        'prevention': 'Resistant varieties, reflective mulches'
    },
    'Tomato___Tomato_mosaic_virus': {
        'scientific_name': 'Tobamovirus',
        'treatment': 'No cure, remove infected plants',
        'agrovet_medications': [
            'No curative chemical available – focus on prevention',
            'Virkon S (disinfectant) – use to sterilize tools and equipment',
            'Karate Zeon 50CS – control aphid/insect vectors to limit spread'
        ],
        'phytomedicine': 'None - focus on prevention',
        'prevention': 'Use certified disease-free seeds, disinfect tools'
    },
    'Tomato___healthy': {
        'scientific_name': 'Healthy tomato plant',
        'treatment': 'No treatment required',
        'agrovet_medications': [],
        'phytomedicine': 'Compost tea as foliar spray',
        'prevention': 'Proper staking, balanced fertilization'
    }
}







# Load Keras model
import os
from tensorflow.keras.models import load_model

def load_keras_model():
    model_path = os.path.join(os.path.dirname(__file__), "trained_plant_model.keras")
    
    # Print immediately so you know loading started
    print("Loading Keras model… please wait, this may take 20–30 seconds")
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found at: {model_path}")
    
    model = load_model(model_path)
    print("Model loaded successfully!")  # Confirmation when done
    return model

try:
    model = load_keras_model()
    print("Keras model loaded successfully")

except Exception as e:
    print(f"Error loading Keras model: {e}")
    exit(1)


# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'webp'}


def predict_disease(img_path, plant_prefix):
    img = image.load_img(img_path, target_size=(128, 128))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) / 255.0

    predictions = model.predict(img_array)
    probabilities = predictions[0]

    # Get indices of diseases for the selected plant only
    valid_indices = [i for i, disease in enumerate(disease_classes)
                     if disease.startswith(plant_prefix)]

    if not valid_indices:
        top_disease = f"{plant_prefix}___healthy"
        confidence = 1.0
    else:
        # Get the highest probability among valid diseases
        valid_probs = probabilities[valid_indices]
        max_idx = np.argmax(valid_probs)
        top_idx = valid_indices[max_idx]
        top_disease = disease_classes[top_idx]
        confidence = probabilities[top_idx]

    return top_disease, float(confidence)


# --- Flask Routes ---

# Other routes...

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):  # Changed to password_hash
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    predictions = Prediction.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', user=current_user, predictions=predictions)


@app.route('/send_verification', methods=['POST'])
def send_verification():
    if request.method == 'POST':
        try:
            email = request.form.get('email')

            if not email:
                return jsonify({'success': False, 'message': 'Email is required'}), 400

            if User.query.filter_by(email=email).first():
                return jsonify({'success': False, 'message': 'Email already registered'}), 400

            # Generate a simple 6-digit code
            verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

            # Store in session (with expiration)
            session['verification_email'] = email
            session['verification_code'] = verification_code
            session['verification_expires'] = datetime.now().timestamp() + 3600  # 1 hour expiration

            # Send email with just the code
            msg = Message(
                'Your Verification Code',
                recipients=[email],
                body=f'Your verification code is: {verification_code}\n\nThis code expires in 1 hour.'
            )

            try:
                mail.send(msg)
                return jsonify({
                    'success': True,
                    'message': 'Verification code sent to your email'
                })
            except Exception as mail_error:
                app.logger.warning(f"Email send failed, returning code directly: {mail_error}")
                # Fallback: return the code directly so user can still register
                return jsonify({
                    'success': True,
                    'message': f'Email service unavailable. Use this code: {verification_code}'
                })

        except Exception as e:
            app.logger.error(f"Verification error: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500


@app.route('/verify_email/<token>')
def verify_email(token):
    try:
        email = serializer.loads(token, salt='email-verify', max_age=3600)  # 1 hour expiration

        # Debugging output
        print(f"Email from token: {email}")
        print(f"Session email: {session.get('verification_email')}")

        if email == session.get('verification_email'):
            session['email_verified'] = True
            flash('Email verified successfully!', 'success')
            return redirect(url_for('register'))
        else:
            flash('Email verification failed - session mismatch', 'danger')
    except Exception as e:
        print(f"Verification error: {str(e)}")  # Debug output
        flash('Invalid or expired verification link', 'danger')

    return redirect(url_for('register'))



# app.py
@app.route('/select-plant', methods=['GET', 'POST'])
@login_required
def select_plant():
    # Check payment status first
    active_payment = Payment.query.filter(
        Payment.user_id == current_user.id,
        Payment.status == 'paid',
        or_(
            Payment.expiry_date.is_(None),
            Payment.expiry_date >= datetime.utcnow()
        )
    ).first()

    if not active_payment:
        flash('Please complete payment to access predictions', 'warning')
        return redirect(url_for('payment'))

    if request.method == 'POST':
        plant_type = request.form.get('plant_type')
        if plant_type:
            return redirect(url_for('predict', plant_type=plant_type))
        flash('Please select a plant type', 'error')

    plants = [
        {'id': 'apple', 'name': 'Apple'},
        {'id': 'blueberry', 'name': 'Blueberry'},
        {'id': 'cherry', 'name': 'Cherry'},
        {'id': 'corn', 'name': 'Corn'},
        {'id': 'grape', 'name': 'Grape'},
        {'id': 'orange', 'name': 'Orange'},
        {'id': 'peach', 'name': 'Peach'},
        {'id': 'pepper', 'name': 'Pepper'},
        {'id': 'potato', 'name': 'Potato'},
        {'id': 'raspberry', 'name': 'Raspberry'},
        {'id': 'soybean', 'name': 'Soybean'},
        {'id': 'squash', 'name': 'Squash'},
        {'id': 'strawberry', 'name': 'Strawberry'},
        {'id': 'tomato', 'name': 'Tomato'}
    ]

    return render_template('select_plant.html',
                           plants=plants,
                           payment_success=request.args.get('payment_success'))


@app.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    form = PaymentForm()
    if form.validate_on_submit():
        try:
            # Test API connectivity first
            if not mpesa.check_api_status():
                app.logger.error("M-Pesa API unreachable")
                flash('M-Pesa service is currently down. Please try again later.', 'danger')
                return redirect(url_for('payment'))

            plan = form.payment_plan.data
            amount = 15 if plan == 'monthly' else 1
            phone = form.phone_number.data

            # Process payment
            response = mpesa.stk_push(
                phone_number=f"254{phone[-9:]}",
                amount=amount,
                account_reference=f"USER{current_user.id}",
                transaction_desc="PlantMD Subscription"
            )

            if response.get('success'):
                # Calculate expiry date
                if plan == 'monthly':
                    expiry_date = datetime.utcnow() + timedelta(days=30)
                else:
                    expiry_date = datetime.utcnow() + timedelta(days=7)

                # Create payment record with pending status
                payment = Payment(
                    user_id=current_user.id,
                    payment_type=plan,
                    amount=amount,
                    status='pending',
                    mpesa_receipt=response.get('checkout_request_id'),
                    phone_number=phone,
                    expiry_date=expiry_date
                )
                db.session.add(payment)
                db.session.commit()

                # Store payment info in session for later email sending
                session['pending_payment_id'] = payment.id
                session['payment_plan'] = plan
                session['payment_amount'] = amount
                session['payment_expiry'] = expiry_date.isoformat()

                flash('Payment initiated successfully! Please check your phone to complete the transaction.', 'success')
                return render_template(
                    'payment_processing.html',
                    payment=payment,
                    redirect_url=url_for('payment_status'),
                    delay=30000,
                    email_sent=payment.confirmation_sent,
                )

            # Handle specific error codes
            error_code = response.get('errorCode')
            if error_code == '400.002.02':
                flash('Invalid phone number format. Use 07... or 2547...', 'danger')
            elif error_code == '400.001.01':
                flash('Insufficient balance in your M-Pesa account', 'warning')
            else:
                flash('Payment initiation failed. Please try again.', 'danger')

        except requests.exceptions.ConnectionError:
            app.logger.error("M-Pesa API connection failed")
            flash('Network error connecting to M-Pesa. Check your internet.', 'danger')
        except requests.exceptions.Timeout:
            app.logger.error("M-Pesa API timeout")
            flash('Payment service timed out. Please try again.', 'danger')
        except Exception as e:
            app.logger.error(f"Payment error: {str(e)}", exc_info=True)
            flash('An unexpected error occurred. Our team has been notified.', 'danger')

    return render_template('payment.html', form=form)


@app.route('/process-payment', methods=['POST'])
@login_required
def process_payment():
    return payment()


@app.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    data = request.get_json()

    # Extract relevant info from callback
    checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
    result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')

    # Find the payment record
    payment = Payment.query.filter_by(mpesa_receipt=checkout_request_id).first()

    if payment:
        if result_code == 0:
            # Payment successful
            payment.status = 'paid'

            # Update with actual M-Pesa receipt number
            callback_metadata = data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
            for item in callback_metadata:
                if item.get('Name') == 'MpesaReceiptNumber':
                    payment.mpesa_receipt = item.get('Value')
                    break

            db.session.commit()

            # Send payment confirmation email
            try:
                expiry_date = payment.expiry_date
                if not expiry_date:
                    # Calculate expiry date if not set
                    if payment.payment_type == 'monthly':
                        expiry_date = datetime.utcnow() + timedelta(days=30)
                    else:
                        expiry_date = datetime.utcnow() + timedelta(days=7)
                    payment.expiry_date = expiry_date
                    db.session.commit()

                email_sent = send_payment_confirmation_email(
                    user=payment.payer,
                    payment_plan=payment.payment_type,
                    amount=payment.amount,
                    expiry_date=expiry_date
                )

                if email_sent:
                    payment.confirmation_sent = True
                    db.session.commit()
                    app.logger.info(f"Payment confirmation email sent for payment {payment.id}")
                else:
                    app.logger.warning(f"Failed to send payment confirmation email for payment {payment.id}")

            except Exception as e:
                app.logger.error(f"Error sending payment confirmation email: {str(e)}")

        else:
            # Payment failed
            payment.status = 'failed'
            db.session.commit()

    return jsonify({'status': 'received'})
# ====== Existing code ======
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, session, jsonify


# ... other imports ...

# ====== Add this with your other routes ======
@app.route('/payment-status')
@login_required
def payment_status():
    try:
        # Query the user's payment history - newest first
        payments_query = Payment.query.filter_by(user_id=current_user.id)
        if hasattr(Payment, 'created_at'):
            payments_query = payments_query.order_by(Payment.created_at.desc())
        else:
            payments_query = payments_query.order_by(Payment.id.desc())

        payments = payments_query.all()

        current_time = datetime.utcnow()
        latest_payment = payments[0] if payments else None
        status_changed = False

        # Reconcile only the newest pending payment to avoid hitting M-Pesa rate limits.
        latest_pending = next((p for p in payments if p.status == 'pending' and p.mpesa_receipt), None)
        if latest_pending:
            try:
                query_response = mpesa.query_stk_status(latest_pending.mpesa_receipt)
                result_code = str(query_response.get('ResultCode', ''))

                if result_code == '0':
                    latest_pending.status = 'paid'
                    if not latest_pending.expiry_date:
                        latest_pending.expiry_date = (
                            current_time + timedelta(days=30)
                            if latest_pending.payment_type == 'monthly'
                            else current_time + timedelta(days=7)
                        )
                    status_changed = True
                elif result_code and result_code != '0':
                    latest_pending.status = 'failed'
                    status_changed = True

            except Exception as exc:
                app.logger.warning(f"Could not reconcile payment status for {latest_pending.id}: {exc}")

        if status_changed:
            db.session.commit()
            payments = payments_query.all()
            latest_payment = payments[0] if payments else None

        # Send missing confirmation emails for newly paid payments.
        email_sent_any = False
        email_failed_any = False
        for paid_payment in [p for p in payments if p.status == 'paid' and not p.confirmation_sent]:
            try:
                if not paid_payment.expiry_date:
                    paid_payment.expiry_date = (
                        current_time + timedelta(days=30)
                        if paid_payment.payment_type == 'monthly'
                        else current_time + timedelta(days=7)
                    )

                email_sent = send_payment_confirmation_email(
                    user=paid_payment.payer,
                    payment_plan=paid_payment.payment_type,
                    amount=paid_payment.amount,
                    expiry_date=paid_payment.expiry_date
                )
                paid_payment.confirmation_sent = bool(email_sent)
                email_sent_any = email_sent_any or email_sent
                email_failed_any = email_failed_any or (not email_sent)
            except Exception as exc:
                email_failed_any = True
                app.logger.error(f"Error sending payment confirmation email for {paid_payment.id}: {exc}")

        if email_sent_any or email_failed_any:
            db.session.commit()
            if email_sent_any:
                flash('Payment confirmation email has been sent!', 'success')
            if email_failed_any:
                flash('Payment confirmed, but we could not send the confirmation email.', 'warning')

        # Check active subscription from any paid, non-expired payment.
        active_subscription = next(
            (
                p for p in payments
                if p.status == 'paid' and p.expiry_date and p.expiry_date > current_time
            ),
            None
        )

        return render_template('payment_status.html',
                               payments=payments,
                               latest_payment=latest_payment,
                               active_subscription=active_subscription,
                               current_time=current_time)

    except Exception as e:
        app.logger.error(f"Error in payment_status: {str(e)}")
        flash('Error loading payment status. Please try again.', 'danger')
        return redirect(url_for('dashboard'))


# Update your predict route to check payment
from datetime import datetime, timedelta


@app.route('/payment/status/<int:payment_id>')
@login_required
def check_payment_status(payment_id):
    payment = Payment.query.get_or_404(payment_id)

    if payment.user_id != current_user.id:
        abort(403)

    # In production, you would verify with M-Pesa API here
    # For demo, we'll just return the current status
    return jsonify({
        'status': payment.status,
        'receipt': payment.mpesa_receipt
    })

import glob


@app.route('/payment/complete/<int:payment_id>')
@login_required
def payment_complete(payment_id):
    payment = Payment.query.get_or_404(payment_id)

    # Verify payment belongs to current user and is successful
    if payment.user_id != current_user.id or payment.status != 'paid':
        abort(403)

    # Redirect to select_plant page instead of predict
    flash('Payment successful! Please select a plant to analyze', 'success')
    return redirect(url_for('select_plant'))


def send_payment_confirmation_email(user, payment_plan, amount, expiry_date):
    """Send payment confirmation email to user"""
    try:
        # Format the email content based on payment plan
        plan_name = "Monthly" if payment_plan == 'monthly' else "Weekly"
        duration = "30 days" if payment_plan == 'monthly' else "7 days"

        subject = f"PlantMD - {plan_name} Subscription Confirmation"

        body = f"""
Dear {user.username},

Thank you for subscribing to PlantMD's {plan_name} package!

Your payment details:
- Package: {plan_name} Subscription
- Amount: KSh {amount}
- Duration: {duration}
- Expiry Date: {expiry_date.strftime('%Y-%m-%d')}
- Features: Plant disease detection, Community forum access, Expert recommendations

Your subscription is now active and you can start using all features immediately.

To get started:
1. Visit the 'Select Plant' page to choose which plant you want to analyze
2. Upload clear images of plant leaves for disease detection
3. Access detailed treatment plans and prevention schedules
4. Join our community forum to share experiences

If you have any questions, please don't hesitate to contact our support team.

Happy Farming!

Best regards,
The PlantMD Team
"""

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #28a745; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .details {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .feature {{ margin: 10px 0; padding: 10px; background: #e9f7ef; border-left: 4px solid #28a745; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌿 PlantMD Subscription Confirmed</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{user.username}</strong>,</p>
            <p>Thank you for subscribing to PlantMD's <strong>{plan_name}</strong> package!</p>

            <div class="details">
                <h3>📋 Payment Details</h3>
                <p><strong>Package:</strong> {plan_name} Subscription</p>
                <p><strong>Amount:</strong> KSh {amount}</p>
                <p><strong>Duration:</strong> {duration}</p>
                <p><strong>Expiry Date:</strong> {expiry_date.strftime('%Y-%m-%d')}</p>
            </div>

            <h3>🚀 What's Included</h3>
            <div class="feature">✅ Unlimited plant disease detection</div>
            <div class="feature">✅ Detailed treatment recommendations</div>
            <div class="feature">✅ Phytomedicine (natural remedy) suggestions</div>
            <div class="feature">✅ Prevention schedules and calendars</div>
            <div class="feature">✅ Community forum access</div>
            <div class="feature">✅ County-specific disease alerts</div>

            <h3>🎯 Getting Started</h3>
            <ol>
                <li>Visit the 'Select Plant' page</li>
                <li>Choose the plant type you want to analyze</li>
                <li>Upload clear images of plant leaves</li>
                <li>Get instant disease detection and treatment plans</li>
            </ol>

            <p>If you have any questions, please don't hesitate to contact our support team.</p>

            <p style="text-align: center; margin-top: 30px;">
                <strong>Happy Farming! 🌱</strong>
            </p>
        </div>
        <div class="footer">
            <p>Best regards,<br>The PlantMD Team</p>
            <p><small>This is an automated email, please do not reply directly.</small></p>
        </div>
    </div>
</body>
</html>
"""

        msg = Message(
            subject=subject,
            recipients=[user.email],
            body=body,
            html=html_body
        )

        mail.send(msg)
        app.logger.info(f"Payment confirmation email sent to {user.email}")
        return True

    except Exception as e:
        app.logger.error(f"Failed to send payment confirmation email: {str(e)}")
        return False

def generate_prevention_events(disease_name):
    """Generate prevention schedule based on disease type"""
    base_events = [
        {"title": "Apply Initial Treatment", "days": 0, "type": "treatment"},
        {"title": "First Follow-up Inspection", "days": 3, "type": "inspection"},
        {"title": "Apply Preventive Spray", "days": 7, "type": "treatment"},
        {"title": "Soil Nutrient Check", "days": 14, "type": "maintenance"},
        {"title": "Final Evaluation", "days": 21, "type": "inspection"}
    ]

    return [
        {
            "title": f"{event['title']} ({disease_name})",
            "start": (datetime.now() + timedelta(days=event["days"])).strftime("%Y-%m-%d"),
            "color": "#28a745" if event["type"] == "treatment" else
            "#17a2b8" if event["type"] == "inspection" else
            "#6c757d"
        }
        for event in base_events
    ]


@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def create_post():
    form = PostForm()
    if form.validate_on_submit():
        post = ForumPost(
            title=form.title.data,
            content=form.content.data,
            disease=form.disease.data,
            county_id=form.county.data,  # Use county_id instead of county
            user_id=current_user.id
        )
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('forum'))
    return render_template('create_post.html', form=form)


@app.route('/forum/comment', methods=['POST'])
@login_required
def create_forum_comment():
    post_id = request.form.get('post_id')
    content = request.form.get('content')

    if not content or not post_id:
        flash('Comment cannot be empty', 'danger')
        return redirect(request.referrer)

    new_comment = ForumComment(
        content=content,
        user_id=current_user.id,
        post_id=post_id
    )
    db.session.add(new_comment)
    db.session.commit()

    flash('Your comment has been added!', 'success')
    return redirect(request.referrer)

@app.route('/forum/post/new', methods=['GET', 'POST'])
@login_required
def create_forum_post():
    form = PostForm()
    if form.validate_on_submit():
        post = ForumPost(
            title=form.title.data,
            content=form.content.data,
            disease=form.disease.data,
            county_id=form.county.data,  # Use county_id instead of county
            user_id=current_user.id      # Explicitly set user_id
        )
        db.session.add(post)
        try:
            db.session.commit()
            flash('Post created successfully!', 'success')
            return redirect(url_for('forum'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating post: {str(e)}', 'danger')
    return render_template('create_post.html', form=form)

from werkzeug.utils import secure_filename
import os


@app.route('/create_comment', methods=['POST'])
@login_required
def create_comment():
    content = request.form.get('content', '').strip()
    post_id = request.form.get('post_id')

    if not content or not post_id:
        flash('Comment cannot be empty', 'danger')
        return redirect(request.referrer)

    # Handle photo upload for comment
    photo_filename = None
    photo = request.files.get('photo')
    if photo and photo.filename:
        filename = secure_filename(
            f"comment_{current_user.id}_{datetime.now().timestamp()}.{photo.filename.split('.')[-1]}"
        )
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'comment_photos', filename)
        os.makedirs(os.path.dirname(photo_path), exist_ok=True)
        photo.save(photo_path)
        photo_filename = os.path.join('comment_photos', filename)

    # Create new comment using ForumComment model
    new_comment = ForumComment(
        content=content,
        user_id=current_user.id,
        post_id=int(post_id),
        photo=photo_filename
    )
    db.session.add(new_comment)
    db.session.commit()
    flash('Comment added successfully!', 'success')
    return redirect(request.referrer)


def get_kenyan_counties():
    return [
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


@app.route('/forum_posts')
def forum_posts():
    county = request.args.get('county', None)
    query = ForumPost.query

    if county:
        county_obj = County.query.filter_by(name=county).first()
        if county_obj:
            query = query.filter_by(county_id=county_obj.id)

    posts = query.order_by(ForumPost.created_at.desc()).all()
    return render_template('forum.html', posts=posts, counties=get_kenyan_counties())

@app.route('/predict', methods=['GET', 'POST'])
@login_required
def predict():
    # Payment check
    active_payment = Payment.query.filter(
        Payment.user_id == current_user.id,
        Payment.status == 'paid',
        or_(
            Payment.expiry_date.is_(None),
            Payment.expiry_date >= datetime.utcnow()
        )
    ).first()

    if not active_payment:
        flash('Please complete payment to access predictions', 'warning')
        return redirect(url_for('payment'))

    # Get plant_type from query parameters
    plant_type = request.args.get('plant_type')

    if not plant_type:
        flash('Please select a plant type first', 'error')
        return redirect(url_for('select_plant'))

    plant_mapping = {
        'apple': 'Apple',
        'blueberry': 'Blueberry',
        'cherry': 'Cherry_(including_sour)',
        'corn': 'Corn_(maize)',
        'grape': 'Grape',
        'orange': 'Orange',
        'peach': 'Peach',
        'pepper': 'Pepper,_bell',
        'potato': 'Potato',
        'raspberry': 'Raspberry',
        'soybean': 'Soybean',
        'squash': 'Squash',
        'strawberry': 'Strawberry',
        'tomato': 'Tomato'
    }

    # Get and validate plant_type
    plant_type = request.args.get('plant_type', '').lower()
    if not plant_type or plant_type not in plant_mapping:
        flash('Please select a valid plant type first', 'error')
        return redirect(url_for('select_plant'))

    plant_prefix = plant_mapping[plant_type]
    MIN_CONFIDENCE = 0.0

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            try:
                # Save uploaded file
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                web_image_path = 'uploads/' + filename

                # Make prediction
                top_disease, confidence = predict_disease(filepath, plant_prefix)

                if confidence < MIN_CONFIDENCE:
                    flash('Prediction confidence too low - please upload a clearer image', 'warning')
                    return redirect(request.url)

                # Get disease information
                disease_data = disease_info.get(top_disease, {
                    'scientific_name': 'Unknown',
                    'treatment': 'Consult agricultural expert',
                    'agrovet_medications': [],
                    'phytomedicine': 'Not specified',
                    'prevention': 'Practice good crop management'
                })

                # Format disease name for display
                display_name = top_disease.replace(f"{plant_prefix}___", "").replace("_", " ")

                # Generate prevention schedule
                prevention_events = generate_prevention_events(display_name)

                # Get example images
                example_images = []
                disease_folder = os.path.join('static', 'disease pics',
                                            'Plant_leave_diseases_dataset_without_augmentation',
                                            top_disease)

                if os.path.exists(disease_folder):
                    example_images = [
                        os.path.join('disease pics',
                                    'Plant_leave_diseases_dataset_without_augmentation',
                                    top_disease,
                                    f).replace('\\', '/')
                        for f in sorted(os.listdir(disease_folder))
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
                    ][:5]
                disease_folder_display = os.path.join(
                    'static',
                    'disease pics',
                    'Plant_leave_diseases_dataset_without_augmentation',
                    top_disease,
                ).replace('\\', '/')

                # Get community forum posts
                county_filter = request.args.get('county')
                forum_query = ForumPost.query.filter(
                    ForumPost.disease.ilike(f"%{display_name}%")
                )

                if county_filter:
                    forum_query = forum_query.filter_by(county=county_filter)

                forum_posts = forum_query.order_by(
                    ForumPost.created_at.desc()
                ).limit(5).all()

                counties = County.query.order_by(County.name).all()

                # Save prediction to database
                new_prediction = Prediction(
                    image_path=filepath,
                    plant_type=plant_type,
                    disease=display_name,
                    scientific_name=disease_data['scientific_name'],
                    phytomedicine=disease_data['phytomedicine'],
                    treatment=disease_data['treatment'],
                    prevention=disease_data['prevention'],
                    confidence=confidence,
                    user_id=current_user.id
                )
                db.session.add(new_prediction)
                db.session.commit()

                return render_template('predict_result.html',
                                    plant_type=plant_type.capitalize(),
                                    disease_name=display_name,
                                    scientific_name=disease_data['scientific_name'],
                                    treatment=disease_data['treatment'],
                                    agrovet_medications=disease_data.get('agrovet_medications', []),
                                    phytomedicine=disease_data['phytomedicine'],
                                    prevention=disease_data['prevention'],
                                    confidence=round(confidence * 100, 2),
                                    user_image=web_image_path,
                                    example_images=example_images,
                                    disease_folder_display=disease_folder_display,
                                    prevention_events=prevention_events,
                                    forum_posts=forum_posts,
                                    counties=counties)

            except Exception as e:
                flash(f'Error processing image: {str(e)}', 'error')
                return redirect(request.url)

    return render_template('predict.html', plant_type=plant_type)
# routes.py
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = CountyForm(obj=current_user)
    if form.validate_on_submit():
        current_user.county = form.county.data
        db.session.commit()
        flash('Your county has been updated!', 'success')  # Added category
        return redirect(url_for('profile'))
    return render_template('profile.html', form=form)


# routes.py
@app.route('/forum')
def forum():
    county_name = request.args.get('county')
    disease = request.args.get('disease')

    query = ForumPost.query.order_by(ForumPost.created_at.desc())

    if county_name:
        county = County.query.filter_by(name=county_name).first()
        if county:
            query = query.filter_by(county_id=county.id)

    if disease:
        query = query.filter_by(disease=disease)

    posts = query.all()

    # Get list of counties as (id, name) tuples for the dropdown
    county_choices = [(c.id, c.name) for c in County.query.order_by(County.name).all()]

    # Get list of unique diseases for filter dropdown
    diseases = db.session.query(ForumPost.disease).distinct().all()
    diseases = [d[0] for d in diseases if d[0]]  # Flatten and remove None

    return render_template(
        'forum.html',
        posts=posts,
        counties=county_choices,  # Pass the prepared choices
        diseases=diseases,
        selected_county=county_name
    )
@app.route('/forum/post/<int:post_id>')
def view_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    return render_template('view_post.html', post=post)


@app.route('/pay', methods=['POST'])
@login_required
def pay():
    amount = request.form.get('amount')
    phone = current_user.phone
    flash(f'Payment of KSh {amount} initiated for phone {phone}')
    return redirect(url_for('dashboard'))


# --- Application Startup ---
def get_model():
    """Load Keras model on first use, store in Flask global context."""
    if 'model' not in g:
        print("Loading Keras model… please wait, this may take 20–30 seconds")
        model_path = os.path.join(os.path.dirname(__file__), "trained_plant_model.keras")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at: {model_path}")
        from tensorflow.keras.models import load_model
        g.model = load_model(model_path)
        print("Model loaded successfully!")
    return g.model


if __name__ == '__main__':
    # Only run the server, don't drop/create tables here
    app.run(debug=True, port=5001, use_reloader=False)