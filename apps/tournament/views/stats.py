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
    """Display song statistics with fibonacci-weighted ranking"""
    try:
        # Get sort parameter from request
        sort_by = request.GET.get('sort', 'fibonacci')  # Default to fibonacci ranking
        
        # Get all songs with different sorting options
        if sort_by == 'pick_rate':
            # Sort by pick rate (% of individual matches won)
            songs = Song.objects.with_calculated_rates().order_by('-calculated_pick_rate', '-total_wins')
        else:  # Default: fibonacci ranking (tournament wins first, then fibonacci score)
            # Overall ranking: tournament wins first, then fibonacci score as tiebreaker
            songs = Song.objects.with_fibonacci_ranking().order_by('-tournament_wins', '-fibonacci_score')
        
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
            },
            'sort_by': sort_by
        })
        
    except Exception as e:
        logger.error(f"Error in song_stats view: {type(e).__name__}: {str(e)}")
        messages.error(request, "Unable to load statistics. Please try again.")
        return redirect('home')