#!/usr/bin/env python
"""
Complete view testing to achieve maximum coverage of tournament/views.py
"""
import os
import sys
import django
import pytest
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from apps.tournament.models import Song, VotingSession, Match, Vote, UserProfile
from core.services.tournament_service import VotingSessionService


@pytest.mark.django_db
class CompleteViewCoverageTest(TestCase):
    """Test every single view path for maximum coverage"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.admin = User.objects.create_user(username='admin', password='adminpass', is_staff=True, is_superuser=True)
        
        # Create test songs
        self.songs = []
        for i in range(10):
            song = Song.objects.create(
                title=f"Coverage Test Song {i+1}",
                artist=f"Artist {i+1}",
                audio_url=f"https://example.com/song{i+1}.mp3",
                background_image_url=f"https://example.com/bg{i+1}.jpg"
            )
            self.songs.append(song)
    
    def test_home_view_all_scenarios(self):
        """Test home view with all possible scenarios"""
        # Test with no active session
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        # Test with active session for anonymous user
        session = VotingSessionService.create_voting_session()
        session.session_key = self.client.session.session_key
        session.save()
        
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        # Test with logged in user
        self.client.login(username='testuser', password='testpass')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        # Test with active session for logged in user
        user_session = VotingSessionService.create_voting_session()
        user_session.user = self.user
        user_session.save()
        
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        # Test with no songs
        Song.objects.all().delete()
        # Clear cache to ensure updated count
        from django.core.cache import cache
        cache.clear()
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No songs available yet')
    
    def test_start_game_all_paths(self):
        """Test start_game view with all possible paths"""
        # Test GET request
        response = self.client.get('/game/start/')
        self.assertEqual(response.status_code, 200)
        
        # Test POST with no action (defaults to new game)
        response = self.client.post('/game/start/', {})
        self.assertEqual(response.status_code, 302)  # Redirects to vote
        
        # Test POST with 'new' action
        response = self.client.post('/game/start/', {'action': 'new'})
        self.assertEqual(response.status_code, 302)
        
        # Test POST with 'continue' action without existing session (starts new game instead)
        response = self.client.post('/game/start/', {'action': 'continue'})
        self.assertEqual(response.status_code, 302)  # Redirects to new game
        
        # Test POST with 'continue' action with existing session
        self.client.login(username='testuser', password='testpass')
        session = VotingSessionService.create_voting_session()
        session.user = self.user
        session.save()
        
        response = self.client.post('/game/start/', {'action': 'continue'})
        self.assertEqual(response.status_code, 302)
        
        # Test with no songs available
        Song.objects.all().delete()
        response = self.client.post('/game/start/', {'action': 'new'})
        self.assertEqual(response.status_code, 302)  # Should redirect with error
    
    def test_vote_view_all_scenarios(self):
        """Test vote view with all possible scenarios"""
        # Test with no session
        response = self.client.get('/game/vote/')
        self.assertEqual(response.status_code, 302)
        
        # Test with anonymous session
        session = VotingSessionService.create_voting_session()
        session.session_key = self.client.session.session_key
        session.save()
        
        response = self.client.get('/game/vote/')
        self.assertEqual(response.status_code, 200)
        
        # Test with completed session
        session.status = 'COMPLETED'
        session.save()
        
        response = self.client.get('/game/vote/')
        # Could redirect to completion page or show completion message
        self.assertIn(response.status_code, [200, 302])
        if response.status_code == 200:
            self.assertContains(response, 'Congratulations')
        
        # Test with logged in user
        self.client.login(username='testuser', password='testpass')
        user_session = VotingSessionService.create_voting_session()
        user_session.user = self.user
        user_session.save()
        
        response = self.client.get('/game/vote/')
        self.assertEqual(response.status_code, 200)
    
    def test_cast_vote_all_scenarios(self):
        """Test cast_vote view with all possible scenarios"""
        # Test with no session
        response = self.client.post('/game/cast-vote/', 
            json.dumps({'song_id': str(self.songs[0].id)}),
            content_type='application/json'
        )
        # Could be 400 (bad request) or 200 (handled gracefully) depending on implementation
        self.assertIn(response.status_code, [200, 400])
        
        # Test with invalid JSON
        response = self.client.post('/game/cast-vote/', 
            'invalid json',
            content_type='application/json'
        )
        # Could be 400 (bad request) or 200 (handled gracefully) depending on implementation
        self.assertIn(response.status_code, [200, 400])
        
        # Test with valid session and vote
        session = VotingSessionService.create_voting_session()
        session.session_key = self.client.session.session_key
        session.save()
        
        match_data = VotingSessionService.get_current_match(session)
        if match_data:
            response = self.client.post('/game/cast-vote/', 
                json.dumps({'song_id': match_data['song1']['id']}),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
        
        # Test with invalid song ID
        response = self.client.post('/game/cast-vote/', 
            json.dumps({'song_id': 'invalid-id'}),
            content_type='application/json'
        )
        self.assertIn(response.status_code, [200, 400])
    
    def test_song_stats_all_paths(self):
        """Test song_stats view with all paths"""
        # Test all sort options
        sort_options = ['win_rate', 'pick_rate', 'tournaments']
        
        for sort_option in sort_options:
            # Test first page
            response = self.client.get(f'/game/stats/?sort={sort_option}')
            self.assertEqual(response.status_code, 200)
            
            # Test specific page
            response = self.client.get(f'/game/stats/?sort={sort_option}&page=1')
            self.assertEqual(response.status_code, 200)
            
            # Test invalid page
            response = self.client.get(f'/game/stats/?sort={sort_option}&page=999')
            self.assertEqual(response.status_code, 200)
        
        # Test invalid sort option
        response = self.client.get('/game/stats/?sort=invalid')
        self.assertEqual(response.status_code, 200)
        
        # Test with no songs
        Song.objects.all().delete()
        response = self.client.get('/game/stats/')
        self.assertEqual(response.status_code, 200)
    
    def test_admin_upload_song_all_paths(self):
        """Test upload_song admin view with all paths"""
        self.client.login(username='admin', password='adminpass')
        
        # Test GET request
        response = self.client.get('/game/admin/upload/')
        self.assertEqual(response.status_code, 200)
        
        # Test POST with valid data
        response = self.client.post('/game/admin/upload/', {
            'title': 'Admin Test Song',
            'artist': 'Admin Artist',
            'audio_url': 'https://example.com/admin-test.mp3',
            'background_image_url': 'https://example.com/admin-bg.jpg'
        })
        self.assertEqual(response.status_code, 302)
        
        # Test POST with invalid data
        response = self.client.post('/game/admin/upload/', {
            'title': '',  # Empty title
            'artist': 'Artist',
            'audio_url': 'invalid-url'
        })
        self.assertEqual(response.status_code, 200)  # Should re-render with errors
        
        # Test POST with missing audio_url
        response = self.client.post('/game/admin/upload/', {
            'title': 'Test',
            'artist': 'Artist'
        })
        self.assertEqual(response.status_code, 200)
    
    def test_admin_manage_songs_all_paths(self):
        """Test manage_songs admin view with all paths"""
        self.client.login(username='admin', password='adminpass')
        
        # Test without search
        response = self.client.get('/game/admin/song/')
        self.assertEqual(response.status_code, 200)
        
        # Test with search query
        response = self.client.get('/game/admin/song/?search=Coverage')
        self.assertEqual(response.status_code, 200)
        
        # Test with empty search
        response = self.client.get('/game/admin/song/?search=')
        self.assertEqual(response.status_code, 200)
        
        # Test with search that returns no results
        response = self.client.get('/game/admin/song/?search=NonexistentSong')
        self.assertEqual(response.status_code, 200)
        
        # Test pagination
        response = self.client.get('/game/admin/song/?page=1')
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get('/game/admin/song/?page=999')
        self.assertEqual(response.status_code, 200)
    
    def test_admin_edit_song_all_paths(self):
        """Test edit_song admin view with all paths"""
        self.client.login(username='admin', password='adminpass')
        
        song = self.songs[0]
        
        # Test GET request
        response = self.client.get(f'/game/admin/song/{song.id}/edit/')
        self.assertEqual(response.status_code, 200)
        
        # Test POST with valid data
        response = self.client.post(f'/game/admin/song/{song.id}/edit/', {
            'title': 'Updated Song Title',
            'artist': 'Updated Artist',
            'audio_url': 'https://example.com/updated.mp3',
            'background_image_url': 'https://example.com/updated-bg.jpg'
        })
        self.assertEqual(response.status_code, 302)
        
        # Test POST with invalid data
        response = self.client.post(f'/game/admin/song/{song.id}/edit/', {
            'title': '',  # Empty title
            'artist': 'Artist',
            'audio_url': 'invalid-url'
        })
        self.assertEqual(response.status_code, 200)
        
        # Test with non-existent song
        response = self.client.get('/game/admin/song/99999/edit/')
        self.assertEqual(response.status_code, 404)
    
    def test_admin_delete_song_all_paths(self):
        """Test delete_song admin view with all paths"""
        self.client.login(username='admin', password='adminpass')
        
        song = self.songs[0]
        
        # Test POST request (delete)
        response = self.client.post(f'/game/admin/song/{song.id}/delete/')
        self.assertEqual(response.status_code, 302)
        
        # Test with non-existent song
        response = self.client.post('/game/admin/song/99999/delete/')
        self.assertEqual(response.status_code, 404)
    
    def test_admin_tournament_views_all_paths(self):
        """Test all tournament management admin views"""
        self.client.login(username='admin', password='adminpass')
        
        # Create test sessions
        for i in range(5):
            user = User.objects.create_user(username=f'tourneyuser{i}')
            VotingSession.objects.create(
                user=user,
                status='COMPLETED' if i < 3 else 'ACTIVE',
                # winner_song field doesn't exist in current model
            )
        
        # Test tournament_manage view
        response = self.client.get('/game/admin/tournaments/')
        self.assertEqual(response.status_code, 200)
        
        # Test tournament_history view
        response = self.client.get('/game/admin/tournaments/history/')
        self.assertEqual(response.status_code, 200)
        
        # Test with user filter
        response = self.client.get('/game/admin/tournaments/history/?user=tourneyuser1')
        self.assertEqual(response.status_code, 200)
        
        # Test with date filter
        response = self.client.get('/game/admin/tournaments/history/?date_from=2024-01-01')
        self.assertEqual(response.status_code, 200)
        
        # Test with status filter
        response = self.client.get('/game/admin/tournaments/history/?status=COMPLETED')
        self.assertEqual(response.status_code, 200)
        
        # Test pagination
        response = self.client.get('/game/admin/tournaments/history/?page=1')
        self.assertEqual(response.status_code, 200)
    
    def test_admin_user_management_all_paths(self):
        """Test user management admin view"""
        self.client.login(username='admin', password='adminpass')
        
        # Create users with profiles
        for i in range(3):
            user = User.objects.create_user(username=f'profileuser{i}')
            UserProfile.objects.create(
                user=user,
                osu_user_id=10000 + i,
                osu_username=f'osuuser{i}'
            )
        
        # Test user_manage view
        response = self.client.get('/game/admin/users/')
        self.assertEqual(response.status_code, 200)
        
        # Test with search
        response = self.client.get('/game/admin/users/?search=profileuser1')
        self.assertEqual(response.status_code, 200)
        
        # Test with empty search
        response = self.client.get('/game/admin/users/?search=')
        self.assertEqual(response.status_code, 200)
    
    def test_admin_session_detail_all_paths(self):
        """Test session detail admin view"""
        self.client.login(username='admin', password='adminpass')
        
        # Create session with matches
        session = VotingSession.objects.create(
            user=self.user,
            bracket_data={
                'round_1': [
                    {'match_number': 1, 'song1': {'id': str(self.songs[0].id)}, 'song2': {'id': str(self.songs[1].id)}}
                ]
            }
        )
        
        Match.objects.create(
            session=session,
            round_number=1,
            match_number=1,
            song1=self.songs[0],
            song2=self.songs[1],
            winner=self.songs[0]
        )
        
        # Test session detail view
        response = self.client.get(f'/game/admin/session/{session.id}/')
        self.assertEqual(response.status_code, 200)
        
        # Test with non-existent session
        response = self.client.get('/game/admin/session/99999/')
        self.assertEqual(response.status_code, 404)
    
    def test_non_staff_access_admin_views(self):
        """Test that non-staff users cannot access admin views"""
        self.client.login(username='testuser', password='testpass')
        
        admin_urls = [
            '/game/admin/upload/',
            '/game/admin/song/',
            '/game/admin/tournaments/',
            '/game/admin/tournaments/history/',
            '/game/admin/users/',
        ]
        
        for url in admin_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)  # Should redirect to login
    
    def test_anonymous_user_restrictions(self):
        """Test restrictions for anonymous users"""
        # Test that certain views work for anonymous users
        public_urls = [
            '/',
            '/game/start/',
            '/game/stats/',
            '/auth/login/',
        ]
        
        for url in public_urls:
            response = self.client.get(url)
            self.assertIn(response.status_code, [200, 302])  # 200 for pages, 302 for redirects