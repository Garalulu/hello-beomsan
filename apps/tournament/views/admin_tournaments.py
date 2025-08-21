"""
Admin views for tournament management
Handles tournament sessions, history, and detailed session monitoring
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.paginator import Paginator
from django.db import transaction

from ..models import Song, VotingSession, Match

import logging

logger = logging.getLogger(__name__)


@staff_member_required
@ensure_csrf_cookie
def tournament_manage(request):
    """Tournament management overview"""
    # Force fresh data from database
    from django.db import connection
    connection.ensure_connection()
    
    # Combine active and abandoned sessions in one query
    active_abandoned_sessions = VotingSession.objects.filter(
        status__in=['ACTIVE', 'ABANDONED']
    ).select_related('user__profile').order_by('-updated_at')
    
    completed_sessions = VotingSession.objects.filter(status='COMPLETED').select_related('user__profile').order_by('-updated_at')[:10]  # Latest 10
    total_songs = Song.objects.count()
    
    return render(request, 'pages/admin/tournament_manage.html', {
        'active_abandoned_sessions': active_abandoned_sessions,
        'completed_sessions': completed_sessions,
        'total_songs': total_songs,
        'stats': {
            'total_active': VotingSession.objects.filter(status='ACTIVE').count(),
            'total_completed': VotingSession.objects.filter(status='COMPLETED').count(),
            'total_abandoned': VotingSession.objects.filter(status='ABANDONED').count(),
        }
    })


@staff_member_required
def tournament_manage_ajax(request):
    """AJAX endpoint for tournament manage page updates"""
    try:
        # Force fresh data from database - use same approach as session_detail_ajax
        with transaction.atomic():
            # Get fresh sessions data with select_for_update to force fresh read
            active_abandoned_sessions = VotingSession.objects.filter(
                status__in=['ACTIVE', 'ABANDONED']
            ).select_related('user__profile').order_by('-updated_at')
            
            completed_sessions = VotingSession.objects.filter(
                status='COMPLETED'
            ).select_related('user__profile').order_by('-updated_at')[:10]
            
            # Force individual refresh for each session  
            for session in active_abandoned_sessions:
                session.refresh_from_db()
        
        # Build sessions data
        def build_session_data(sessions):
            data = []
            for session in sessions:
                # Force refresh each session before building data
                session.refresh_from_db()
                data.append({
                    'id': str(session.id),
                    'status': session.status,
                    'user_display': session.user.username if session.user else f"Anonymous ({session.session_key[:8]}...)",
                    'osu_username': session.user.profile.osu_username if session.user and hasattr(session.user, 'profile') and session.user.profile else None,
                    'round_name': session.get_round_name(),
                    'match_progress': session.get_match_progress(),
                    'created_at': session.created_at.strftime('%b %d, %Y %H:%M'),
                    'updated_at': session.updated_at.strftime('%b %d, %Y %H:%M'),
                })
            return data
        
        response = JsonResponse({
            'success': True,
            'active_abandoned_sessions': build_session_data(active_abandoned_sessions),
            'completed_sessions': build_session_data(completed_sessions),
            'stats': {
                'total_active': VotingSession.objects.filter(status='ACTIVE').count(),
                'total_completed': VotingSession.objects.filter(status='COMPLETED').count(),
                'total_abandoned': VotingSession.objects.filter(status='ABANDONED').count(),
            }
        })
        
        # Add headers to prevent caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logger.error(f"Error in tournament_manage_ajax: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@staff_member_required
@ensure_csrf_cookie
def tournament_history(request):
    """Tournament history with filtering"""
    sessions = VotingSession.objects.filter(status='COMPLETED').select_related('user').order_by('-created_at')
    
    # Filter by user if specified
    user_filter = request.GET.get('user', '').strip()
    if user_filter:
        try:
            # Try to find user by username
            from django.contrib.auth.models import User
            target_user = User.objects.get(username=user_filter)
            sessions = sessions.filter(user=target_user)
        except User.DoesNotExist:
            # If user doesn't exist, show empty results
            sessions = sessions.none()
    
    # Pagination
    paginator = Paginator(sessions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'pages/admin/tournament_history.html', {
        'page_obj': page_obj,
        'user_filter': user_filter,
    })


@staff_member_required
@ensure_csrf_cookie
def session_detail(request, session_id):
    """Detailed view of a voting session"""
    session = get_object_or_404(VotingSession, id=session_id)
    matches = Match.objects.filter(session=session).order_by('round_number', 'match_number')
    
    # Get winner song if tournament is completed
    winner_song = None
    if session.status == 'COMPLETED':
        try:
            final_match = Match.objects.filter(
                session=session,
                round_number=7  # Grand Finals
            ).first()
            winner_song = final_match.winner if final_match else None
        except Exception as e:
            logger.warning(f"Error getting tournament winner: {e}")
    
    return render(request, 'pages/admin/session_detail.html', {
        'session': session,
        'matches': matches,
        'winner_song': winner_song
    })


@staff_member_required
def session_detail_ajax(request, session_id):
    """AJAX endpoint for real-time session updates"""
    try:
        # Force fresh query from database - no caching
        # Use atomic transaction to ensure we get the latest data
        with transaction.atomic():
            # Get fresh data from database - use select_for_update to force fresh read
            session = VotingSession.objects.select_for_update(nowait=True).get(id=session_id)
            matches = Match.objects.filter(session=session).select_related('song1', 'song2', 'winner').order_by('round_number', 'match_number')
            
        
        # Build matches data
        matches_data = []
        for match in matches:
            matches_data.append({
                'round_number': match.round_number,
                'match_number': match.match_number,
                'song1_title': match.song1.title,
                'song1_original': match.song1.original_song or '',
                'song2_title': match.song2.title,
                'song2_original': match.song2.original_song or '',
                'winner_title': match.winner.title if match.winner else None,
                'winner_is_song1': match.winner == match.song1 if match.winner else None,
            })
        
        # Get winner info
        winner_song = None
        if session.status == 'COMPLETED':
            try:
                final_match = Match.objects.filter(
                    session=session,
                    round_number=7
                ).first()
                if final_match and final_match.winner:
                    winner_song = {
                        'title': final_match.winner.title,
                        'original_song': final_match.winner.original_song or '',
                        'background_image_url': final_match.winner.background_image_url,
                        'audio_url': final_match.winner.audio_url
                    }
            except Exception:
                pass
        
        response = JsonResponse({
            'success': True,
            'session': {
                'id': str(session.id),
                'status': session.status,
                'current_round': session.current_round,
                'current_match': session.current_match,
                'round_name': session.get_round_name(),
                'match_progress': session.get_match_progress(),
                'updated_at': session.updated_at.isoformat()
            },
            'matches': matches_data,
            'winner_song': winner_song,
            'total_matches': len(matches_data)
        })
        
        # Add headers to prevent caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logger.error(f"Error in session_detail_ajax: {e}")
        return JsonResponse({'success': False, 'error': str(e)})