import requests
import secrets
import logging
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.db import transaction, IntegrityError
from apps.tournament.models import UserProfile

logger = logging.getLogger(__name__)


class OsuOAuthService:
    """Service for handling osu! OAuth 2.0 authentication"""
    
    OSU_AUTH_URL = "https://osu.ppy.sh/oauth/authorize"
    OSU_TOKEN_URL = "https://osu.ppy.sh/oauth/token"
    OSU_API_URL = "https://osu.ppy.sh/api/v2"
    
    @classmethod
    def get_authorization_url(cls, state=None):
        """Generate osu! OAuth authorization URL"""
        try:
            # Validate required settings
            if not hasattr(settings, 'OSU_CLIENT_ID') or not settings.OSU_CLIENT_ID:
                logger.error("OSU_CLIENT_ID not configured")
                raise ValueError("OAuth client ID not configured")
            
            if not hasattr(settings, 'OSU_REDIRECT_URI') or not settings.OSU_REDIRECT_URI:
                logger.error("OSU_REDIRECT_URI not configured")
                raise ValueError("OAuth redirect URI not configured")
            
            if state is None:
                try:
                    state = secrets.token_urlsafe(32)
                except Exception as e:
                    logger.error(f"Error generating OAuth state: {e}")
                    raise ValueError("Failed to generate secure state token")
            
            params = {
                'client_id': settings.OSU_CLIENT_ID,
                'redirect_uri': settings.OSU_REDIRECT_URI,
                'response_type': 'code',
                'scope': 'identify',
                'state': state
            }
            
            try:
                query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
                auth_url = f"{cls.OSU_AUTH_URL}?{query_string}"
                logger.info("Generated OAuth authorization URL successfully")
                return auth_url, state
            except Exception as e:
                logger.error(f"Error building authorization URL: {e}")
                raise ValueError("Failed to build authorization URL")
                
        except Exception as e:
            logger.error(f"Error in get_authorization_url: {type(e).__name__}: {str(e)}")
            raise
    
    @classmethod
    def exchange_code_for_token(cls, code):
        """Exchange authorization code for access token"""
        try:
            if not code:
                raise ValueError("Authorization code is required")
            
            # Validate required settings
            if not hasattr(settings, 'OSU_CLIENT_SECRET') or not settings.OSU_CLIENT_SECRET:
                logger.error("OSU_CLIENT_SECRET not configured")
                raise ValueError("OAuth client secret not configured")
            
            data = {
                'client_id': settings.OSU_CLIENT_ID,
                'client_secret': settings.OSU_CLIENT_SECRET,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': settings.OSU_REDIRECT_URI
            }
            
            try:
                response = requests.post(cls.OSU_TOKEN_URL, data=data, timeout=30)
            except requests.exceptions.Timeout:
                logger.error("Token exchange request timed out")
                raise Exception("Authentication service is slow. Please try again.")
            except requests.exceptions.ConnectionError:
                logger.error("Connection error during token exchange")
                raise Exception("Unable to connect to authentication service.")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error during token exchange: {e}")
                raise Exception("Authentication service error.")
            
            if response.status_code == 200:
                try:
                    token_data = response.json()
                    if 'access_token' not in token_data:
                        logger.error("Token response missing access_token")
                        raise Exception("Invalid token response from authentication service")
                    logger.info("Token exchange successful")
                    return token_data
                except ValueError as e:
                    logger.error(f"Invalid JSON in token response: {e}")
                    raise Exception("Invalid response from authentication service")
            else:
                logger.error(f"Token exchange failed with status {response.status_code}: {response.text}")
                if response.status_code == 400:
                    raise Exception("Invalid authorization code")
                elif response.status_code == 401:
                    raise Exception("Authentication configuration error")
                else:
                    raise Exception(f"Authentication service error (status {response.status_code})")
                    
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.error(f"Error in exchange_code_for_token: {type(e).__name__}: {str(e)}")
            raise
    
    @classmethod
    def get_user_info(cls, access_token):
        """Get user information from osu! API"""
        try:
            if not access_token:
                raise ValueError("Access token is required")
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            try:
                response = requests.get(f"{cls.OSU_API_URL}/me", headers=headers, timeout=30)
            except requests.exceptions.Timeout:
                logger.error("User info request timed out")
                raise Exception("User information service is slow. Please try again.")
            except requests.exceptions.ConnectionError:
                logger.error("Connection error during user info request")
                raise Exception("Unable to connect to user information service.")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error during user info request: {e}")
                raise Exception("User information service error.")
            
            if response.status_code == 200:
                try:
                    user_data = response.json()
                    # Validate required fields
                    required_fields = ['id', 'username']
                    for field in required_fields:
                        if field not in user_data:
                            logger.error(f"User data missing required field: {field}")
                            raise Exception("Invalid user data received")
                    logger.info(f"Retrieved user info for osu! user {user_data['username']}")
                    return user_data
                except ValueError as e:
                    logger.error(f"Invalid JSON in user info response: {e}")
                    raise Exception("Invalid response from user information service")
            elif response.status_code == 401:
                logger.error("User info request failed: invalid token")
                raise Exception("Authentication token expired or invalid")
            else:
                logger.error(f"User info request failed with status {response.status_code}: {response.text}")
                raise Exception(f"User information service error (status {response.status_code})")
                
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.error(f"Error in get_user_info: {type(e).__name__}: {str(e)}")
            raise
    
    @classmethod
    def create_or_update_user(cls, osu_user_data):
        """Create or update Django user from osu! user data"""
        try:
            if not osu_user_data:
                raise ValueError("User data is required")
            
            osu_user_id = osu_user_data.get('id')
            osu_username = osu_user_data.get('username')
            avatar_url = osu_user_data.get('avatar_url', '')
            
            if not osu_user_id or not osu_username:
                logger.error(f"Invalid user data: missing id or username")
                raise ValueError("Invalid user data: missing required fields")
            
            # Convert osu_user_id to int if it's a string
            try:
                osu_user_id = int(osu_user_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid osu_user_id format: {osu_user_id}")
                raise ValueError("Invalid user ID format")
            
            # Sanitize username
            if len(osu_username) > 150:  # Django username max length
                osu_username = osu_username[:150]
                logger.warning(f"Truncated long username to {osu_username}")
            
            with transaction.atomic():
                # Try to find existing user profile
                try:
                    profile = UserProfile.objects.get(osu_user_id=osu_user_id)
                    user = profile.user
                    
                    # Update profile data
                    try:
                        profile.osu_username = osu_username
                        profile.avatar_url = avatar_url
                        profile.save()
                        
                        # Update user data if needed
                        if user.username != osu_username:
                            # Check if new username is available
                            if User.objects.filter(username=osu_username).exclude(id=user.id).exists():
                                logger.warning(f"Username {osu_username} already taken, keeping existing username {user.username}")
                            else:
                                user.username = osu_username
                                user.save()
                        
                        logger.info(f"Updated existing user profile for osu! user {osu_username}")
                        
                    except Exception as e:
                        logger.error(f"Error updating existing user profile: {e}")
                        raise Exception("Failed to update user profile")
                        
                except UserProfile.DoesNotExist:
                    # Create new user and profile
                    try:
                        # Handle username conflicts
                        username = osu_username
                        counter = 1
                        max_attempts = 100  # Prevent infinite loop
                        
                        while User.objects.filter(username=username).exists() and counter <= max_attempts:
                            username = f"{osu_username}_{counter}"
                            counter += 1
                        
                        if counter > max_attempts:
                            logger.error(f"Could not find available username after {max_attempts} attempts")
                            raise Exception("Unable to create unique username")
                        
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
                        
                        logger.info(f"Created new user profile for osu! user {osu_username}")
                        
                    except IntegrityError as e:
                        logger.error(f"Database integrity error creating user: {e}")
                        raise Exception("Failed to create user account")
                    except Exception as e:
                        logger.error(f"Error creating new user profile: {e}")
                        raise Exception("Failed to create user profile")
            
            return user, profile
            
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.error(f"Error in create_or_update_user: {type(e).__name__}: {str(e)}")
            raise
    
    @classmethod
    def authenticate_user(cls, request, code, state):
        """Complete OAuth flow and authenticate user"""
        try:
            if not request:
                raise ValueError("Request object is required")
            
            if not code:
                raise ValueError("Authorization code is required")
            
            # Exchange code for token
            try:
                token_data = cls.exchange_code_for_token(code)
                access_token = token_data.get('access_token')
                
                if not access_token:
                    logger.error("No access token in token response")
                    raise Exception("Failed to obtain access token")
                    
            except Exception as e:
                logger.error(f"Token exchange failed: {e}")
                raise Exception(f"Authentication failed: {str(e)}")
            
            # Get user info
            try:
                osu_user_data = cls.get_user_info(access_token)
            except Exception as e:
                logger.error(f"Failed to get user info: {e}")
                raise Exception(f"Failed to retrieve user information: {str(e)}")
            
            # Create or update user
            try:
                user, profile = cls.create_or_update_user(osu_user_data)
                
                if not user or not profile:
                    logger.error("User creation/update returned None")
                    raise Exception("Failed to create or update user account")
                    
            except Exception as e:
                logger.error(f"Failed to create/update user: {e}")
                raise Exception(f"Failed to create user account: {str(e)}")
            
            # Log user in
            try:
                login(request, user)
                logger.info(f"User {user.username} logged in successfully")
            except Exception as e:
                logger.error(f"Failed to log in user: {e}")
                raise Exception("Failed to complete login")
            
            return user, profile
            
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.error(f"Error in authenticate_user: {type(e).__name__}: {str(e)}")
            raise