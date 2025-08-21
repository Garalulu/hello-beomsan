from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import cache_page
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.html import escape
from .models import Song, VotingSession, Match, Vote
from core.services.tournament_service import VotingSessionService
import json
import logging
import csv
import io
import re

# Security validation functions
def validate_url(url):
    """Validate URL format and allowed domains"""
    if not url:
        return True  # Allow empty URLs
    
    # Basic URL format validation
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
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
    
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.split(':')[0]  # Remove port if present
    
    return any(domain.endswith(allowed) for allowed in allowed_domains)

def sanitize_input(text, max_length=200):
    """Sanitize text input"""
    if not text:
        return ''
    return escape(str(text).strip())[:max_length]

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def rate_limit(max_requests=60, window=60):
    """Simple rate limiting decorator"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            client_ip = get_client_ip(request)
            cache_key = f'rate_limit:{client_ip}:{view_func.__name__}'
            
            # Get current request count
            requests = cache.get(cache_key, 0)
            
            if requests >= max_requests:
                return JsonResponse({
                    'success': False,
                    'error': 'Rate limit exceeded. Please try again later.'
                }, status=429)
            
            # Increment counter
            cache.set(cache_key, requests + 1, window)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

logger = logging.getLogger(__name__)


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
    from django.core.cache import cache
    cache.delete_many([
        'home_stats_total_songs',
        'completed_tournaments_count'
    ])
    # Clear song stats cache patterns
    cache_patterns = ['song_stats_*']
    for pattern in cache_patterns:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(pattern)


def check_duplicate_song(title, original_song=None):
    """
    Check if a song with the same title and original_song already exists
    Returns (is_duplicate, existing_song_or_none)
    """
    from django.db.models import Q
    
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
        
        # Get some statistics safely with caching
        try:
            # Cache statistics for 5 minutes
            cache_key_songs = 'home_stats_total_songs'
            cache_key_votes = 'home_stats_total_votes'
            
            total_songs = cache.get(cache_key_songs)
            if total_songs is None:
                total_songs = Song.objects.count()
                cache.set(cache_key_songs, total_songs, 300)  # Cache for 5 minutes
                
            total_votes = cache.get(cache_key_votes)
            if total_votes is None:
                total_votes = Vote.objects.count()
                cache.set(cache_key_votes, total_votes, 300)  # Cache for 5 minutes
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
    
        return render(request, 'pages/main/start_game.html', {
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
@rate_limit(max_requests=30, window=60)  # Limit voting to prevent abuse
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


# ADMIN VIEWS

@staff_member_required
@ensure_csrf_cookie
def upload_song(request):
    """Upload new song"""
    try:
        if request.method == 'POST':
            # Sanitize and validate inputs
            title = sanitize_input(request.POST.get('title', ''))
            original_song = sanitize_input(request.POST.get('original_song', ''))
            audio_url = request.POST.get('audio_url', '').strip()
            background_image_url = request.POST.get('background_image_url', '').strip()
            
            # Security validation
            if not validate_url(audio_url):
                messages.error(request, "Invalid or unauthorized audio URL domain.")
                return render(request, 'pages/admin/upload_song.html')
                
            if not validate_url(background_image_url):
                messages.error(request, "Invalid or unauthorized image URL domain.")
                return render(request, 'pages/admin/upload_song.html')
            
            # Basic validation
            if not title:
                messages.error(request, "Song title is required.")
            elif not audio_url:
                messages.error(request, "Audio URL is required.")
            else:
                # Check for duplicates
                is_duplicate, existing_song = check_duplicate_song(title, original_song)
                if is_duplicate:
                    if original_song:
                        messages.error(request, f"Song '{title}' (Original: {original_song}) already exists in the database.")
                    else:
                        messages.error(request, f"Song '{title}' already exists in the database.")
                else:
                    try:
                        # Convert Google Drive URLs to proper format
                        audio_url = convert_google_drive_url(audio_url, 'audio')
                        background_image_url = convert_google_drive_url(background_image_url, 'image')
                        
                        with transaction.atomic():
                            song = Song.objects.create(
                                title=title,
                                original_song=original_song,
                                audio_url=audio_url,
                                background_image_url=background_image_url
                            )
                        
                        # Clear relevant caches after adding new song
                        clear_song_caches()
                        
                        messages.success(request, f"Song '{title}' uploaded successfully!")
                        return redirect('manage_songs')
                        
                    except IntegrityError as e:
                        logger.error(f"Database integrity error creating song: {e}")
                        messages.error(request, "A song with this information already exists.")
                    except Exception as e:
                        logger.error(f"Error creating song: {e}")
                        messages.error(request, "An error occurred while uploading the song.")
        
        return render(request, 'pages/admin/upload_song.html')
        
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
        
        return render(request, 'pages/admin/manage_songs.html', {
            'page_obj': page_obj
        })
        
    except Exception as e:
        logger.error(f"Error in manage_songs view: {type(e).__name__}: {str(e)}")
        messages.error(request, "Unable to load songs management page.")
        return render(request, 'pages/admin/manage_songs.html', {
            'page_obj': None
        })


@staff_member_required
@ensure_csrf_cookie
def edit_song(request, song_id):
    """Edit existing song"""
    song = get_object_or_404(Song, id=song_id)
    
    if request.method == 'POST':
        # Sanitize and validate inputs
        title = sanitize_input(request.POST.get('title', ''))
        original_song = sanitize_input(request.POST.get('original_song', ''))
        audio_url = request.POST.get('audio_url', '').strip()
        background_image_url = request.POST.get('background_image_url', '').strip()
        
        # Security validation
        if not validate_url(audio_url):
            messages.error(request, "Invalid or unauthorized audio URL domain.")
            return render(request, 'pages/admin/edit_song.html', {'song': song})
            
        if not validate_url(background_image_url):
            messages.error(request, "Invalid or unauthorized image URL domain.")
            return render(request, 'pages/admin/edit_song.html', {'song': song})
        
        if title and audio_url:
            # Check for duplicates only if title or original_song changed
            if song.title != title or song.original_song != original_song:
                is_duplicate, existing_song = check_duplicate_song(title, original_song)
                if is_duplicate and existing_song.id != song.id:
                    if original_song:
                        messages.error(request, f"Song '{title}' (Original: {original_song}) already exists in the database.")
                    else:
                        messages.error(request, f"Song '{title}' already exists in the database.")
                    return render(request, 'pages/admin/edit_song.html', {'song': song})
            
            # Convert Google Drive URLs to proper format
            audio_url = convert_google_drive_url(audio_url, 'audio')
            background_image_url = convert_google_drive_url(background_image_url, 'image')
            
            song.title = title
            song.original_song = original_song
            song.audio_url = audio_url
            song.background_image_url = background_image_url
            song.save()
            
            # Clear relevant caches after updating song
            clear_song_caches()
            
            messages.success(request, f"Song '{title}' updated successfully!")
            return redirect('manage_songs')
        else:
            messages.error(request, "Title and audio URL are required.")
    
    return render(request, 'pages/admin/edit_song.html', {'song': song})


@staff_member_required
@require_POST
def delete_song(request, song_id):
    """Delete existing song"""
    try:
        song = get_object_or_404(Song, id=song_id)
        title = song.title
        song.delete()
        
        # Clear relevant caches
        clear_song_caches()
        
        logger.info(f"Song '{title}' deleted by {request.user.username}")
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({
                'success': True,
                'message': f"Song '{title}' deleted successfully!"
            })
        else:
            messages.success(request, f"Song '{title}' deleted successfully!")
            return redirect('manage_songs')
            
    except Exception as e:
        logger.error(f"Error deleting song {song_id}: {e}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({
                'success': False,
                'error': f"Error deleting song: {str(e)}"
            })
        else:
            messages.error(request, f"Error deleting song: {str(e)}")
            return redirect('manage_songs')


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
        from django.db import transaction
        
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
    sessions = VotingSession.objects.filter(status='COMPLETED').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(sessions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'pages/admin/tournament_history.html', {
        'page_obj': page_obj
    })


@staff_member_required
@ensure_csrf_cookie
def user_manage(request):
    """User management interface"""
    from .models import UserProfile
    profiles = UserProfile.objects.select_related('user').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(profiles, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'pages/admin/user_manage.html', {
        'page_obj': page_obj
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
        from django.db import transaction
        
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


@staff_member_required
@ensure_csrf_cookie
def upload_csv(request):
    """Bulk upload songs from CSV file"""
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            messages.error(request, "Please select a CSV file to upload.")
            return render(request, 'pages/admin/upload_csv.html')
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "File must be a CSV file.")
            return render(request, 'pages/admin/upload_csv.html')
        
        try:
            # Read CSV file with robust parsing for Google Sheets exports
            file_data = csv_file.read().decode('utf-8')
            csv_data = io.StringIO(file_data)
            
            # Try to detect the CSV format
            sample = file_data[:1024]
            sniffer = csv.Sniffer()
            
            try:
                # Try to detect the dialect
                dialect = sniffer.sniff(sample, delimiters=',')
                csv_data.seek(0)
                reader = csv.DictReader(csv_data, dialect=dialect)
            except csv.Error:
                # If dialect detection fails, use a flexible approach
                csv_data.seek(0)
                # Use QUOTE_MINIMAL which handles unquoted fields better
                reader = csv.DictReader(csv_data, 
                                      quoting=csv.QUOTE_MINIMAL,
                                      skipinitialspace=True)
            
            # Validate required columns
            required_columns = ['title', 'audio_url']
            fieldnames = reader.fieldnames or []
            
            # Log detected fieldnames for debugging
            logger.info(f"CSV upload - Detected columns: {fieldnames}")
            
            if not all(col in fieldnames for col in required_columns):
                missing_cols = [col for col in required_columns if col not in fieldnames]
                available_cols = ', '.join(fieldnames) if fieldnames else 'None detected'
                messages.error(request, 
                              f"CSV must contain columns: {', '.join(required_columns)}. "
                              f"Missing: {', '.join(missing_cols)}. "
                              f"Available columns: {available_cols}. "
                              f"Optional: original_song, background_image_url")
                return render(request, 'pages/admin/upload_csv.html')
            
            # Process rows
            created_count = 0
            error_count = 0
            errors = []
            processed_songs = set()  # Track songs in this CSV to prevent within-file duplicates
            
            with transaction.atomic():
                for row_num, row in enumerate(reader, start=2):  # Start at 2 since row 1 is headers
                    title = row.get('title', '').strip()
                    original_song = row.get('original_song', '').strip()
                    audio_url = row.get('audio_url', '').strip()
                    background_image_url = row.get('background_image_url', '').strip()
                    
                    # Validate required fields
                    if not title:
                        errors.append(f"Row {row_num}: Missing title")
                        error_count += 1
                        continue
                    
                    if not audio_url:
                        errors.append(f"Row {row_num}: Missing audio_url")
                        error_count += 1
                        continue
                    
                    try:
                        # Create a key for tracking duplicates within this CSV
                        song_key = (title.lower(), original_song.lower())
                        
                        # Check for duplicates within this CSV file
                        if song_key in processed_songs:
                            if original_song:
                                errors.append(f"Row {row_num}: '{title}' (Original: {original_song}) - Duplicate within this CSV file")
                            else:
                                errors.append(f"Row {row_num}: '{title}' - Duplicate within this CSV file")
                            error_count += 1
                            continue
                        
                        # Check for duplicates in existing database
                        is_duplicate, existing_song = check_duplicate_song(title, original_song)
                        if is_duplicate:
                            if original_song:
                                errors.append(f"Row {row_num}: '{title}' (Original: {original_song}) - Song already exists in database")
                            else:
                                errors.append(f"Row {row_num}: '{title}' - Song already exists in database")
                            error_count += 1
                            continue
                        
                        # Convert Google Drive URLs to proper format
                        audio_url = convert_google_drive_url(audio_url, 'audio')
                        background_image_url = convert_google_drive_url(background_image_url, 'image')
                        
                        # Create song
                        song = Song.objects.create(
                            title=title,
                            original_song=original_song,
                            audio_url=audio_url,
                            background_image_url=background_image_url
                        )
                        
                        # Mark this song as processed to prevent duplicates within this CSV
                        processed_songs.add(song_key)
                        created_count += 1
                        
                    except IntegrityError as e:
                        errors.append(f"Row {row_num}: {title} - Database error (possibly duplicate)")
                        error_count += 1
                    except Exception as e:
                        errors.append(f"Row {row_num}: {title} - {str(e)}")
                        error_count += 1
            
            # Clear relevant caches if songs were added
            if created_count > 0:
                clear_song_caches()
            
            # Show results
            if created_count > 0:
                messages.success(request, f"Successfully uploaded {created_count} songs.")
            
            if error_count > 0:
                # Categorize errors for better reporting
                duplicate_errors = [e for e in errors if 'Duplicate' in e or 'already exists' in e]
                other_errors = [e for e in errors if e not in duplicate_errors]
                
                if duplicate_errors:
                    dup_count = len(duplicate_errors)
                    dup_msg = f"Skipped {dup_count} duplicate song(s)."
                    if dup_count <= 5:
                        dup_msg += " " + "; ".join(duplicate_errors)
                    else:
                        dup_msg += f" First 5: " + "; ".join(duplicate_errors[:5])
                    messages.warning(request, dup_msg)
                
                if other_errors:
                    error_msg = f"Failed to upload {len(other_errors)} song(s) due to errors."
                    if len(other_errors) <= 5:
                        error_msg += " Errors: " + "; ".join(other_errors)
                    else:
                        error_msg += f" First 5 errors: " + "; ".join(other_errors[:5])
                    messages.error(request, error_msg)
            
            if created_count > 0:
                return redirect('manage_songs')
                
        except UnicodeDecodeError as e:
            logger.error(f"CSV file encoding error: {e}")
            messages.error(request, "Error reading CSV file. Please ensure the file is saved as UTF-8 encoding.")
        except csv.Error as e:
            logger.error(f"CSV parsing error: {e}")
            messages.error(request, f"Error parsing CSV file: {str(e)}. Please check the file format and ensure proper CSV structure.")
        except Exception as e:
            logger.error(f"Error processing CSV upload: {e}")
            messages.error(request, f"Error processing CSV file: {str(e)}")
    
    return render(request, 'pages/admin/upload_csv.html')