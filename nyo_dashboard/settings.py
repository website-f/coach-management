import os
from pathlib import Path
from decimal import Decimal

from django.contrib.messages import constants as message_constants

BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(key, default=False):
    return os.environ.get(key, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(key, default=""):
    raw_value = os.environ.get(key, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


SECRET_KEY = os.environ.get("SECRET_KEY", "nyo-admin-dashboard-development-key")
DEBUG = env_bool("DEBUG", False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts.apps.AccountsConfig",
    "members.apps.MembersConfig",
    "sessions.apps.SessionsConfig",
    "finance.apps.FinanceConfig",
    "payments.apps.PaymentsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nyo_dashboard.urls"

template_options = {
    "context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "accounts.context_processors.global_dashboard_context",
    ],
}
if not DEBUG:
    template_options["loaders"] = [
        (
            "django.template.loaders.cached.Loader",
            [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
        )
    ]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": DEBUG,
        "OPTIONS": template_options,
    },
]

WSGI_APPLICATION = "nyo_dashboard.wsgi.application"

DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").lower()
if DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "nyo_dashboard"),
            "USER": os.environ.get("DB_USER", "nyo_user"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "nyo_password"),
            "HOST": os.environ.get("DB_HOST", "db"),
            "PORT": int(os.environ.get("DB_PORT", "3306")),
            "OPTIONS": {
                "charset": "utf8mb4",
            },
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "0")),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kuala_Lumpur"

USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles"))
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MESSAGE_TAGS = {
    message_constants.DEBUG: "info",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "error",
}

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@nyo.local")
DEFAULT_REGISTRATION_FEE = Decimal(os.environ.get("DEFAULT_REGISTRATION_FEE", "120.00"))
DEFAULT_MONTHLY_FEE = Decimal(os.environ.get("DEFAULT_MONTHLY_FEE", "180.00"))
AI_PLANNER_BACKEND = os.environ.get("AI_PLANNER_BACKEND", "ollama").lower()
AI_PLANNER_ENABLED = env_bool("AI_PLANNER_ENABLED", True)
AI_PLANNER_FALLBACK_ENABLED = env_bool("AI_PLANNER_FALLBACK_ENABLED", True)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b-instruct")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "45"))
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "4096"))
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "420"))
OLLAMA_TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.35"))
OLLAMA_TOP_P = float(os.environ.get("OLLAMA_TOP_P", "0.85"))
OLLAMA_REPEAT_PENALTY = float(os.environ.get("OLLAMA_REPEAT_PENALTY", "1.05"))
OLLAMA_REQUEST_KEEP_ALIVE = os.environ.get("OLLAMA_REQUEST_KEEP_ALIVE", "15m")

if env_bool("ENABLE_HTTPS", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
