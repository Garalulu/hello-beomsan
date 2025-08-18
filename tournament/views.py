from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from .models import Song, VotingSession, Match, Vote
from .services import VotingSessionService
import json


@ensure_csrf_cookie
def home(request):
    """Main page with login/start game buttons"""
    # Check if user has an active session
    active_session = None
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
    
    # Get some statistics
    total_songs = Song.objects.count()
    total_votes = Vote.objects.count()
    
    return render(request, 'main/home.html', {
        'active_session': active_session,
        'total_songs': total_songs,
        'total_votes': total_votes
    })


@ensure_csrf_cookie
def start_game(request):
    """Start new voting session or ask about continuing existing one"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'continue' and request.user.is_authenticated:
            # Continue existing session
            session = VotingSession.objects.filter(
                user=request.user,
                status='ACTIVE'
            ).first()
            if session:
                return redirect('vote')
        
        # Start new session (abandon existing if any)
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
        
        return redirect('vote')
    
    # Check for existing session
    existing_session = None
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
    
    return render(request, 'main/start_game.html', {
        'existing_session': existing_session
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
    
    if sort_by == 'pick_rate':
        songs = Song.objects.filter(total_picks__gt=0).order_by('-total_picks')
        # Calculate pick rate and sort in Python
        songs_list = list(songs)
        songs_list.sort(key=lambda s: s.pick_rate, reverse=True)
    elif sort_by == 'tournaments':
        songs = Song.objects.order_by('-tournament_wins')
        songs_list = list(songs)
    else:  # win_rate
        songs = Song.objects.filter(total_picks__gt=0).order_by('-tournament_wins')
        # Calculate win rate and sort in Python for now
        songs_list = list(songs)
        songs_list.sort(key=lambda s: s.win_rate, reverse=True)
    
    # Convert back to queryset-like structure for pagination
    from django.core.paginator import Paginator
    paginator = Paginator(songs_list, 20)
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
    song = get_object_or_404(Song, id=song_id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        artist = request.POST.get('artist', '')
        audio_url = request.POST.get('audio_url')
        background_image_url = request.POST.get('background_image_url', '')
        
        if not title or not audio_url:
            messages.error(request, "Title and audio URL are required.")
        else:
            try:
                song.title = title
                song.artist = artist
                song.audio_url = audio_url
                song.background_image_url = background_image_url
                song.save()
                
                messages.success(request, f"Song '{title}' updated successfully!")
                return redirect('manage_songs')
                
            except Exception as e:
                messages.error(request, f"Error updating song: {str(e)}")
    
    return render(request, 'admin/edit_song.html', {'song': song})


@staff_member_required
@require_POST
@ensure_csrf_cookie
def delete_song(request, song_id):
    """Delete song"""
    song = get_object_or_404(Song, id=song_id)
    
    try:
        song_title = song.title
        song.delete()
        
        return JsonResponse({
            'success': True,
            'message': f"Song '{song_title}' deleted successfully"
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@staff_member_required
@ensure_csrf_cookie
def tournament_manage(request):
    """Tournament management dashboard"""
    # Get active sessions
    active_sessions = VotingSession.objects.filter(status='ACTIVE').select_related('user').order_by('-updated_at')
    
    # Get recent completed sessions
    completed_sessions = VotingSession.objects.filter(status='COMPLETED').select_related('user').order_by('-updated_at')[:20]
    
    # Calculate statistics
    total_active = active_sessions.count()
    total_completed = VotingSession.objects.filter(status='COMPLETED').count()
    total_abandoned = VotingSession.objects.filter(status='ABANDONED').count()
    
    return render(request, 'admin/tournament_manage.html', {
        'active_sessions': active_sessions,
        'completed_sessions': completed_sessions,
        'stats': {
            'total_active': total_active,
            'total_completed': total_completed,
            'total_abandoned': total_abandoned,
        }
    })


@staff_member_required
@ensure_csrf_cookie
def tournament_history(request):
    """Tournament history with filtering"""
    sessions = VotingSession.objects.filter(status='COMPLETED').select_related('user').order_by('-updated_at')
    
    # Filter by user if specified
    user_filter = request.GET.get('user')
    if user_filter:
        sessions = sessions.filter(user__username__icontains=user_filter)
    
    # Pagination
    paginator = Paginator(sessions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin/tournament_history.html', {
        'page_obj': page_obj,
        'user_filter': user_filter or ''
    })


@staff_member_required
@ensure_csrf_cookie
def user_manage(request):
    """User management with statistics"""
    from django.db.models import Count, Q
    from accounts.models import UserProfile
    
    # Get users with their statistics
    users = User.objects.select_related('profile').annotate(
        total_sessions=Count('voting_sessions'),
        completed_sessions=Count('voting_sessions', filter=Q(voting_sessions__status='COMPLETED')),
        active_sessions=Count('voting_sessions', filter=Q(voting_sessions__status='ACTIVE'))
    ).order_by('-total_sessions')
    
    # Filter by username if specified
    username_filter = request.GET.get('username')
    if username_filter:
        users = users.filter(username__icontains=username_filter)
    
    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin/user_manage.html', {
        'page_obj': page_obj,
        'username_filter': username_filter or ''
    })


@staff_member_required
def session_detail(request, session_id):
    """View detailed session information"""
    session = get_object_or_404(VotingSession, id=session_id)
    
    # Get all matches for this session
    matches = Match.objects.filter(session=session).select_related('song1', 'song2', 'winner').order_by('round_number', 'match_number')
    
    # Get session winner if completed
    winner_song = None
    if session.status == 'COMPLETED':
        # Find the winner from the final match
        final_match = matches.filter(round_number=session.current_round).first()
        if final_match:
            winner_song = final_match.winner
    
    return render(request, 'admin/session_detail.html', {
        'session': session,
        'matches': matches,
        'winner_song': winner_song
    })