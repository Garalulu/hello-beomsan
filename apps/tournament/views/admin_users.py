"""
Admin views for user management
Handles user listing, search, and statistics
"""
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages

from ..models import VotingSession, UserProfile

import logging

logger = logging.getLogger(__name__)


@staff_member_required
def user_manage(request):
    """User management interface"""
    from django.contrib.auth.models import User
    
    # Clean up orphaned profiles (profiles without users)
    try:
        orphaned_profiles = UserProfile.objects.filter(user__isnull=True)
        if orphaned_profiles.exists():
            count = orphaned_profiles.count()
            orphaned_profiles.delete()
            messages.success(request, f'Cleaned up {count} orphaned user profile(s)')
            logger.info(f'Cleaned up {count} orphaned user profiles')
    except Exception as e:
        logger.error(f'Error cleaning up orphaned profiles: {e}')
    
    # Get search filter
    username_filter = request.GET.get('username', '').strip()
    
    # Base queryset - get only users that actually exist with optional profile data
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
    
    # Apply username filter if provided - be defensive about profile access
    if username_filter:
        profile_filter = Q(profile__osu_username__icontains=username_filter)
        users = users.filter(
            Q(username__icontains=username_filter) | profile_filter
        )
    
    # Profile relationship is already accessible via select_related('profile')
    # No need to manually set it
    
    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    response = render(request, 'pages/admin/user_manage.html', {
        'page_obj': page_obj,
        'username_filter': username_filter,
    })
    
    # Add headers to prevent caching of user list
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response


@staff_member_required
def user_stats_ajax(request, user_id):
    """AJAX endpoint for user statistics"""
    try:
        from django.contrib.auth.models import User
        
        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'})
        
        # Get user's voting sessions
        user_sessions = VotingSession.objects.filter(user=user)
        
        # Basic statistics
        total_sessions = user_sessions.count()
        completed_sessions = user_sessions.filter(status='COMPLETED').count()
        active_sessions = user_sessions.filter(status='ACTIVE').count()
        abandoned_sessions = user_sessions.filter(status='ABANDONED').count()
        
        # Recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_sessions = user_sessions.filter(created_at__gte=thirty_days_ago).count()
        
        # Get user profile info - be defensive about profile access
        profile_info = {}
        try:
            if hasattr(user, 'profile') and user.profile:
                profile_info = {
                    'osu_username': user.profile.osu_username,
                    'osu_user_id': user.profile.osu_user_id,
                    'avatar_url': user.profile.avatar_url,
                }
        except (AttributeError, UserProfile.DoesNotExist) as e:
            logger.warning(f'Profile access issue for user {user.id}: {e}')
            profile_info = {'osu_username': 'No profile', 'osu_user_id': None, 'avatar_url': ''}
        
        # Get most recent sessions for activity timeline
        recent_activity = []
        latest_sessions = user_sessions.order_by('-created_at')[:5]
        for session in latest_sessions:
            recent_activity.append({
                'id': str(session.id),
                'status': session.status,
                'created_at': session.created_at.strftime('%b %d, %Y %H:%M'),
                'round_info': session.get_round_name() if session.status == 'ACTIVE' else None,
            })
        
        # Calculate completion rate
        completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
        
        return JsonResponse({
            'success': True,
            'user_info': {
                'username': user.username,
                'date_joined': user.date_joined.strftime('%b %d, %Y'),
                'is_staff': user.is_staff,
                'email': user.email,
                **profile_info
            },
            'statistics': {
                'total_sessions': total_sessions,
                'completed_sessions': completed_sessions,
                'active_sessions': active_sessions,
                'abandoned_sessions': abandoned_sessions,
                'completion_rate': round(completion_rate, 1),
                'recent_sessions_30d': recent_sessions,
            },
            'recent_activity': recent_activity,
        })
        
    except Exception as e:
        logger.error(f"Error in user_stats_ajax: {e}")
        return JsonResponse({'success': False, 'error': str(e)})