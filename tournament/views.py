from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from .models import Song, VotingSession, Match, Vote
from .services import VotingSessionService
import json
import logging

logger = logging.getLogger(__name__)


@ensure_csrf_cookie
def home(request):
    """Main page with login/start game buttons"""
    try:
        # Check if user has an active session
        active_session = None
        
        try:
            if request.user.is_authenticated:
                active_session = VotingSession.objects.filter(
                    user=request.user,
                    status='ACTIVE'
                ).first()
            else:
                session_key = request.session.session_key
                if session_key:
                    active_session = VotingSession.objects.filter(
                        session_key=session_key,
                        status='ACTIVE'
                    ).first()
        except Exception as e:
            logger.warning(f"Error checking active session: {e}")
            active_session = None
        
        # Get some statistics safely
        try:
            total_songs = Song.objects.count()
            total_votes = Vote.objects.count()
        except Exception as e:
            logger.warning(f"Error getting statistics: {e}")
            total_songs = 0
            total_votes = 0
        
        return render(request, 'main/home.html', {
            'active_session': active_session,
            'total_songs': total_songs,
            'total_votes': total_votes
        })
        
    except Exception as e:
        logger.error(f"Error in home view: {type(e).__name__}: {str(e)}")
        # Return a basic error page if everything fails
        return render(request, 'main/home.html', {
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
                if action == 'continue' and request.user.is_authenticated:
                    # Continue existing session
                    session = VotingSession.objects.filter(
                        user=request.user,
                        status='ACTIVE'
                    ).first()
                    if session:
                        return redirect('vote')
                
                # Start new session (abandon existing if any)
                with transaction.atomic():
                    if request.user.is_authenticated:
                        # Mark old sessions as abandoned
                        VotingSession.objects.filter(
                            user=request.user,
                            status='ACTIVE'
                        ).update(status='ABANDONED')
                        
                        session = VotingSessionService.create_voting_session(user=request.user)
                    else:
                        # Anonymous user
                        if not request.session.session_key:
                            request.session.create()
                        
                        # Mark old sessions as abandoned
                        VotingSession.objects.filter(
                            session_key=request.session.session_key,
                            status='ACTIVE'
                        ).update(status='ABANDONED')
                        
                        session = VotingSessionService.create_voting_session(
                            session_key=request.session.session_key
                        )
                
                if session:
                    messages.success(request, "Tournament started successfully!")
                    return redirect('vote')
                else:
                    messages.error(request, "Unable to start tournament. Please try again.")
                    return redirect('home')
                    
            except Exception as e:
                logger.error(f"Error starting game session: {type(e).__name__}: {str(e)}")
                messages.error(request, "An error occurred while starting the tournament. Please try again.")
                return redirect('home')
        
        # GET request - Check for existing session
        existing_session = None
        try:
            if request.user.is_authenticated:
                existing_session = VotingSession.objects.filter(
                    user=request.user,
                    status='ACTIVE'
                ).first()
            else:
                session_key = request.session.session_key
                if session_key:
                    existing_session = VotingSession.objects.filter(
                        session_key=session_key,
                        status='ACTIVE'
                    ).first()
        except Exception as e:
            logger.warning(f"Error checking existing session: {e}")
            existing_session = None
    
        return render(request, 'main/start_game.html', {
            'existing_session': existing_session
        })
        
    except Exception as e:
        logger.error(f"Error in start_game view: {type(e).__name__}: {str(e)}")
        messages.error(request, "An error occurred. Please try again.")
        return redirect('home')


@ensure_csrf_cookie
def vote(request):
    """Main voting interface"""
    try:
        # Get or create session
        session, is_existing = VotingSessionService.get_or_create_session(
            user=request.user if request.user.is_authenticated else None,
            session_key=request.session.session_key
        )
        
        if not session:
            messages.error(request, "Unable to access tournament session. Please try starting a new game.")
            return redirect('start_game')
        
        # Check if session is completed
        if session.status == 'COMPLETED':
            # Get the winner
            try:
                final_match = Match.objects.filter(
                    session=session,
                    round_number=1  # Final round
                ).first()
                winner_song = final_match.winner if final_match else None
            except Exception as e:
                logger.warning(f"Error getting tournament winner: {e}")
                winner_song = None
            
            return render(request, 'main/completed.html', {
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
        
        return render(request, 'main/vote.html', {
            'match': current_match,
            'session': session
        })
        
    except Exception as e:
        logger.error(f"Error in vote view: {type(e).__name__}: {str(e)}")
        messages.error(request, "An error occurred while loading the voting page.")
        return redirect('home')


@require_POST
@ensure_csrf_cookie
def cast_vote(request):
    """Handle vote submission via AJAX"""
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        chosen_song_id = data.get('chosen_song_id')
        
        if not session_id or not chosen_song_id:
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
                return JsonResponse({
                    'success': False,
                    'error': 'Not authorized for this session'
                })
        else:
            if session.session_key != request.session.session_key:
                return JsonResponse({
                    'success': False,
                    'error': 'Not authorized for this session'
                })
        
        # Cast vote
        try:
            success = VotingSessionService.cast_vote(session, chosen_song_id)
            if not success:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to cast vote'
                })
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
        
        return render(request, 'main/stats.html', {
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


# ADMIN VIEWS

@staff_member_required
@ensure_csrf_cookie
def upload_song(request):
    """Upload new song"""
    try:
        if request.method == 'POST':
            title = request.POST.get('title', '').strip()
            artist = request.POST.get('artist', '').strip()
            audio_url = request.POST.get('audio_url', '').strip()
            background_image_url = request.POST.get('background_image_url', '').strip()
            
            # Validation
            if not title:
                messages.error(request, "Song title is required.")
            elif not audio_url:
                messages.error(request, "Audio URL is required.")
            else:
                try:
                    with transaction.atomic():
                        song = Song.objects.create(
                            title=title,
                            artist=artist,
                            audio_url=audio_url,
                            background_image_url=background_image_url
                        )
                    
                    messages.success(request, f"Song '{title}' uploaded successfully!")
                    return redirect('manage_songs')
                    
                except IntegrityError as e:
                    logger.error(f"Database integrity error creating song: {e}")
                    messages.error(request, "A song with this information already exists.")
                except Exception as e:
                    logger.error(f"Error creating song: {e}")
                    messages.error(request, "An error occurred while uploading the song.")
        
        return render(request, 'admin/upload_song.html')
        
    except Exception as e:
        logger.error(f"Error in upload_song view: {type(e).__name__}: {str(e)}")
        messages.error(request, "An error occurred. Please try again.")
        return redirect('manage_songs')


@staff_member_required
@ensure_csrf_cookie
def manage_songs(request):
    """Manage existing songs"""
    try:
        songs = Song.objects.all().order_by('-created_at')
        
        # Pagination
        paginator = Paginator(songs, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        return render(request, 'admin/manage_songs.html', {
            'page_obj': page_obj
        })
        
    except Exception as e:
        logger.error(f"Error in manage_songs view: {type(e).__name__}: {str(e)}")
        messages.error(request, "Unable to load songs management page.")
        return render(request, 'admin/manage_songs.html', {
            'page_obj': None
        })


@ensure_csrf_cookie
def vote(request):
    """Display voting interface"""
    # First check for recently completed session to show results
    if request.user.is_authenticated:
        completed_session = VotingSession.objects.filter(
            user=request.user,
            status='COMPLETED'
        ).order_by('-updated_at').first()
    else:
        if not request.session.session_key:
            request.session.create()
        completed_session = VotingSession.objects.filter(
            session_key=request.session.session_key,
            status='COMPLETED'
        ).order_by('-updated_at').first()
    
    # If there's a recently completed session (within last 10 minutes), show results
    if completed_session:
        from django.utils import timezone
        from datetime import timedelta
        if completed_session.updated_at > timezone.now() - timedelta(minutes=10):
            return render(request, 'main/completed.html', {
                'session': completed_session
            })
    
    # Get or create active voting session
    if request.user.is_authenticated:
        session, existing = VotingSessionService.get_or_create_session(user=request.user)
    else:
        session, existing = VotingSessionService.get_or_create_session(
            session_key=request.session.session_key
        )
    
    # Get current match
    match_data = VotingSessionService.get_current_match(session)
    
    if not match_data:
        # Session completed
        return render(request, 'main/completed.html', {
            'session': session
        })
    
    return render(request, 'main/vote.html', {
        'match_data': match_data,
        'session': session
    })


@require_POST
@ensure_csrf_cookie
def cast_vote(request):
    """Handle vote submission via AJAX"""
    try:
        data = json.loads(request.body)
        song_id = data.get('song_id')
        
        # Get session
        if request.user.is_authenticated:
            session = VotingSession.objects.filter(
                user=request.user,
                status='ACTIVE'
            ).first()
        else:
            session_key = request.session.session_key
            session = VotingSession.objects.filter(
                session_key=session_key,
                status='ACTIVE'
            ).first()
        
        if not session:
            return JsonResponse({
                'success': False,
                'error': 'No active session found'
            })
        
        # Cast vote
        success = VotingSessionService.cast_vote(session, song_id)
        
        if success:
            # Get next match or completion status
            next_match = VotingSessionService.get_current_match(session)
            
            return JsonResponse({
                'success': True,
                'completed': session.status == 'COMPLETED',
                'next_match': next_match,
                'progress': VotingSessionService.calculate_progress(session)
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Vote could not be cast'
            })
            
    except Exception as e:
        import traceback
        error_details = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'traceback': traceback.format_exc()
        }
        print(f"Vote casting error: {error_details}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'debug': error_details
        })


def song_stats(request):
    """Display song statistics"""
    # Get sorting parameter
    sort_by = request.GET.get('sort', 'win_rate')
    
    # Use optimized manager methods for better performance
    if sort_by == 'pick_rate':
        songs = Song.objects.for_statistics().filter(total_picks__gt=0).order_by('-calculated_pick_rate')
    elif sort_by == 'tournaments':
        songs = Song.objects.for_statistics().order_by('-tournament_wins')
    else:  # win_rate
        songs = Song.objects.for_statistics().filter(tournament_wins__gt=0).order_by('-tournament_wins')
    
    # Use QuerySet directly for pagination (more efficient)
    from django.core.paginator import Paginator
    paginator = Paginator(songs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'main/stats.html', {
        'page_obj': page_obj,
        'sort_by': sort_by
    })


# Admin views for song management
@staff_member_required
@ensure_csrf_cookie
def upload_song(request):
    """Upload new song with Google Drive URLs"""
    if request.method == 'POST':
        title = request.POST.get('title')
        artist = request.POST.get('artist', '')
        audio_url = request.POST.get('audio_url')
        background_image_url = request.POST.get('background_image_url', '')
        
        if not title or not audio_url:
            messages.error(request, "Title and audio URL are required.")
            return render(request, 'admin/upload_song.html')
        
        try:
            # Create song record
            song = Song.objects.create(
                title=title,
                artist=artist,
                audio_url=audio_url,
                background_image_url=background_image_url
            )
            
            messages.success(request, f"Song '{title}' added successfully!")
            return redirect('song_stats')
            
        except Exception as e:
            messages.error(request, f"Error adding song: {str(e)}")
    
    return render(request, 'admin/upload_song.html')


@staff_member_required
@ensure_csrf_cookie
def manage_songs(request):
    """Manage existing songs"""
    songs = Song.objects.all().order_by('title')
    paginator = Paginator(songs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin/manage_songs.html', {
        'page_obj': page_obj
    })


@staff_member_required
@ensure_csrf_cookie
def edit_song(request, song_id):
    """Edit song details"""
    try:
        song = get_object_or_404(Song, id=song_id)
        
        if request.method == 'POST':
            title = request.POST.get('title', '').strip()
            artist = request.POST.get('artist', '').strip()
            audio_url = request.POST.get('audio_url', '').strip()
            background_image_url = request.POST.get('background_image_url', '').strip()
            
            if not title or not audio_url:
                messages.error(request, "Title and audio URL are required.")
            else:
                try:
                    with transaction.atomic():
                        song.title = title
                        song.artist = artist
                        song.audio_url = audio_url
                        song.background_image_url = background_image_url
                        song.save()
                    
                    messages.success(request, f"Song '{title}' updated successfully!")
                    return redirect('manage_songs')
                    
                except Exception as e:
                    logger.error(f"Error updating song {song_id}: {e}")
                    messages.error(request, f"Error updating song: {str(e)}")
        
        return render(request, 'admin/edit_song.html', {'song': song})
        
    except Exception as e:
        logger.error(f"Error in edit_song view: {type(e).__name__}: {str(e)}")
        messages.error(request, "Unable to load song for editing.")
        return redirect('manage_songs')


@staff_member_required
@require_POST
@ensure_csrf_cookie
def delete_song(request, song_id):
    """Delete song"""
    try:
        song = get_object_or_404(Song, id=song_id)
        
        # Check if song is being used in active sessions
        active_sessions_count = VotingSession.objects.filter(status='ACTIVE').count()
        if active_sessions_count > 0:
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete song while tournaments are active'
            })
        
        song_title = song.title
        
        with transaction.atomic():
            song.delete()
        
        logger.info(f"Song '{song_title}' deleted by {request.user.username}")
        return JsonResponse({
            'success': True,
            'message': f"Song '{song_title}' deleted successfully"
        })
        
    except Exception as e:
        logger.error(f"Error deleting song {song_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while deleting the song'
        })


@staff_member_required
@ensure_csrf_cookie
def tournament_manage(request):
    """Tournament management dashboard"""
    try:
        # Get active sessions
        try:
            active_sessions = VotingSession.objects.filter(status='ACTIVE').select_related('user').order_by('-updated_at')
        except Exception as e:
            logger.warning(f"Error getting active sessions: {e}")
            active_sessions = []
        
        # Get recent completed sessions
        try:
            completed_sessions = VotingSession.objects.filter(status='COMPLETED').select_related('user').order_by('-updated_at')[:20]
        except Exception as e:
            logger.warning(f"Error getting completed sessions: {e}")
            completed_sessions = []
        
        # Calculate statistics
        try:
            total_active = VotingSession.objects.filter(status='ACTIVE').count()
            total_completed = VotingSession.objects.filter(status='COMPLETED').count()
            total_abandoned = VotingSession.objects.filter(status='ABANDONED').count()
        except Exception as e:
            logger.warning(f"Error calculating tournament statistics: {e}")
            total_active = 0
            total_completed = 0
            total_abandoned = 0
        
        return render(request, 'admin/tournament_manage.html', {
            'active_sessions': active_sessions,
            'completed_sessions': completed_sessions,
            'stats': {
                'total_active': total_active,
                'total_completed': total_completed,
                'total_abandoned': total_abandoned,
            }
        })
        
    except Exception as e:
        logger.error(f"Error in tournament_manage view: {type(e).__name__}: {str(e)}")
        messages.error(request, "Unable to load tournament management dashboard.")
        return render(request, 'admin/tournament_manage.html', {
            'active_sessions': [],
            'completed_sessions': [],
            'stats': {'total_active': 0, 'total_completed': 0, 'total_abandoned': 0}
        })


@staff_member_required
@ensure_csrf_cookie
def tournament_history(request):
    """Tournament history with filtering"""
    try:
        sessions = VotingSession.objects.filter(status='COMPLETED').select_related('user').order_by('-updated_at')
        
        # Filter by user if specified
        user_filter = request.GET.get('user', '').strip()
        if user_filter:
            try:
                sessions = sessions.filter(user__username__icontains=user_filter)
            except Exception as e:
                logger.warning(f"Error filtering sessions by user: {e}")
        
        # Pagination
        try:
            paginator = Paginator(sessions, 20)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
        except Exception as e:
            logger.error(f"Error paginating tournament history: {e}")
            page_obj = None
        
        return render(request, 'admin/tournament_history.html', {
            'page_obj': page_obj,
            'user_filter': user_filter
        })
        
    except Exception as e:
        logger.error(f"Error in tournament_history view: {type(e).__name__}: {str(e)}")
        messages.error(request, "Unable to load tournament history.")
        return render(request, 'admin/tournament_history.html', {
            'page_obj': None,
            'user_filter': ''
        })


@staff_member_required
@ensure_csrf_cookie
def user_manage(request):
    """User management with statistics"""
    try:
        from django.db.models import Count, Q
        from django.contrib.auth.models import User
        
        # Get users with their statistics
        try:
            users = User.objects.select_related('profile').annotate(
                total_sessions=Count('voting_sessions'),
                completed_sessions=Count('voting_sessions', filter=Q(voting_sessions__status='COMPLETED')),
                active_sessions=Count('voting_sessions', filter=Q(voting_sessions__status='ACTIVE'))
            ).order_by('-total_sessions')
        except Exception as e:
            logger.error(f"Error querying users with statistics: {e}")
            users = User.objects.all().order_by('-date_joined')
        
        # Filter by username if specified
        username_filter = request.GET.get('username', '').strip()
        if username_filter:
            try:
                users = users.filter(username__icontains=username_filter)
            except Exception as e:
                logger.warning(f"Error filtering users by username: {e}")
        
        # Pagination
        try:
            paginator = Paginator(users, 20)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
        except Exception as e:
            logger.error(f"Error paginating users: {e}")
            page_obj = None
        
        return render(request, 'admin/user_manage.html', {
            'page_obj': page_obj,
            'username_filter': username_filter
        })
        
    except Exception as e:
        logger.error(f"Error in user_manage view: {type(e).__name__}: {str(e)}")
        messages.error(request, "Unable to load user management page.")
        return render(request, 'admin/user_manage.html', {
            'page_obj': None,
            'username_filter': ''
        })


@staff_member_required
def session_detail(request, session_id):
    """View detailed session information"""
    try:
        session = get_object_or_404(VotingSession, id=session_id)
        
        # Get all matches for this session
        try:
            matches = Match.objects.filter(session=session).select_related('song1', 'song2', 'winner').order_by('round_number', 'match_number')
        except Exception as e:
            logger.warning(f"Error getting matches for session {session_id}: {e}")
            matches = []
        
        # Get session winner if completed
        winner_song = None
        if session.status == 'COMPLETED':
            try:
                # Find the winner from the final match
                final_match = matches.filter(round_number=1).first()  # Round 1 is the final
                if final_match:
                    winner_song = final_match.winner
            except Exception as e:
                logger.warning(f"Error getting winner for session {session_id}: {e}")
        
        return render(request, 'admin/session_detail.html', {
            'session': session,
            'matches': matches,
            'winner_song': winner_song
        })
        
    except Exception as e:
        logger.error(f"Error in session_detail view: {type(e).__name__}: {str(e)}")
        messages.error(request, "Unable to load session details.")
        return redirect('tournament_manage')