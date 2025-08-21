"""
Test settings for hello_beomsan project.
"""

from .base import *

# Test settings
DEBUG = False

# Use in-memory SQLite for faster tests
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': ':memory:',
    'OPTIONS': {
        'timeout': 30,
    }
}

# Use dummy cache for testing
CACHES['default'] = {
    'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
}

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Test-specific settings
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',  # Fast hashing for tests
]

# Email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Simplified logging for tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}

# Disable security features that aren't needed in tests
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Test media storage
MEDIA_ROOT = BASE_DIR / 'test_media'

print("Testing settings loaded")