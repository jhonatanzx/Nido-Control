import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DJANGO_BINARY_BUILDER = {
    "NAME": "NidoControl",
    "VERSION": "1.1.0",
    "PUBLISHER": "Equipo de Desarrollo NidoControl",
    "EXECUTABLE_NAME": "NidoControl",
    "ICON": BASE_DIR / "static" / "icono.ico",
}


def _safe_binary_directory_name(value):
    characters = [
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in str(value).strip()
    ]
    normalized = "".join(characters).strip("-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized or "DjangoBinaryBuilder"


def _resolve_data_root(base_dir, environ=None):
    base_dir = Path(base_dir)
    if not (base_dir / "launcher.py").is_file():
        return base_dir

    environ = os.environ if environ is None else environ
    data_root = environ.get("DJANGO_BINARY_DATA_DIR")
    if data_root:
        data_root = Path(data_root).expanduser().resolve()
    else:
        local_app_data = environ.get("LOCALAPPDATA")
        data_root = (
            Path(local_app_data)
            if local_app_data
            else Path.home() / ".local" / "share"
        )
        data_root /= _safe_binary_directory_name(DJANGO_BINARY_BUILDER["PUBLISHER"])
        data_root /= _safe_binary_directory_name(DJANGO_BINARY_BUILDER["NAME"])

    return data_root.resolve()


SECRET_KEY = 'django-insecure-cambia-esta-clave-por-una-segura'

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_bootstrap5',
    'core',
    "django_binary_builder",
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

ROOT_URLCONF = 'nidocontrol.urls'

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

WSGI_APPLICATION = 'nidocontrol.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
DATA_ROOT = _resolve_data_root(BASE_DIR)
MEDIA_ROOT = DATA_ROOT / 'media'
REPORTS_ROOT = DATA_ROOT / 'reportes'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'core.Usuario'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'debug',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}
