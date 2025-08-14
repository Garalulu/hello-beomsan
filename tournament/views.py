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
    # Get or create voting session
    if request.user.is_authenticated:
        session, existing = VotingSessionService.get_or_create_session(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
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
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def song_stats(request):
    """Display song statistics"""
    # Get sorting parameter
    sort_by = request.GET.get('sort', 'win_rate')
    
    if sort_by == 'pick_rate':
        songs = Song.objects.filter(total_picks__gt=0).order_by('-total_picks')
    elif sort_by == 'wins':
        songs = Song.objects.filter(total_wins__gt=0).order_by('-total_wins')
    else:  # win_rate
        songs = Song.objects.filter(total_picks__gt=0).order_by('-total_wins')
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