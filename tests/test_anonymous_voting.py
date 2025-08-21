#!/usr/bin/env python
"""
Test anonymous user voting flow to identify session issues.
"""
import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

def test_anonymous_voting_flow():
    """Test anonymous user voting session handling"""
    from django.test import Client
    from apps.tournament.models import VotingSession
    import json
    
    print("Testing Anonymous User Voting Flow")
    print("=" * 40)
    
    # Clean up any existing test sessions
    VotingSession.objects.filter(session_key__startswith='test_anon').delete()
    
    client = Client()
    
    try:
        # Step 1: Anonymous user visits start game page
        print("\n1. Anonymous user visits start game page")
        response = client.get('/game/start/')
        print(f"   Status: {response.status_code}")
        assert response.status_code == 200
        
        # Step 2: Anonymous user starts new tournament
        print("\n2. Anonymous user starts new tournament")
        csrf_token = client.cookies.get('csrftoken').value if client.cookies.get('csrftoken') else None
        
        response = client.post('/game/start/', {
            'csrfmiddlewaretoken': csrf_token,
            'action': 'new'
        })
        print(f"   Status: {response.status_code}")
        print(f"   Redirect: {response.get('Location', 'No redirect')}")
        
        if response.status_code == 302 and '/game/vote/?new=1' in response['Location']:
            print("   SUCCESS: Redirected to voting page")
        else:
            print(f"   FAIL: Expected redirect to vote?new=1")
            return False
        
        # Step 3: Follow redirect to voting page
        print("\n3. Access voting page")
        response = client.get('/game/vote/?new=1')
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200 and 'Vote:' in response.content.decode():
            print("   SUCCESS: Voting page loaded")
        else:
            print(f"   FAIL: Voting page not loaded properly")
            return False
        
        # Step 4: Extract session info from page
        content = response.content.decode()
        
        # Look for session ID in the page (should be in JavaScript)
        import re
        session_match = re.search(r'sessionId:\s*[\'"]([^\'\"]+)[\'"]', content)
        if not session_match:
            print("   FAIL: No session ID found in voting page")
            return False
        
        session_id = session_match.group(1)
        print(f"   Found session ID: {session_id}")
        
        # Look for song IDs
        song_matches = re.findall(r'data-song-id=[\'"]([^\'\"]+)[\'"]', content)
        if len(song_matches) < 2:
            print("   FAIL: Not enough songs found for voting")
            return False
        
        song1_id = song_matches[0]
        song2_id = song_matches[1]
        print(f"   Found songs: {song1_id}, {song2_id}")
        
        # Step 5: Test voting (multiple votes)
        print("\n4. Test multiple votes")
        
        for vote_num in range(1, 4):  # Test 3 votes
            print(f"\n   Vote {vote_num}:")
            
            # Choose first song
            vote_data = {
                'session_id': session_id,
                'chosen_song_id': song1_id
            }
            
            response = client.post('/game/cast-vote/', 
                                 data=json.dumps(vote_data),
                                 content_type='application/json',
                                 HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"   SUCCESS: Vote {vote_num} cast successfully")
                    if result.get('completed'):
                        print("   Tournament completed!")
                        break
                    else:
                        # Get next songs for next vote
                        next_match = result.get('next_match', {})
                        song1_id = next_match.get('song1', {}).get('id', song1_id)
                        song2_id = next_match.get('song2', {}).get('id', song2_id) 
                        print(f"   Next songs: {song1_id}, {song2_id}")
                else:
                    print(f"   FAIL: Vote {vote_num} failed: {result.get('error', 'Unknown error')}")
                    return False
            else:
                print(f"   FAIL: Vote {vote_num} request failed with status {response.status_code}")
                return False
        
        print(f"\n" + "=" * 40)
        print("SUCCESS: Anonymous user voting flow working!")
        print("- Anonymous user can start tournament")
        print("- Voting page loads correctly")
        print("- Multiple votes can be cast successfully")
        print("- Session is maintained throughout voting")
        return True
        
    except Exception as e:
        print(f"\nERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_anonymous_voting_flow()
    print(f"\nTest result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)