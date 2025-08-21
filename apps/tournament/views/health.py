"""
Health check views for monitoring and keeping the app warm
"""
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
import time


@csrf_exempt
@require_GET

def health_check(request):
    """
    Simple health check endpoint to keep Fly.io machines warm
    Returns basic status information
    """
    try:
        # Basic database connectivity test
        from ..models import Song
        song_count = Song.objects.count()
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': time.time(),
            'songs': song_count,
            'message': 'Service is running'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'timestamp': time.time(),
            'error': str(e),
            'message': 'Service has issues'
        }, status=503)