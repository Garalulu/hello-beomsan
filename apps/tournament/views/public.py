"""
Public-facing views for the tournament application
Handles homepage, game starting, voting, and session APIs
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from ..models import Song, VotingSession, Match, Vote
from core.services.tournament_service import VotingSessionService
from .utils import rate_limit

import json
import logging

logger = logging.getLogger(__name__)


@ensure_csrf_cookie
def home(request):
    """Main page with login/start game buttons"""
    try:
        # Check if user has an active session - optimized query
        active_session = None
        
        try:
            if request.user.is_authenticated:
                # Use the new composite index for faster lookups
                active_session = VotingSession.objects.select_related('user').filter(
                    user=request.user,
                    status='ACTIVE'
                ).only('id', 'current_round', 'current_match', 'created_at', 'user__username').first()
            else:
                session_key = request.session.session_key
                if session_key:
                    # Use the new composite index for faster lookups
                    active_session = VotingSession.objects.filter(
                        session_key=session_key,
                        status='ACTIVE'
                    ).only('id', 'current_round', 'current_match', 'created_at', 'session_key').first()
        except Exception as e:
            logger.warning(f"Error checking active session: {e}")
            active_session = None
        
        # Get some statistics safely with aggressive caching
        try:
            # Cache statistics for 15 minutes (longer cache for better performance)
            cache_key_stats = 'home_stats_combined'
            
            stats = cache.get(cache_key_stats)
            if stats is None:
                # Fetch both counts in a single operation where possible
                total_songs = Song.objects.count()
                total_votes = Vote.objects.count()
                stats = {
                    'total_songs': total_songs,
                    'total_votes': total_votes
                }
                cache.set(cache_key_stats, stats, 900)  # Cache for 15 minutes
            
            total_songs = stats['total_songs']
            total_votes = stats['total_votes']
        except Exception as e:
            logger.warning(f"Error getting statistics: {e}")
            total_songs = 0
            total_votes = 0
        
        return render(request, 'pages/main/home.html', {
            'active_session': active_session,
            'total_songs': total_songs,
            'total_votes': total_votes
        })
        
    except Exception as e:
        logger.error(f"Error in home view: {type(e).__name__}: {str(e)}")
        # Return a basic error page if everything fails
        return render(request, 'pages/main/home.html', {
            'active_session': None,
            'total_songs': 0,
            'total_votes': 0,
            'error_message': 'Unable to load homepage data. Please try again later.'
        })


@ensure_csrf_cookie
def start_game(request):
    """Start new voting session or ask about continuing existing one"""
    try:
        # Check if songs are available first
        if Song.objects.count() == 0:
            messages.error(request, "No songs available. Please contact an administrator to add songs.")
            return redirect('home')
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            try:
                if action == 'continue':
                    # Continue existing ACTIVE session only
                    if request.user.is_authenticated:
                        user = request.user
                        session_key = None
                    else:
                        user = None
                        session_key = request.session.session_key
                    
                    session, is_existing = VotingSessionService.get_or_create_session(
                        user=user,
                        session_key=session_key,
                        preference='active_only'
                    )
                    if session and is_existing:
                        return redirect('/game/vote/?continue=1')  # Add parameter to indicate continuing session
                    else:
                        messages.error(request, "No active session found to continue.")
                        return redirect('start_game')
                
                # Start new session - force create new (abandon existing ACTIVE)
                try:
                    if request.user.is_authenticated:
                        user = request.user
                        session_key = None
                        logger.info(f"Starting new session for authenticated user: {user.username}")
                    else:
                        user = None
                        if not request.session.session_key:
                            request.session.create()
                        session_key = request.session.session_key
                        logger.info(f"Starting new session for anonymous user with session_key: {session_key}")
                    
                    session, is_existing = VotingSessionService.get_or_create_session(
                        user=user,
                        session_key=session_key,
                        preference='create_new'
                    )
                    
                    if session:
                        logger.info(f"Successfully created session {session.id}, redirecting to vote?new=1")
                        return redirect('/game/vote/?new=1')  # Add parameter to indicate new session
                    else:
                        logger.error("get_or_create_session returned None for create_new preference")
                        messages.error(request, "Unable to start tournament. Please try again.")
                        return redirect('home')
                        
                except Exception as session_error:
                    logger.error(f"Error in session creation logic: {type(session_error).__name__}: {str(session_error)}")
                    messages.error(request, f"Session creation failed: {str(session_error)}")
                    return redirect('home')
                    
            except Exception as e:
                logger.error(f"Error starting game session: {type(e).__name__}: {str(e)}")
                messages.error(request, "An error occurred while starting the tournament. Please try again.")
                return redirect('home')
        
        # GET request - Check for existing ACTIVE session only
        existing_session = None
        try:
            if request.user.is_authenticated:
                user = request.user
                session_key = None
            else:
                user = None
                session_key = request.session.session_key
            
            session, is_existing = VotingSessionService.get_or_create_session(
                user=user,
                session_key=session_key,
                preference='active_only'
            )
            
            if session and is_existing:
                existing_session = session
                
        except Exception as e:
            logger.warning(f"Error checking existing session: {e}")
            existing_session = None
    
        return render(request, 'pages/main/start_game.html', {
            'existing_session': existing_session
        })
        
    except Exception as e:
        logger.error(f"Error in start_game view: {type(e).__name__}: {str(e)}")
        messages.error(request, "An error occurred. Please try again.")
        return redirect('home')


@ensure_csrf_cookie
@rate_limit(max_requests=200, window=600)  # Allow frequent page loads during tournament
def vote(request):
    """Main voting interface"""
    try:
        # Check user intention based on URL parameters
        is_new_session = request.GET.get('new') == '1'
        is_continue_session = request.GET.get('continue') == '1'
        
        if is_new_session or is_continue_session:
            # User coming from "start new session" or "continue session" - look for ACTIVE sessions only
            if request.user.is_authenticated:
                user = request.user
                session_key = None
            else:
                user = None
                # Ensure session exists for anonymous users
                if not request.session.session_key:
                    request.session.create()
                session_key = request.session.session_key
                logger.info(f"Anonymous user vote view with session_key: {session_key}")
            
            session, is_existing = VotingSessionService.get_or_create_session(
                user=user,
                session_key=session_key,
                preference='active_only'  # Only look for ACTIVE sessions
            )
            if not session:
                # No active session found, redirect back to start_game
                action = "continue" if is_continue_session else "start new"
                messages.error(request, f"No active session found to {action}. Please start a new tournament.")
                return redirect('start_game')
        else:
            # Default behavior - show COMPLETED results or continue ACTIVE session
            if request.user.is_authenticated:
                user = request.user
                session_key = None
            else:
                user = None
                # Ensure session exists for anonymous users
                if not request.session.session_key:
                    request.session.create()
                session_key = request.session.session_key
                logger.info(f"Anonymous user default vote view with session_key: {session_key}")
            
            session, is_existing = VotingSessionService.get_or_create_session(
                user=user,
                session_key=session_key,
                preference='default'  # COMPLETED (show results) -> ACTIVE (continue) -> CREATE NEW
            )
        
        if not session:
            messages.error(request, "Unable to access tournament session. Please try starting a new game.")
            return redirect('start_game')
        
        # Check if session is completed
        if session.status == 'COMPLETED':
            # Get the winner from the final round (highest round number)
            try:
                final_match = Match.objects.filter(
                    session=session
                ).order_by('-round_number').first()  # Get match from highest round (final)
                winner_song = final_match.winner if final_match else None
                
                logger.info(f"Tournament completed! Winner: {winner_song.title if winner_song else 'Unknown'}")
            except Exception as e:
                logger.warning(f"Error getting tournament winner: {e}")
                winner_song = None
            
            return render(request, 'pages/main/completed.html', {
                'session': session,
                'winner_song': winner_song
            })
        
        # Get current match
        try:
            current_match = VotingSessionService.get_current_match(session)
            if not current_match:
                # Session might be corrupted, mark as abandoned
                session.status = 'ABANDONED'
                session.save()
                messages.error(request, "Tournament session encountered an error. Please start a new game.")
                return redirect('start_game')
        except Exception as e:
            logger.error(f"Error getting current match: {e}")
            messages.error(request, "Unable to load current match. Please try again.")
            return redirect('start_game')
        
        # Add debugging info and cache headers
        response = render(request, 'pages/main/vote.html', {
            'match_data': current_match,
            'session': session,
            'debug_info': {
                'session_id': str(session.id),
                'current_match': session.current_match,
                'current_round': session.current_round,
                'last_updated': session.updated_at.isoformat(),
                'page_generated_at': timezone.now().isoformat()
            }
        })
        
        # Add aggressive cache control headers to prevent caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['Last-Modified'] = 'Thu, 01 Jan 1970 00:00:00 GMT'
        response['ETag'] = ''
        
        return response
        
    except Exception as e:
        logger.error(f"Error in vote view: {type(e).__name__}: {str(e)}")
        messages.error(request, "An error occurred while loading the voting page.")
        return redirect('home')


@require_POST
@ensure_csrf_cookie
@rate_limit(max_requests=150, window=600)  # Allow tournament completion (127 votes + buffer over 10 minutes)
def cast_vote(request):
    """Handle vote submission via AJAX"""
    try:
        # Log the raw request body for debugging
        logger.info(f"Cast vote request body: {request.body}")
        
        data = json.loads(request.body)
        session_id = data.get('session_id')
        chosen_song_id = data.get('chosen_song_id')
        
        logger.info(f"Parsed vote data: session_id={session_id}, chosen_song_id={chosen_song_id}")
        
        if not session_id or not chosen_song_id:
            logger.error(f"Missing data in vote request: session_id={session_id}, chosen_song_id={chosen_song_id}")
            return JsonResponse({
                'success': False,
                'error': 'Missing session ID or song ID'
            })
        
        # Get session
        try:
            session = VotingSession.objects.get(id=session_id)
        except VotingSession.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Session not found'
            })
        
        # Verify session ownership
        if request.user.is_authenticated:
            if session.user != request.user:
                logger.warning(f"Authenticated user {request.user.username} tried to access session belonging to {session.user}")
                return JsonResponse({
                    'success': False,
                    'error': 'Not authorized for this session'
                })
        else:
            # Handle anonymous user session validation
            current_session_key = request.session.session_key
            stored_session_key = session.session_key
            
            # Ensure session exists for anonymous user
            if not current_session_key:
                logger.error("Anonymous user has no session key - creating new session")
                request.session.create()
                current_session_key = request.session.session_key
                if not current_session_key:
                    return JsonResponse({
                        'success': False,
                        'error': 'Unable to maintain session. Please start a new tournament.'
                    })
            
            if stored_session_key != current_session_key:
                logger.warning(f"Session key mismatch for anonymous user: stored={stored_session_key}, current={current_session_key}")
                
                # In development, be strict about session validation
                # In production, be more lenient due to session cookie complexities
                if settings.DEBUG:
                    return JsonResponse({
                        'success': False,
                        'error': 'Session expired. Please start a new tournament.'
                    })
                else:
                    # In production, try to update the session to the current one
                    logger.info(f"Production mode: updating session key from {stored_session_key} to {current_session_key}")
                    session.session_key = current_session_key
                    session.save()
        
        # Check per-session vote limits (prevent excessive voting on single session)
        session_vote_key = f'session_votes:{session.id}'
        session_votes = cache.get(session_vote_key, 0)
        
        # A complete tournament needs 127 votes, so limit to 130 as safety buffer
        if session_votes >= 130:
            return JsonResponse({
                'success': False,
                'error': 'Session vote limit exceeded. This may indicate unusual voting activity.'
            })

        # Cast vote
        try:
            success = VotingSessionService.cast_vote(session, chosen_song_id)
            if not success:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to cast vote'
                })
            
            # Increment session vote counter (expires when session would typically complete)
            cache.set(session_vote_key, session_votes + 1, 3600)  # 1 hour expiry
            
        except Exception as e:
            logger.error(f"Error casting vote: {e}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred while casting your vote'
            })
        
        # Refresh session
        session.refresh_from_db()
        
        # Check if tournament is completed
        if session.status == 'COMPLETED':
            return JsonResponse({
                'success': True,
                'completed': True,
                'redirect_url': '/game/vote/'  # Will show completion page
            })
        
        # Get next match
        try:
            next_match = VotingSessionService.get_current_match(session)
            if not next_match:
                return JsonResponse({
                    'success': False,
                    'error': 'Unable to load next match'
                })
        except Exception as e:
            logger.error(f"Error getting next match: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Error loading next match'
            })
        
        # Ensure session is saved for anonymous users
        if not request.user.is_authenticated:
            request.session.save()
            
        return JsonResponse({
            'success': True,
            'next_match': next_match
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        })
    except Exception as e:
        logger.error(f"Error in cast_vote: {type(e).__name__}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred'
        })


@ensure_csrf_cookie
def session_songs_api(request):
    """API endpoint to get all songs in current session for preloading"""
    try:
        # Get current session
        if request.user.is_authenticated:
            session = VotingSession.objects.filter(
                user=request.user,
                status='ACTIVE'
            ).first()
        else:
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'error': 'No session found'}, status=404)
            session = VotingSession.objects.filter(
                session_key=session_key,
                status='ACTIVE'
            ).first()
        
        if not session:
            return JsonResponse({'error': 'No active session found'}, status=404)
        
        # Extract all songs from bracket data
        all_songs = []
        song_ids = set()
        
        try:
            for round_key, matches in session.bracket_data.items():
                for match in matches:
                    # Get song1
                    if 'song1' in match and match['song1'] and 'id' in match['song1']:
                        song_ids.add(match['song1']['id'])
                    # Get song2
                    if 'song2' in match and match['song2'] and 'id' in match['song2']:
                        song_ids.add(match['song2']['id'])
                    # Get winner if exists
                    if 'winner' in match and match['winner'] and 'id' in match['winner']:
                        song_ids.add(match['winner']['id'])
            
            # Fetch Song objects for all unique IDs
            songs = Song.objects.filter(id__in=song_ids)
            
            for song in songs:
                all_songs.append({
                    'id': str(song.id),
                    'title': song.title,
                    'original_song': song.original_song or '',
                    'audio_url': song.audio_url,
                    'background_image_url': song.background_image_url
                })
            
            logger.info(f"Session songs API: returning {len(all_songs)} songs for session {session.id}")
            return JsonResponse(all_songs, safe=False)
            
        except Exception as e:
            logger.error(f"Error processing bracket data: {e}")
            return JsonResponse({'error': 'Error processing session data'}, status=500)
        
    except Exception as e:
        logger.error(f"Error in session_songs_api: {type(e).__name__}: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)