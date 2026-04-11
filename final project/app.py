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

mpesa = MpesaGateway()
print("MAIL_USERNAME loaded:", os.getenv('MAIL_USERNAME') is not None)
print("SECRET_KEY loaded:", os.getenv('SECRET_KEY') is not None)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
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

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Initialize database
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Language preference storage (in session)
def get_user_language():
    return session.get('language', 'en')

def set_user_language(lang):
    session['language'] = lang

# ============== KISWAHILI TRANSLATIONS ==============
translations = {
    'en': {
        # Legacy keys (kept for backward compatibility)
        'welcome': 'Welcome to PlantDoc',
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
        'upload_image': 'Upload Image',
        'analyze': 'Analyze',
        'share_experience': 'Share Your Experience',
        'add_comment': 'Add Comment',
        'subscription_active': 'Your subscription is active',
        'subscription_expired': 'Your subscription has expired',
        'pay_now': 'Pay Now',
        'payment_successful': 'Payment Successful',
        'payment_failed': 'Payment Failed',
        'kenyan_shillings': 'KSh',
        # Navigation
        'nav_home': 'Home',
        'nav_community': 'Community',
        'nav_dashboard': 'Dashboard',
        'nav_new_scan': 'New Scan',
        'nav_account': 'Account',
        'nav_profile': 'Profile',
        'nav_subscription': 'Subscription',
        'nav_logout': 'Logout',
        'nav_login': 'Login',
        'nav_register': 'Register',
        'nav_language': 'Language',
        # Footer
        'footer_tagline': 'Helping farmers detect plant diseases early for better crop yields.',
        'footer_quick_links': 'Quick Links',
        'footer_contact': 'Contact',
        'footer_copyright': '\u00a9 2025 PlantDoc. All rights reserved.',
        # Index page
        'index_hero_title': 'Plant Disease Detection',
        'index_hero_subtitle': 'Identify plant diseases quickly and get treatment recommendations',
        'index_start_prediction': 'Start New Prediction',
        'index_get_started': 'Get Started',
        'index_how_works_title': 'How Our System Works',
        'index_upload_title': 'Upload Image',
        'index_upload_desc': 'Capture clear photos of affected leaves using your smartphone or camera',
        'index_upload_tip1': 'Focus on affected areas',
        'index_upload_tip2': 'Use natural lighting',
        'index_upload_tip3': 'Include whole leaf when possible',
        'index_ai_title': 'AI Analysis',
        'index_ai_desc': 'Our deep learning model processes your image in seconds',
        'index_model_accuracy': 'Model accuracy:',
        'index_across_crops': '96% across common crops',
        'index_treatment_title': 'Get Treatment',
        'index_treatment_desc': 'Immediate actionable recommendations',
        'index_organic': 'Organic',
        'index_chemical': 'Chemical',
        'index_prevention': 'Prevention',
        'index_crops_title': 'We Detect Diseases in 14+ Crops',
        'index_crops_subtitle': 'Our system recognizes common diseases affecting:',
        'index_see_full_list': 'See Full List',
        'index_stories_title': 'Farmer Success Stories',
        'index_saved_crop': 'Saved My Entire Crop',
        'index_saved_quote': '"Detected rust disease early and followed the organic treatment plan. Yield increased by 40%!"',
        'index_nakuru': 'Nakuru County',
        # Login page
        'login_title': 'Login',
        'login_remember': 'Remember me',
        'login_no_account': "Don't have an account?",
        'login_register_link': 'Register',
        # Register page
        'register_title': 'Register',
        'register_send_code': 'Send Code',
        'register_sending': 'Sending\u2026',
        'register_have_account': 'Already have an account?',
        'register_login_here': 'Login here',
        'register_email_empty': 'Please enter your email first',
        'register_code_sent': 'Verification code sent to your email!',
        'register_send_failed': 'Failed to send verification code',
        'register_error': 'An error occurred',
        # Dashboard
        'dashboard_welcome': 'Welcome,',
        'dashboard_new_prediction': 'New Prediction',
        'dashboard_recent': 'Your Recent Predictions',
        'dashboard_treatment_label': 'Treatment:',
        'dashboard_no_predictions': "You haven't made any predictions yet.",
        'dashboard_start_first': 'Start your first prediction',
        # Predict / Upload
        'predict_upload_title': 'Upload Image',
        'predict_select_image': 'Select Image',
        'predict_upload_hint': 'Upload a clear photo of the affected plant part (max 16MB)',
        'predict_btn': 'Predict Disease',
        # Select plant
        'select_plant_title': 'Select Plant Type',
        'select_plant': 'Select Plant Type',
        'select_plant_desc': 'Please choose the plant you want to analyze for diseases:',
        'select_plant_back': 'Back to Dashboard',
        'select_plant_error': 'Please select a plant type',
        'low_confidence': 'Image quality too low to make a reliable prediction. Please upload a clear, close-up photo of the affected leaf or fruit in good lighting.',
        'payment_required': 'A subscription is required to access disease detection.',
        # Forum
        'forum_title': 'Community Forum',
        'forum': 'Community Forum',
        'forum_new_post': 'New Post',
        'forum_filter_county': 'Filter by County:',
        'forum_all_counties': 'All Counties',
        'forum_apply': 'Apply',
        'forum_clear_filter': 'Clear Filter',
        'forum_posted_by': 'Posted by',
        'forum_from': 'from',
        'forum_county': 'County',
        'forum_comments': 'Comments',
        'forum_write_comment': 'Write a comment\u2026',
        'forum_add_photo': 'Add Photo',
        'forum_max_5mb': 'Max 5MB',
        'forum_post_btn': 'Post',
        'forum_no_posts': 'No posts available yet. Start the discussion!',
        'forum_close': 'Close',
        'forum_delete_comment': 'Delete',
        'forum_delete_post': 'Delete Post',
        'forum_confirm_delete_comment': 'Delete this comment?',
        'forum_confirm_delete_post': 'Delete this post and all its comments?',
        'comment_added': 'Comment posted successfully.',
        'comment_empty': 'Comment cannot be empty.',
        'comment_deleted': 'Comment deleted.',
        'post_deleted': 'Post deleted.',
        # Profile
        'profile_title': 'User Profile',
        'profile': 'Profile',
        'profile_change_photo': 'Change Photo',
        'profile_county_not_set': 'County not set',
        'profile_member_since': 'Member since',
        'profile_recently': 'Recently',
        'profile_update_county': 'Update County Information',
        'profile_county_help': 'Select your county to help us provide localized plant disease information.',
        'profile_save_changes': 'Save Changes',
        'profile_predictions_made': 'Predictions Made',
        'profile_forum_posts': 'Forum Posts',
        'profile_quick_actions': 'Quick Actions',
        'profile_community_forum': 'Community Forum',
        # Create post
        'create_post_title': 'Create New Forum Post',
        'create_post_submit': 'Post Discussion',
        'create_post_cancel': 'Cancel',
        # Payment
        'dashboard': 'Dashboard',
        'predict': 'Predict Disease',
        'forum_nav': 'Community Forum',
        'payment': 'Payment',
        'profile_nav': 'Profile',
        'logout': 'Logout',
        'login': 'Login',
        'register': 'Register',
        'back': 'Back',
        'comments': 'Comments',
        'monthly': 'Monthly',
        'weekly': 'Weekly',
        'amount': 'Amount',
        'phone_number': 'Phone Number',
        # Payment status
        'payment_status_title': 'Subscription Status',
        'payment_status_new_sub': 'New Subscription',
        'payment_status_current': 'Current Subscription',
        'payment_status_active': 'Active Subscription',
        'payment_status_plan': 'Plan:',
        'payment_status_amount': 'Amount:',
        'payment_status_status': 'Status:',
        'payment_status_expiry': 'Expiry Date:',
        'payment_status_days': 'Days Remaining:',
        'payment_status_phone': 'Phone:',
        'payment_status_days_unit': 'days',
        'payment_status_no_active': 'No Active Subscription',
        'payment_status_no_active_desc': "You don't have an active subscription. Subscribe to access all features.",
        'payment_status_subscribe_now': 'Subscribe Now',
        'payment_status_history': 'Payment History',
        'payment_status_col_date': 'Date',
        'payment_status_col_plan': 'Plan',
        'payment_status_col_amount': 'Amount',
        'payment_status_col_status': 'Status',
        'payment_status_col_expiry': 'Expiry',
        'payment_status_col_phone': 'Phone',
        'payment_status_paid': 'Paid',
        'payment_status_pending': 'Pending',
        'payment_status_no_history': 'No Payment History',
        'payment_status_no_history_desc': "You haven't made any payments yet.",
        'payment_status_benefits': 'Subscription Benefits',
        'payment_status_benefit1': 'Unlimited plant disease detection',
        'payment_status_benefit2': 'Detailed treatment recommendations',
        'payment_status_benefit3': 'Natural remedy suggestions',
        'payment_status_benefit4': 'Prevention schedules',
        'payment_status_benefit5': 'Community forum access',
        'payment_status_benefit6': 'County-specific alerts',
        'payment_status_back': 'Back to Dashboard',
        'payment_status_get_sub': 'Get Subscription',
        # Payment success
        'payment_success_title': 'Payment Successful!',
        'payment_success_redirect': 'You will be redirected shortly\u2026',
        'payment_success_click': 'Click here',
        # Payment processing
        'payment_processing_title': 'Payment Processing',
        'payment_processing_subtitle': 'Your payment is being processed. Please wait while we confirm your transaction.',
        'payment_processing_initiated': 'Payment Initiated',
        'payment_processing_initiated_sub': 'Transaction request sent to M-Pesa',
        'payment_processing_received': 'Payment Received',
        'payment_processing_received_sub': 'Funds successfully processed',
        'payment_processing_email': 'Confirmation Email',
        'payment_processing_activating': 'Activating Subscription',
        'payment_processing_activating_sub': 'Granting access to premium features',
        'payment_processing_details': 'Payment Details',
        'payment_processing_plan': 'Plan:',
        'payment_processing_amount': 'Amount:',
        'payment_processing_phone': 'Phone:',
        'payment_processing_ref': 'Reference:',
        'payment_processing_redirecting': 'Redirecting to dashboard in',
        'payment_processing_seconds': 'seconds\u2026',
        'payment_processing_continue': 'Continue to Dashboard Now',
        'payment_email_sent_title': 'Confirmation Email Sent!',
        'payment_email_sent_sub': "We've sent a confirmation email to",
        'payment_email_sent_details': 'with your subscription details.',
        'payment_email_failed_title': 'Email Delivery Issue',
        'payment_email_failed_sub': "Payment processed successfully, but we couldn't send the confirmation email to",
        'payment_email_failed_details': 'Your subscription is still active.',
    },
    'sw': {
        # Legacy keys (kept for backward compatibility)
        'welcome': 'Karibu PlantDoc',
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
        'upload_image': 'Pakia Picha',
        'analyze': 'Chambua',
        'share_experience': 'Shiriki Uzoefu Wako',
        'add_comment': 'Ongeza Maoni',
        'subscription_active': 'Usajili wako ni hai',
        'subscription_expired': 'Usajili wako umeisha',
        'pay_now': 'Lipa Sasa',
        'payment_successful': 'Malipo Yamekamilika',
        'payment_failed': 'Malipo Yameshindikana',
        'kenyan_shillings': 'KSh',
        # Navigation
        'nav_home': 'Nyumbani',
        'nav_community': 'Jamii',
        'nav_dashboard': 'Dashibodi',
        'nav_new_scan': 'Skani Mpya',
        'nav_account': 'Akaunti',
        'nav_profile': 'Wasifu',
        'nav_subscription': 'Usajili',
        'nav_logout': 'Toka',
        'nav_login': 'Ingia',
        'nav_register': 'Jisajili',
        'nav_language': 'Lugha',
        # Footer
        'footer_tagline': 'Kusaidia wakulima kutambua magonjwa ya mimea mapema kwa mavuno bora.',
        'footer_quick_links': 'Viungo vya Haraka',
        'footer_contact': 'Mawasiliano',
        'footer_copyright': '\u00a9 2025 PlantDoc. Haki zote zimehifadhiwa.',
        # Index page
        'index_hero_title': 'Utambuzi wa Magonjwa ya Mimea',
        'index_hero_subtitle': 'Tambua magonjwa ya mimea haraka na upate mapendekezo ya matibabu',
        'index_start_prediction': 'Anza Utabiri Mpya',
        'index_get_started': 'Anza Sasa',
        'index_how_works_title': 'Jinsi Mfumo Wetu Unavyofanya Kazi',
        'index_upload_title': 'Pakia Picha',
        'index_upload_desc': 'Piga picha wazi za majani yaliyoathirika ukitumia simu au kamera',
        'index_upload_tip1': 'Zingatia maeneo yaliyoathirika',
        'index_upload_tip2': 'Tumia mwanga wa asili',
        'index_upload_tip3': 'Jumuisha jani zima iwezekanavyo',
        'index_ai_title': 'Uchambuzi wa AI',
        'index_ai_desc': 'Mfano wetu wa kujifunza kwa kina unachakata picha yako kwa sekunde',
        'index_model_accuracy': 'Usahihi wa mfano:',
        'index_across_crops': '96% kwa mazao ya kawaida',
        'index_treatment_title': 'Pata Matibabu',
        'index_treatment_desc': 'Mapendekezo ya haraka yanayotekelezeka',
        'index_organic': 'Asili',
        'index_chemical': 'Kemikali',
        'index_prevention': 'Kinga',
        'index_crops_title': 'Tunatambua Magonjwa katika Mazao 14+',
        'index_crops_subtitle': 'Mfumo wetu unatambua magonjwa ya kawaida yanayoathiri:',
        'index_see_full_list': 'Tazama Orodha Kamili',
        'index_stories_title': 'Hadithi za Mafanikio ya Wakulima',
        'index_saved_crop': 'Niliokoa Mazao Yangu Yote',
        'index_saved_quote': '"Niligundu ugonjwa wa kutu mapema na kufuata mpango wa matibabu ya asili. Mavuno yaliongezeka kwa 40%!"',
        'index_nakuru': 'Kaunti ya Nakuru',
        # Login page
        'login_title': 'Ingia',
        'login_remember': 'Nikumbuke',
        'login_no_account': 'Huna akaunti?',
        'login_register_link': 'Jisajili',
        # Register page
        'register_title': 'Jisajili',
        'register_send_code': 'Tuma Msimbo',
        'register_sending': 'Inatuma\u2026',
        'register_have_account': 'Una akaunti tayari?',
        'register_login_here': 'Ingia hapa',
        'register_email_empty': 'Tafadhali ingiza barua pepe kwanza',
        'register_code_sent': 'Msimbo wa uthibitisho umetumwa kwa barua pepe yako!',
        'register_send_failed': 'Imeshindwa kutuma msimbo wa uthibitisho',
        'register_error': 'Hitilafu imetokea',
        # Dashboard
        'dashboard_welcome': 'Karibu,',
        'dashboard_new_prediction': 'Utabiri Mpya',
        'dashboard_recent': 'Utabiri Wako wa Hivi Karibuni',
        'dashboard_treatment_label': 'Matibabu:',
        'dashboard_no_predictions': 'Bado hujafanya utabiri wowote.',
        'dashboard_start_first': 'Anza utabiri wako wa kwanza',
        # Predict / Upload
        'predict_upload_title': 'Pakia Picha',
        'predict_select_image': 'Chagua Picha',
        'predict_upload_hint': 'Pakia picha wazi ya sehemu iliyoathirika ya mmea (kiwango cha juu 16MB)',
        'predict_btn': 'Tabiri Ugonjwa',
        # Select plant
        'select_plant_title': 'Chagua Aina ya Mmea',
        'select_plant': 'Chagua Aina ya Mmea',
        'select_plant_desc': 'Tafadhali chagua mmea unaotaka kuchunguza magonjwa:',
        'select_plant_back': 'Rudi Dashibodini',
        'select_plant_error': 'Tafadhali chagua aina ya mmea',
        'low_confidence': 'Ubora wa picha ni mdogo sana kufanya utabiri wa kuaminika. Tafadhali pakia picha iliyo wazi na ya karibu ya jani au tunda lililoathirika katika mwanga mzuri.',
        'payment_required': 'Usajili unahitajika kufikia utambuzi wa magonjwa.',
        # Forum
        'forum_title': 'Jukwaa la Jamii',
        'forum': 'Jukwaa la Jamii',
        'forum_new_post': 'Chapisho Jipya',
        'forum_filter_county': 'Chuja kwa Kaunti:',
        'forum_all_counties': 'Kaunti Zote',
        'forum_apply': 'Tumia',
        'forum_clear_filter': 'Futa Chujio',
        'forum_posted_by': 'Imechapishwa na',
        'forum_from': 'kutoka',
        'forum_county': 'Kaunti',
        'forum_comments': 'Maoni',
        'forum_write_comment': 'Andika maoni yako\u2026',
        'forum_add_photo': 'Ongeza Picha',
        'forum_max_5mb': 'Kiwango cha juu 5MB',
        'forum_post_btn': 'Chapisha',
        'forum_no_posts': 'Hakuna machapisho bado. Anzisha mjadala!',
        'forum_close': 'Funga',
        'forum_delete_comment': 'Futa',
        'forum_delete_post': 'Futa Chapisho',
        'forum_confirm_delete_comment': 'Futa maoni haya?',
        'forum_confirm_delete_post': 'Futa chapisho hili na maoni yake yote?',
        'comment_added': 'Maoni yameongezwa.',
        'comment_empty': 'Maoni hayawezi kuwa tupu.',
        'comment_deleted': 'Maoni yamefutwa.',
        'post_deleted': 'Chapisho limefutwa.',
        # Profile
        'profile_title': 'Wasifu wa Mtumiaji',
        'profile': 'Wasifu',
        'profile_change_photo': 'Badilisha Picha',
        'profile_county_not_set': 'Kaunti haijawekwa',
        'profile_member_since': 'Mwanachama tangu',
        'profile_recently': 'Hivi karibuni',
        'profile_update_county': 'Sasisha Taarifa za Kaunti',
        'profile_county_help': 'Chagua kaunti yako kutusaidia kutoa taarifa za magonjwa ya mimea za eneo lako.',
        'profile_save_changes': 'Hifadhi Mabadiliko',
        'profile_predictions_made': 'Utabiri Uliofanywa',
        'profile_forum_posts': 'Machapisho ya Jukwaa',
        'profile_quick_actions': 'Vitendo vya Haraka',
        'profile_community_forum': 'Jukwaa la Jamii',
        # Create post
        'create_post_title': 'Unda Chapisho Jipya la Jukwaa',
        'create_post_submit': 'Chapisha Majadiliano',
        'create_post_cancel': 'Ghairi',
        # Payment
        'dashboard': 'Dashibodi',
        'predict': 'Tabiri Ugonjwa',
        'forum_nav': 'Jukwaa la Jamii',
        'payment': 'Malipo',
        'profile_nav': 'Wasifu',
        'logout': 'Toka',
        'login': 'Ingia',
        'register': 'Jisajili',
        'back': 'Rudi',
        'comments': 'Maoni',
        'monthly': 'Kila Mwezi',
        'weekly': 'Kila Wiki',
        'amount': 'Kiasi',
        'phone_number': 'Namba ya Simu',
        # Payment status
        'payment_status_title': 'Hali ya Usajili',
        'payment_status_new_sub': 'Usajili Mpya',
        'payment_status_current': 'Usajili wa Sasa',
        'payment_status_active': 'Usajili Hai',
        'payment_status_plan': 'Mpango:',
        'payment_status_amount': 'Kiasi:',
        'payment_status_status': 'Hali:',
        'payment_status_expiry': 'Tarehe ya Kumalizika:',
        'payment_status_days': 'Siku Zilizobaki:',
        'payment_status_phone': 'Simu:',
        'payment_status_days_unit': 'siku',
        'payment_status_no_active': 'Hakuna Usajili Hai',
        'payment_status_no_active_desc': 'Huna usajili hai. Jisajili kupata ufikiaji wa vipengele vyote.',
        'payment_status_subscribe_now': 'Jisajili Sasa',
        'payment_status_history': 'Historia ya Malipo',
        'payment_status_col_date': 'Tarehe',
        'payment_status_col_plan': 'Mpango',
        'payment_status_col_amount': 'Kiasi',
        'payment_status_col_status': 'Hali',
        'payment_status_col_expiry': 'Kumalizika',
        'payment_status_col_phone': 'Simu',
        'payment_status_paid': 'Imelipwa',
        'payment_status_pending': 'Inasubiri',
        'payment_status_no_history': 'Hakuna Historia ya Malipo',
        'payment_status_no_history_desc': 'Bado hujafanya malipo yoyote.',
        'payment_status_benefits': 'Faida za Usajili',
        'payment_status_benefit1': 'Utambuzi usio na kikomo wa magonjwa ya mimea',
        'payment_status_benefit2': 'Mapendekezo ya kina ya matibabu',
        'payment_status_benefit3': 'Mapendekezo ya dawa za asili',
        'payment_status_benefit4': 'Ratiba za kinga',
        'payment_status_benefit5': 'Ufikiaji wa jukwaa la jamii',
        'payment_status_benefit6': 'Arifa za kaunti',
        'payment_status_back': 'Rudi Dashibodini',
        'payment_status_get_sub': 'Pata Usajili',
        # Payment success
        'payment_success_title': 'Malipo Yamekamilika!',
        'payment_success_redirect': 'Utaelekezwa hivi karibuni\u2026',
        'payment_success_click': 'Bonyeza hapa',
        # Payment processing
        'payment_processing_title': 'Malipo Yanachakatwa',
        'payment_processing_subtitle': 'Malipo yako yanachakatwa. Tafadhali subiri uthibitisho wa muamala wako.',
        'payment_processing_initiated': 'Malipo Yameanzishwa',
        'payment_processing_initiated_sub': 'Ombi la muamala limetumwa kwa M-Pesa',
        'payment_processing_received': 'Malipo Yamepokelewa',
        'payment_processing_received_sub': 'Fedha zimechakatwa kwa mafanikio',
        'payment_processing_email': 'Barua Pepe ya Uthibitisho',
        'payment_processing_activating': 'Kuwasha Usajili',
        'payment_processing_activating_sub': 'Kutoa ufikiaji wa vipengele vya malipo',
        'payment_processing_details': 'Maelezo ya Malipo',
        'payment_processing_plan': 'Mpango:',
        'payment_processing_amount': 'Kiasi:',
        'payment_processing_phone': 'Simu:',
        'payment_processing_ref': 'Kumbukumbu:',
        'payment_processing_redirecting': 'Kuelekezwa kwa dashibodi ndani ya',
        'payment_processing_seconds': 'sekunde\u2026',
        'payment_processing_continue': 'Endelea kwa Dashibodi Sasa',
        'payment_email_sent_title': 'Barua Pepe ya Uthibitisho Imetumwa!',
        'payment_email_sent_sub': 'Tumetuma barua pepe ya uthibitisho kwa',
        'payment_email_sent_details': 'na maelezo ya usajili wako.',
        'payment_email_failed_title': 'Tatizo la Uwasilishaji wa Barua Pepe',
        'payment_email_failed_sub': 'Malipo yamechakatwa lakini hatukuweza kutuma barua pepe ya uthibitisho kwa',
        'payment_email_failed_details': 'Usajili wako bado uko hai.',
    }
}

def t(key, lang=None):
    """Translation helper function — returns EN fallback when key is missing."""
    if lang is None:
        lang = get_user_language()
    lang_dict = translations.get(lang, translations['en'])
    return lang_dict.get(key, translations['en'].get(key, key))

# ============== CONTEXT PROCESSOR — injects lang + t() into every template ==
@app.context_processor
def inject_i18n():
    lang = get_user_language()
    bound_t = lambda key: t(key, lang)
    return dict(lang=lang, t=bound_t)

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

# ── Disease information (English) ───────────────────────────────────────────
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
            'Captan 50WP – apply every 10-14 days from bud break',
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
        'treatment': 'No treatment required. Your plant is healthy!',
        'agrovet_medications': [],
        'phytomedicine': 'Preventive neem oil sprays every 2 weeks',
        'prevention': 'Maintain proper nutrition and irrigation, regular pruning'
    },
    'Blueberry___healthy': {
        'scientific_name': 'Healthy blueberry plant',
        'treatment': 'No treatment required. Your plant is healthy!',
        'agrovet_medications': [],
        'phytomedicine': 'Aloe vera leaf extract as foliar spray',
        'prevention': 'Maintain acidic soil pH (4.0-5.0), proper mulching'
    },
    'Cherry_(including_sour)___Powdery_mildew': {
        'scientific_name': 'Podosphaera clandestina',
        'treatment': 'Apply sulfur or potassium bicarbonate fungicides',
        'agrovet_medications': [
            'Kumulus DF (sulfur 80%) – apply every 7-10 days in dry weather',
            'Topas 100EC (penconazole) – systemic triazole at first symptoms',
            'Karathane (dinocap) – specific powdery mildew fungicide'
        ],
        'phytomedicine': 'Milk spray (1 part milk to 9 parts water) weekly',
        'prevention': 'Improve air circulation, avoid overhead irrigation'
    },
    'Cherry_(including_sour)___healthy': {
        'scientific_name': 'Healthy cherry plant',
        'treatment': 'No treatment required. Your plant is healthy!',
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
            'Dithane M-45 80WP (mancozeb) – apply every 7-10 days during wet periods',
            'Bravo 720SC (chlorothalonil) – protectant spray at tasseling',
            'Headline EC (pyraclostrobin) – systemic strobilurin at early onset'
        ],
        'phytomedicine': 'Tithonia diversifolia (Mexican sunflower) leaf extract',
        'prevention': 'Crop rotation, tillage to bury crop residue'
    },
    'Corn_(maize)___healthy': {
        'scientific_name': 'Healthy maize plant',
        'treatment': 'No treatment required. Your plant is healthy!',
        'agrovet_medications': [],
        'phytomedicine': 'Fermented plant extracts for soil health',
        'prevention': 'Proper spacing, timely weeding, crop rotation'
    },
    'Grape___Black_rot': {
        'scientific_name': 'Guignardia bidwellii',
        'treatment': 'Apply fungicides early in season, remove infected material',
        'agrovet_medications': [
            'Mancozeb 80WP (Dithane M-45) – protectant spray every 7-10 days',
            'Topsin M 70WP (thiophanate-methyl) – systemic curative fungicide',
            'Captan 50WP – apply from bud break through berry set'
        ],
        'phytomedicine': 'Fermented pawpaw leaf extract',
        'prevention': 'Proper pruning, canopy management, remove mummified fruits'
    },
    'Grape___Esca_(Black_Measles)': {
        'scientific_name': 'Phaeomoniella spp.',
        'treatment': 'Prune infected wood. No effective chemical control; focus on prevention.',
        'agrovet_medications': [
            'Trichoderma-based bioagent (Trichomax) – soil/wound treatment to suppress trunk pathogens',
            'Benlate 50WP (benomyl) – wound-sealing paste after pruning',
            'Garlic extract wound sealant – traditional protective measure'
        ],
        'phytomedicine': 'Garlic and ginger rhizome extract',
        'prevention': 'Avoid pruning wounds, use clean pruning tools'
    },
    'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)': {
        'scientific_name': 'Pseudocercospora vitis',
        'treatment': 'Copper-based fungicides during wet periods',
        'agrovet_medications': [
            'Cuprocaffaro 37.5WP (copper oxychloride) – spray every 10-14 days',
            'Dithane M-45 80WP (mancozeb) – protective cover spray',
            'Score 250EC (difenoconazole) – systemic curative at early infection'
        ],
        'phytomedicine': 'Ocimum gratissimum (African basil) leaf extract',
        'prevention': 'Improve air circulation, avoid overhead irrigation'
    },
    'Grape___healthy': {
        'scientific_name': 'Healthy grape vine',
        'treatment': 'No treatment required. Your plant is healthy!',
        'agrovet_medications': [],
        'phytomedicine': 'Seaweed extract as foliar spray',
        'prevention': 'Proper trellising, balanced nutrition'
    },
    'Orange___Haunglongbing_(Citrus_greening)': {
        'scientific_name': 'Candidatus Liberibacter asiaticus',
        'treatment': 'Remove infected trees, control psyllid vectors with insecticides',
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
        'treatment': 'No treatment required. Your plant is healthy!',
        'agrovet_medications': [],
        'phytomedicine': 'Comfrey leaf tea as foliar feed',
        'prevention': 'Proper pruning, balanced fertilization'
    },
    'Pepper,_bell___Bacterial_spot': {
        'scientific_name': 'Xanthomonas campestris pv. vesicatoria',
        'treatment': 'Copper-based bactericides, avoid working with wet plants',
        'agrovet_medications': [
            'Kocide 2000 (copper hydroxide) – apply every 7-10 days in wet conditions',
            'Cuprocaffaro 37.5WP (copper oxychloride) – protective bactericide spray',
            'Agrimycin 17 (streptomycin) – for severe outbreaks in combination with copper'
        ],
        'phytomedicine': 'Fermented African marigold (Tagetes minuta) extract',
        'prevention': 'Use disease-free seeds, crop rotation'
    },
    'Pepper,_bell___healthy': {
        'scientific_name': 'Healthy bell pepper plant',
        'treatment': 'No treatment required. Your plant is healthy!',
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
        'treatment': 'Apply metalaxyl or chlorothalonil fungicides immediately',
        'agrovet_medications': [
            'Ridomil Gold MZ 68WG (metalaxyl-M + mancozeb) – curative + protectant control',
            'Dithane M-45 80WP (mancozeb) – protectant sprays every 5-7 days in wet weather',
            'Acrobat MZ 69WP (dimethomorph + mancozeb) – for resistance rotation'
        ],
        'phytomedicine': 'Horsetail tea spray every 5 days',
        'prevention': 'Plant resistant varieties, avoid overhead irrigation'
    },
    'Potato___healthy': {
        'scientific_name': 'Healthy potato plant',
        'treatment': 'No treatment required. Your plant is healthy!',
        'agrovet_medications': [],
        'phytomedicine': 'Compost tea as soil drench',
        'prevention': 'Proper hilling, crop rotation'
    },
    'Raspberry___healthy': {
        'scientific_name': 'Healthy raspberry plant',
        'treatment': 'No treatment required. Your plant is healthy!',
        'agrovet_medications': [],
        'phytomedicine': 'Fermented banana peel extract',
        'prevention': 'Proper trellising, regular pruning'
    },
    'Soybean___healthy': {
        'scientific_name': 'Healthy soybean plant',
        'treatment': 'No treatment required. Your plant is healthy!',
        'agrovet_medications': [],
        'phytomedicine': 'Rhizobium inoculants for nitrogen fixation',
        'prevention': 'Proper spacing, crop rotation'
    },
    'Squash___Powdery_mildew': {
        'scientific_name': 'Podosphaera xanthii',
        'treatment': 'Apply sulfur or potassium bicarbonate',
        'agrovet_medications': [
            'Kumulus DF (sulfur 80%) – apply every 7-10 days when disease pressure is high',
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
            'Captan 50WP – apply every 10-14 days during wet weather',
            'Topsin M 70WP (thiophanate-methyl) – systemic fungicide at first symptoms',
            'Mancozeb 80WP (Dithane M-45) – broad-spectrum protective spray'
        ],
        'phytomedicine': 'Fermented comfrey leaf extract',
        'prevention': 'Remove infected leaves, improve air circulation'
    },
    'Strawberry___healthy': {
        'scientific_name': 'Healthy strawberry plant',
        'treatment': 'No treatment required. Your plant is healthy!',
        'agrovet_medications': [],
        'phytomedicine': 'Seaweed extract as foliar spray',
        'prevention': 'Proper mulching, drip irrigation'
    },
    'Tomato___Bacterial_spot': {
        'scientific_name': 'Xanthomonas spp.',
        'treatment': 'Copper-based bactericides, avoid working with wet plants',
        'agrovet_medications': [
            'Kocide 2000 (copper hydroxide) – apply every 5-7 days during wet periods',
            'Cuprocaffaro 37.5WP (copper oxychloride) – protectant bactericide spray',
            'Agrimycin 17 (streptomycin + oxytetracycline) – for severe bacterial outbreaks'
        ],
        'phytomedicine': 'Garlic and chili pepper extract spray',
        'prevention': 'Use disease-free seeds, crop rotation'
    },
    'Tomato___Early_blight': {
        'scientific_name': 'Alternaria solani',
        'treatment': 'Apply chlorothalonil, remove lower infected leaves',
        'agrovet_medications': [
            'Bravo 720SC (chlorothalonil) – apply every 7-10 days from first symptoms',
            'Dithane M-45 80WP (mancozeb) – protectant spray every 7 days',
            'Amistar 250SC (azoxystrobin) – systemic fungicide for curative action'
        ],
        'phytomedicine': 'Fermented stinging nettle extract',
        'prevention': 'Crop rotation, proper plant spacing'
    },
    'Tomato___Late_blight': {
        'scientific_name': 'Phytophthora infestans',
        'treatment': 'Apply chlorothalonil immediately, destroy heavily infected plants',
        'agrovet_medications': [
            'Ridomil Gold MZ 68WG (metalaxyl-M + mancozeb) – early outbreak control',
            'Dithane M-45 / Mancozeb 80WP – preventive sprays every 5-7 days in rainy periods',
            'Acrobat MZ 69WP (dimethomorph + mancozeb) – follow-up sprays and rotation',
            'Bravo 720SC (chlorothalonil) – protectant disease suppression'
        ],
        'phytomedicine': 'Horsetail tea spray every 5 days',
        'prevention': 'Resistant varieties, avoid overhead watering'
    },
    'Tomato___Leaf_Mold': {
        'scientific_name': 'Passalora fulva',
        'treatment': 'Improve air circulation, apply chlorothalonil',
        'agrovet_medications': [
            'Bravo 720SC (chlorothalonil) – apply every 7-10 days in humid conditions',
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
            'Kocide 2000 (copper hydroxide) – protective spray every 7-10 days',
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
            'Bravo 720SC (chlorothalonil) – apply every 7-10 days from first symptoms',
            'Amistar 250SC (azoxystrobin) – systemic strobilurin for curative action',
            'Mancozeb 80WP (Dithane M-45) – protectant spray every 7 days'
        ],
        'phytomedicine': 'Fermented pawpaw leaf extract',
        'prevention': 'Crop rotation, resistant varieties'
    },
    'Tomato___Tomato_Yellow_Leaf_Curl_Virus': {
        'scientific_name': 'Begomovirus',
        'treatment': 'Control whitefly vectors with insecticides, remove infected plants',
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
        'treatment': 'No chemical cure. Remove and destroy infected plants immediately.',
        'agrovet_medications': [
            'No curative chemical available – focus on prevention',
            'Virkon S (disinfectant) – sterilize tools and equipment',
            'Karate Zeon 50CS – control aphid/insect vectors to limit spread'
        ],
        'phytomedicine': 'None – focus entirely on prevention',
        'prevention': 'Use certified disease-free seeds, disinfect tools'
    },
    'Tomato___healthy': {
        'scientific_name': 'Healthy tomato plant',
        'treatment': 'No treatment required. Your plant is healthy!',
        'agrovet_medications': [],
        'phytomedicine': 'Compost tea as foliar spray',
        'prevention': 'Proper staking, balanced fertilization'
    },
}

# ── Swahili translations for disease content ─────────────────────────────────
disease_info_sw = {
    'Apple___Apple_scab': {
        'treatment': 'Piga dawa ya shaba au salfa. Kata matawi yaliyoathirika na angamiza majani yaliyoanguka.',
        'agrovet_medications': [
            'Cuprocaffaro 37.5WP (copper oxychloride) – dawa ya kinga, nyunyiza kila siku 7',
            'Dithane M-45 80WP (mancozeb) – tumia wakati wa maua kuanguka',
            'Score 250EC (difenoconazole) – dawa ya kutibu, nyunyiza mara unapoona vidonda vya kwanza'
        ],
        'phytomedicine': 'Dawa ya mafuta ya neem (Azadirachta indica) kila siku 10',
        'prevention': 'Panda aina zinazostahimili ugonjwa, weka nafasi kati ya miti, ondoa takataka za mmea'
    },
    'Apple___Black_rot': {
        'treatment': 'Ondoa matunda yaliyokauka na matawi yaliyoathirika. Piga dawa ya captan.',
        'agrovet_medications': [
            'Captan 50WP – tumia kila siku 10-14 kuanzia kuvunjika kwa bua',
            'Mancozeb 80WP (Dithane M-45) – dawa ya kinga wakati wa mvua',
            'Thiophanate-methyl 70WP – dawa ya uyoga ya kimfumo kwa matibabu'
        ],
        'phytomedicine': 'Dawa ya vitunguu (Allium sativum) na pilipili iliyosagwa',
        'prevention': 'Epuka kuumiza mti, safisha bustani vizuri mara kwa mara'
    },
    'Apple___Cedar_apple_rust': {
        'treatment': 'Piga dawa mapema majira ya masika. Kata mimea ya juniper iliyo karibu.',
        'agrovet_medications': [
            'Syllit 400SC (dodine) – tumia wakati wa hatua ya waridi, rudia kila siku 10',
            'Score 250EC (difenoconazole) – triazole ya kimfumo wakati wa dalili za kwanza',
            'Sulfur 80WP – dawa ya kinga kutoka ncha ya kijani hadi kuanguka kwa petali'
        ],
        'phytomedicine': 'Mchanganyiko wa soda ya kuoka (kijiko 1 kwa lita) na mafuta ya kilimo',
        'prevention': 'Panda aina zinazostahimili, ondoa mimea mbadala ndani ya kilomita 2'
    },
    'Apple___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Piga dawa ya kinga ya mafuta ya neem kila wiki 2',
        'prevention': 'Dumisha lishe na umwagiliaji sahihi, kata matawi mara kwa mara'
    },
    'Blueberry___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Dawa ya jani la aloe vera kama mbolea ya majani',
        'prevention': 'Dumisha tindikali ya udongo (pH 4.0-5.0), mulch sahihi'
    },
    'Cherry_(including_sour)___Powdery_mildew': {
        'treatment': 'Piga dawa ya salfa au potasiamu bicarbonate',
        'agrovet_medications': [
            'Kumulus DF (sulfur 80%) – tumia kila siku 7-10 wakati wa ukame',
            'Topas 100EC (penconazole) – triazole ya kimfumo wakati wa dalili za kwanza',
            'Karathane (dinocap) – dawa maalum ya uyoga wa unga'
        ],
        'phytomedicine': 'Dawa ya maziwa (sehemu 1 maziwa kwa sehemu 9 maji) kila wiki',
        'prevention': 'Boresha mzunguko wa hewa, epuka umwagiliaji wa juu'
    },
    'Cherry_(including_sour)___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Chai ya mboji kama mbolea ya udongo kila mwezi',
        'prevention': 'Kata matawi mara kwa mara, mbolea ya kusawazisha'
    },
    'Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot': {
        'treatment': 'Piga dawa yenye azoxystrobin au propiconazole',
        'agrovet_medications': [
            'Amistar 250SC (azoxystrobin) – tumia wakati wa kutawanya, rudia baada ya siku 14',
            'Tilt 250EC (propiconazole) – tumia mara unapoona vidonda vya kwanza',
            'Folicur 250EW (tebuconazole) – triazole ya kimfumo mwanzoni mwa ugonjwa'
        ],
        'phytomedicine': 'Dawa ya mmea wa nettle uliochanganywa kwa uchachushaji (Urtica dioica)',
        'prevention': 'Pinda mazao, aina zinazostahimili, nafasi sahihi kati ya mimea'
    },
    'Corn_(maize)___Common_rust_': {
        'treatment': 'Piga dawa ya triazole wakati ugonjwa unaanza',
        'agrovet_medications': [
            'Tilt 250EC (propiconazole) – tumia mara vidonda vya kwanza vinapoonekana',
            'Folicur 250EW (tebuconazole) – udhibiti wa kimfumo wa kutu',
            'Amistar Top (azoxystrobin + difenoconazole) – udhibiti wa wigo mpana'
        ],
        'phytomedicine': 'Dawa ya majani ya Lantana camara iliyonyunyiziwa',
        'prevention': 'Panda mapema, aina zinazostahimili, mbolea ya kusawazisha'
    },
    'Corn_(maize)___Northern_Leaf_Blight': {
        'treatment': 'Piga dawa ya chlorothalonil au mancozeb',
        'agrovet_medications': [
            'Dithane M-45 80WP (mancozeb) – tumia kila siku 7-10 wakati wa mvua',
            'Bravo 720SC (chlorothalonil) – dawa ya kinga wakati wa kutawanya',
            'Headline EC (pyraclostrobin) – strobilurin ya kimfumo mwanzoni mwa ugonjwa'
        ],
        'phytomedicine': 'Dawa ya majani ya Tithonia diversifolia (maua ya Meksiko)',
        'prevention': 'Pinda mazao, lima udongo kuzika mabaki ya mazao'
    },
    'Corn_(maize)___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Dawa za mmea zilizochachushwa kwa afya ya udongo',
        'prevention': 'Nafasi sahihi, palilia kwa wakati, pinda mazao'
    },
    'Grape___Black_rot': {
        'treatment': 'Piga dawa mapema msimu, ondoa nyenzo zilizoathirika',
        'agrovet_medications': [
            'Mancozeb 80WP (Dithane M-45) – dawa ya kinga kila siku 7-10',
            'Topsin M 70WP (thiophanate-methyl) – dawa ya uyoga ya kimfumo kwa matibabu',
            'Captan 50WP – tumia kuanzia kuvunjika kwa bua hadi kuwekwa kwa matunda'
        ],
        'phytomedicine': 'Dawa ya majani ya papai iliyochachushwa',
        'prevention': 'Kata matawi, simamia msitu, ondoa matunda yaliyokauka'
    },
    'Grape___Esca_(Black_Measles)': {
        'treatment': 'Kata miti iliyoathirika, hakuna dawa nzuri ya kemikali',
        'agrovet_medications': [
            'Trichoderma-based bioagent (Trichomax) – matibabu ya udongo/jeraha kuzuia vimelea vya shina',
            'Benlate 50WP (benomyl) – bandia ya kufunika jeraha baada ya kukata',
            'Dawa ya vitunguu kwa kufunika jeraha – njia ya jadi ya kinga'
        ],
        'phytomedicine': 'Dawa ya vitunguu na tangawizi',
        'prevention': 'Epuka kuumiza mti wakati wa kukata, tumia zana safi'
    },
    'Grape___Leaf_blight_(Isariopsis_Leaf_Spot)': {
        'treatment': 'Piga dawa ya shaba wakati wa mvua',
        'agrovet_medications': [
            'Cuprocaffaro 37.5WP (copper oxychloride) – nyunyiza kila siku 10-14',
            'Dithane M-45 80WP (mancozeb) – dawa ya kinga ya jalada',
            'Score 250EC (difenoconazole) – dawa ya kimfumo ya kutibu mwanzoni mwa maambukizi'
        ],
        'phytomedicine': 'Dawa ya majani ya Ocimum gratissimum (mnanaa wa Afrika)',
        'prevention': 'Boresha mzunguko wa hewa, epuka umwagiliaji wa juu'
    },
    'Grape___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Dawa ya mwani baharini kama mbolea ya majani',
        'prevention': 'Weka msalaba sahihi, lishe ya kusawazisha'
    },
    'Orange___Haunglongbing_(Citrus_greening)': {
        'treatment': 'Ondoa miti iliyoathirika, dhibiti wadudu wa psyllid',
        'agrovet_medications': [
            'Actara 25WG (thiamethoxam) – dawa ya kimfumo ya wadudu kwa udhibiti wa psyllid',
            'Karate Zeon 50CS (lambda-cyhalothrin) – dawa ya kuwasiliana ya wadudu kwa psyllid',
            'Imidacloprid 200SL (Confidor) – kumwagilia udongo/majani kwa udhibiti wa vienezaji'
        ],
        'phytomedicine': 'Mafuta ya neem kudhibiti psyllid',
        'prevention': 'Panda miche isiyoathirika, fuatilia wadudu'
    },
    'Peach___Bacterial_spot': {
        'treatment': 'Piga dawa ya shaba wakati wa usingizi wa mmea, streptomycin wakati wa kukua',
        'agrovet_medications': [
            'Cuprocaffaro 37.5WP (copper oxychloride) – nyunyiza wakati wa usingizi na mwanzo wa msimu',
            'Agrimycin 17 (streptomycin sulfate) – dawa ya bakteria wakati wa ukuaji',
            'Kocide 2000 (copper hydroxide) – dawa ya kinga ya shaba wakati maua yanaanguka'
        ],
        'phytomedicine': 'Dawa ya chai ya mkia wa farasi (Equisetum arvense)',
        'prevention': 'Panda aina zinazostahimili, epuka umwagiliaji wa juu'
    },
    'Peach___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Chai ya majani ya comfrey kama mbolea ya majani',
        'prevention': 'Kata matawi sahihi, mbolea ya kusawazisha'
    },
    'Pepper,_bell___Bacterial_spot': {
        'treatment': 'Piga dawa ya bakteria ya shaba, epuka kufanya kazi na mimea yenye unyevu',
        'agrovet_medications': [
            'Kocide 2000 (copper hydroxide) – tumia kila siku 7-10 wakati wa unyevu',
            'Cuprocaffaro 37.5WP (copper oxychloride) – dawa ya kinga ya bakteria',
            'Agrimycin 17 (streptomycin) – kwa mlipuko mkali pamoja na dawa ya shaba'
        ],
        'phytomedicine': 'Dawa ya maua ya African marigold (Tagetes minuta) iliyochachushwa',
        'prevention': 'Tumia mbegu zisizokuwa na ugonjwa, pinda mazao'
    },
    'Pepper,_bell___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Gel ya aloe vera iliyochanganywa na maji kama mbolea ya majani',
        'prevention': 'Nafasi sahihi, mulch, umwagiliaji wa matone'
    },
    'Potato___Early_blight': {
        'treatment': 'Piga dawa ya chlorothalonil au mancozeb',
        'agrovet_medications': [
            'Dithane M-45 80WP (mancozeb) – tumia kila siku 7 kuanzia kufunika kwa msongamano wa majani',
            'Bravo 720SC (chlorothalonil) – dawa ya uyoga ya kinga ya wigo mpana',
            'Amistar 250SC (azoxystrobin) – strobilurin ya kimfumo kwa matibabu'
        ],
        'phytomedicine': 'Dawa ya mmea wa nettle uliyochachushwa',
        'prevention': 'Pinda mazao, mbolea sahihi, ondoa mabaki ya mazao'
    },
    'Potato___Late_blight': {
        'treatment': 'Piga dawa ya metalaxyl au chlorothalonil, angamiza mimea iliyoathirika sana',
        'agrovet_medications': [
            'Ridomil Gold MZ 68WG (metalaxyl-M + mancozeb) – udhibiti wa kutibu na kinga',
            'Dithane M-45 80WP (mancozeb) – dawa ya kinga kila siku 5-7 wakati wa mvua',
            'Acrobat MZ 69WP (dimethomorph + mancozeb) – kwa mzunguko wa upinzani'
        ],
        'phytomedicine': 'Dawa ya chai ya mkia wa farasi kila siku 5',
        'prevention': 'Panda aina zinazostahimili, epuka umwagiliaji wa juu'
    },
    'Potato___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Chai ya mboji kama mbolea ya udongo',
        'prevention': 'Tunza vizuri, pinda mazao'
    },
    'Raspberry___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Dawa ya ngozi ya ndizi iliyochachushwa',
        'prevention': 'Weka msalaba sahihi, kata matawi mara kwa mara'
    },
    'Soybean___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Vimelea vya Rhizobium kwa kurekebisha nitrojeni',
        'prevention': 'Nafasi sahihi, pinda mazao'
    },
    'Squash___Powdery_mildew': {
        'treatment': 'Piga dawa ya salfa au potasiamu bicarbonate',
        'agrovet_medications': [
            'Kumulus DF (sulfur 80%) – tumia kila siku 7-10 msongo wa ugonjwa ukiwa mkubwa',
            'Topas 100EC (penconazole) – triazole ya kimfumo mara unapoona unga mweupe',
            'Thiovit Jet 80WG (sulfur) – udhibiti wa kinga na matibabu ya uyoga wa unga'
        ],
        'phytomedicine': 'Dawa ya maziwa (uwiano 1:9 na maji) kila wiki',
        'prevention': 'Aina zinazostahimili, nafasi sahihi'
    },
    'Strawberry___Leaf_scorch': {
        'treatment': 'Piga dawa ya captan au thiophanate-methyl',
        'agrovet_medications': [
            'Captan 50WP – tumia kila siku 10-14 wakati wa mvua',
            'Topsin M 70WP (thiophanate-methyl) – dawa ya uyoga ya kimfumo wakati wa dalili za kwanza',
            'Mancozeb 80WP (Dithane M-45) – dawa ya kinga ya wigo mpana'
        ],
        'phytomedicine': 'Dawa ya majani ya comfrey iliyochachushwa',
        'prevention': 'Ondoa majani yaliyoathirika, boresha mzunguko wa hewa'
    },
    'Strawberry___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Dawa ya mwani baharini kama mbolea ya majani',
        'prevention': 'Mulch sahihi, umwagiliaji wa matone'
    },
    'Tomato___Bacterial_spot': {
        'treatment': 'Piga dawa ya bakteria ya shaba, epuka kufanya kazi na mimea yenye unyevu',
        'agrovet_medications': [
            'Kocide 2000 (copper hydroxide) – tumia kila siku 5-7 wakati wa mvua',
            'Cuprocaffaro 37.5WP (copper oxychloride) – dawa ya kinga ya bakteria',
            'Agrimycin 17 (streptomycin + oxytetracycline) – kwa mlipuko mkali wa bakteria'
        ],
        'phytomedicine': 'Dawa ya vitunguu na pilipili iliyonyunyiziwa',
        'prevention': 'Tumia mbegu zisizokuwa na ugonjwa, pinda mazao'
    },
    'Tomato___Early_blight': {
        'treatment': 'Piga dawa ya chlorothalonil, ondoa majani ya chini',
        'agrovet_medications': [
            'Bravo 720SC (chlorothalonil) – tumia kila siku 7-10 kuanzia dalili za kwanza',
            'Dithane M-45 80WP (mancozeb) – dawa ya kinga kila siku 7',
            'Amistar 250SC (azoxystrobin) – dawa ya uyoga ya kimfumo kwa matibabu'
        ],
        'phytomedicine': 'Dawa ya mmea wa nettle uliyochachushwa',
        'prevention': 'Pinda mazao, nafasi sahihi kati ya mimea'
    },
    'Tomato___Late_blight': {
        'treatment': 'Piga dawa ya chlorothalonil, angamiza mimea iliyoathirika',
        'agrovet_medications': [
            'Ridomil Gold MZ 68WG (metalaxyl-M + mancozeb) – kwa udhibiti wa mlipuko wa mapema',
            'Dithane M-45 / Mancozeb 80WP – dawa za kinga (kila siku 5-7 wakati wa mvua)',
            'Acrobat MZ 69WP (dimethomorph + mancozeb) – dawa za ufuatiliaji na mzunguko',
            'Bravo 720SC / chlorothalonil – dawa za kukandamiza ugonjwa'
        ],
        'phytomedicine': 'Dawa ya chai ya mkia wa farasi kila siku 5',
        'prevention': 'Aina zinazostahimili, epuka kumwagilia kutoka juu'
    },
    'Tomato___Leaf_Mold': {
        'treatment': 'Boresha mzunguko wa hewa, piga dawa ya chlorothalonil',
        'agrovet_medications': [
            'Bravo 720SC (chlorothalonil) – tumia kila siku 7-10 katika hali ya unyevu',
            'Flint 50WG (trifloxystrobin) – strobilurin ya kimfumo kwa udhibiti wa ukungu wa jani',
            'Dithane M-45 80WP (mancozeb) – dawa ya kinga katika hali ya unyevu mkubwa'
        ],
        'phytomedicine': 'Mchanganyiko wa soda ya kuoka (kijiko 1 kwa lita)',
        'prevention': 'Nafasi sahihi, uingizaji hewa wa greenhouse'
    },
    'Tomato___Septoria_leaf_spot': {
        'treatment': 'Piga dawa ya shaba, ondoa majani yaliyoathirika',
        'agrovet_medications': [
            'Kocide 2000 (copper hydroxide) – dawa ya kinga kila siku 7-10',
            'Bravo 720SC (chlorothalonil) – dawa ya uyoga ya kinga ya wigo mpana',
            'Topsin M 70WP (thiophanate-methyl) – dawa ya uyoga ya kimfumo kwa matibabu'
        ],
        'phytomedicine': 'Dawa ya maua ya African marigold iliyochachushwa',
        'prevention': 'Pinda mazao, epuka umwagiliaji wa juu'
    },
    'Tomato___Spider_mites Two-spotted_spider_mite': {
        'treatment': 'Piga dawa ya kuua utitiri au sabuni ya wadudu',
        'agrovet_medications': [
            'Oberon SC (spiromesifen) – dawa ya utitiri maalum kwa utitiri wa buibui',
            'Abamectin 1.8EC (Agrimek) – dawa ya utitiri/wadudu ya wigo mpana',
            'Envidor 240SC (spirodiclofen) – udhibiti wa mayai na utitiri wazima'
        ],
        'phytomedicine': 'Mafuta ya neem yaliyochanganywa na sabuni ya maji',
        'prevention': 'Dumisha unyevu, palilia magugu'
    },
    'Tomato___Target_Spot': {
        'treatment': 'Piga dawa ya chlorothalonil, ondoa nyenzo zilizoathirika',
        'agrovet_medications': [
            'Bravo 720SC (chlorothalonil) – tumia kila siku 7-10 kuanzia dalili za kwanza',
            'Amistar 250SC (azoxystrobin) – strobilurin ya kimfumo kwa matibabu',
            'Mancozeb 80WP (Dithane M-45) – dawa ya kinga kila siku 7'
        ],
        'phytomedicine': 'Dawa ya majani ya papai iliyochachushwa',
        'prevention': 'Pinda mazao, aina zinazostahimili'
    },
    'Tomato___Tomato_Yellow_Leaf_Curl_Virus': {
        'treatment': 'Dhibiti wadudu wa nzi weupe, ondoa mimea iliyoathirika',
        'agrovet_medications': [
            'Actara 25WG (thiamethoxam) – dawa ya kimfumo ya wadudu kwa udhibiti wa nzi weupe',
            'Confidor 200SL (imidacloprid) – kumwagilia udongo au majani kwa nzi weupe',
            'Karate Zeon 50CS (lambda-cyhalothrin) – dawa ya kuwasiliana ya wadudu kwa vienezaji'
        ],
        'phytomedicine': 'Mafuta ya neem kudhibiti nzi weupe',
        'prevention': 'Aina zinazostahimili, mulch inayoakisi mwanga'
    },
    'Tomato___Tomato_mosaic_virus': {
        'treatment': 'Hakuna dawa ya kuponya, ondoa mimea iliyoathirika mara moja',
        'agrovet_medications': [
            'Hakuna dawa ya kutibu – zingatia kuzuia',
            'Virkon S (disinfectant) – tumia kusafisha zana na vifaa',
            'Karate Zeon 50CS – dhibiti vienezaji (aphid/wadudu) kupunguza kuenea'
        ],
        'phytomedicine': 'Hakuna – zingatia kuzuia peke yake',
        'prevention': 'Tumia mbegu zilizoidhinishwa, safisha zana'
    },
    'Tomato___healthy': {
        'treatment': 'Hakuna matibabu yanayohitajika. Mmea wako una afya!',
        'agrovet_medications': [],
        'phytomedicine': 'Chai ya mboji kama dawa ya majani',
        'prevention': 'Weka msalaba sahihi, mbolea ya kusawazisha'
    },
}


def get_disease_info(disease_key, language='en'):
    """Get disease information in the requested language."""
    en_info = disease_info.get(disease_key, {})
    sw_info = disease_info_sw.get(disease_key, {})

    if language == 'sw':
        return {
            'scientific_name': en_info.get('scientific_name', 'Haijulikani'),
            'treatment': sw_info.get('treatment') or en_info.get('treatment', 'Wasiliana na mtaalamu wa kilimo'),
            'agrovet_medications': sw_info.get('agrovet_medications') or en_info.get('agrovet_medications', []),
            'phytomedicine': sw_info.get('phytomedicine') or en_info.get('phytomedicine', ''),
            'prevention': sw_info.get('prevention') or en_info.get('prevention', ''),
        }
    else:
        return {
            'scientific_name': en_info.get('scientific_name', 'Unknown'),
            'treatment': en_info.get('treatment', 'Consult an agricultural extension officer'),
            'agrovet_medications': en_info.get('agrovet_medications', []),
            'phytomedicine': en_info.get('phytomedicine', ''),
            'prevention': en_info.get('prevention', ''),
        }


def disease_display_name(disease_key, lang):
    """Return the current-language display name for a disease key."""
    if not disease_key:
        return ''
    if 'healthy' in disease_key.lower():
        return 'Mwenye Afya' if lang == 'sw' else 'Healthy'
    info = disease_info.get(disease_key, {})
    if lang == 'sw' and info.get('swahili_name'):
        return info['swahili_name']
    # English: strip plant prefix and underscores
    parts = disease_key.split('___')
    return parts[-1].replace('_', ' ') if len(parts) > 1 else disease_key.replace('_', ' ')


# ============== HELPER FUNCTIONS ==============
def find_disease_key(plant_type, disease_display_name):
    """Reverse-lookup the disease_info key from plant_type + display_name.
    Handles both English display names and Swahili names."""
    plant_mapping_rev = {
        'apple': 'Apple', 'blueberry': 'Blueberry',
        'cherry': 'Cherry_(including_sour)', 'corn': 'Corn_(maize)',
        'grape': 'Grape', 'orange': 'Orange', 'peach': 'Peach',
        'pepper': 'Pepper,_bell', 'potato': 'Potato', 'raspberry': 'Raspberry',
        'soybean': 'Soybean', 'squash': 'Squash', 'strawberry': 'Strawberry',
        'tomato': 'Tomato'
    }
    plant_prefix = plant_mapping_rev.get((plant_type or '').lower(), '')
    dn_lower = (disease_display_name or '').lower()

    # Healthy plants
    if 'healthy' in dn_lower or 'mwenye afya' in dn_lower:
        return f"{plant_prefix}___healthy" if plant_prefix else None

    for key, info in disease_info.items():
        # Must start with same plant prefix when we have one
        if plant_prefix and not key.startswith(plant_prefix):
            continue
        # Match Swahili name
        if info.get('swahili_name', '').lower() == dn_lower:
            return key
        # Match formatted English name
        formatted = key.replace(f"{plant_prefix}___", "").replace("_", " ").lower()
        if formatted == dn_lower:
            return key

    # Looser fallback: search all keys regardless of plant prefix
    for key, info in disease_info.items():
        if info.get('swahili_name', '').lower() == dn_lower:
            return key
        formatted = key.split("___")[-1].replace("_", " ").lower()
        if formatted == dn_lower or dn_lower in formatted:
            return key
    return None


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


def ensure_disease_key_column():
    """Add disease_key column to predictions table if it doesn't exist."""
    try:
        inspector = inspect(db.engine)
        pred_columns = {column['name'] for column in inspector.get_columns('predictions')}
        if 'disease_key' not in pred_columns:
            db.session.execute(text(
                'ALTER TABLE predictions ADD COLUMN disease_key VARCHAR(150)'
            ))
            db.session.commit()
            app.logger.info('Added disease_key column to predictions table')
    except Exception as exc:
        app.logger.warning(f'Could not ensure disease_key column: {exc}')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    initialize_counties()
    ensure_payment_confirmation_column()
    ensure_disease_key_column()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'webp'}

def load_keras_model():
    # Search for the model file in order:
    # 1. Same folder as app.py  (when running from inside final project/)
    # 2. One level up           (when model sits at repo root in DeepMind_Dynamics)
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, "trained_plant_model.keras"),
        os.path.join(base, "..", "trained_plant_model.keras"),
    ]
    model_path = next((p for p in candidates if os.path.exists(p)), None)
    print("Loading Keras model… please wait, this may take 20–30 seconds")
    if model_path is None:
        raise FileNotFoundError(
            "Model file 'trained_plant_model.keras' not found. "
            "Place it in the same folder as app.py or one level above it."
        )
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
        # Normalize confidence against only the valid classes for this plant
        # so a plant with few classes isn't penalized vs plants with many classes
        total_valid_prob = float(np.sum(valid_probs))
        if total_valid_prob > 0:
            confidence = float(valid_probs[max_idx]) / total_valid_prob
        else:
            confidence = float(valid_probs[max_idx])

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

        county = County.query.filter_by(name=form.county.data).first()
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

def _clear_password_reset_session():
    session.pop('password_reset_email', None)
    session.pop('password_reset_otp', None)
    session.pop('password_reset_expires', None)


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    now_ts = datetime.utcnow().timestamp()
    expires_ts = float(session.get('password_reset_expires', 0) or 0)

    if expires_ts and now_ts > expires_ts:
        _clear_password_reset_session()

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'send_otp':
            email = request.form.get('email', '').strip().lower()
            user = User.query.filter_by(email=email).first()
            if not user:
                flash('No account found with that email.', 'danger')
                return redirect(url_for('forgot_password'))

            otp = ''.join(str(random.randint(0, 9)) for _ in range(6))
            session['password_reset_email'] = email
            session['password_reset_otp'] = otp
            session['password_reset_expires'] = (datetime.utcnow() + timedelta(minutes=10)).timestamp()

            msg = Message(
                'Your Password Reset OTP',
                recipients=[email],
                body=(
                    f'Your PlantDoc password reset OTP is: {otp}\n\n'
                    'This OTP expires in 10 minutes.'
                )
            )
            try:
                mail.send(msg)
                flash('OTP sent to your email. Enter it below to reset your password.', 'success')
            except Exception as exc:
                app.logger.error(f'Password reset email failed: {exc}')
                _clear_password_reset_session()
                flash('Could not send OTP email right now. Please try again later.', 'danger')
            return redirect(url_for('forgot_password'))

        if action == 'reset_password':
            otp_input = request.form.get('otp', '').strip()
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            reset_email = session.get('password_reset_email')
            stored_otp = session.get('password_reset_otp')
            expires = float(session.get('password_reset_expires', 0) or 0)

            if not reset_email or not stored_otp or not expires:
                flash('Start password reset again to get a valid OTP.', 'warning')
                return redirect(url_for('forgot_password'))

            if datetime.utcnow().timestamp() > expires:
                _clear_password_reset_session()
                flash('OTP expired. Request a new one.', 'warning')
                return redirect(url_for('forgot_password'))

            if otp_input != stored_otp:
                flash('Invalid OTP code.', 'danger')
                return redirect(url_for('forgot_password'))

            if len(new_password) < 6:
                flash('Password must be at least 6 characters.', 'danger')
                return redirect(url_for('forgot_password'))

            if new_password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return redirect(url_for('forgot_password'))

            user = User.query.filter_by(email=reset_email).first()
            if not user:
                _clear_password_reset_session()
                flash('Account not found. Please register first.', 'danger')
                return redirect(url_for('register'))

            user.set_password(new_password)
            db.session.commit()
            _clear_password_reset_session()
            flash('Password reset successful. Please log in.', 'success')
            return redirect(url_for('login'))

        flash('Invalid password reset action.', 'danger')
        return redirect(url_for('forgot_password'))

    reset_email = session.get('password_reset_email')
    otp_pending = bool(
        reset_email and
        session.get('password_reset_otp') and
        float(session.get('password_reset_expires', 0) or 0) > datetime.utcnow().timestamp()
    )
    return render_template('forgot_password.html', otp_pending=otp_pending, reset_email=reset_email)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    lang = get_user_language()
    predictions = Prediction.query.filter_by(
        user_id=current_user.id
    ).order_by(Prediction.created_at.desc()).all()
    # Pre-compute display names in current language so stored Swahili/English names don't bleed through
    pred_display_names = {}
    for p in predictions:
        key = p.disease_key or find_disease_key(p.plant_type, p.disease)
        if key:
            pred_display_names[p.id] = disease_display_name(key, lang)
        else:
            # Old prediction stored in a different language — show raw stored name
            # but strip generic Swahili placeholders that aren't useful
            raw = p.disease.replace('_', ' ')
            if raw.lower() in ('ugonjwa', 'disease', ''):
                raw = 'Unknown Disease'
            pred_display_names[p.id] = raw
    return render_template('dashboard.html', user=current_user, predictions=predictions,
                           pred_display_names=pred_display_names, t=t, lang=lang)

@app.route('/prediction/<int:prediction_id>')
@login_required
def view_prediction(prediction_id):
    """View a saved prediction result by ID."""
    prediction = Prediction.query.filter_by(
        id=prediction_id, user_id=current_user.id
    ).first_or_404()
    lang = get_user_language()

    # Use stored disease_key if available, otherwise reverse-lookup
    disease_key = prediction.disease_key or find_disease_key(prediction.plant_type, prediction.disease)

    if disease_key:
        disease_data = get_disease_info(disease_key, lang)
    else:
        # Fallback: use whatever was stored on the prediction row
        disease_data = {
            'scientific_name': prediction.scientific_name or 'Unknown',
            'treatment': prediction.treatment or '',
            'agrovet_medications': [],
            'phytomedicine': prediction.phytomedicine or '',
            'prevention': prediction.prevention or '',
        }

    # Example images from dataset folder (if present)
    example_images = []
    if disease_key:
        disease_folder = os.path.join(
            'static', 'disease pics',
            'Plant_leave_diseases_dataset_without_augmentation',
            disease_key
        )
        if os.path.exists(disease_folder):
            example_images = [
                os.path.join(
                    'disease pics',
                    'Plant_leave_diseases_dataset_without_augmentation',
                    disease_key, f
                ).replace('\\', '/')
                for f in sorted(os.listdir(disease_folder))
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
            ][:5]

    prevention_events = generate_prevention_events(prediction.disease)

    forum_posts = ForumPost.query.filter(
        ForumPost.disease.ilike(f"%{prediction.disease}%")
    ).order_by(ForumPost.created_at.desc()).limit(5).all()

    counties = County.query.order_by(County.name).all()

    # Compute display name in current language from disease_key.
    # Never use raw prediction.disease as fallback — it was stored in the scan language.
    if disease_key:
        d_name = disease_display_name(disease_key, lang)
    else:
        d_name = 'Ugonjwa Usiojulikana' if lang == 'sw' else 'Unknown Disease'

    # Language-aware generic messages — used only when disease_key has no entry in disease_info
    # NEVER fall back to stored prediction text: it was saved in whatever language was active
    # at scan time and would show the wrong language.
    if lang == 'sw':
        fallback_scientific  = 'Haijulikani'
        fallback_treatment   = 'Wasiliana na mtaalamu wa kilimo'
        fallback_phyto       = ''
        fallback_prevention  = ''
    else:
        fallback_scientific  = 'Unknown'
        fallback_treatment   = 'Consult an agricultural extension officer'
        fallback_phyto       = ''
        fallback_prevention  = ''

    conf_pct = (prediction.confidence or 0)
    return render_template(
        'predict_result.html',
        plant_type=prediction.plant_type.capitalize(),
        disease_name=d_name,
        scientific_name=disease_data.get('scientific_name') or fallback_scientific,
        treatment=disease_data.get('treatment') or fallback_treatment,
        agrovet_medications=disease_data.get('agrovet_medications', []),
        phytomedicine=disease_data.get('phytomedicine') or fallback_phyto,
        prevention=disease_data.get('prevention') or fallback_prevention,
        confidence=round(conf_pct * 100, 2),
        low_confidence_warning=(conf_pct < 0.40),
        user_image=prediction.image_path,
        example_images=example_images,
        prevention_events=prevention_events,
        forum_posts=forum_posts,
        counties=counties,
        t=t, lang=lang
    )

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

            try:
                msg = Message(
                    'Your Verification Code',
                    recipients=[email],
                    body=f'Your verification code is: {verification_code}\n\nThis code expires in 1 hour.'
                )
                mail.send(msg)
                print(f"[VERIFICATION] Code sent to {email}: {verification_code}")
            except Exception as mail_err:
                app.logger.warning(f"Email send failed, using console fallback: {mail_err}")
                print(f"\n{'='*50}")
                print(f"[VERIFICATION CODE] Email: {email}")
                print(f"[VERIFICATION CODE] Code:  {verification_code}")
                print(f"{'='*50}\n")

            return jsonify({
                'success': True,
                'message': 'Verification code sent (check your email or server console)'
            })

        except Exception as e:
            app.logger.error(f"Verification error: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
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
    # Only reject completely unreadable images (blank, corrupted, non-plant).
    # Everything above 10% shows a result; low-confidence images show an advisory
    # instead of a hard rejection so farmers still get useful output.
    MIN_CONFIDENCE = 0.10

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
                saved_filename = unique_filename

                # Make prediction
                top_disease, confidence = predict_disease(filepath, plant_prefix)

                # Hard-reject only completely unreadable images
                if confidence < MIN_CONFIDENCE:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    flash(t('low_confidence', lang), 'warning')
                    return redirect(request.url)

                # Flag low-but-acceptable confidence so template can show advisory
                low_confidence_warning = confidence < 0.40

                # Get disease info in selected language
                disease_data = get_disease_info(top_disease, lang)

                # Use disease_display_name helper for consistent language handling
                display_name = disease_display_name(top_disease, lang)

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
                                     top_disease, f).replace('\\', '/')
                        for f in sorted(os.listdir(disease_folder))
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
                    ][:5]

                # Get community forum posts
                forum_posts = ForumPost.query.filter(
                    ForumPost.disease.ilike(f"%{display_name}%")
                ).order_by(ForumPost.created_at.desc()).limit(5).all()

                counties = County.query.order_by(County.name).all()

                # Save to DB always in English so re-viewing in any language works
                en_data = get_disease_info(top_disease, 'en')
                new_prediction = Prediction(
                    image_path=saved_filename,
                    plant_type=plant_type,
                    disease=display_name,
                    disease_key=top_disease,
                    scientific_name=en_data.get('scientific_name', 'Unknown'),
                    phytomedicine=en_data.get('phytomedicine', ''),
                    treatment=en_data.get('treatment', ''),
                    prevention=en_data.get('prevention', ''),
                    confidence=confidence,
                    user_id=current_user.id
                )
                db.session.add(new_prediction)
                db.session.commit()

                return render_template('predict_result.html',
                                       plant_type=plant_type.capitalize(),
                                       disease_name=display_name,
                                       scientific_name=disease_data.get('scientific_name', ''),
                                       treatment=disease_data.get('treatment', ''),
                                       agrovet_medications=disease_data.get('agrovet_medications', []),
                                       phytomedicine=disease_data.get('phytomedicine', ''),
                                       prevention=disease_data.get('prevention', ''),
                                       confidence=round(confidence * 100, 2),
                                       low_confidence_warning=low_confidence_warning,
                                       user_image=saved_filename,
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

    counties = County.query.order_by(County.name).all()
    diseases = db.session.query(ForumPost.disease).distinct().all()
    diseases = [d[0] for d in diseases if d[0]]

    return render_template(
        'forum.html',
        posts=posts,
        counties=counties,
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


@app.route('/forum/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_forum_comment(comment_id):
    comment = ForumComment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        flash('You can only delete your own comments.', 'danger')
        return redirect(request.referrer or url_for('forum'))
    db.session.delete(comment)
    db.session.commit()
    lang = get_user_language()
    flash(t('comment_deleted', lang), 'success')
    return redirect(request.referrer or url_for('forum'))


@app.route('/forum/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_forum_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('You can only delete your own posts.', 'danger')
        return redirect(url_for('forum'))
    db.session.delete(post)
    db.session.commit()
    lang = get_user_language()
    flash(t('post_deleted', lang), 'success')
    return redirect(url_for('forum'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    lang = get_user_language()
    form = CountyForm(obj=current_user)
    if form.validate_on_submit():
        current_user.county = form.county.data
        db.session.commit()
        flash(t('profile_updated', lang), 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', form=form, t=t, lang=lang)

@app.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
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