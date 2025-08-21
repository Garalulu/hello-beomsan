#!/usr/bin/env python
"""
Test the user_manage view query to make sure it works correctly.
"""
import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

def test_user_manage_query():
    """Test the user management query"""
    from django.db.models import Count, Q
    from django.contrib.auth.models import User
    
    print("Testing user_manage query...")
    print("=" * 40)
    
    try:
        # Test the same query from the view
        users = User.objects.select_related('profile').annotate(
            total_sessions=Count('voting_sessions', distinct=True),
            completed_sessions=Count(
                'voting_sessions',
                filter=Q(voting_sessions__status='COMPLETED'),
                distinct=True
            ),
            active_sessions=Count(
                'voting_sessions', 
                filter=Q(voting_sessions__status='ACTIVE'),
                distinct=True
            )
        ).order_by('-date_joined')
        
        print(f"Total users found: {users.count()}")
        
        # Test first few users
        for i, user in enumerate(users[:5]):
            print(f"\nUser {i+1}: {user.username}")
            print(f"  Date joined: {user.date_joined}")
            print(f"  Total sessions: {user.total_sessions}")
            print(f"  Completed sessions: {user.completed_sessions}")
            print(f"  Active sessions: {user.active_sessions}")
            
            # Check profile access
            try:
                profile = user.profile
                print(f"  Profile: osu! {profile.osu_username} (ID: {profile.osu_user_id})")
            except:
                print("  Profile: None")
        
        # Test search functionality
        print(f"\n" + "=" * 40)
        print("Testing search functionality...")
        
        # Search for users with 'test' in username
        search_users = users.filter(
            Q(username__icontains='test') |
            Q(profile__osu_username__icontains='test')
        )
        print(f"Users with 'test' in username: {search_users.count()}")
        
        print("\nSUCCESS: User management query works correctly!")
        return True
        
    except Exception as e:
        print(f"ERROR: Query failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_user_manage_query()
    sys.exit(0 if success else 1)