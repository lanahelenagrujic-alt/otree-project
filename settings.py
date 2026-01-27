from os import environ
import os
import dj_database_url

# Force secure mode - 'STUDY'
OTREE_AUTH_LEVEL = os.environ.get('OTREE_AUTH_LEVEL', 'STUDY')

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')  # set in Render dashboard

SESSION_CONFIGS = [
    dict(
        name='social_investment',
        display_name="Social Investment Experiment",
        app_sequence=['social_investment'],
        num_demo_participants=3,
    ),
]

ROOMS = [
    dict(
        name='social_investment_app',
        display_name='Social Investment Experiment Room',
    ),
]

SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=1.00,
    participation_fee=0.00,
    doc=""
)

PARTICIPANT_FIELDS = []
SESSION_FIELDS = []

LANGUAGE_CODE = 'en'
REAL_WORLD_CURRENCY_CODE = 'USD'
USE_POINTS = True
POINTS_DECIMAL_PLACES = 2

DEMO_PAGE_INTRO_HTML = """ """

SECRET_KEY = environ.get('SECRET_KEY', 'changeme-in-prod')
DEBUG = False
OTREE_PRODUCTION = True

ALLOWED_HOSTS = ['otree-render-project.onrender.com']

DATABASES = {
    'default': dj_database_url.config(default=os.environ.get('DATABASE_URL'))
}