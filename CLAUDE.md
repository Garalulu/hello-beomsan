# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django 5.2.5 web application for a song tournament voting system inspired by piku.co.kr. Users vote in head-to-head battles between songs in a World Cup-style elimination bracket with 128 randomly selected songs.

## Architecture

- **Framework**: Django 5.2.5 with two main apps: `tournament` and `accounts`
- **Database**: SQLite (db.sqlite3) for local development
- **Authentication**: osu! OAuth 2.0 integration
- **File Storage**: Google Drive URLs for audio and background images
- **Frontend**: Bootstrap 5 with custom CSS and JavaScript
- **WSGI Server**: Gunicorn for production deployment

## Core Models

### Tournament App
- **Song**: Individual songs with Google Drive URLs for audio/images, plus statistics
- **VotingSession**: User's tournament session with JSON bracket data and progress tracking
- **Match**: Individual song battles within a session
- **Vote**: Records each vote cast in matches
- **UserProfile**: osu! user data linked to Django User

### Key Features
- Session-based voting (not multiple tournaments)
- 128 songs randomly selected per session
- Progress saving for logged-in users
- Anonymous voting support
- Real-time statistics (win rate, pick rate)
- Complete bracket visualization

## URL Structure

```
/                          # Home page with start game button
/game/start/              # Start new session or continue existing
/game/vote/               # Main voting interface
/game/cast-vote/          # AJAX vote submission
/game/stats/              # Song statistics page
/game/admin/upload/       # Admin: Add songs (staff only)
/game/admin/manage/       # Admin: Manage songs (staff only)
/auth/login/              # osu! OAuth login
/auth/logout/             # Logout
/auth/callback/           # OAuth callback
/auth/profile/            # User profile
```

## Common Commands

### Development
```bash
# Start development server
python manage.py runserver

# Run Django shell
python manage.py shell

# Check for issues
python manage.py check
```

### Database Operations
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### Custom Management Commands
```bash
# Create voting session programmatically
python manage.py shell -c "from tournament.services import VotingSessionService; VotingSessionService.create_voting_session()"

# Import songs from CSV (if implemented)
python manage.py import_songs songs.csv --audio-dir /path/to/audio --image-dir /path/to/images
```

## Key Services

### VotingSessionService (tournament/services.py)
- `create_voting_session()`: Creates new 128-song bracket
- `get_current_match()`: Gets current voting match
- `cast_vote()`: Processes vote and advances session
- `get_or_create_session()`: Handles session continuation

### OsuOAuthService (accounts/services.py)
- `get_authorization_url()`: Generates osu! OAuth URL
- `authenticate_user()`: Completes OAuth flow
- `create_or_update_user()`: Manages user/profile creation

## File Structure

```
tournament/
├── models.py           # Core data models
├── services.py         # Business logic services
├── views.py           # View handlers
├── admin.py           # Django admin configuration
└── management/
    └── commands/      # Custom management commands

accounts/
├── services.py        # osu! OAuth integration
├── views.py          # Authentication views
└── urls.py           # Auth URL routing

templates/
├── base.html         # Base template with Bootstrap
├── main/             # Main voting interface templates
│   ├── home.html     # Landing page
│   ├── start_game.html # Session start/continue
│   ├── vote.html     # Voting interface
│   ├── completed.html # Tournament completion
│   └── stats.html    # Song statistics
└── admin/            # Admin interface templates
```

## Google Drive Integration

Songs use Google Drive URLs:
- **Audio**: `https://drive.google.com/uc?export=download&id=FILE_ID`
- **Images**: `https://drive.google.com/uc?export=view&id=FILE_ID`
- Files must be publicly accessible ("Anyone with link can view")

## Development Notes

- Session data stored in `VotingSession.bracket_data` as JSON
- Anonymous users identified by `session_key`
- Logged-in users can continue interrupted sessions
- Statistics updated in real-time during voting
- Bootstrap 5 with custom CSS for song cards and voting UI
- Audio players auto-pause when another starts playing
- Test everything the changes locally first before committing
- use uv for python command
- Commit and push the changes after test is finished well
- Fix SSH console "handle is invalid" error on Windows - use GitHub Actions for deployment