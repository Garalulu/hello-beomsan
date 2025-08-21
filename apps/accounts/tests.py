from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch, Mock
import json

from apps.tournament.models import UserProfile
from core.services.accounts_service import OsuOAuthService


class OsuOAuthServiceTest(TestCase):
    """Test osu! OAuth service functionality"""
    
    def setUp(self):
        self.mock_settings = {
            'OSU_CLIENT_ID': 'test_client_id',
            'OSU_CLIENT_SECRET': 'test_client_secret',
            'OSU_REDIRECT_URI': 'http://localhost:8000/auth/callback/'
        }
    
    @patch('core.services.accounts_service.settings')
    def test_get_authorization_url(self, mock_settings):
        """Test getting OAuth authorization URL"""
        for key, value in self.mock_settings.items():
            setattr(mock_settings, key, value)
        
        auth_url, state = OsuOAuthService.get_authorization_url()
        
        self.assertIsNotNone(auth_url)
        self.assertIsNotNone(state)
        self.assertIn('osu.ppy.sh', auth_url)
        self.assertIn('test_client_id', auth_url)
    
    @patch('core.services.accounts_service.settings')
    @patch('core.services.accounts_service.requests.post')
    def test_exchange_code_for_token(self, mock_post, mock_settings):
        """Test exchanging code for access token"""
        for key, value in self.mock_settings.items():
            setattr(mock_settings, key, value)
        
        # Mock successful token response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'token_type': 'Bearer'
        }
        mock_post.return_value = mock_response
        
        token_data = OsuOAuthService.exchange_code_for_token('test_code')
        
        self.assertIsNotNone(token_data)
        self.assertEqual(token_data['access_token'], 'test_access_token')
    
    @patch('core.services.accounts_service.settings')  
    @patch('core.services.accounts_service.requests.post')
    def test_exchange_code_for_token_error(self, mock_post, mock_settings):
        """Test token exchange with error response"""
        for key, value in self.mock_settings.items():
            setattr(mock_settings, key, value)
        
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        # Should raise exception, not return None
        with self.assertRaises(Exception) as cm:
            OsuOAuthService.exchange_code_for_token('invalid_code')
        self.assertIn('Invalid authorization code', str(cm.exception))
    
    @patch('core.services.accounts_service.requests.get')
    def test_get_user_info(self, mock_get):
        """Test getting user info from osu! API"""
        # Mock successful user info response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 12345,
            'username': 'testuser',
            'country_code': 'US'
        }
        mock_get.return_value = mock_response
        
        user_data = OsuOAuthService.get_user_info('test_access_token')
        
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data['id'], 12345)
        self.assertEqual(user_data['username'], 'testuser')
    
    @patch('core.services.accounts_service.requests.get')
    def test_get_user_info_error(self, mock_get):
        """Test getting user info with error response"""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        # Should raise exception, not return None
        with self.assertRaises(Exception) as cm:
            OsuOAuthService.get_user_info('invalid_token')
        self.assertIn('Authentication token expired or invalid', str(cm.exception))
    
    def test_create_or_update_user_new(self):
        """Test creating a new user from osu! data"""
        osu_data = {
            'id': 12345,
            'username': 'newtestuser',
            'country_code': 'US'
        }
        
        user, profile = OsuOAuthService.create_or_update_user(osu_data)
        
        self.assertIsNotNone(user)
        self.assertIsNotNone(profile)
        self.assertEqual(user.username, 'newtestuser')  # Username is just the osu username unless there's a conflict
        self.assertEqual(profile.osu_user_id, 12345)
        self.assertEqual(profile.osu_username, 'newtestuser')
    
    def test_create_or_update_user_existing(self):
        """Test updating an existing user from osu! data"""
        # Create existing user and profile
        existing_user = User.objects.create_user(username='existing_12345')
        existing_profile = UserProfile.objects.create(
            user=existing_user,
            osu_user_id=12345,
            osu_username='existing'
        )
        
        osu_data = {
            'id': 12345,
            'username': 'updated_username',
            'country_code': 'CA'
        }
        
        user, profile = OsuOAuthService.create_or_update_user(osu_data)
        
        # Should return the same user and update profile
        self.assertEqual(user.id, existing_user.id)
        self.assertEqual(user, existing_user)
        
        # Profile should be updated
        self.assertEqual(profile.osu_username, 'updated_username')
    
    @patch('core.services.accounts_service.settings')
    def test_authenticate_user_success(self, mock_settings):
        """Test successful user authentication flow"""
        for key, value in self.mock_settings.items():
            setattr(mock_settings, key, value)
        
        with patch.object(OsuOAuthService, 'exchange_code_for_token') as mock_exchange, \
             patch.object(OsuOAuthService, 'get_user_info') as mock_user_info, \
             patch.object(OsuOAuthService, 'create_or_update_user') as mock_create_user:
            
            # Mock the chain of OAuth calls
            mock_exchange.return_value = {'access_token': 'test_token'}
            mock_user_info.return_value = {'id': 12345, 'username': 'testuser'}
            mock_user = User.objects.create_user(username='testuser')
            mock_profile = UserProfile(osu_user_id=12345, osu_username='testuser')
            mock_create_user.return_value = (mock_user, mock_profile)
            
            # Mock request object with session
            from django.test import RequestFactory
            from django.contrib.sessions.backends.db import SessionStore
            request = RequestFactory().get('/auth/callback/')
            request.session = SessionStore()
            request.session.create()
            user, profile = OsuOAuthService.authenticate_user(request, 'test_code', 'test_state')
            
            self.assertIsNotNone(user)
            self.assertIsNotNone(profile)
            self.assertEqual(user.username, 'testuser')  # Username is just the osu username unless there's a conflict
    
    @patch('core.services.accounts_service.settings')
    def test_authenticate_user_failure(self, mock_settings):
        """Test user authentication failure"""
        for key, value in self.mock_settings.items():
            setattr(mock_settings, key, value)
        
        with patch.object(OsuOAuthService, 'exchange_code_for_token') as mock_exchange:
            # Mock token exchange failure
            mock_exchange.return_value = None
            
            # Mock request object with session
            from django.test import RequestFactory
            from django.contrib.sessions.backends.db import SessionStore
            request = RequestFactory().get('/auth/callback/')
            request.session = SessionStore()
            request.session.create()
            
            # Should raise exception, not return None
            with self.assertRaises(Exception):
                OsuOAuthService.authenticate_user(request, 'invalid_code', 'test_state')


class UserProfileModelTest(TestCase):
    """Test UserProfile model functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser')
        self.profile = UserProfile.objects.create(
            user=self.user,
            osu_user_id=12345,
            osu_username='testuser'
        )
    
    def test_profile_creation(self):
        """Test profile creation and string representation"""
        # UserProfile format: "osu_username (user.username)"
        self.assertEqual(str(self.profile), "testuser (testuser)")
        self.assertEqual(self.profile.user, self.user)
        self.assertEqual(self.profile.osu_user_id, 12345)
        self.assertEqual(self.profile.osu_username, 'testuser')
    
    def test_profile_unique_constraint(self):
        """Test that osu_user_id is unique"""
        from django.db import IntegrityError
        
        with self.assertRaises(IntegrityError):
            UserProfile.objects.create(
                user=User.objects.create_user(username='another'),
                osu_user_id=12345,  # Same osu_user_id
                osu_username='another'
            )


class AuthViewsTest(TestCase):
    """Test authentication views"""
    
    def setUp(self):
        self.client = Client()
    
    @patch('accounts.views.OsuOAuthService.get_authorization_url')
    def test_login_view(self, mock_get_auth_url):
        """Test login view redirects to osu!"""
        mock_get_auth_url.return_value = ('https://osu.ppy.sh/oauth/authorize?...', 'test_state')
        
        response = self.client.get('/auth/login/')
        
        self.assertEqual(response.status_code, 302)  # Redirect to osu!
        
        # Check that state was stored in session
        self.assertIn('oauth_state', self.client.session)
    
    @patch('accounts.views.OsuOAuthService.get_authorization_url')
    def test_login_view_error(self, mock_get_auth_url):
        """Test login view with OAuth service error"""
        mock_get_auth_url.side_effect = Exception('OAuth service error')
        
        response = self.client.get('/auth/login/')
        
        self.assertEqual(response.status_code, 302)  # Redirect to home
    
    @patch('accounts.views.OsuOAuthService.authenticate_user')
    def test_oauth_callback_success(self, mock_authenticate):
        """Test successful OAuth callback"""
        # Set up session state
        session = self.client.session
        session['oauth_state'] = 'test_state'
        session.save()
        
        # Mock successful authentication
        mock_user = User.objects.create_user(username='testuser')
        mock_profile = UserProfile(osu_user_id=12345, osu_username='testuser')
        mock_authenticate.return_value = (mock_user, mock_profile)
        
        response = self.client.get('/auth/callback/?code=test_code&state=test_state')
        
        self.assertEqual(response.status_code, 302)  # Redirect after login
        
        # Verify authentication was called properly
        mock_authenticate.assert_called_once()
    
    @patch('accounts.views.OsuOAuthService.authenticate_user')
    def test_oauth_callback_invalid_state(self, mock_authenticate):
        """Test OAuth callback with invalid state"""
        # Set up different session state
        session = self.client.session
        session['oauth_state'] = 'correct_state'
        session.save()
        
        response = self.client.get('/auth/callback/?code=test_code&state=wrong_state')
        
        self.assertEqual(response.status_code, 302)  # Redirect to home
        
        # Authentication should not be attempted
        mock_authenticate.assert_not_called()
    
    @patch('accounts.views.OsuOAuthService.authenticate_user')
    def test_oauth_callback_authentication_failure(self, mock_authenticate):
        """Test OAuth callback with authentication failure"""
        # Set up session state
        session = self.client.session
        session['oauth_state'] = 'test_state'
        session.save()
        
        # Mock authentication failure
        mock_authenticate.return_value = (None, None)
        
        response = self.client.get('/auth/callback/?code=test_code&state=test_state')
        
        self.assertEqual(response.status_code, 302)  # Redirect to home
        
        # User should not be logged in
        self.assertNotIn('_auth_user_id', self.client.session)
    
    def test_logout_view(self):
        """Test logout view"""
        # Log in a user first
        user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        
        response = self.client.post('/auth/logout/')
        
        self.assertEqual(response.status_code, 302)  # Redirect after logout
        
        # User should be logged out
        self.assertNotIn('_auth_user_id', self.client.session)
    
    def test_oauth_callback_missing_parameters(self):
        """Test OAuth callback with missing parameters"""
        response = self.client.get('/auth/callback/')  # No code or state
        
        self.assertEqual(response.status_code, 302)  # Redirect to home


class IntegrationTest(TestCase):
    """Test integration between accounts and tournament apps"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='integrationuser')
        self.profile = UserProfile.objects.create(
            user=self.user,
            osu_user_id=99999,
            osu_username='integrationuser'
        )
    
    def test_authenticated_tournament_flow(self):
        """Test tournament flow with authenticated user"""
        from apps.tournament.models import Song
        
        # Create test songs
        for i in range(3):
            Song.objects.create(
                title=f"Integration Test Song {i+1}",
                artist=f"Artist {i+1}",
                audio_url=f"https://example.com/song{i+1}.mp3",
                background_image_url=f"https://example.com/bg{i+1}.jpg"
            )
        
        # Log in user
        self.client.force_login(self.user)
        
        # Test that home page shows user info
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'integrationuser')  # Should show osu username
        
        # Test starting a game as authenticated user
        response = self.client.post('/game/start/', {'action': 'new'})
        self.assertEqual(response.status_code, 302)
        
        # Check that session was created for the user
        from apps.tournament.models import VotingSession
        session = VotingSession.objects.filter(user=self.user).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.user, self.user)
    
    def test_user_profile_in_navigation(self):
        """Test that user profile shows correctly in navigation"""
        self.client.force_login(self.user)
        
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        # Should show osu username in navigation
        self.assertContains(response, 'integrationuser')  # osu_username
        self.assertContains(response, 'Logout')
    
    def test_session_persistence_for_authenticated_users(self):
        """Test that authenticated users can resume sessions"""
        from apps.tournament.models import Song, VotingSession
        from core.services.tournament_service import VotingSessionService
        
        # Create test songs
        for i in range(3):
            Song.objects.create(
                title=f"Persistence Test Song {i+1}",
                artist=f"Artist {i+1}",
                audio_url=f"https://example.com/song{i+1}.mp3",
                background_image_url=f"https://example.com/bg{i+1}.jpg"
            )
        
        self.client.force_login(self.user)
        
        # Create a session for the user
        session = VotingSessionService.create_voting_session()
        session.user = self.user
        session.save()
        
        # Simulate returning to the site
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        # Should indicate there's a session in progress
        self.assertContains(response, 'session in progress')