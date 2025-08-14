from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseBadRequest
from .services import OsuOAuthService


def login_view(request):
    """Initiate osu! OAuth login"""
    if request.user.is_authenticated:
        return redirect('home')
    
    auth_url, state = OsuOAuthService.get_authorization_url()
    
    # Store state in session for security
    request.session['oauth_state'] = state
    
    return redirect(auth_url)


def oauth_callback(request):
    """Handle osu! OAuth callback"""
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f"OAuth error: {error}")
        return redirect('home')
    
    if not code or not state:
        return HttpResponseBadRequest("Missing code or state parameter")
    
    # Verify state to prevent CSRF attacks
    stored_state = request.session.get('oauth_state')
    if not stored_state or stored_state != state:
        return HttpResponseBadRequest("Invalid state parameter")
    
    # Clear state from session
    del request.session['oauth_state']
    
    try:
        user, profile = OsuOAuthService.authenticate_user(request, code, state)
        messages.success(request, f"Welcome, {profile.osu_username}!")
        return redirect('home')
        
    except Exception as e:
        messages.error(request, f"Authentication failed: {str(e)}")
        return redirect('home')


def logout_view(request):
    """Log out user"""
    if request.method == 'POST':
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect('home')
    else:
        # For GET requests, show a logout confirmation page or redirect
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect('home')


def profile_view(request):
    """Display user profile"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        profile = request.user.profile
    except:
        messages.error(request, "Profile not found.")
        return redirect('home')
    
    # Get user's voting statistics
    from tournament.models import Vote
    user_votes = Vote.objects.filter(user=request.user)
    vote_count = user_votes.count()
    
    # Get tournaments user participated in
    participated_tournaments = set()
    for vote in user_votes:
        participated_tournaments.add(vote.match.tournament)
    
    context = {
        'profile': profile,
        'vote_count': vote_count,
        'tournaments_participated': len(participated_tournaments)
    }
    
    return render(request, 'accounts/profile.html', context)
