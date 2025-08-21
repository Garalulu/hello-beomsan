"""
Development settings for hello_beomsan project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '0.0.0.0', 'testserver']

# CSRF settings for development
CSRF_TRUSTED_ORIGINS = []

# Template settings for development
TEMPLATES[0]['OPTIONS']['loaders'] = [
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
]

# Enable template debug in development
TEMPLATES[0]['OPTIONS']['debug'] = DEBUG

# CORS settings for development
CORS_ALLOW_ALL_ORIGINS = True  # Only for development
CORS_ALLOWED_ORIGINS = [
    "https://osu.ppy.sh",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# WhiteNoise settings for development
WHITENOISE_USE_FINDERS = True

# Development-specific logging
LOGGING = LOGGING.copy()
LOGGING['loggers']['django.db.backends'] = {
    'handlers': ['console'],
    'level': 'DEBUG' if os.environ.get('DJANGO_LOG_SQL', 'False').lower() == 'true' else 'INFO',
    'propagate': False,
}

# Development cache settings (optional: use dummy cache for testing)
if os.environ.get('USE_DUMMY_CACHE', 'False').lower() == 'true':
    CACHES['default'] = {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Development-specific middleware additions
MIDDLEWARE += [
    # Add any development-specific middleware here
]

# Django Debug Toolbar (optional)
if os.environ.get('USE_DEBUG_TOOLBAR', 'False').lower() == 'true':
    try:
        import debug_toolbar
        INSTALLED_APPS += ['debug_toolbar']
        MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
        INTERNAL_IPS = ['127.0.0.1', '::1']
    except ImportError:
        pass

print("Development settings loaded")