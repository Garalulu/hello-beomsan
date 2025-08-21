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
from .models import Song, VotingSession, Match, Vote
from .services import VotingSessionService
import json
import logging
import csv
import io

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
            original_song = request.POST.get('original_song', '').strip()
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
                            original_song=original_song,
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


@staff_member_required
@ensure_csrf_cookie
def edit_song(request, song_id):
    """Edit existing song"""
    song = get_object_or_404(Song, id=song_id)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        original_song = request.POST.get('original_song', '').strip()
        audio_url = request.POST.get('audio_url', '').strip()
        background_image_url = request.POST.get('background_image_url', '').strip()
        
        if title and audio_url:
            song.title = title
            song.original_song = original_song
            song.audio_url = audio_url
            song.background_image_url = background_image_url
            song.save()
            
            messages.success(request, f"Song '{title}' updated successfully!")
            return redirect('manage_songs')
        else:
            messages.error(request, "Title and audio URL are required.")
    
    return render(request, 'admin/edit_song.html', {'song': song})


@staff_member_required
@require_POST
def delete_song(request, song_id):
    """Delete existing song"""
    song = get_object_or_404(Song, id=song_id)
    title = song.title
    song.delete()
    
    messages.success(request, f"Song '{title}' deleted successfully!")
    logger.info(f"Song '{title}' deleted by {request.user.username}")
    return redirect('manage_songs')


@staff_member_required
@ensure_csrf_cookie
def tournament_manage(request):
    """Tournament management overview"""
    active_sessions = VotingSession.objects.filter(status='ACTIVE').order_by('-updated_at')
    completed_sessions = VotingSession.objects.filter(status='COMPLETED').order_by('-updated_at')[:10]  # Latest 10
    abandoned_sessions = VotingSession.objects.filter(status='ABANDONED').count()
    total_songs = Song.objects.count()
    
    return render(request, 'admin/tournament_manage.html', {
        'active_sessions': active_sessions,
        'completed_sessions': completed_sessions,
        'total_songs': total_songs,
        'stats': {
            'total_active': active_sessions.count(),
            'total_completed': VotingSession.objects.filter(status='COMPLETED').count(),
            'total_abandoned': abandoned_sessions,
        }
    })


@staff_member_required
@ensure_csrf_cookie
def tournament_history(request):
    """Tournament history with filtering"""
    sessions = VotingSession.objects.filter(status='COMPLETED').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(sessions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin/tournament_history.html', {
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
    
    return render(request, 'admin/user_manage.html', {
        'page_obj': page_obj
    })


@staff_member_required
@ensure_csrf_cookie
def session_detail(request, session_id):
    """Detailed view of a voting session"""
    session = get_object_or_404(VotingSession, id=session_id)
    matches = Match.objects.filter(session=session).order_by('round_number', 'match_number')
    
    return render(request, 'admin/session_detail.html', {
        'session': session,
        'matches': matches
    })


@staff_member_required
@ensure_csrf_cookie
def upload_csv(request):
    """Bulk upload songs from CSV file"""
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            messages.error(request, "Please select a CSV file to upload.")
            return render(request, 'admin/upload_csv.html')
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "File must be a CSV file.")
            return render(request, 'admin/upload_csv.html')
        
        try:
            # Read CSV file
            file_data = csv_file.read().decode('utf-8')
            csv_data = io.StringIO(file_data)
            reader = csv.DictReader(csv_data)
            
            # Validate required columns
            required_columns = ['title', 'audio_url']
            if not all(col in reader.fieldnames for col in required_columns):
                messages.error(request, f"CSV must contain columns: {', '.join(required_columns)}. Optional: original_song, background_image_url")
                return render(request, 'admin/upload_csv.html')
            
            # Process rows
            created_count = 0
            error_count = 0
            errors = []
            
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
                        # Create song
                        song = Song.objects.create(
                            title=title,
                            original_song=original_song,
                            audio_url=audio_url,
                            background_image_url=background_image_url
                        )
                        created_count += 1
                        
                    except IntegrityError as e:
                        errors.append(f"Row {row_num}: {title} - Database error (possibly duplicate)")
                        error_count += 1
                    except Exception as e:
                        errors.append(f"Row {row_num}: {title} - {str(e)}")
                        error_count += 1
            
            # Show results
            if created_count > 0:
                messages.success(request, f"Successfully uploaded {created_count} songs.")
            
            if error_count > 0:
                error_msg = f"Failed to upload {error_count} songs."
                if len(errors) <= 10:
                    error_msg += " Errors: " + "; ".join(errors)
                else:
                    error_msg += f" First 10 errors: " + "; ".join(errors[:10])
                messages.error(request, error_msg)
            
            if created_count > 0:
                return redirect('manage_songs')
                
        except Exception as e:
            logger.error(f"Error processing CSV upload: {e}")
            messages.error(request, f"Error processing CSV file: {str(e)}")
    
    return render(request, 'admin/upload_csv.html')