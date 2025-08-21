# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django 5.2.5 web application for a song tournament voting system inspired by piku.co.kr. Users vote in head-to-head battles between songs in a World Cup-style elimination bracket with 128 randomly selected songs.

## Architecture

- **Framework**: Django 5.2.5 with modern project structure
- **Database**: SQLite (db.sqlite3) for local development
- **Authentication**: osu! OAuth 2.0 integration
- **File Storage**: Google Drive URLs for audio and background images
- **Frontend**: Bootstrap 5 with custom CSS and JavaScript
- **WSGI Server**: Gunicorn for production deployment

## ✅ PROJECT REORGANIZATION STATUS

**Status**: COMPLETED - Modern Django Structure Implementation

### Completed:
1. ✅ Created modern directory structure:
   - `apps/` - All Django applications
   - `config/` - Configuration files and settings
   - `core/` - Business logic and services
   - `static/` - Static files
   - `templates/` - Template files
   - `tests/` - Centralized testing
   - `requirements/` - Environment-specific requirements

2. ✅ Environment-specific settings structure:
   - `config/settings/base.py` - Common settings
   - `config/settings/development.py` - Development settings
   - `config/settings/production.py` - Production settings
   - `config/settings/testing.py` - Test settings

3. ✅ Moved apps to new structure:
   - `apps/tournament/` - Tournament logic
   - `apps/accounts/` - Authentication & user management

4. ✅ Updated configuration files:
   - `config/wsgi.py` - WSGI application
   - `config/asgi.py` - ASGI application
   - `config/urls.py` - Root URL configuration
   - `manage.py` - Management commands

5. ✅ Started core services layer:
   - `core/services/tournament_service.py` - Tournament business logic

### ✅ Completed Reorganization:
6. ✅ Moved remaining services to core layer
7. ✅ Updated all import statements in views and models
8. ✅ Reorganized templates with component-based structure
9. ✅ Created requirements structure (dev/prod/test)
10. ✅ Updated all imports throughout the codebase
11. ✅ Tested the reorganized structure
12. ✅ Updated deployment configurations

### New Project Structure:
```
hello_beomsan/
├── apps/                          # Django applications
│   ├── accounts/                  # Authentication & user management
│   └── tournament/                # Tournament logic
├── config/                        # Configuration files
│   ├── settings/                  # Environment-specific settings
│   │   ├── base.py               # Common settings
│   │   ├── development.py        # Development settings
│   │   ├── production.py         # Production settings
│   │   └── testing.py            # Test settings
│   ├── urls.py                   # Root URL configuration
│   ├── wsgi.py                   # WSGI application
│   └── asgi.py                   # ASGI application
├── core/                          # Business logic & services
│   ├── services/                  # Business logic services
│   │   ├── tournament_service.py  # Tournament operations
│   │   └── accounts_service.py    # OAuth services
│   ├── utils/                     # Utility functions
│   └── exceptions.py              # Custom exceptions
├── templates/                     # Component-based templates
│   ├── base/                      # Base templates & partials
│   │   ├── base.html             # Main base template
│   │   └── partials/             # Reusable template parts
│   ├── components/                # UI components
│   │   ├── song_card.html        # Reusable song card
│   │   ├── progress_bar.html     # Progress component
│   │   └── pagination.html       # Pagination component
│   ├── pages/                     # Page templates
│   │   ├── main/                 # Main app pages
│   │   └── admin/                # Admin pages
│   └── emails/                    # Email templates (future)
├── requirements/                  # Environment-specific requirements
│   ├── base.txt                  # Core dependencies
│   ├── development.txt           # Dev tools & testing
│   ├── production.txt            # Production-specific
│   └── testing.txt               # Testing-only deps
├── static/                        # Static files
├── tests/                         # Centralized testing
│   ├── test_comprehensive.py     # Comprehensive test suite
│   ├── test_error_handling.py    # Error handling tests
│   ├── test_models_complete.py   # Model tests
│   └── test_views_complete.py    # View tests
└── manage.py                      # Django management
```

### Updated Settings Usage:
- Development: `DJANGO_SETTINGS_MODULE=config.settings.development`
- Production: `DJANGO_SETTINGS_MODULE=config.settings.production`
- Testing: `DJANGO_SETTINGS_MODULE=config.settings.testing`

### Important Notes:
- All imports need to be updated from old structure to new structure
- Services moved from `apps.tournament.services` to `core.services.tournament_service`
- Apps now use `apps.` prefix in imports and INSTALLED_APPS
- Configuration now uses `config.` prefix instead of `hello_beomsan.`

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
python manage.py shell -c "from core.services.tournament_service import VotingSessionService; VotingSessionService.create_voting_session()"

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
- you should use && source .venv/Scripts/activate for venv
- please do not insert unicode emoji when testing, especially using Windows console.