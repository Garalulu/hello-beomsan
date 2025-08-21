"""
Statistics views for the tournament application
Handles song performance statistics and analytics
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.paginator import Paginator

from ..models import Song, VotingSession

import logging

logger = logging.getLogger(__name__)


@ensure_csrf_cookie
def song_stats(request):
    """Display song statistics"""
    try:
        # Get all songs with statistics
        songs = Song.objects.all().order_by('-total_wins')
        
        # Pagination
        paginator = Paginator(songs, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Calculate overall statistics
        try:
            total_songs = songs.count()
            total_matches = sum(song.total_picks for song in songs)
            total_tournaments = VotingSession.objects.filter(status='COMPLETED').count()
        except Exception as e:
            logger.warning(f"Error calculating stats: {e}")
            total_songs = 0
            total_matches = 0
            total_tournaments = 0
        
        return render(request, 'pages/main/stats.html', {
            'page_obj': page_obj,
            'stats': {
                'total_songs': total_songs,
                'total_matches': total_matches,
                'total_tournaments': total_tournaments
            }
        })
        
    except Exception as e:
        logger.error(f"Error in song_stats view: {type(e).__name__}: {str(e)}")
        messages.error(request, "Unable to load statistics. Please try again.")
        return redirect('home')