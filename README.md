# DeepMind Dynamics / PlantDoc

PlantDoc is a Flask-based web application for plant disease detection and farmer support. Users can upload plant images, get disease predictions from a trained Keras model, view treatment and prevention guidance, join a community forum, manage their profile, and use the M-Pesa payment flow for subscription access.

## Features

- Plant disease prediction using the included TensorFlow/Keras model
- Disease details, treatment, prevention, and drug recommendations
- Community forum for posts and comments
- User accounts with county selection and profile updates
- Image uploads for predictions and profile photos
- M-Pesa payment integration for paid access
- Email verification and confirmation support

## Requirements

- Python 3.11 or compatible
- A virtual environment is recommended
- The model file `trained_plant_model.keras` must be present in the project root

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with the environment variables your deployment needs. At minimum, the app reads:

```bash
SECRET_KEY=your-secret-key
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MPESA_CONSUMER_KEY=your-mpesa-key
MPESA_CONSUMER_SECRET=your-mpesa-secret
MPESA_CALLBACK_URL=https://your-public-callback-url
```

Optional M-Pesa production settings:

```bash
MPESA_ENVIRONMENT=sandbox
MPESA_BUSINESS_SHORTCODE=your-business-shortcode
MPESA_PASSKEY=your-passkey
```

## Run

Start the app from the project root:

```bash
source .venv/bin/activate
set -a
source .env
set +a
python app.py
```

Then open:

```text
http://127.0.0.1:5001
```

## Notes

- The app uses SQLite and creates its tables automatically on startup.
- Counties are seeded automatically on startup.
- If M-Pesa credentials are missing, the app still starts, but payment routes will show that M-Pesa is not configured.
- Uploaded files are saved under `static/uploads/`.

## Project Structure

- `app.py` - Flask application, routes, prediction flow, payments, forum, and profile handling
- `models.py` - Database models
- `forms.py` - WTForms definitions and county choices
- `mpesa.py` - M-Pesa STK Push client
- `templates/` - HTML templates
- `static/` - CSS, images, and uploaded files
- `trained_plant_model.keras` - Pretrained disease classification model
