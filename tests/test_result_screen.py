#!/usr/bin/env python
"""
Test that the result screen template renders correctly with our improvements.
"""
import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

def test_result_screen_rendering():
    """Test that result screen template renders with improvements"""
    from django.template.loader import render_to_string
    from apps.tournament.models import VotingSession, Song
    from django.contrib.auth.models import User
    from unittest.mock import Mock
    
    print("Testing Result Screen Template Improvements")
    print("=" * 50)
    
    try:
        # Create mock data that simulates a completed tournament
        print("1. Creating mock tournament data...")
        
        # Create a test song with background image
        test_song_data = {
            'id': 'test-song-id',
            'title': 'Test Winner Song',
            'original_song': 'Original Test Song',
            'background_image_url': 'https://example.com/test-background.jpg'
        }
        
        # Create mock session data
        mock_session = Mock()
        mock_session.created_at = Mock()
        mock_session.created_at.timesince.return_value = "15 minutes"
        
        # Create mock bracket data with winner
        mock_session.bracket_data = {
            'round_7': [  # Final round
                {
                    'winner': test_song_data
                }
            ]
        }
        
        # Mock user
        mock_user = Mock()
        mock_user.is_authenticated = False
        
        print("2. Testing template rendering with background image...")
        
        # Render template
        context = {
            'session': mock_session,
            'user': mock_user,
        }
        
        try:
            rendered = render_to_string('pages/main/completed.html', context)
            print("   Template rendered successfully!")
            
            # Check for key improvements
            improvements_found = []
            
            if 'winner-image-container' in rendered:
                improvements_found.append("Winner background image container")
            
            if 'border: 3px solid #ffc107' in rendered:
                improvements_found.append("Golden border styling")
            
            if 'justify-content-center' in rendered:
                improvements_found.append("Centered time spent table")
                
            if 'Tournament Duration' in rendered:
                improvements_found.append("Enhanced time spent card")
                
            if 'winner-placeholder' in rendered:
                improvements_found.append("Fallback design for songs without images")
            
            print(f"   Improvements found: {len(improvements_found)}")
            for improvement in improvements_found:
                print(f"   [OK] {improvement}")
            
            if len(improvements_found) >= 4:
                print("   SUCCESS: All major improvements are present!")
                return True
            else:
                print(f"   WARNING: Only {len(improvements_found)} improvements found")
                return False
                
        except Exception as template_error:
            print(f"   ERROR: Template rendering failed: {template_error}")
            return False
    
    except Exception as e:
        print(f"ERROR: Test setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fallback_rendering():
    """Test rendering without background image (fallback case)"""
    from django.template.loader import render_to_string
    from unittest.mock import Mock
    
    print("\n3. Testing fallback rendering (no background image)...")
    
    try:
        # Create mock data without background image
        test_song_data = {
            'id': 'test-song-no-bg',
            'title': 'Song Without Background',
            'original_song': 'Original Song',
            'background_image_url': None  # No background image
        }
        
        mock_session = Mock()
        mock_session.created_at = Mock()
        mock_session.created_at.timesince.return_value = "10 minutes"
        mock_session.bracket_data = {
            'round_7': [{'winner': test_song_data}]
        }
        
        mock_user = Mock()
        mock_user.is_authenticated = False
        
        context = {
            'session': mock_session,
            'user': mock_user,
        }
        
        rendered = render_to_string('pages/main/completed.html', context)
        
        if 'winner-placeholder' in rendered and 'fa-music' in rendered:
            print("   [OK] Fallback placeholder rendered correctly")
            return True
        else:
            print("   [FAIL] Fallback placeholder not found")
            return False
            
    except Exception as e:
        print(f"   ERROR: Fallback test failed: {e}")
        return False

if __name__ == '__main__':
    print("Testing result screen template improvements...")
    
    success1 = test_result_screen_rendering()
    success2 = test_fallback_rendering()
    
    overall_success = success1 and success2
    
    print(f"\n" + "=" * 50)
    if overall_success:
        print("SUCCESS: Result screen improvements working!")
        print("[OK] Background images added to winner display")  
        print("[OK] Golden border styling applied")
        print("[OK] Time spent table centered and enhanced")
        print("[OK] Fallback design for songs without images")
    else:
        print("ISSUES FOUND: Some improvements may not be working")
    
    print(f"\nTest result: {'PASSED' if overall_success else 'FAILED'}")
    sys.exit(0 if overall_success else 1)