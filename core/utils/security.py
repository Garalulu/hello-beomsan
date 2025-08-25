"""
Security utility functions for the application.
"""
import re
import logging
from urllib.parse import urlparse
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def validate_url(url):
    """Validate URL format and allowed domains"""
    if not url:
        raise ValidationError("URL cannot be empty")
    
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValidationError("Invalid URL format")
        
        # Allow only HTTPS for external URLs (except localhost for development)
        if parsed.netloc not in ['localhost', '127.0.0.1'] and parsed.scheme != 'https':
            raise ValidationError("Only HTTPS URLs are allowed")
        
        # Whitelist allowed domains
        allowed_domains = [
            'drive.google.com',
            'docs.google.com',
            'localhost',
            '127.0.0.1'
        ]
        
        if not any(parsed.netloc.endswith(domain) for domain in allowed_domains):
            raise ValidationError(f"Domain {parsed.netloc} is not allowed")
        
        return True
        
    except Exception as e:
        logger.warning(f"URL validation failed for {url}: {e}")
        raise ValidationError(f"Invalid URL: {str(e)}")


def validate_file_extension(filename):
    """Validate file extension against allowed list"""
    allowed_extensions = ['.mp3', '.wav', '.ogg', '.m4a', '.jpg', '.jpeg', '.png', '.gif', '.webp']
    
    if not filename:
        raise ValidationError("Filename cannot be empty")
    
    # Extract extension
    if '.' not in filename:
        raise ValidationError("File must have an extension")
    
    extension = '.' + filename.rsplit('.', 1)[1].lower()
    
    if extension not in allowed_extensions:
        raise ValidationError(f"File extension {extension} is not allowed")
    
    return True


def sanitize_string(text, max_length=None):
    """Sanitize string input for safe storage and display"""
    if not text:
        return ""
    
    # Remove potentially dangerous characters
    text = re.sub(r'[<>"\'\&]', '', str(text))
    
    # Limit length if specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()


def validate_integer(value, min_value=None, max_value=None):
    """Validate integer with optional range constraints"""
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValidationError("Value must be an integer")
    
    if min_value is not None and int_value < min_value:
        raise ValidationError(f"Value must be at least {min_value}")
    
    if max_value is not None and int_value > max_value:
        raise ValidationError(f"Value must be at most {max_value}")
    
    return int_value