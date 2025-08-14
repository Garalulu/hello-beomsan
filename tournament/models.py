from django.db import models
from django.contrib.auth.models import User
import uuid
import json


class Song(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    artist = models.CharField(max_length=200, blank=True)
    audio_url = models.URLField(max_length=500)  # Google Drive direct download URL
    background_image_url = models.URLField(max_length=500, blank=True)  # Google Drive image URL
    
    # Statistics
    total_wins = models.PositiveIntegerField(default=0)
    total_losses = models.PositiveIntegerField(default=0)
    total_picks = models.PositiveIntegerField(default=0)  # How many times this song appeared in matches
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'songs'
        
    def __str__(self):
        return f"{self.title} - {self.artist}" if self.artist else self.title
    
    @property
    def win_rate(self):
        if self.total_picks == 0:
            return 0
        return (self.total_wins / self.total_picks) * 100
    
    @property
    def pick_rate(self):
        # Calculate how often this song is picked relative to total votes
        total_votes = Vote.objects.count()
        if total_votes == 0:
            return 0
        return (self.total_picks / total_votes) * 100


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
        
    def __str__(self):
        user_str = self.user.username if self.user else f"Anonymous ({self.session_key})"
        return f"Session by {user_str} - Round {self.current_round}"
    
    def get_current_match_data(self):
        """Get current match songs from bracket data"""
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
        
        self.save()


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
