"""
Tournament utility functions for validation, security, and caching
"""
from django.http import JsonResponse
from django.core.cache import cache
from django.db.models import Q
from urllib.parse import urlparse
import re
import time
import logging

logger = logging.getLogger(__name__)


def validate_url(url):
    """Validate URL format and allowed domains"""
    if not url:
        return True  # Allow empty URLs
    
    # Basic URL format validation
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\\.)+[A-Z]{2,6}\\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})'  # ...or ip
        r'(?::\\d+)?'  # optional port
        r'(?:/?|[/?]\\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        return False
    
    # Allow specific domains for Google Drive and osu!
    allowed_domains = [
        'drive.google.com',
        'docs.google.com', 
        'osu.ppy.sh',
        'localhost',
        '127.0.0.1'
    ]
    
    parsed = urlparse(url)
    domain = parsed.netloc.split(':')[0]  # Remove port if present
    
    return any(domain.endswith(allowed) for allowed in allowed_domains)


def sanitize_input(text, max_length=200):
    """Sanitize text input for storage (not HTML escaping)"""
    if not text:
        return ''
    # Only strip whitespace and limit length - no HTML escaping for database storage
    return str(text).strip()[:max_length]


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def rate_limit(max_requests=60, window=60):
    """Tournament-aware rate limiting decorator"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            client_ip = get_client_ip(request)
            cache_key = f'rate_limit:{client_ip}:{view_func.__name__}'
            
            # Get current request count
            requests = cache.get(cache_key, 0)
            
            # Enhanced rate limiting for cast_vote
            if view_func.__name__ == 'cast_vote':
                # Check for velocity-based abuse (>2 votes per second)
                velocity_key = f'vote_velocity:{client_ip}'
                recent_votes = cache.get(velocity_key, [])
                current_time = time.time()
                
                # Remove votes older than 10 seconds
                recent_votes = [vote_time for vote_time in recent_votes if current_time - vote_time < 10]
                
                # Check if voting too fast (more than 2 votes in last 2 seconds)
                very_recent = [vote_time for vote_time in recent_votes if current_time - vote_time < 2]
                if len(very_recent) >= 2:
                    return JsonResponse({
                        'success': False,
                        'error': 'Voting too fast. Please wait a moment between votes.'
                    }, status=429)
                
                # Add current vote time and update cache
                recent_votes.append(current_time)
                cache.set(velocity_key, recent_votes, 60)  # Keep for 1 minute
            
            # Standard rate limiting
            if requests >= max_requests:
                remaining_time = cache.ttl(cache_key)  # Time until reset
                if remaining_time <= 0:
                    remaining_time = window
                
                error_message = f'Rate limit exceeded. You can vote again in {remaining_time // 60}m {remaining_time % 60}s.'
                if view_func.__name__ == 'cast_vote':
                    error_message = f'Tournament vote limit reached ({max_requests} votes per {window//60} minutes). Please wait {remaining_time // 60}m {remaining_time % 60}s to continue.'
                
                return JsonResponse({
                    'success': False,
                    'error': error_message
                }, status=429)
            
            # Increment counter
            cache.set(cache_key, requests + 1, window)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def convert_google_drive_url(url, url_type='view'):
    """
    Convert Google Drive sharing URLs to appropriate format based on use case
    url_type: 
    - 'image' for image display/thumbnails
    - 'audio' for audio streaming/preview  
    - 'download' for direct downloads
    - 'view' for general viewing (legacy)
    """
    if not url or 'drive.google.com' not in url:
        return url
    
    # Extract file ID from various Google Drive URL formats
    file_id_patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',  # /file/d/FILE_ID/view or /file/d/FILE_ID/edit
        r'id=([a-zA-Z0-9_-]+)',       # ?id=FILE_ID
    ]
    
    file_id = None
    for pattern in file_id_patterns:
        match = re.search(pattern, url)
        if match:
            file_id = match.group(1)
            break
    
    if file_id:
        if url_type == 'image':
            # Use thumbnail API for images - works better for embedding
            return f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000"
        elif url_type == 'audio':
            # Use preview format for audio streaming
            return f"https://drive.google.com/file/d/{file_id}/preview"
        elif url_type == 'download':
            # Use download format for actual downloads
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        else:  # view (legacy)
            return f"https://drive.google.com/uc?export=view&id={file_id}"
    
    return url


def clear_song_caches():
    """Clear all song-related caches"""
    # Clear specific song-related caches
    cache_keys_to_clear = [
        'home_stats_total_songs',
        'home_stats_total_votes', 
        'completed_tournaments_count',
        'song_stats_all',
        'song_stats_wins',
        'song_stats_picks',
        'song_stats_winrate'
    ]
    
    cache.delete_many(cache_keys_to_clear)
    
    # Clear song stats cache patterns if supported
    cache_patterns = ['song_stats_*', 'home_stats_*']
    for pattern in cache_patterns:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(pattern)
    
    # Force clear the entire cache if patterns aren't supported (for development)
    if not hasattr(cache, 'delete_pattern'):
        try:
            cache.clear()
            logger.info("Cleared entire cache due to song deletion")
        except Exception as e:
            logger.warning(f"Could not clear cache: {e}")


def check_duplicate_song(title, original_song=None):
    """
    Check if a song with the same title and original_song already exists
    Returns (is_duplicate, existing_song_or_none)
    """
    from ..models import Song
    
    title = title.strip()
    original_song = original_song.strip() if original_song else ''
    
    # Build query for potential duplicates
    if original_song:
        # If original_song is provided, check for exact match on both fields
        duplicate_query = Q(title__iexact=title) & Q(original_song__iexact=original_song)
    else:
        # If no original_song, check for songs with same title and no original_song
        duplicate_query = Q(title__iexact=title) & (Q(original_song='') | Q(original_song__isnull=True))
    
    # Also check for potential conflicts where title matches regardless of original_song
    title_conflict_query = Q(title__iexact=title)
    
    existing_song = Song.objects.filter(duplicate_query).first()
    if existing_song:
        return True, existing_song
    
    # Check for title conflicts that might be confusing
    title_conflict = Song.objects.filter(title_conflict_query).first()
    if title_conflict and title_conflict.original_song != original_song:
        # Different original_song but same title - might be confusing but not a strict duplicate
        return False, title_conflict
    
    return False, None