# PlantDoc — AI Plant Disease Detection

A Flask web app that lets farmers upload a photo of a plant leaf or fruit,
identifies the disease using a trained Keras model, and provides treatment
recommendations, drug prescriptions, natural remedies, and a prevention
schedule — in English or Kiswahili.

---

## Quick Start (for new contributors)

### 1. Clone the repo

```bash
git clone https://github.com/Virgi-niawamaitha/DeepMind_Dynamics.git
cd "DeepMind_Dynamics/final project"
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Set up the `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | What it is |
|---|---|
| `SECRET_KEY` | Any long random string (e.g. `openssl rand -hex 32`) |
| `MAIL_USERNAME` | Gmail address used to send OTP password-reset emails |
| `MAIL_PASSWORD` | Gmail **App Password** (not your normal password — [create one here](https://myaccount.google.com/apppasswords)) |
| `MPESA_*` | Only needed if using the M-Pesa payment feature. Leave blank otherwise. |

> The email fields are only required for the "Forgot Password" feature. The app runs fine without them; password reset emails just won't send.

### 4. Place the model file

The trained Keras model is **not included in the `final project/` folder** because of its size.
It is located at the **root of this repository** as `trained_plant_model.keras`.

The app finds it automatically — no action needed as long as you run from inside `final project/`.

If you ever move the project elsewhere, place `trained_plant_model.keras` either:
- In the same folder as `app.py`, **or**
- One folder above `app.py`

### 5. Run the app

```bash
python app.py
```

Open your browser at: **http://127.0.0.1:5001**

The database is created automatically on first run. No migrations needed.

---

## Features

- Upload a plant image → AI identifies the disease (38 classes across 14 plant types)
- Full disease info: scientific name, treatment, agrovet drug recommendations, natural remedies, prevention tips
- English / Kiswahili language switching (persists per session)
- Healthy plants: no drug recommendations shown
- Low-confidence predictions: shows advisory instead of blocking the result
- Community forum: post, comment, delete own posts/comments — county-filtered
- Prediction history dashboard
- OTP-based forgot-password email flow
- M-Pesa payment integration (optional)

## Plant types supported

Apple, Blueberry, Cherry, Corn (Maize), Grape, Orange, Peach, Bell Pepper,
Potato, Raspberry, Soybean, Squash, Strawberry, Tomato

---

## Project structure

```
final project/
├── app.py                  # Main Flask application
├── models.py               # SQLAlchemy database models
├── forms.py                # WTForms form definitions
├── mpesa.py                # M-Pesa Daraja API integration
├── requirements.txt        # All Python dependencies (pinned)
├── .env.example            # Template for environment variables
├── static/
│   ├── css/style.css
│   ├── i18n/               # EN + SW translation strings
│   ├── images/             # Static site images
│   └── disease pics/       # Example images for each disease class
└── templates/              # Jinja2 HTML templates
```

The SQLite database (`instance/plantdoc.db`) and uploaded scan images
(`static/uploads/`) are created at runtime and are not committed to git.
