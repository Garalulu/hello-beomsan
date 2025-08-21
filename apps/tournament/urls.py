from django.urls import path
from . import views

urlpatterns = [
    path('start/', views.start_game, name='start_game'),
    path('vote/', views.vote, name='vote'),
    path('cast-vote/', views.cast_vote, name='cast_vote'),
    path('api/session-songs/', views.session_songs_api, name='session_songs_api'),
    path('stats/', views.song_stats, name='song_stats'),
    
    # Admin paths
    path('admin/upload/', views.upload_song, name='upload_song'),
    path('admin/upload-csv/', views.upload_csv, name='upload_csv'),
    path('admin/manage/', views.manage_songs, name='manage_songs'),
    path('admin/song/<uuid:song_id>/edit/', views.edit_song, name='edit_song'),
    path('admin/song/<uuid:song_id>/delete/', views.delete_song, name='delete_song'),
    
    # Tournament management
    path('admin/tournaments/', views.tournament_manage, name='tournament_manage'),
    path('admin/tournaments/ajax/', views.tournament_manage_ajax, name='tournament_manage_ajax'),
    path('admin/tournaments/history/', views.tournament_history, name='tournament_history'),
    path('admin/session/<uuid:session_id>/', views.session_detail, name='session_detail'),
    path('admin/session/<uuid:session_id>/ajax/', views.session_detail_ajax, name='session_detail_ajax'),
    
    # User management
    path('admin/users/', views.user_manage, name='user_manage'),
]