from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseBadRequest
from .services import OsuOAuthService
import logging

logger = logging.getLogger(__name__)


def login_view(request):
    """Initiate osu! OAuth login"""
    try:
        if request.user.is_authenticated:
            return redirect('home')
        
        try:
            auth_url, state = OsuOAuthService.get_authorization_url()
        except Exception as e:
            logger.error(f"Error getting OAuth authorization URL: {e}")
            messages.error(request, "Unable to initiate login. Please try again later.")
            return redirect('home')
        
        if not auth_url or not state:
            logger.error("OAuth service returned invalid auth_url or state")
            messages.error(request, "Login service is currently unavailable.")
            return redirect('home')
        
        # Store state in session for security
        try:
            request.session['oauth_state'] = state
        except Exception as e:
            logger.error(f"Error storing OAuth state in session: {e}")
            messages.error(request, "Unable to initiate secure login.")
            return redirect('home')
        
        return redirect(auth_url)
        
    except Exception as e:
        logger.error(f"Unexpected error in login_view: {type(e).__name__}: {str(e)}")
        messages.error(request, "An error occurred during login. Please try again.")
        return redirect('home')


def oauth_callback(request):
    """Handle osu! OAuth callback"""
    try:
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        error_description = request.GET.get('error_description', '')
        
        # Handle OAuth errors
        if error:
            error_msg = f"OAuth error: {error}"
            if error_description:
                error_msg += f" - {error_description}"
            logger.warning(f"OAuth error received: {error} - {error_description}")
            messages.error(request, error_msg)
            return redirect('home')
        
        # Validate required parameters
        if not code:
            logger.error("OAuth callback missing authorization code")
            messages.error(request, "Invalid login response. Please try again.")
            return redirect('home')
        
        if not state:
            logger.error("OAuth callback missing state parameter")
            messages.error(request, "Invalid login response. Please try again.")
            return redirect('home')
        
        # Verify state to prevent CSRF attacks
        try:
            stored_state = request.session.get('oauth_state')
        except Exception as e:
            logger.error(f"Error accessing session for OAuth state: {e}")
            messages.error(request, "Session error during login. Please try again.")
            return redirect('home')
        
        if not stored_state:
            logger.error("No OAuth state found in session")
            messages.error(request, "Login session expired. Please try again.")
            return redirect('home')
        
        if stored_state != state:
            logger.error(f"OAuth state mismatch: expected {stored_state}, got {state}")
            messages.error(request, "Invalid login session. Please try again.")
            return redirect('home')
        
        # Clear state from session
        try:
            del request.session['oauth_state']
        except Exception as e:
            logger.warning(f"Error clearing OAuth state from session: {e}")
            # Continue anyway
        
        # Authenticate user
        try:
            user, profile = OsuOAuthService.authenticate_user(request, code, state)
            if user and profile:
                logger.info(f"User {user.username} logged in successfully via osu! OAuth")
                messages.success(request, f"Welcome, {profile.osu_username}!")
                return redirect('home')
            else:
                logger.error("OAuth service returned None for user or profile")
                messages.error(request, "Authentication failed. Please try again.")
                return redirect('home')
                
        except Exception as e:
            logger.error(f"Error during user authentication: {type(e).__name__}: {str(e)}")
            messages.error(request, "Authentication failed. Please try again later.")
            return redirect('home')
            
    except Exception as e:
        logger.error(f"Unexpected error in oauth_callback: {type(e).__name__}: {str(e)}")
        messages.error(request, "An error occurred during login. Please try again.")
        return redirect('home')


def logout_view(request):
    """Log out user"""
    try:
        if request.user.is_authenticated:
            username = request.user.username
            try:
                logout(request)
                logger.info(f"User {username} logged out successfully")
                messages.success(request, "You have been logged out.")
            except Exception as e:
                logger.error(f"Error during logout for user {username}: {e}")
                messages.error(request, "An error occurred during logout.")
        else:
            messages.info(request, "You are not currently logged in.")
        
        return redirect('home')
        
    except Exception as e:
        logger.error(f"Unexpected error in logout_view: {type(e).__name__}: {str(e)}")
        messages.error(request, "An error occurred. Please try again.")
        return redirect('home')


def profile_view(request):
    """Display user profile"""
    try:
        if not request.user.is_authenticated:
            messages.info(request, "Please log in to view your profile.")
            return redirect('accounts:login')
        
        # Get user profile
        try:
            profile = request.user.profile
        except Exception as e:
            logger.error(f"Error getting profile for user {request.user.username}: {e}")
            messages.error(request, "Profile not found. Please contact support.")
            return redirect('home')
        
        # Get user's voting statistics safely
        try:
            from tournament.models import VotingSession, Vote
            
            # Get user's voting sessions
            user_sessions = VotingSession.objects.filter(user=request.user)
            total_sessions = user_sessions.count()
            completed_sessions = user_sessions.filter(status='COMPLETED').count()
            
            # Get user's votes
            user_votes = Vote.objects.filter(session__user=request.user)
            vote_count = user_votes.count()
            
        except Exception as e:
            logger.warning(f"Error getting voting statistics for user {request.user.username}: {e}")
            total_sessions = 0
            completed_sessions = 0
            vote_count = 0
        
        context = {
            'profile': profile,
            'vote_count': vote_count,
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions
        }
        
        return render(request, 'accounts/profile.html', context)
        
    except Exception as e:
        logger.error(f"Unexpected error in profile_view: {type(e).__name__}: {str(e)}")
        messages.error(request, "An error occurred while loading your profile.")
        return redirect('home')
