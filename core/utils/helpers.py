"""
General helper utilities for the application.
"""
import json
import logging
from typing import Dict, Any, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)


def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """Safely parse JSON string with fallback default"""
    if not json_string:
        return default
    
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON: {e}")
        return default


def safe_json_dumps(data: Any, default: str = "{}") -> str:
    """Safely serialize data to JSON with fallback default"""
    if data is None:
        return default
    
    try:
        return json.dumps(data)
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to serialize JSON: {e}")
        return default


def get_client_ip(request) -> str:
    """Get client IP address from request, considering proxies"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def cache_key_for_user(user, prefix: str) -> str:
    """Generate cache key for a user with given prefix"""
    if user and user.is_authenticated:
        return f"{prefix}:user:{user.id}"
    else:
        return f"{prefix}:anonymous"


def invalidate_user_cache(user, prefixes: list):
    """Invalidate cache entries for a user with given prefixes"""
    for prefix in prefixes:
        key = cache_key_for_user(user, prefix)
        cache.delete(key)
        logger.debug(f"Invalidated cache key: {key}")


def calculate_percentage(part: int, total: int) -> float:
    """Calculate percentage with safe division"""
    if total == 0:
        return 0.0
    return round((part / total) * 100, 2)


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to maximum length with optional suffix"""
    if not text or len(text) <= max_length:
        return text
    
    if len(suffix) >= max_length:
        return text[:max_length]
    
    return text[:max_length - len(suffix)] + suffix