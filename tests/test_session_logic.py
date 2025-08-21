#!/usr/bin/env python
"""
Test session logic for anonymous users without web requests.
"""
import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

def test_session_logic():
    """Test session creation and validation logic"""
    from apps.tournament.models import VotingSession
    from core.services.tournament_service import VotingSessionService
    
    print("Testing Session Logic for Anonymous Users")
    print("=" * 50)
    
    # Clean up test sessions
    VotingSession.objects.filter(session_key__startswith='test_session').delete()
    
    try:
        # Test 1: Create anonymous session
        print("\n1. Creating anonymous session")
        test_session_key = 'test_session_12345'
        
        session, is_existing = VotingSessionService.get_or_create_session(
            user=None,
            session_key=test_session_key,
            preference='create_new'
        )
        
        print(f"   Created session: {session.id if session else None}")
        print(f"   Is existing: {is_existing}")
        print(f"   Status: {session.status if session else None}")
        print(f"   Session key: {session.session_key if session else None}")
        
        if not session or session.session_key != test_session_key:
            print("   FAIL: Session not created properly")
            return False
        
        # Test 2: Retrieve same session
        print("\n2. Retrieving same session")
        session2, is_existing2 = VotingSessionService.get_or_create_session(
            user=None,
            session_key=test_session_key,
            preference='default'
        )
        
        print(f"   Retrieved session: {session2.id if session2 else None}")
        print(f"   Same session: {session.id == session2.id if session and session2 else False}")
        print(f"   Is existing: {is_existing2}")
        
        if not session2 or session.id != session2.id:
            print("   FAIL: Session not retrieved properly")
            return False
        
        # Test 3: Test with different session key (should not match)
        print("\n3. Testing with different session key")
        different_session_key = 'test_session_67890'
        
        session3, is_existing3 = VotingSessionService.get_or_create_session(
            user=None,
            session_key=different_session_key,
            preference='active_only'
        )
        
        print(f"   Retrieved session: {session3.id if session3 else None}")
        print(f"   Should be None: {session3 is None}")
        
        if session3 is not None:
            print("   FAIL: Should not find session with different key")
            return False
        
        # Test 4: Test session key update (production fix)
        print("\n4. Testing session key update logic")
        print(f"   Original session key: {session.session_key}")
        
        # Simulate the production fix - update session key
        new_session_key = 'test_session_updated'
        session.session_key = new_session_key
        session.save()
        
        print(f"   Updated session key: {session.session_key}")
        
        # Verify it can be found with new key
        session4, is_existing4 = VotingSessionService.get_or_create_session(
            user=None,
            session_key=new_session_key,
            preference='default'
        )
        
        print(f"   Found with new key: {session4.id if session4 else None}")
        print(f"   Same session: {session.id == session4.id if session4 else False}")
        
        if not session4 or session.id != session4.id:
            print("   FAIL: Session not found with updated key")
            return False
        
        print(f"\n" + "=" * 50)
        print("SUCCESS: Session logic working correctly!")
        print("✓ Anonymous sessions can be created")
        print("✓ Sessions can be retrieved with same key")
        print("✓ Sessions are properly isolated by key")
        print("✓ Session keys can be updated (production fix)")
        
        return True
        
    except Exception as e:
        print(f"\nERROR: Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_session_logic()
    print(f"\nOverall result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)