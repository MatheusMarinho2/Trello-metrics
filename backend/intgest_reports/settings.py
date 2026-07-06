from __future__ import annotations

import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BASE_DIR))

from trello_metrics.config import load_env_file

load_env_file(PROJECT_ROOT / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-intgest-reports-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "rest_framework",
    "reports",
]

MIDDLEWARE = [
    "intgest_reports.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "intgest_reports.urls"
WSGI_APPLICATION = "intgest_reports.wsgi.application"
ASGI_APPLICATION = "intgest_reports.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "reports.utils.auth.SignedTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "UNAUTHENTICATED_USER": None,
}

INTGEST_ADMIN_USER = os.getenv("INTGEST_ADMIN_USER", "gestor")
INTGEST_ADMIN_PASSWORD = os.getenv("INTGEST_ADMIN_PASSWORD", "intgest")
INTGEST_AUTH_TOKEN_TTL_SECONDS = int(os.getenv("INTGEST_AUTH_TOKEN_TTL_SECONDS", "43200"))
INTGEST_CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "INTGEST_CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
    ).split(",")
    if origin.strip()
]

DEFAULT_TRELLO_BOARD_ID = os.getenv("TRELLO_BOARD_ID", "yo4qzLai")
DEFAULT_TIMEZONE = os.getenv("INTGEST_DEFAULT_TIMEZONE", "America/Sao_Paulo")
