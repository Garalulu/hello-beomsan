import requests
import secrets
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import login
from tournament.models import UserProfile


class OsuOAuthService:
    """Service for handling osu! OAuth 2.0 authentication"""
    
    OSU_AUTH_URL = "https://osu.ppy.sh/oauth/authorize"
    OSU_TOKEN_URL = "https://osu.ppy.sh/oauth/token"
    OSU_API_URL = "https://osu.ppy.sh/api/v2"
    
    @classmethod
    def get_authorization_url(cls, state=None):
        """Generate osu! OAuth authorization URL"""
        if state is None:
            state = secrets.token_urlsafe(32)
        
        params = {
            'client_id': settings.OSU_CLIENT_ID,
            'redirect_uri': settings.OSU_REDIRECT_URI,
            'response_type': 'code',
            'scope': 'identify',
            'state': state
        }
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{cls.OSU_AUTH_URL}?{query_string}", state
    
    @classmethod
    def exchange_code_for_token(cls, code):
        """Exchange authorization code for access token"""
        data = {
            'client_id': settings.OSU_CLIENT_ID,
            'client_secret': settings.OSU_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': settings.OSU_REDIRECT_URI
        }
        
        response = requests.post(cls.OSU_TOKEN_URL, data=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Token exchange failed: {response.text}")
    
    @classmethod
    def get_user_info(cls, access_token):
        """Get user information from osu! API"""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(f"{cls.OSU_API_URL}/me", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"User info request failed: {response.text}")
    
    @classmethod
    def create_or_update_user(cls, osu_user_data):
        """Create or update Django user from osu! user data"""
        osu_user_id = osu_user_data['id']
        osu_username = osu_user_data['username']
        avatar_url = osu_user_data.get('avatar_url', '')
        
        # Try to find existing user profile
        try:
            profile = UserProfile.objects.get(osu_user_id=osu_user_id)
            user = profile.user
            
            # Update profile data
            profile.osu_username = osu_username
            profile.avatar_url = avatar_url
            profile.save()
            
            # Update user data if needed
            if user.username != osu_username:
                user.username = osu_username
                user.save()
                
        except UserProfile.DoesNotExist:
            # Create new user and profile
            # Handle username conflicts
            username = osu_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{osu_username}_{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=f"{osu_user_id}@osu.local"  # Placeholder email
            )
            
            profile = UserProfile.objects.create(
                user=user,
                osu_user_id=osu_user_id,
                osu_username=osu_username,
                avatar_url=avatar_url
            )
        
        return user, profile
    
    @classmethod
    def authenticate_user(cls, request, code, state):
        """Complete OAuth flow and authenticate user"""
        # Exchange code for token
        token_data = cls.exchange_code_for_token(code)
        access_token = token_data['access_token']
        
        # Get user info
        osu_user_data = cls.get_user_info(access_token)
        
        # Create or update user
        user, profile = cls.create_or_update_user(osu_user_data)
        
        # Log user in
        login(request, user)
        
        return user, profile