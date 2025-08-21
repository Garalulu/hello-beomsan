"""
Settings module for hello_beomsan project.

This module determines which settings to load based on the DJANGO_SETTINGS_MODULE
environment variable or defaults to development settings.
"""

import os

# Determine which settings to use
DJANGO_SETTINGS_MODULE = os.environ.get('DJANGO_SETTINGS_MODULE')

if DJANGO_SETTINGS_MODULE:
    # If explicitly set, respect it
    pass
elif os.environ.get('DEBUG', 'True').lower() == 'false':
    # Production environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
elif 'test' in os.environ.get('DJANGO_COMMAND', ''):
    # Testing environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
else:
    # Default to development
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')