"""
Production settings for hello_beomsan project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Production hosts
APP_NAME = os.environ.get("FLY_APP_NAME")
if APP_NAME:
    ALLOWED_HOSTS = [f"{APP_NAME}.fly.dev", '127.0.0.1', 'localhost']
else:
    ALLOWED_HOSTS = []

# CSRF settings for production
CSRF_TRUSTED_ORIGINS = []
if APP_NAME:
    CSRF_TRUSTED_ORIGINS = [f"https://{APP_NAME}.fly.dev"]

# HTTPS/SSL Security
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookie Security
SECURE_COOKIES = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
# OAuth-compatible SameSite settings
SESSION_COOKIE_SAMESITE = 'Lax'  # Allow cross-site requests for OAuth redirects
CSRF_COOKIE_SAMESITE = 'Lax'     # Allow CSRF token in OAuth flows
# Session configuration for OAuth and anonymous users
SESSION_COOKIE_AGE = 1209600      # 2 weeks  
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True  # Ensure session is saved for OAuth flows and voting
# Additional session settings for anonymous user stability
SESSION_COOKIE_NAME = 'sessionid'  # Explicit session cookie name
SESSION_COOKIE_DOMAIN = None       # Use default domain
SESSION_COOKIE_PATH = '/'          # Available on entire site

# Content Security and Headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Template settings for production
TEMPLATES[0]['OPTIONS']['loaders'] = [
    ('django.template.loaders.cached.Loader', [
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    ]),
]

# CORS settings for production
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://osu.ppy.sh",
]

# WhiteNoise settings for production
WHITENOISE_USE_FINDERS = True
WHITENOISE_MAX_AGE = 31536000  # 1 year cache for static files
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'zip', 'gz', 'tgz', 'bz2', 'tbz', 'xz', 'br']

# Production logging with file handler
LOGGING = LOGGING.copy()
log_dir = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir)
    except OSError:
        pass

LOGGING['handlers']['file'] = {
    'level': 'WARNING',
    'class': 'logging.FileHandler',
    'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
    'formatter': 'verbose',
}

# Add file handler to all loggers
for logger_name in LOGGING['loggers']:
    LOGGING['loggers'][logger_name]['handlers'].append('file')

# Email configuration for production (configure as needed)
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = os.environ.get('EMAIL_HOST')
# EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
# EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
# EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
# EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
# DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@example.com')

print("Production settings loaded")