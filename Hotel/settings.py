
"""
Django settings for Hotel project.

This file contains the main configuration for:
- Installed Django and third-party applications
- Middleware
- MySQL database connection
- Password validation
- Time zone
- Django REST Framework
- JWT authentication
- API pagination
- Consistent API error responses
"""

from pathlib import Path
from datetime import timedelta


# =========================================================
# 1. BASE DIRECTORY
# =========================================================
# BASE_DIR represents the root folder of the Django project.
# It is used when defining paths for files and folders.

BASE_DIR = Path(__file__).resolve().parent.parent


# =========================================================
# 2. SECURITY SETTINGS
# =========================================================

# Keep your existing local SECRET_KEY here.
# Do not share this key or upload it to GitHub.
SECRET_KEY = "PASTE_YOUR_EXISTING_SECRET_KEY_HERE"

# True is suitable for local development only.
# Set this to False before production deployment.
DEBUG = True

# Hosts allowed to access this Django application.
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
]


# =========================================================
# 3. INSTALLED APPLICATIONS
# =========================================================
# Django applications and third-party applications
# must be registered here before they can be used.

INSTALLED_APPS = [

    # Default Django applications.
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Our hotel room booking application.
    "roombooking",

    # Django REST Framework provides REST API functionality.
    "rest_framework",

]


# =========================================================
# 4. MIDDLEWARE
# =========================================================
# Middleware processes incoming requests and outgoing responses.
# Keep the standard Django middleware enabled.

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# 5. PROJECT URL AND TEMPLATE SETTINGS
# =========================================================

# Main URL configuration file.
ROOT_URLCONF = "Hotel.urls"

# Django template configuration.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        # Additional template directories can be added here.
        "DIRS": [],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# WSGI application used by Django servers.
WSGI_APPLICATION = "Hotel.wsgi.application"


# =========================================================
# 6. MYSQL DATABASE CONFIGURATION
# =========================================================
# Django uses this configuration to connect to MySQL.
# Keep your existing local database password here.
# We will move credentials into .env later.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "HotelBookingDB",
        "USER": "root",
        "PASSWORD": "",
        "HOST": "localhost",
        "PORT": "3306",
    }
}


# =========================================================
# 7. PASSWORD VALIDATION
# =========================================================
# These validators check whether a user's password
# is sufficiently strong when creating or changing accounts.

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


# =========================================================
# 8. INTERNATIONALIZATION AND TIME ZONE
# =========================================================

LANGUAGE_CODE = "en-us"

# Keep UTC as the database/application time zone.
# Django converts dates and times using timezone utilities.
TIME_ZONE = "UTC"

USE_I18N = True

# Enables timezone-aware datetime handling.
USE_TZ = True


# =========================================================
# 9. STATIC FILES
# =========================================================

STATIC_URL = "static/"


# =========================================================
# 10. DEFAULT PRIMARY KEY
# =========================================================
# Django uses BigAutoField for automatically generated IDs
# unless a model defines another primary key.

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =========================================================
# 11. DJANGO REST FRAMEWORK CONFIGURATION
# =========================================================
# Controls authentication, permissions, pagination
# and error handling for REST API endpoints.

REST_FRAMEWORK = {

    # JWTAuthentication checks the access token supplied by
    # the client in the Authorization request header.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],

    # All API endpoints require an authenticated user by default.
    # Individual views can override this permission if required.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],

    # Pagination controls how many records are returned per page.
    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),

    # Return 10 records per page by default.
    "PAGE_SIZE": 10,

    # Use our custom exception handler to standardize API errors.
    "EXCEPTION_HANDLER": (
        "roombooking.exceptions.custom_exception_handler"
    ),

}


# =========================================================
# 12. JWT CONFIGURATION
# =========================================================
# SimpleJWT creates and validates access and refresh tokens.

SIMPLE_JWT = {

    # Access token is valid for 30 minutes.
    # Clients use this token to access protected APIs.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),

    # Refresh token is valid for one day.
    # It can be used to obtain a new access token.
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),

    # Keep refresh-token rotation disabled for this setup.
    "ROTATE_REFRESH_TOKENS": False,

    # Identify users by their Django user ID.
    "USER_ID_FIELD": "id",

    # The user ID is stored in the token using this claim name.
    "USER_ID_CLAIM": "user_id",

}
