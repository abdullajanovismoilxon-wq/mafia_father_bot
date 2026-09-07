import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from backend/ or project root
load_dotenv(BASE_DIR / '.env')
load_dotenv(BASE_DIR.parent / '.env')

# Security: DEBUG defaults to False (safe for production).
# Developers must set DEBUG=True explicitly in .env.
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

_secret_key_env = os.environ.get('DJANGO_SECRET_KEY', '')
if not _secret_key_env:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY environment variable is required in production (DEBUG=False). "
            "Set it in your .env file or deployment secrets."
        )
    # Dev-only fallback — intentionally obvious so developers notice it.
    _secret_key_env = 'django-insecure-dev-key-mafia-bot-father-2026!'

SECRET_KEY = _secret_key_env

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',') if os.environ.get('ALLOWED_HOSTS') else ['*']

_csrf_origins = [
    'http://16.171.175.23',
    'https://16.171.175.23',
    'http://16.171.175.23:8000',
    'https://16.171.175.23:8000',
    'http://16-171-175-23.sslip.io',
    'https://16-171-175-23.sslip.io',
    'http://16.171.175.23.nip.io',
    'https://16.171.175.23.nip.io',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
if os.environ.get('CSRF_TRUSTED_ORIGINS'):
    _csrf_origins.extend([origin.strip() for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()])

CSRF_TRUSTED_ORIGINS = list(set(_csrf_origins))
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party packages
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',

    # Domain Apps
    'apps.users',
    'apps.common',
    'apps.bots',
    'apps.subscriptions',
    'apps.payments',
    'apps.templates',
    'apps.games',
    'apps.analytics',
    'apps.tournaments',
    'apps.economy',
    'apps.stats',
    'apps.superadmin',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database Configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres'):
    import psycopg2
    # Simple parse for postgres URL
    # Format: postgres://user:pass@host:port/dbname
    from urllib.parse import urlparse
    url = urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': url.path[1:],
            'USER': url.username,
            'PASSWORD': url.password,
            'HOST': url.hostname,
            'PORT': url.port or 5432,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.environ.get('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', 60))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.environ.get('JWT_REFRESH_TOKEN_LIFETIME_DAYS', 7))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': os.environ.get('JWT_SECRET', SECRET_KEY),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'MAFIA BOT FATHER — Control Plane API',
    'DESCRIPTION': 'API documentation for Mafia Bot Father platform control plane.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
    if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = DEBUG

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
    if origin.strip()
]

# Redis & Celery
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
# Prevent broker connection from blocking indefinitely when Redis is unavailable.
# Tests and local dev without Redis will fail fast instead of hanging.
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False
CELERY_BROKER_CONNECTION_MAX_RETRIES = 1
# When running Django tests (no Redis), run tasks synchronously in-process.
# This allows test_advance_phase tests to work without a live Redis connection.
if os.environ.get('DJANGO_TESTING', '').lower() in ('1', 'true'):
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True


# Fernet Encryption Key for sensitive Bot Credentials (Telegram API tokens).
# MUST be set via environment variable in production.
_enc_key_env = os.environ.get('ENCRYPTION_KEY', '')
if not _enc_key_env:
    if not DEBUG:
        raise ImproperlyConfigured(
            "ENCRYPTION_KEY environment variable is required in production (DEBUG=False). "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    # Dev-only fallback
    _enc_key_env = 'Ym90ZmF0aGVyLWVuanlvdHktc2VjcmV0LWtleS0xMjM0NTY3ODk='

ENCRYPTION_KEY = _enc_key_env

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
APPEND_SLASH = False

# P2P Payment Configuration
P2P_CARD_NUMBER = os.environ.get('P2P_CARD_NUMBER', '5614682011504018')
