import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from codelabx.configuration import (
    build_cache_settings,
    build_database_settings,
    build_task_settings,
)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_int(name, default):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f'{name} must be an integer.'
        ) from exc


def env_list(name, default=''):
    value = os.getenv(name, default)
    return [
        item.strip()
        for item in value.split(',')
        if item.strip()
    ]


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '').strip()

if not SECRET_KEY:
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY is required. '
        'Copy .env.example to .env and configure it.'
    )

DEBUG = env_bool('DJANGO_DEBUG', False)

ALLOWED_HOSTS = env_list(
    'DJANGO_ALLOWED_HOSTS',
    '127.0.0.1,localhost',
)

CSRF_TRUSTED_ORIGINS = env_list(
    'DJANGO_CSRF_TRUSTED_ORIGINS'
)

GEMINI_API_KEY = (
    os.getenv('GEMINI_API_KEY', '').strip() or None
)

GEMINI_MODEL = os.getenv(
    'GEMINI_MODEL',
    'gemini-flash-latest',
).strip()

AI_FEATURES_ENABLED = env_bool(
    'AI_FEATURES_ENABLED',
    False,
)

ASSESSMENTS_ENABLED = env_bool(
    'ASSESSMENTS_ENABLED',
    False,
)

CODING_CHALLENGES_ENABLED = env_bool(
    'CODING_CHALLENGES_ENABLED',
    False,
)

IMAGE_ANALYSIS_ENABLED = env_bool(
    'IMAGE_ANALYSIS_ENABLED',
    False,
)

AI_DAILY_REQUEST_LIMIT = env_int(
    'AI_DAILY_REQUEST_LIMIT',
    25,
)

AI_JSON_BODY_MAX_BYTES = env_int(
    'AI_JSON_BODY_MAX_BYTES',
    64 * 1024,
)

AI_CHAT_MAX_CHARS = env_int(
    'AI_CHAT_MAX_CHARS',
    4000,
)

AI_CODE_MAX_CHARS = env_int(
    'AI_CODE_MAX_CHARS',
    20000,
)

AI_PROBLEM_MAX_CHARS = env_int(
    'AI_PROBLEM_MAX_CHARS',
    5000,
)

AI_TOPIC_MAX_CHARS = env_int(
    'AI_TOPIC_MAX_CHARS',
    200,
)

AI_IMAGE_MAX_BYTES = env_int('AI_IMAGE_MAX_BYTES', 5 * 1024 * 1024)
AI_IMAGE_MAX_PIXELS = env_int('AI_IMAGE_MAX_PIXELS', 20_000_000)
AI_IMAGE_MAX_DIMENSION = env_int('AI_IMAGE_MAX_DIMENSION', 8192)
AI_IMAGE_NORMALIZED_MAX_DIMENSION = env_int(
    'AI_IMAGE_NORMALIZED_MAX_DIMENSION',
    4096,
)

AI_IMAGE_QUESTION_MAX_CHARS = env_int(
    'AI_IMAGE_QUESTION_MAX_CHARS',
    2000,
)

AUTH_LOGIN_ATTEMPTS = env_int('AUTH_LOGIN_ATTEMPTS', 5)
AUTH_LOGIN_WINDOW_SECONDS = env_int('AUTH_LOGIN_WINDOW_SECONDS', 300)
AUTH_REGISTER_ATTEMPTS = env_int('AUTH_REGISTER_ATTEMPTS', 3)
AUTH_REGISTER_WINDOW_SECONDS = env_int('AUTH_REGISTER_WINDOW_SECONDS', 3600)

RATE_LIMIT_ENABLED = env_bool(
    'RATE_LIMIT_ENABLED',
    True,
)

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
DATABASE_REQUIRE_TLS = env_bool('DATABASE_REQUIRE_TLS', True)
DB_CONNECTION_MAX_AGE = env_int('DJANGO_DB_CONN_MAX_AGE', 60)
DB_CONNECT_TIMEOUT_SECONDS = env_int(
    'DJANGO_DB_CONNECT_TIMEOUT_SECONDS',
    10,
)

REDIS_URL = os.getenv('REDIS_URL', '').strip()
REDIS_REQUIRE_TLS = env_bool('REDIS_REQUIRE_TLS', True)
CACHE_KEY_PREFIX = os.getenv(
    'DJANGO_CACHE_KEY_PREFIX',
    'codelabx',
).strip()
CACHE_DEFAULT_TIMEOUT = env_int(
    'DJANGO_CACHE_DEFAULT_TIMEOUT',
    300,
)
CACHE_SOCKET_TIMEOUT_SECONDS = env_int(
    'DJANGO_CACHE_SOCKET_TIMEOUT_SECONDS',
    5,
)
SHARED_CACHE_CONFIGURED = bool(REDIS_URL)

TASK_BACKEND = os.getenv(
    'DJANGO_TASK_BACKEND',
    'django.tasks.backends.immediate.ImmediateBackend',
).strip()
TASK_QUEUES = env_list(
    'DJANGO_TASK_QUEUES',
    'default,ai,maintenance',
)
TASKS = build_task_settings(
    backend=TASK_BACKEND,
    queues=TASK_QUEUES,
)

USE_WHITENOISE = env_bool(
    'DJANGO_USE_WHITENOISE',
    False,
)
TRUST_X_FORWARDED_PROTO = env_bool(
    'DJANGO_TRUST_X_FORWARDED_PROTO',
    False,
)
TRUST_X_FORWARDED_HOST = env_bool(
    'DJANGO_USE_X_FORWARDED_HOST',
    False,
)

CSP_LEGACY_INLINE_ALLOWED = False
CSP_STYLE_ATTRIBUTES_ALLOWED = True

AI_RATE_LIMIT_WINDOW_SECONDS = env_int(
    'AI_RATE_LIMIT_WINDOW_SECONDS',
    60,
)

AI_CHAT_BURST_LIMIT = env_int(
    'AI_CHAT_BURST_LIMIT',
    10,
)

AI_CODE_REVIEW_BURST_LIMIT = env_int(
    'AI_CODE_REVIEW_BURST_LIMIT',
    5,
)

AI_GENERATION_BURST_LIMIT = env_int(
    'AI_GENERATION_BURST_LIMIT',
    5,
)

AI_IMAGE_BURST_LIMIT = env_int(
    'AI_IMAGE_BURST_LIMIT',
    3,
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'accounts',
    'dashboard',
    'learning',
    'content',
    'practice',
    'assessments',
    'ai_tools',
    'progress',
    'notes',
    'challenges',
    'intelligence',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    *(
        ['whitenoise.middleware.WhiteNoiseMiddleware']
        if USE_WHITENOISE
        else []
    ),
    'codelabx.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'codelabx.urls'

TEMPLATES = [
    {
        'BACKEND': (
            'django.template.backends.django.'
            'DjangoTemplates'
        ),
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                (
                    'django.template.context_processors.'
                    'request'
                ),
                (
                    'django.contrib.auth.'
                    'context_processors.auth'
                ),
                (
                    'django.contrib.messages.'
                    'context_processors.messages'
                ),
            ],
        },
    },
]

WSGI_APPLICATION = 'codelabx.wsgi.application'
ASGI_APPLICATION = 'codelabx.asgi.application'

DATABASES = build_database_settings(
    base_dir=BASE_DIR,
    database_url=DATABASE_URL,
    sqlite_path=os.getenv('SQLITE_PATH', 'db.sqlite3'),
    connection_max_age=DB_CONNECTION_MAX_AGE,
    connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
)

CACHES = build_cache_settings(
    redis_url=REDIS_URL,
    key_prefix=CACHE_KEY_PREFIX,
    default_timeout=CACHE_DEFAULT_TIMEOUT,
    socket_timeout=CACHE_SOCKET_TIMEOUT_SECONDS,
)

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'MinimumLengthValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'
        ),
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = os.getenv(
    'DJANGO_TIME_ZONE',
    'UTC',
)

USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'codelabx.storage.CodeLabXStaticFilesStorage'
            if USE_WHITENOISE
            else 'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}

WHITENOISE_MAX_AGE = 31_536_000
WHITENOISE_ALLOW_ALL_ORIGINS = False
WHITENOISE_MANIFEST_STRICT = True

EMAIL_BACKEND = os.getenv(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = os.getenv(
    'DJANGO_DEFAULT_FROM_EMAIL',
    'CodeLabX <noreply@localhost>',
)

LOGIN_URL = 'accounts:login'

DEFAULT_AUTO_FIELD = (
    'django.db.models.BigAutoField'
)

SECURE_SSL_REDIRECT = env_bool(
    'DJANGO_SECURE_SSL_REDIRECT',
    False,
)

SESSION_COOKIE_SECURE = env_bool(
    'DJANGO_SESSION_COOKIE_SECURE',
    False,
)

CSRF_COOKIE_SECURE = env_bool(
    'DJANGO_CSRF_COOKIE_SECURE',
    False,
)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

SECURE_HSTS_SECONDS = env_int(
    'DJANGO_HSTS_SECONDS',
    0,
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    'DJANGO_HSTS_INCLUDE_SUBDOMAINS',
    False,
)

SECURE_HSTS_PRELOAD = env_bool(
    'DJANGO_HSTS_PRELOAD',
    False,
)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

if TRUST_X_FORWARDED_PROTO:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

USE_X_FORWARDED_HOST = TRUST_X_FORWARDED_HOST

X_FRAME_OPTIONS = 'DENY'

DATA_UPLOAD_MAX_MEMORY_SIZE = env_int(
    'DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE',
    6 * 1024 * 1024,
)

FILE_UPLOAD_MAX_MEMORY_SIZE = env_int(
    'DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE',
    6 * 1024 * 1024,
)

LOG_LEVEL = os.getenv(
    'DJANGO_LOG_LEVEL',
    'INFO',
).upper()

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': (
                '{levelname} {asctime} '
                '{name}: {message}'
            ),
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}
