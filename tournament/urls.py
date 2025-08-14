from django.urls import path
from . import views

urlpatterns = [
    path('start/', views.start_game, name='start_game'),
    path('vote/', views.vote, name='vote'),
    path('cast-vote/', views.cast_vote, name='cast_vote'),
    path('stats/', views.song_stats, name='song_stats'),
    
    # Admin paths
    path('admin/upload/', views.upload_song, name='upload_song'),
    path('admin/manage/', views.manage_songs, name='manage_songs'),
    path('admin/song/<uuid:song_id>/delete/', views.delete_song, name='delete_song'),
]