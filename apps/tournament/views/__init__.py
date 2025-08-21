"""
Tournament views package - imports all views for backward compatibility

This package organizes views into focused modules:
- utils: Utility functions and decorators
- public: Public-facing views (home, start_game, vote, etc.)
- stats: Statistics views
- admin_songs: Song management admin views
- admin_tournaments: Tournament management admin views  
- admin_users: User management admin views

All views are re-exported here to maintain backward compatibility
with existing URL patterns and imports.
"""

# Import utility functions
from .utils import (
    validate_url,
    sanitize_input, 
    get_client_ip,
    rate_limit,
    convert_google_drive_url,
    clear_song_caches,
    check_duplicate_song
)

# Import public views
from .public import (
    home,
    start_game,
    vote,
    cast_vote,
    session_songs_api
)

# Import statistics views
from .stats import (
    song_stats
)

# Import admin song management views
from .admin_songs import (
    upload_song,
    manage_songs,
    edit_song,
    delete_song,
    upload_csv
)

# Import admin tournament management views
from .admin_tournaments import (
    tournament_manage,
    tournament_manage_ajax,
    tournament_history,
    session_detail,
    session_detail_ajax
)

# Import admin user management views
from .admin_users import (
    user_manage,
    user_stats_ajax
)

# Import health check views
from .health import (
    health_check
)

# Export all for backward compatibility
__all__ = [
    # Utility functions
    'validate_url',
    'sanitize_input',
    'get_client_ip', 
    'rate_limit',
    'convert_google_drive_url',
    'clear_song_caches',
    'check_duplicate_song',
    
    # Public views
    'home',
    'start_game', 
    'vote',
    'cast_vote',
    'session_songs_api',
    
    # Statistics views
    'song_stats',
    
    # Admin song management views
    'upload_song',
    'manage_songs',
    'edit_song',
    'delete_song',
    'upload_csv',
    
    # Admin tournament management views
    'tournament_manage',
    'tournament_manage_ajax',
    'tournament_history',
    'session_detail',
    'session_detail_ajax',
    
    # Admin user management views
    'user_manage',
    'user_stats_ajax',
    
    # Health check views
    'health_check'
]