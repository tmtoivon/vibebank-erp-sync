"""
Django settings for vibebank_erp project.
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-changeme-in-production'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounting_sync',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'vibebank_erp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'vibebank_erp.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ERP Sync Settings
# Configure these in your environment or local settings

# Netvisor API settings
NETVISOR_HOST = os.environ.get('NETVISOR_HOST', '')
NETVISOR_SENDER = os.environ.get('NETVISOR_SENDER', '')
NETVISOR_CUSTOMER_ID = os.environ.get('NETVISOR_CUSTOMER_ID', '')
NETVISOR_CUSTOMER_KEY = os.environ.get('NETVISOR_CUSTOMER_KEY', '')
NETVISOR_PARTNER_ID = os.environ.get('NETVISOR_PARTNER_ID', '')
NETVISOR_PARTNER_KEY = os.environ.get('NETVISOR_PARTNER_KEY', '')
NETVISOR_ORGANIZATION_ID = os.environ.get('NETVISOR_ORGANIZATION_ID', '')
NETVISOR_LANGUAGE = os.environ.get('NETVISOR_LANGUAGE', 'FI')

# Fennoa API settings
FENNOA_API_KEY = os.environ.get('FENNOA_API_KEY', '')
FENNOA_BASE_URL = os.environ.get('FENNOA_BASE_URL', 'https://api.fennoa.com')

# Procountor API settings
PROCOUNTOR_CLIENT_ID = os.environ.get('PROCOUNTOR_CLIENT_ID', '')
PROCOUNTOR_CLIENT_SECRET = os.environ.get('PROCOUNTOR_CLIENT_SECRET', '')
PROCOUNTOR_REDIRECT_URI = os.environ.get('PROCOUNTOR_REDIRECT_URI', '')
PROCOUNTOR_API_KEY = os.environ.get('PROCOUNTOR_API_KEY', '')
PROCOUNTOR_COMPANY_ID = os.environ.get('PROCOUNTOR_COMPANY_ID', '')
PROCOUNTOR_BASE_URL = os.environ.get('PROCOUNTOR_BASE_URL', 'https://api.procountor.com')
