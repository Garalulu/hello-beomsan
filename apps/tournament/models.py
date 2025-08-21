from django.db import models
from django.contrib.auth.models import User
from django.db.models import F, Case, When, FloatField, Q
from django.utils.functional import cached_property
import uuid


class SongManager(models.Manager):
    def with_calculated_rates(self):
        """Annotate songs with calculated win and pick rates using database operations"""
        return self.annotate(
            calculated_pick_rate=Case(
                When(total_picks=0, then=0.0),
                default=(F('total_wins') * 100.0) / F('total_picks'),
                output_field=FloatField()
            )
        )
    
    def for_statistics(self):
        """Optimized queryset for statistics page with pre-cached tournament count"""
        from core.services.tournament_service import VotingSessionService
        
        # Get cached completed tournaments count
        completed_count = VotingSessionService.get_cached_completed_tournaments_count()
        
        queryset = self.with_calculated_rates()
        
        # Cache the completed tournaments count on each song instance
        for song in queryset:
            song._cached_completed_tournaments = completed_count
        
        return queryset


class Song(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    original_song = models.CharField(max_length=200, blank=True)
    audio_url = models.URLField(max_length=500)  # Google Drive direct download URL
    background_image_url = models.URLField(max_length=500, blank=True)  # Google Drive image URL
    
    # Statistics
    total_wins = models.PositiveIntegerField(default=0)  # Match wins (pick rate)
    total_losses = models.PositiveIntegerField(default=0)
    total_picks = models.PositiveIntegerField(default=0)  # How many times this song appeared in matches
    tournament_wins = models.PositiveIntegerField(default=0)  # Tournament wins (win rate)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = SongManager()
    
    class Meta:
        db_table = 'songs'
        indexes = [
            models.Index(fields=['-tournament_wins'], name='song_tournament_wins_idx'),
            models.Index(fields=['-total_wins'], name='song_total_wins_idx'),
            models.Index(fields=['-total_picks'], name='song_total_picks_idx'),
            models.Index(fields=['total_picks'], name='song_total_picks_gt_idx'),  # For filtering total_picks > 0
        ]
        
    def __str__(self):
        return f"{self.title} - {self.original_song}" if self.original_song else self.title
    
    @property
    def win_rate(self):
        """Tournament win rate: % of completed tournaments where this song was the final winner"""
        # Use cached value if available, otherwise calculate
        if hasattr(self, '_cached_completed_tournaments'):
            completed_tournaments = self._cached_completed_tournaments
        else:
            completed_tournaments = VotingSession.objects.filter(status='COMPLETED').count()
        
        if completed_tournaments == 0:
            return 0
        return (self.tournament_wins / completed_tournaments) * 100
    
    @property
    def pick_rate(self):
        """Pick rate: % of individual matches won by this song"""
        if self.total_picks == 0:
            return 0
        return (self.total_wins / self.total_picks) * 100


class VotingSession(models.Model):
    """Represents a user's voting session (like a tournament bracket for one user)"""
    SESSION_STATUS = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('ABANDONED', 'Abandoned'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voting_sessions', null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)  # For anonymous users
    
    # Store the randomized song bracket as JSON
    bracket_data = models.JSONField(default=dict)  # Store entire bracket structure
    current_round = models.PositiveIntegerField(default=1)
    current_match = models.PositiveIntegerField(default=1)
    
    status = models.CharField(max_length=10, choices=SESSION_STATUS, default='ACTIVE')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'voting_sessions'
        indexes = [
            models.Index(fields=['status'], name='voting_session_status_idx'),
            models.Index(fields=['user'], name='voting_session_user_idx'),
            models.Index(fields=['session_key'], name='voting_session_key_idx'),
            models.Index(fields=['-created_at'], name='voting_session_created_idx'),
        ]
        
    def __str__(self):
        user_str = self.user.username if self.user else f"Anonymous ({self.session_key})"
        return f"Session by {user_str} - Round {self.current_round}"
    
    
    @cached_property
    def progress_data(self):
        """Calculate overall tournament progress percentage with caching"""
        if self.status == 'COMPLETED':
            return {'percentage': 100, 'matches_completed': 'All', 'matches_total': 'All'}
        
        total_matches = 0
        completed_matches = 0
        
        for round_num in range(self.current_round + 1, 8):  # Count future rounds
            round_key = f"round_{round_num}"
            if round_key in self.bracket_data:
                total_matches += len(self.bracket_data[round_key])
        
        for round_num in range(1, self.current_round):  # Count completed rounds
            round_key = f"round_{round_num}"
            if round_key in self.bracket_data:
                total_matches += len(self.bracket_data[round_key])
                completed_matches += len(self.bracket_data[round_key])
        
        # Add current round
        round_key = f"round_{self.current_round}"
        if round_key in self.bracket_data:
            total_matches += len(self.bracket_data[round_key])
            completed_matches += (self.current_match - 1)
        
        if total_matches == 0:
            return {'percentage': 0, 'matches_completed': 0, 'matches_total': 0}
        
        percentage = (completed_matches / total_matches) * 100
        return {
            'percentage': round(percentage, 1),
            'matches_completed': completed_matches,
            'matches_total': total_matches
        }

    def calculate_progress(self):
        """Calculate overall tournament progress percentage (backward compatibility)"""
        return self.progress_data
    
    def get_current_match_data(self):
        """Get current match songs from bracket data"""
        if self.status == 'COMPLETED':
            return None
            
        if not self.bracket_data:
            return None
        
        round_key = f"round_{self.current_round}"
        if round_key not in self.bracket_data:
            return None
            
        matches = self.bracket_data[round_key]
        if self.current_match <= len(matches):
            return matches[self.current_match - 1]
        return None
    
    def advance_to_next_match(self):
        """Move to next match or round"""
        round_key = f"round_{self.current_round}"
        if round_key in self.bracket_data:
            total_matches = len(self.bracket_data[round_key])
            
            if self.current_match < total_matches:
                self.current_match += 1
            else:
                # Check if there's a next round
                next_round_key = f"round_{self.current_round + 1}"
                if next_round_key in self.bracket_data:
                    self.current_round += 1
                    self.current_match = 1
                else:
                    self.status = 'COMPLETED'
                    # Track tournament winner
                    self._record_tournament_winner()
        
        self.save()
    
    def _record_tournament_winner(self):
        """Record tournament winner when session completes"""
        # Find the winner from the final round
        final_round_key = f"round_{self.current_round}"
        if final_round_key in self.bracket_data:
            final_matches = self.bracket_data[final_round_key]
            if final_matches and final_matches[0].get('winner'):
                winner_data = final_matches[0]['winner']
                try:
                    winner_song = Song.objects.get(id=winner_data['id'])
                    winner_song.tournament_wins += 1
                    winner_song.save()
                except Song.DoesNotExist:
                    pass
    
    @cached_property
    def round_name_lookup(self):
        """Cached lookup table for round names"""
        total_rounds = len(self.bracket_data)
        if total_rounds == 7:  # 128 song tournament
            return {
                1: "Round of 64",
                2: "Round of 32", 
                3: "Round of 16",
                4: "Quarter-Finals",
                5: "Semi-Finals",
                6: "Finals",
                7: "Grand Finals"
            }
        return {}

    def get_round_name(self):
        """Get proper tournament round name"""
        return self.round_name_lookup.get(self.current_round, f"Round {self.current_round}")
    
    def get_match_progress(self):
        """Get current match progress (e.g., "2/64")"""
        round_key = f"round_{self.current_round}"
        if round_key in self.bracket_data:
            total_matches = len(self.bracket_data[round_key])
            return f"{self.current_match}/{total_matches}"
        return f"{self.current_match}/?"


class Match(models.Model):
    """Individual match within a voting session"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(VotingSession, on_delete=models.CASCADE, related_name='matches')
    round_number = models.PositiveIntegerField()
    match_number = models.PositiveIntegerField()
    
    song1 = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='matches_as_song1')
    song2 = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='matches_as_song2')
    winner = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='won_matches', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'matches'
        unique_together = ['session', 'round_number', 'match_number']
        
    def __str__(self):
        return f"R{self.round_number} M{self.match_number}: {self.song1} vs {self.song2}"


class Vote(models.Model):
    """Individual vote cast in a match"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='votes')
    session = models.ForeignKey(VotingSession, on_delete=models.CASCADE, related_name='votes')
    chosen_song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='received_votes')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'votes'
        
    def __str__(self):
        return f"Vote for {self.chosen_song.title} in {self.match}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    osu_user_id = models.BigIntegerField(unique=True)
    osu_username = models.CharField(max_length=100)
    avatar_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        
    def __str__(self):
        return f"{self.osu_username} ({self.user.username})"
