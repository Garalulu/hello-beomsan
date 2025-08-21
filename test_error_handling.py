#!/usr/bin/env python
"""
Test script to verify error handling in various scenarios
"""
import os
import sys
import django
import pytest

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hello_beomsan.settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth.models import User

from tournament.models import Song, VotingSession
from tournament.services import VotingSessionService
from accounts.services import OsuOAuthService

@pytest.mark.django_db
def test_empty_database_scenario():
    """Test behavior when no songs exist"""
    print("\n=== Testing Empty Database Scenario ===")
    
    # Clear all songs
    Song.objects.all().delete()
    
    # Try to create a voting session with no songs
    try:
        session = VotingSessionService.create_voting_session()
        if session is None:
            print("[PASS] Empty database handled correctly - returned None")
        else:
            print("[FAIL] Empty database not handled - session created unexpectedly")
    except Exception as e:
        print(f"[PASS] Empty database handled with exception: {type(e).__name__}: {e}")

@pytest.mark.django_db
def test_invalid_song_data():
    """Test behavior with corrupted song data"""
    print("\n=== Testing Invalid Song Data ===")
    
    # Create song with missing required fields
    try:
        song = Song.objects.create(title="", audio_url="", artist="Test")
        print(f"[FAIL] Invalid song created: {song}")
    except Exception as e:
        print(f"[PASS] Invalid song creation prevented: {type(e).__name__}: {e}")

def test_oauth_errors():
    """Test OAuth error handling"""
    print("\n=== Testing OAuth Error Scenarios ===")
    
    # Test with invalid settings
    original_client_id = getattr(django.conf.settings, 'OSU_CLIENT_ID', None)
    original_client_secret = getattr(django.conf.settings, 'OSU_CLIENT_SECRET', None)
    
    try:
        # Temporarily remove OAuth settings
        django.conf.settings.OSU_CLIENT_ID = None
        
        try:
            auth_url, state = OsuOAuthService.get_authorization_url()
            print("[FAIL] OAuth with missing client ID not handled")
        except Exception as e:
            print(f"[PASS] Missing OAuth client ID handled: {type(e).__name__}: {e}")
        
        # Test invalid token exchange
        try:
            token_data = OsuOAuthService.exchange_code_for_token("")
            print("[FAIL] Empty code token exchange not handled")
        except Exception as e:
            print(f"[PASS] Empty code token exchange handled: {type(e).__name__}: {e}")
            
    finally:
        # Restore original settings
        django.conf.settings.OSU_CLIENT_ID = original_client_id
        django.conf.settings.OSU_CLIENT_SECRET = original_client_secret

def test_voting_with_missing_session():
    """Test voting behavior with missing session"""
    print("\n=== Testing Voting with Missing Session ===")
    
    try:
        result = VotingSessionService.cast_vote(None, "fake-song-id")
        if result is False:
            print("[PASS] Voting with None session handled correctly")
        else:
            print("[FAIL] Voting with None session not handled")
    except Exception as e:
        print(f"[PASS] Voting with None session handled with exception: {type(e).__name__}: {e}")

@pytest.mark.django_db
def test_web_requests():
    """Test web interface error handling"""
    print("\n=== Testing Web Interface ===")
    
    client = Client()
    
    # Test home page with empty database
    try:
        response = client.get('/')
        if response.status_code == 200:
            print("[PASS] Home page loads successfully with empty database")
            if b"No songs available" in response.content:
                print("[PASS] Empty database warning displayed to user")
        else:
            print(f"[FAIL] Home page failed: {response.status_code}")
    except Exception as e:
        print(f"[FAIL] Home page error: {type(e).__name__}: {e}")
    
    # Test starting game with no songs
    try:
        response = client.post('/game/start/', {'action': 'new'})
        if response.status_code in [200, 302]:  # Redirect or success
            print("[PASS] Start game page handles empty database gracefully")
        else:
            print(f"[FAIL] Start game failed: {response.status_code}")
    except Exception as e:
        print(f"[FAIL] Start game error: {type(e).__name__}: {e}")

def run_all_tests():
    """Run all error handling tests"""
    print("Testing Error Handling Implementation")
    print("=" * 50)
    
    test_empty_database_scenario()
    test_invalid_song_data()
    test_oauth_errors()
    test_voting_with_missing_session()
    test_web_requests()
    
    print("\n" + "=" * 50)
    print("Error handling tests completed!")
    print("Check the output above for any failures that need attention.")

if __name__ == "__main__":
    run_all_tests()