from django.contrib import admin
from .models import Song, VotingSession, Match, Vote, UserProfile


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ['title', 'artist', 'total_wins', 'total_losses', 'total_picks', 'win_rate', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'artist']
    readonly_fields = ['id', 'total_wins', 'total_losses', 'total_picks', 'created_at', 'updated_at']


@admin.register(VotingSession)
class VotingSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'session_key', 'status', 'current_round', 'current_match', 'created_at']
    list_filter = ['status', 'created_at']
    readonly_fields = ['id', 'bracket_data', 'created_at', 'updated_at']


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['session', 'round_number', 'match_number', 'song1', 'song2', 'winner', 'created_at']
    list_filter = ['round_number', 'created_at']
    readonly_fields = ['id', 'created_at']


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['session', 'match', 'chosen_song', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['id', 'created_at']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['osu_username', 'user', 'osu_user_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['osu_username', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
