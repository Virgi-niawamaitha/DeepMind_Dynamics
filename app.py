import os
import glob
import random
import json

import requests
from flask import Flask, render_template, request, redirect, url_for, flash, abort, g, jsonify
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
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

from models import County, User, Prediction, Payment, UserCalendar, ForumPost, ForumComment, PostPhoto, db
from forms import LoginForm, RegistrationForm, PredictionForm, CommentForm, PostForm, CountyForm, PaymentForm
from forms import KENYAN_COUNTIES, initialize_counties

from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv

from mpesa import MpesaGateway

# Initialize Flask app
app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
load_dotenv()

try:
    mpesa = MpesaGateway()
    MPESA_AVAILABLE = True
except Exception as exc:
    mpesa = None
    MPESA_AVAILABLE = False
    print(f"M-Pesa disabled at startup: {exc}")
print("MAIL_USERNAME loaded:", os.getenv('MAIL_USERNAME') is not None)
print("SECRET_KEY loaded:", os.getenv('SECRET_KEY') is not None)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Initialize database
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

with app.app_context():
    db.create_all()
    initialize_counties()

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Language preference storage (in session)
def get_user_language():
    return session.get('language', 'en')

def set_user_language(lang):
    session['language'] = lang

# ============== KISWAHILI TRANSLATIONS ==============
translations = {
    'en': {
        'welcome': 'Welcome to PlantMD',
        'dashboard': 'Dashboard',
        'predict': 'Predict Disease',
        'forum': 'Community Forum',
        'payment': 'Payment',
        'profile': 'Profile',
        'logout': 'Logout',
        'login': 'Login',
        'register': 'Register',
        'disease_detected': 'Disease Detected',
        'confidence': 'Confidence',
        'treatment': 'Treatment',
        'prevention': 'Prevention',
        'phytomedicine': 'Phytomedicine (Natural Remedy)',
        'drug_recommendations': 'Drug Recommendations',
        'scientific_name': 'Scientific Name',
        'dosage': 'Dosage',
        'frequency': 'Frequency',
        'warning': 'Warning',
        'select_plant': 'Select Plant Type',
        'upload_image': 'Upload Image',
        'analyze': 'Analyze',
        'back': 'Back',
        'share_experience': 'Share Your Experience',
        'comments': 'Comments',
        'add_comment': 'Add Comment',
        'subscription_active': 'Your subscription is active',
        'subscription_expired': 'Your subscription has expired',
        'pay_now': 'Pay Now',
        'monthly': 'Monthly',
        'weekly': 'Weekly',
        'amount': 'Amount',
        'phone_number': 'Phone Number',
        'payment_successful': 'Payment Successful',
        'payment_failed': 'Payment Failed',
        'kenyan_shillings': 'KSh'
    },
    'sw': {
        'welcome': 'Karibu PlantMD',
        'dashboard': 'Dashibodi',
        'predict': 'Tabiri Ugonjwa',
        'forum': 'Jukwaa la Jamii',
        'payment': 'Malipo',
        'profile': 'Wasifu',
        'logout': 'Toka',
        'login': 'Ingia',
        'register': 'Jisajili',
        'disease_detected': 'Ugonjwa Uligunduliwa',
        'confidence': 'Uhakika',
        'treatment': 'Matibabu',
        'prevention': 'Kinga',
        'phytomedicine': 'Dawa za Asili',
        'drug_recommendations': 'Mapendekezo ya Dawa',
        'scientific_name': 'Jina la Kisayansi',
        'dosage': 'Kipimo',
        'frequency': 'Mara ngapi',
        'warning': 'Tahadhari',
        'select_plant': 'Chagua Aina ya Mmea',
        'upload_image': 'Pakia Picha',
        'analyze': 'Chambua',
        'back': 'Rudi',
        'share_experience': 'Shiriki Uzoefu Wako',
        'comments': 'Maoni',
        'add_comment': 'Ongeza Maoni',
        'subscription_active': 'Usajili wako ni hai',
        'subscription_expired': 'Usajili wako umeisha',
        'pay_now': 'Lipa Sasa',
        'monthly': 'Kila Mwezi',
        'weekly': 'Kila Wiki',
        'amount': 'Kiasi',
        'phone_number': 'Namba ya Simu',
        'payment_successful': 'Malipo Yamekamilika',
        'payment_failed': 'Malipo Yameshindikana',
        'kenyan_shillings': 'KSh'
    }
}

def t(key, lang=None):
    """Translation helper function"""
    if lang is None:
        lang = get_user_language()
    return translations.get(lang, translations['en']).get(key, key)

# ============== DISEASE INFORMATION WITH KISWAHILI AND DRUGS ==============
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

# Complete disease information with Kiswahili names and drug recommendations
disease_info = {
    'Apple___Apple_scab': {
        'scientific_name': 'Venturia inaequalis',
        'swahili_name': 'Ukungu wa Tufaha',
        'treatment': 'Apply copper-based fungicides or sulfur sprays. Prune infected branches and destroy fallen leaves.',
        'treatment_sw': 'Tumia dawa za kuua ukungu zenye shaba au salfa. Kata matawi yaliyoathirika na choma majani yaliyoanguka.',
        'phytomedicine': 'Neem oil (Azadirachta indica) spray every 10 days',
        'phytomedicine_sw': 'Mafuta ya Mwarobaini kila siku 10',
        'prevention': 'Plant resistant varieties, maintain proper tree spacing, remove infected plant debris',
        'prevention_sw': 'Panda aina zinazokinza, weka umbali mwafaka kati ya miti, ondoa mabaki ya mimea yenye ugonjwa',
        'drugs': [
            {'name': 'Copper hydroxide', 'name_sw': 'Hidroksidi ya Shaba', 'dosage': '2g per liter water', 'dosage_sw': '2g kwa lita moja ya maji', 'frequency': 'Every 7-10 days', 'frequency_sw': 'Kila siku 7-10'},
            {'name': 'Mancozeb', 'name_sw': 'Mancozeb', 'dosage': '2.5g per liter', 'dosage_sw': '2.5g kwa lita', 'frequency': 'Weekly during wet season', 'frequency_sw': 'Kila wiki wakati wa mvua'}
        ]
    },
    'Apple___Black_rot': {
        'scientific_name': 'Botryosphaeria obtusa',
        'swahili_name': 'Uozo Mweusi wa Tufaha',
        'treatment': 'Remove mummified fruits and infected branches. Apply captan fungicide.',
        'treatment_sw': 'Ondoa matunda yaliyokauka na matawi yenye ugonjwa. Tumia dawa ya captan.',
        'phytomedicine': 'Garlic (Allium sativum) and chili pepper extract spray',
        'phytomedicine_sw': 'Dawa ya kitunguu saumu na pilipili kali',
        'prevention': 'Avoid tree wounds, practice good orchard sanitation',
        'prevention_sw': 'Epuka kuumiza miti, safisha shamba vizuri',
        'drugs': [
            {'name': 'Captan 50WP', 'name_sw': 'Captan 50WP', 'dosage': '2g per liter', 'dosage_sw': '2g kwa lita', 'frequency': 'Every 10-14 days', 'frequency_sw': 'Kila siku 10-14'},
            {'name': 'Copper oxychloride', 'name_sw': 'Oksikloridi ya Shaba', 'dosage': '2.5g per liter', 'dosage_sw': '2.5g kwa lita', 'frequency': 'Weekly', 'frequency_sw': 'Kila wiki'}
        ]
    },
    'Potato___Late_blight': {
        'scientific_name': 'Phytophthora infestans',
        'swahili_name': 'Kivujiju cha Viazi',
        'treatment': 'Apply metalaxyl or chlorothalonil fungicides. Destroy infected plants immediately.',
        'treatment_sw': 'Tumia dawa za metalaxyl au chlorothalonil. Haribu mimea yenye ugonjwa mara moja.',
        'phytomedicine': 'Horsetail tea spray every 5 days',
        'phytomedicine_sw': 'Chai ya kimbia kila siku 5',
        'prevention': 'Plant resistant varieties, avoid overhead irrigation, crop rotation',
        'prevention_sw': 'Panda aina zinazokinza, epuka kumwagilia maji kwa kunyeshea, mzunguko wa mazao',
        'drugs': [
            {'name': 'Ridomil Gold MZ 68WG', 'name_sw': 'Ridomil Gold MZ 68WG', 'dosage': '2.5g per liter water', 'dosage_sw': '2.5g kwa lita moja ya maji', 'frequency': 'Every 5-7 days', 'frequency_sw': 'Kila siku 5-7'},
            {'name': 'Dithane M-45 80WP', 'name_sw': 'Dithane M-45 80WP', 'dosage': '2g per liter water', 'dosage_sw': '2g kwa lita moja ya maji', 'frequency': 'Weekly', 'frequency_sw': 'Kila wiki'},
            {'name': 'Acrobat MZ 69WP', 'name_sw': 'Acrobat MZ 69WP', 'dosage': '2g per liter', 'dosage_sw': '2g kwa lita', 'frequency': 'Every 7 days', 'frequency_sw': 'Kila siku 7'}
        ]
    },
    'Tomato___Late_blight': {
        'scientific_name': 'Phytophthora infestans',
        'swahili_name': 'Kivujiju cha Nyanya',
        'treatment': 'Apply chlorothalonil or metalaxyl fungicides. Destroy infected plants.',
        'treatment_sw': 'Tumia dawa za chlorothalonil au metalaxyl. Haribu mimea yenye ugonjwa.',
        'phytomedicine': 'Horsetail tea spray every 5 days',
        'phytomedicine_sw': 'Chai ya kimbia kila siku 5',
        'prevention': 'Resistant varieties, avoid overhead watering, proper staking',
        'prevention_sw': 'Aina zinazokinza, epuka kumwagilia kwa kunyeshea, weka vigingi vizuri',
        'drugs': [
            {'name': 'Ridomil Gold MZ 68WG', 'name_sw': 'Ridomil Gold MZ 68WG', 'dosage': '2.5g per liter', 'dosage_sw': '2.5g kwa lita', 'frequency': 'Every 5-7 days', 'frequency_sw': 'Kila siku 5-7'},
            {'name': 'Dithane M-45', 'name_sw': 'Dithane M-45', 'dosage': '2g per liter', 'dosage_sw': '2g kwa lita', 'frequency': 'Weekly', 'frequency_sw': 'Kila wiki'},
            {'name': 'Bravo 720SC', 'name_sw': 'Bravo 720SC', 'dosage': '1.5ml per liter', 'dosage_sw': '1.5ml kwa lita', 'frequency': 'Every 7-10 days', 'frequency_sw': 'Kila siku 7-10'}
        ]
    },
    'Tomato___Early_blight': {
        'scientific_name': 'Alternaria solani',
        'swahili_name': 'Ukungu wa Mapema wa Nyanya',
        'treatment': 'Apply chlorothalonil, remove lower leaves',
        'treatment_sw': 'Tumia chlorothalonil, ondoa majani ya chini',
        'phytomedicine': 'Fermented stinging nettle extract',
        'phytomedicine_sw': 'Dawa ya kienyeji ya kigutu',
        'prevention': 'Crop rotation, proper plant spacing',
        'prevention_sw': 'Mzunguko wa mazao, umbali mwafaka wa mimea',
        'drugs': [
            {'name': 'Chlorothalonil 720SC', 'name_sw': 'Chlorothalonil 720SC', 'dosage': '2ml per liter', 'dosage_sw': '2ml kwa lita', 'frequency': 'Every 7 days', 'frequency_sw': 'Kila siku 7'},
            {'name': 'Copper oxychloride', 'name_sw': 'Oksikloridi ya Shaba', 'dosage': '2g per liter', 'dosage_sw': '2g kwa lita', 'frequency': 'Weekly', 'frequency_sw': 'Kila wiki'},
            {'name': 'Mancozeb', 'name_sw': 'Mancozeb', 'dosage': '2g per liter', 'dosage_sw': '2g kwa lita', 'frequency': 'Every 5-7 days', 'frequency_sw': 'Kila siku 5-7'}
        ]
    },
    'Corn_(maize)___Common_rust_': {
        'scientific_name': 'Puccinia sorghi',
        'swahili_name': 'Kutu wa Mahindi',
        'treatment': 'Apply triazole fungicides at disease onset',
        'treatment_sw': 'Tumia dawa za triazole ugonjwa unapoanza',
        'phytomedicine': 'Lantana camara leaf extract spray',
        'phytomedicine_sw': 'Dawa ya majani ya mwabangwangu',
        'prevention': 'Early planting, resistant varieties, balanced fertilization',
        'prevention_sw': 'Panda mapema, aina zinazokinza, mbolea bora',
        'drugs': [
            {'name': 'Azoxystrobin', 'name_sw': 'Azoxystrobin', 'dosage': '1ml per liter', 'dosage_sw': '1ml kwa lita', 'frequency': 'Every 10-14 days', 'frequency_sw': 'Kila siku 10-14'},
            {'name': 'Propiconazole', 'name_sw': 'Propiconazole', 'dosage': '1ml per liter', 'dosage_sw': '1ml kwa lita', 'frequency': 'Weekly', 'frequency_sw': 'Kila wiki'},
            {'name': 'Tebuconazole', 'name_sw': 'Tebuconazole', 'dosage': '0.8ml per liter', 'dosage_sw': '0.8ml kwa lita', 'frequency': 'Every 7-10 days', 'frequency_sw': 'Kila siku 7-10'}
        ]
    },
    'Grape___Black_rot': {
        'scientific_name': 'Guignardia bidwellii',
        'swahili_name': 'Uozo Mweusi wa Zabibu',
        'treatment': 'Apply fungicides early in season, remove infected material',
        'treatment_sw': 'Tumia dawa mapema msimu, ondoa vitu vilivyoathirika',
        'phytomedicine': 'Fermented pawpaw leaf extract',
        'phytomedicine_sw': 'Dawa ya majani ya papai',
        'prevention': 'Proper pruning, canopy management, remove mummified fruits',
        'prevention_sw': 'Kata vizuri, weka mizabibu vizuri, ondoa matunda yaliyokauka',
        'drugs': [
            {'name': 'Mancozeb', 'name_sw': 'Mancozeb', 'dosage': '2g per liter', 'dosage_sw': '2g kwa lita', 'frequency': 'Every 7-10 days', 'frequency_sw': 'Kila siku 7-10'},
            {'name': 'Myclobutanil', 'name_sw': 'Myclobutanil', 'dosage': '0.5ml per liter', 'dosage_sw': '0.5ml kwa lita', 'frequency': 'Weekly', 'frequency_sw': 'Kila wiki'}
        ]
    },
    'Orange___Haunglongbing_(Citrus_greening)': {
        'scientific_name': 'Candidatus Liberibacter asiaticus',
        'swahili_name': 'Ugonjwa wa Kuwaangamiza Michungwa',
        'treatment': 'Remove infected trees, control psyllid vectors',
        'treatment_sw': 'Ondoa miti yenye ugonjwa, dhibiti wadudu wanaoeneza',
        'phytomedicine': 'Neem oil for psyllid control',
        'phytomedicine_sw': 'Mafuta ya Mwarobaini kwa wadudu',
        'prevention': 'Plant disease-free nursery stock, vector monitoring',
        'prevention_sw': 'Panda miche safi, fuatilia wadudu',
        'drugs': [
            {'name': 'Imidacloprid', 'name_sw': 'Imidacloprid', 'dosage': '0.5ml per liter', 'dosage_sw': '0.5ml kwa lita', 'frequency': 'Every 14 days (for vector control)', 'frequency_sw': 'Kila siku 14 (kwa wadudu)'},
            {'name': 'Neem oil (organic)', 'name_sw': 'Mafuta ya Mwarobaini (asili)', 'dosage': '5ml per liter', 'dosage_sw': '5ml kwa lita', 'frequency': 'Weekly', 'frequency_sw': 'Kila wiki'}
        ]
    },
    'Pepper,_bell___Bacterial_spot': {
        'scientific_name': 'Xanthomonas campestris pv. vesicatoria',
        'swahili_name': 'Madoa ya Bakteria kwenye Pilipili',
        'treatment': 'Copper-based bactericides, avoid working with wet plants',
        'treatment_sw': 'Dawa za kuua bakteria zenye shaba, epuka kugusa mimea ikiwa na maji',
        'phytomedicine': 'Fermented African marigold extract',
        'phytomedicine_sw': 'Dawa ya mario na majani',
        'prevention': 'Use disease-free seeds, crop rotation',
        'prevention_sw': 'Tumia mbegu safi, mzunguko wa mazao',
        'drugs': [
            {'name': 'Copper hydroxide', 'name_sw': 'Hidroksidi ya Shaba', 'dosage': '2g per liter', 'dosage_sw': '2g kwa lita', 'frequency': 'Every 7 days', 'frequency_sw': 'Kila siku 7'},
            {'name': 'Streptomycin', 'name_sw': 'Streptomycin', 'dosage': '0.5g per liter', 'dosage_sw': '0.5g kwa lita', 'frequency': 'Every 5-7 days', 'frequency_sw': 'Kila siku 5-7'}
        ]
    },
    'Tomato___Bacterial_spot': {
        'scientific_name': 'Xanthomonas spp.',
        'swahili_name': 'Madoa ya Bakteria kwenye Nyanya',
        'treatment': 'Copper-based bactericides, avoid working with wet plants',
        'treatment_sw': 'Dawa za kuua bakteria zenye shaba, epuka kugusa mimea ikiwa na maji',
        'phytomedicine': 'Garlic and chili pepper extract spray',
        'phytomedicine_sw': 'Dawa ya kitunguu saumu na pilipili kali',
        'prevention': 'Use disease-free seeds, crop rotation',
        'prevention_sw': 'Tumia mbegu safi, mzunguko wa mazao',
        'drugs': [
            {'name': 'Copper hydroxide', 'name_sw': 'Hidroksidi ya Shaba', 'dosage': '2g per liter', 'dosage_sw': '2g kwa lita', 'frequency': 'Every 7 days', 'frequency_sw': 'Kila siku 7'},
            {'name': 'Copper oxychloride', 'name_sw': 'Oksikloridi ya Shaba', 'dosage': '2.5g per liter', 'dosage_sw': '2.5g kwa lita', 'frequency': 'Weekly', 'frequency_sw': 'Kila wiki'}
        ]
    },
    'Tomato___Leaf_Mold': {
        'scientific_name': 'Passalora fulva',
        'swahili_name': 'Ukungu wa Majani kwenye Nyanya',
        'treatment': 'Improve air circulation, apply chlorothalonil',
        'treatment_sw': 'Boresha mzunguko wa hewa, tumia chlorothalonil',
        'phytomedicine': 'Baking soda solution (1 tbsp per liter)',
        'phytomedicine_sw': 'Soda kauni (kijiko 1 kwa lita)',
        'prevention': 'Proper spacing, greenhouse ventilation',
        'prevention_sw': 'Umbali mwafaka, uingizaji hewa kwenye chafu',
        'drugs': [
            {'name': 'Chlorothalonil', 'name_sw': 'Chlorothalonil', 'dosage': '2ml per liter', 'dosage_sw': '2ml kwa lita', 'frequency': 'Every 7 days', 'frequency_sw': 'Kila siku 7'},
            {'name': 'Sulfur', 'name_sw': 'Salfa', 'dosage': '3g per liter', 'dosage_sw': '3g kwa lita', 'frequency': 'Every 5-7 days', 'frequency_sw': 'Kila siku 5-7'}
        ]
    },
    'Tomato___Septoria_leaf_spot': {
        'scientific_name': 'Septoria lycopersici',
        'swahili_name': 'Madoa ya Septoria kwenye Nyanya',
        'treatment': 'Copper-based fungicides, remove infected leaves',
        'treatment_sw': 'Dawa za kuua ukungu zenye shaba, ondoa majani yenye ugonjwa',
        'phytomedicine': 'Fermented African marigold extract',
        'phytomedicine_sw': 'Dawa ya mario na majani',
        'prevention': 'Crop rotation, avoid overhead irrigation',
        'prevention_sw': 'Mzunguko wa mazao, epuka kumwagilia kwa kunyeshea',
        'drugs': [
            {'name': 'Copper hydroxide', 'name_sw': 'Hidroksidi ya Shaba', 'dosage': '2g per liter', 'dosage_sw': '2g kwa lita', 'frequency': 'Every 7 days', 'frequency_sw': 'Kila siku 7'},
            {'name': 'Mancozeb', 'name_sw': 'Mancozeb', 'dosage': '2g per liter', 'dosage_sw': '2g kwa lita', 'frequency': 'Weekly', 'frequency_sw': 'Kila wiki'}
        ]
    }
}

# Default info for healthy plants
healthy_info = {
    'scientific_name': 'Healthy plant',
    'swahili_name': 'Mmea wenye afya',
    'treatment': 'No treatment required. Your plant is healthy!',
    'treatment_sw': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
    'phytomedicine': 'Preventive neem oil sprays every 2 weeks',
    'phytomedicine_sw': 'Dawa ya kuzuia ya mafuta ya Mwarobaini kila wiki 2',
    'prevention': 'Maintain proper nutrition and irrigation, regular pruning',
    'prevention_sw': 'Endelea na lishe bora na umwagiliaji, kata mara kwa mara',
    'drugs': []
}

def get_disease_info(disease_key, language='en'):
    """Get disease information in specified language"""
    if 'healthy' in disease_key.lower():
        info = healthy_info.copy()
    else:
        info = disease_info.get(disease_key, {})
    
    if language == 'sw':
        return {
            'scientific_name': info.get('scientific_name', 'Haijulikani'),
            'swahili_name': info.get('swahili_name', 'Ugonjwa'),
            'treatment': info.get('treatment_sw', info.get('treatment', 'Wasiliana na mtaalamu wa kilimo')),
            'phytomedicine': info.get('phytomedicine_sw', info.get('phytomedicine', 'Hakuna dawa ya asili iliyopendekezwa')),
            'prevention': info.get('prevention_sw', info.get('prevention', 'Endelea na mazoea mazuri ya kilimo')),
            'drugs': info.get('drugs', [])
        }
    else:
        return {
            'scientific_name': info.get('scientific_name', 'Unknown'),
            'swahili_name': info.get('swahili_name', 'Disease'),
            'treatment': info.get('treatment', 'Consult agricultural expert'),
            'phytomedicine': info.get('phytomedicine', 'Not specified'),
            'prevention': info.get('prevention', 'Practice good crop management'),
            'drugs': info.get('drugs', [])
        }

# ============== HELPER FUNCTIONS ==============
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

def ensure_user_profile_photo_column():
    try:
        inspector = inspect(db.engine)
        user_columns = {column['name'] for column in inspector.get_columns('users')}
        if 'profile_photo' not in user_columns:
            db.session.execute(text(
                'ALTER TABLE users ADD COLUMN profile_photo VARCHAR(200)'
            ))
            db.session.commit()
    except Exception as exc:
        app.logger.warning(f'Could not ensure user profile photo column: {exc}')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    ensure_payment_confirmation_column()
    ensure_user_profile_photo_column()

def is_mpesa_available():
    return MPESA_AVAILABLE and mpesa is not None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'webp'}

def load_keras_model():
    model_path = os.path.join(os.path.dirname(__file__), "trained_plant_model.keras")
    print("Loading Keras model… please wait, this may take 20–30 seconds")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found at: {model_path}")
    model = load_model(model_path)
    print("Model loaded successfully!")
    return model

try:
    model = load_keras_model()
    print("Keras model loaded successfully")
except Exception as e:
    print(f"Error loading Keras model: {e}")
    exit(1)

def predict_disease(img_path, plant_prefix):
    img = image.load_img(img_path, target_size=(128, 128))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) / 255.0

    predictions = model.predict(img_array)
    probabilities = predictions[0]

    valid_indices = [i for i, disease in enumerate(disease_classes)
                     if disease.startswith(plant_prefix)]

    if not valid_indices:
        top_disease = f"{plant_prefix}___healthy"
        confidence = 1.0
    else:
        valid_probs = probabilities[valid_indices]
        max_idx = np.argmax(valid_probs)
        top_idx = valid_indices[max_idx]
        top_disease = disease_classes[top_idx]
        confidence = probabilities[top_idx]

    return top_disease, float(confidence)

def generate_prevention_events(disease_name):
    """Generate prevention schedule based on disease type"""
    base_events = [
        {"title": "Apply Initial Treatment / Tumia Matibabu ya Kwanza", "days": 0, "type": "treatment"},
        {"title": "First Follow-up Inspection / Ukaguzi wa Kwanza", "days": 3, "type": "inspection"},
        {"title": "Apply Preventive Spray / Paka Dawa ya Kuzuia", "days": 7, "type": "treatment"},
        {"title": "Soil Nutrient Check / Angalia Rutuba ya Udongo", "days": 14, "type": "maintenance"},
        {"title": "Final Evaluation / Tathmini ya Mwisho", "days": 21, "type": "inspection"}
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

def send_payment_confirmation_email(user, payment_plan, amount, expiry_date):
    """Send payment confirmation email to user"""
    try:
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
            <div class="feature">✅ Drug recommendations with dosages</div>
            <div class="feature">✅ Prevention schedules and calendars</div>
            <div class="feature">✅ Community forum access</div>

            <p>If you have any questions, please don't hesitate to contact our support team.</p>

            <p style="text-align: center; margin-top: 30px;">
                <strong>Happy Farming! 🌱</strong>
            </p>
        </div>
        <div class="footer">
            <p>Best regards,<br>The PlantMD Team</p>
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

# ============== LANGUAGE ROUTE ==============
@app.route('/set_language/<lang>')
def set_language(lang):
    """Set user's language preference and redirect back"""
    if lang in ['en', 'sw']:
        set_user_language(lang)
        flash('Language updated' if lang == 'en' else 'Lugha imebadilishwa', 'success')
    
    # Get the return URL from query parameter or referrer
    next_url = request.args.get('next')
    if next_url:
        return redirect(next_url)
    
    referrer = request.referrer
    if referrer and referrer != request.url:
        return redirect(referrer)
    
    return redirect(url_for('index'))

# ============== FLASK ROUTES ==============
@app.route('/')
def index():
    lang = get_user_language()
    return render_template('index.html', t=t, lang=lang, current_lang=lang)

@app.route('/login', methods=['GET', 'POST'])
def login():
    lang = get_user_language()
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash(t('login_success', lang), 'success')
            return redirect(url_for('dashboard'))
        flash(t('invalid_credentials', lang), 'danger')
    return render_template('login.html', form=form, t=t, lang=lang)

@app.route('/register', methods=['GET', 'POST'])
def register():
    lang = get_user_language()
    form = RegistrationForm()
    if form.validate_on_submit():
        if (session.get('verification_email') != form.email.data or
                session.get('verification_code') != form.verification_code.data or
                session.get('verification_expires', 0) < datetime.now().timestamp()):
            flash(t('invalid_verification', lang), 'danger')
            return redirect(url_for('register'))

        county = County.query.get(form.county.data)
        user = User(
            username=form.username.data,
            email=form.email.data,
            county=county
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        session.pop('verification_email', None)
        session.pop('verification_code', None)
        session.pop('verification_expires', None)

        flash(t('registration_success', lang), 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form, t=t, lang=lang)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    lang = get_user_language()
    predictions = Prediction.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', user=current_user, predictions=predictions, t=t, lang=lang)

@app.route('/send_verification', methods=['POST'])
def send_verification():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            if not email:
                return jsonify({'success': False, 'message': 'Email is required'}), 400

            if User.query.filter_by(email=email).first():
                return jsonify({'success': False, 'message': 'Email already registered'}), 400

            verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

            session['verification_email'] = email
            session['verification_code'] = verification_code
            session['verification_expires'] = datetime.now().timestamp() + 3600

            msg = Message(
                'Your Verification Code',
                recipients=[email],
                body=f'Your verification code is: {verification_code}\n\nThis code expires in 1 hour.'
            )

            mail.send(msg)

            return jsonify({
                'success': True,
                'message': 'Verification code sent to your email'
            })

        except Exception as e:
            app.logger.error(f"Email error: {str(e)}")
            return jsonify({
                'success': False,
                'message': 'Failed to send verification code'
            }), 500

@app.route('/select-plant', methods=['GET', 'POST'])
@login_required
def select_plant():
    lang = get_user_language()
    
    active_payment = Payment.query.filter(
        Payment.user_id == current_user.id,
        Payment.status == 'paid',
        or_(
            Payment.expiry_date.is_(None),
            Payment.expiry_date >= datetime.utcnow()
        )
    ).first()

    if not active_payment:
        flash(t('payment_required', lang), 'warning')
        return redirect(url_for('payment'))

    if request.method == 'POST':
        plant_type = request.form.get('plant_type')
        if plant_type:
            return redirect(url_for('predict', plant_type=plant_type, lang=lang))
        flash(t('select_plant_error', lang), 'error')

    plants = [
        {'id': 'apple', 'name': 'Apple' if lang == 'en' else 'Tufaha'},
        {'id': 'blueberry', 'name': 'Blueberry' if lang == 'en' else 'Blueberry'},
        {'id': 'cherry', 'name': 'Cherry' if lang == 'en' else 'Cherry'},
        {'id': 'corn', 'name': 'Corn' if lang == 'en' else 'Mahindi'},
        {'id': 'grape', 'name': 'Grape' if lang == 'en' else 'Zabibu'},
        {'id': 'orange', 'name': 'Orange' if lang == 'en' else 'Michungwa'},
        {'id': 'peach', 'name': 'Peach' if lang == 'en' else 'Pichi'},
        {'id': 'pepper', 'name': 'Pepper' if lang == 'en' else 'Pilipili'},
        {'id': 'potato', 'name': 'Potato' if lang == 'en' else 'Viazi'},
        {'id': 'raspberry', 'name': 'Raspberry' if lang == 'en' else 'Raspberry'},
        {'id': 'soybean', 'name': 'Soybean' if lang == 'en' else 'Soya'},
        {'id': 'squash', 'name': 'Squash' if lang == 'en' else 'Boga'},
        {'id': 'strawberry', 'name': 'Strawberry' if lang == 'en' else 'Stroberi'},
        {'id': 'tomato', 'name': 'Tomato' if lang == 'en' else 'Nyanya'}
    ]

    return render_template('select_plant.html',
                           plants=plants,
                           payment_success=request.args.get('payment_success'),
                           t=t, lang=lang)
@app.route('/predict', methods=['GET', 'POST'])
@login_required
def predict():
    lang = get_user_language()
    
    active_payment = Payment.query.filter(
        Payment.user_id == current_user.id,
        Payment.status == 'paid',
        or_(
            Payment.expiry_date.is_(None),
            Payment.expiry_date >= datetime.utcnow()
        )
    ).first()

    if not active_payment:
        flash(t('payment_required', lang), 'warning')
        return redirect(url_for('payment'))

    plant_type = request.args.get('plant_type')

    if not plant_type:
        flash(t('select_plant_error', lang), 'error')
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

    plant_type = request.args.get('plant_type', '').lower()
    if not plant_type or plant_type not in plant_mapping:
        flash(t('select_plant_error', lang), 'error')
        return redirect(url_for('select_plant'))

    plant_prefix = plant_mapping[plant_type]
    MIN_CONFIDENCE = 0.0

    if request.method == 'POST':
        if 'file' not in request.files:
            flash(t('no_file', lang), 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash(t('no_file', lang), 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            try:
                # Create uploads directory if it doesn't exist
                upload_folder = app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                
                # Generate unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_filename = secure_filename(file.filename)
                unique_filename = f"{timestamp}_{safe_filename}"
                
                # Save the file
                filepath = os.path.join(upload_folder, unique_filename)
                file.save(filepath)
                
                # Store just the filename, not the full path
                saved_filename = unique_filename
                
                # Make prediction
                top_disease, confidence = predict_disease(filepath, plant_prefix)

                if confidence < MIN_CONFIDENCE:
                    flash(t('low_confidence', lang), 'warning')
                    # Clean up the uploaded file
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    return redirect(request.url)

                # Get disease info in selected language
                disease_data = get_disease_info(top_disease, lang)
                
                # Format disease name for display
                if 'healthy' in top_disease.lower():
                    display_name = 'Healthy' if lang == 'en' else 'Mwenye Afya'
                else:
                    display_name = top_disease.replace(f"{plant_prefix}___", "").replace("_", " ")
                    if lang == 'sw' and disease_data.get('swahili_name'):
                        display_name = disease_data['swahili_name']

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

                # Get community forum posts
                forum_posts = ForumPost.query.filter(
                    ForumPost.disease.ilike(f"%{display_name}%")
                ).order_by(ForumPost.created_at.desc()).limit(5).all()

                counties = County.query.order_by(County.name).all()

                # Save prediction to database
                new_prediction = Prediction(
                    image_path=saved_filename,  # Store just the filename
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
                                    drugs=disease_data.get('drugs', []),
                                    phytomedicine=disease_data['phytomedicine'],
                                    prevention=disease_data['prevention'],
                                    confidence=round(confidence * 100, 2),
                                    user_image=saved_filename,  # Pass just the filename
                                    example_images=example_images,
                                    prevention_events=prevention_events,
                                    forum_posts=forum_posts,
                                    counties=counties,
                                    t=t, lang=lang)

            except Exception as e:
                app.logger.error(f"Error processing image: {str(e)}")
                flash(f'Error processing image: {str(e)}', 'error')
                return redirect(request.url)

    return render_template('predict.html', plant_type=plant_type, t=t, lang=lang)
@app.route('/uploads/<filename>')
# In app.py, add this near your other routes (around line 700-800)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files from the uploads folder"""
    from flask import send_from_directory, abort
    import os
    
    # Security: Prevent directory traversal
    safe_filename = os.path.basename(filename)
    
    # Get the upload folder path
    upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')
    
    # Build the full file path
    filepath = os.path.join(upload_folder, safe_filename)
    
    # Check if file exists
    if not os.path.exists(filepath):
        abort(404)
    
    # Send the file
    return send_from_directory(upload_folder, safe_filename)

@app.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    lang = get_user_language()
    form = PaymentForm()
    if form.validate_on_submit():
        try:
            if not is_mpesa_available():
                flash('M-Pesa is not configured on this server.', 'warning')
                return redirect(url_for('payment'))

            if not mpesa.check_api_status():
                app.logger.error("M-Pesa API unreachable")
                flash(t('mpesa_down', lang), 'danger')
                return redirect(url_for('payment'))

            plan = form.payment_plan.data
            amount = 15 if plan == 'monthly' else 1
            phone = form.phone_number.data

            response = mpesa.stk_push(
                phone_number=f"254{phone[-9:]}",
                amount=amount,
                account_reference=f"USER{current_user.id}",
                transaction_desc="PlantMD Subscription"
            )

            if response.get('success'):
                if plan == 'monthly':
                    expiry_date = datetime.utcnow() + timedelta(days=30)
                else:
                    expiry_date = datetime.utcnow() + timedelta(days=7)

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

                session['pending_payment_id'] = payment.id
                session['payment_plan'] = plan
                session['payment_amount'] = amount
                session['payment_expiry'] = expiry_date.isoformat()

                flash(t('payment_initiated', lang), 'success')
                return render_template(
                    'payment_processing.html',
                    payment=payment,
                    redirect_url=url_for('payment_status'),
                    delay=30000,
                    email_sent=payment.confirmation_sent,
                    t=t, lang=lang
                )

            error_code = response.get('errorCode')
            if error_code == '400.002.02':
                flash(t('invalid_phone', lang), 'danger')
            elif error_code == '400.001.01':
                flash(t('insufficient_balance', lang), 'warning')
            else:
                flash(t('payment_failed', lang), 'danger')

        except requests.exceptions.ConnectionError:
            app.logger.error("M-Pesa API connection failed")
            flash(t('network_error', lang), 'danger')
        except requests.exceptions.Timeout:
            app.logger.error("M-Pesa API timeout")
            flash(t('timeout_error', lang), 'danger')
        except Exception as e:
            app.logger.error(f"Payment error: {str(e)}", exc_info=True)
            flash(t('unexpected_error', lang), 'danger')

    return render_template('payment.html', form=form, t=t, lang=lang)

@app.route('/payment-status')
@login_required
def payment_status():
    lang = get_user_language()
    
    try:
        payments_query = Payment.query.filter_by(user_id=current_user.id)
        if hasattr(Payment, 'created_at'):
            payments_query = payments_query.order_by(Payment.created_at.desc())
        else:
            payments_query = payments_query.order_by(Payment.id.desc())

        payments = payments_query.all()
        current_time = datetime.utcnow()
        latest_payment = payments[0] if payments else None
        status_changed = False

        latest_pending = next((p for p in payments if p.status == 'pending' and p.mpesa_receipt), None)
        if latest_pending and is_mpesa_available():
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
                flash(t('email_sent', lang), 'success')
            if email_failed_any:
                flash(t('email_failed', lang), 'warning')

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
                               current_time=current_time,
                               t=t, lang=lang)

    except Exception as e:
        app.logger.error(f"Error in payment_status: {str(e)}")
        flash(t('status_error', lang), 'danger')
        return redirect(url_for('dashboard'))

@app.route('/forum')
def forum():
    lang = get_user_language()
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

    county_choices = [(c.id, c.name) for c in County.query.order_by(County.name).all()]
    diseases = db.session.query(ForumPost.disease).distinct().all()
    diseases = [d[0] for d in diseases if d[0]]

    return render_template(
        'forum.html',
        posts=posts,
        counties=county_choices,
        diseases=diseases,
        selected_county=county_name,
        t=t, lang=lang
    )

@app.route('/forum/post/<int:post_id>')
def view_post(post_id):
    lang = get_user_language()
    post = ForumPost.query.get_or_404(post_id)
    return render_template('view_post.html', post=post, t=t, lang=lang)

@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def create_post():
    lang = get_user_language()
    form = PostForm()
    
    # Populate county choices
    form.county.choices = [(c.id, c.name) for c in County.query.order_by(County.name).all()]
    
    if form.validate_on_submit():
        try:
            post = ForumPost(
                title=form.title.data,
                content=form.content.data,
                disease=form.disease.data,
                county_id=form.county.data,
                user_id=current_user.id
            )
            db.session.add(post)
            db.session.commit()
            
            # Handle photo uploads if any
            photos = request.files.getlist('photos')
            for photo in photos:
                if photo and photo.filename:
                    filename = secure_filename(f"post_{post.id}_{datetime.now().timestamp()}.{photo.filename.split('.')[-1]}")
                    photo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'post_photos', filename)
                    os.makedirs(os.path.dirname(photo_path), exist_ok=True)
                    photo.save(photo_path)
                    
                    post_photo = PostPhoto(
                        post_id=post.id,
                        filename=os.path.join('post_photos', filename)
                    )
                    db.session.add(post_photo)
            
            db.session.commit()
            flash(t('post_created', lang), 'success')
            return redirect(url_for('forum'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating post: {str(e)}")
            flash(f'Error creating post: {str(e)}', 'danger')
    
    return render_template('create_post.html', form=form, t=t, lang=lang)

@app.route('/forum/comment', methods=['POST'])
@login_required
def create_forum_comment():
    lang = get_user_language()
    post_id = request.form.get('post_id')
    content = request.form.get('content')

    if not content or not post_id:
        flash(t('comment_empty', lang), 'danger')
        return redirect(request.referrer)

    new_comment = ForumComment(
        content=content,
        user_id=current_user.id,
        post_id=post_id
    )
    db.session.add(new_comment)
    db.session.commit()

    flash(t('comment_added', lang), 'success')
    return redirect(request.referrer)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    lang = get_user_language()
    form = CountyForm()
    if request.method == 'GET':
        form.county.data = current_user.county_id
    profile_photo = request.files.get('profile_photo')
    photo_updated = False

    if profile_photo and profile_photo.filename:
        if not allowed_file(profile_photo.filename):
            flash('Profile photo must be a PNG, JPG, JPEG, or WEBP image.', 'danger')
            return redirect(url_for('profile'))

        photo_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_photos')
        os.makedirs(photo_folder, exist_ok=True)
        file_extension = profile_photo.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f'profile_{current_user.id}_{datetime.now().timestamp()}.{file_extension}')
        profile_photo.save(os.path.join(photo_folder, filename))
        current_user.profile_photo = filename
        photo_updated = True

    county_updated = False
    if form.validate_on_submit():
        county = County.query.get(form.county.data)
        if not county:
            flash(t('select_plant_error', lang), 'danger')
            return redirect(url_for('profile'))

        current_user.county = county
        current_user.county_id = county.id
        county_updated = True

    if photo_updated or county_updated:
        db.session.commit()
        flash(t('profile_updated', lang), 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', form=form, t=t, lang=lang)

@app.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    if not is_mpesa_available():
        return jsonify({'status': 'ignored', 'message': 'M-Pesa is not configured'}), 503

    data = request.get_json()
    checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
    result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')

    payment = Payment.query.filter_by(mpesa_receipt=checkout_request_id).first()

    if payment:
        if result_code == 0:
            payment.status = 'paid'
            callback_metadata = data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
            for item in callback_metadata:
                if item.get('Name') == 'MpesaReceiptNumber':
                    payment.mpesa_receipt = item.get('Value')
                    break
            db.session.commit()

            try:
                expiry_date = payment.expiry_date
                if not expiry_date:
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

            except Exception as e:
                app.logger.error(f"Error sending payment confirmation email: {str(e)}")
        else:
            payment.status = 'failed'
            db.session.commit()

    return jsonify({'status': 'received'})

if __name__ == '__main__':
    app.run(debug=True, port=5001, use_reloader=False)