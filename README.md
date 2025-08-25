# Song Tournament

A Django web application for song tournament voting system inspired by piku.co.kr. Users participate in World Cup-style elimination brackets with 128 randomly selected songs.

## Features

- **World Cup Style Tournament**: 128 songs randomly seeded into elimination brackets with winner reshuffling between rounds
- **osu! OAuth Integration**: Login with osu! accounts for progress saving and session recovery
- **Anonymous Play**: Robust anonymous voting with session persistence across production environments
- **Session-based Voting**: Each user gets randomly seeded tournaments with proper session flow management
- **Google Drive Storage**: Audio and background images stored on Google Drive with optimized loading
- **Real-time Statistics**: Song win rates and pick rates tracking with comprehensive user management
- **Admin Interface**: Full CRUD operations for songs, tournament management, and user administration
- **Enhanced Result Screen**: Winner display with background images, golden borders, and centered statistics
- **Modern Django Architecture**: Apps, config, core services separation with proper error handling
- **Component-based Templates**: Reusable UI components and organized template structure

## Tech Stack

- **Framework**: Django 5.2.5
- **Database**: SQLite with LiteFS distributed replication
- **Authentication**: osu! OAuth 2.0
- **Frontend**: Bootstrap 5 with custom CSS/JS
- **File Storage**: Google Drive URLs
- **Deployment**: Fly.io with Docker and GitHub Actions CI/CD
- **Distributed Storage**: LiteFS for SQLite replication and persistence

## Quick Start

### Local Development

#### Quick Setup (Windows)
```bash
# Clone the repository
git clone <repository-url>
cd hello-beomsan

# Run automated setup
dev-setup.bat
```

#### Manual Setup (All Platforms)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd hello-beomsan
   ```

2. **Set up Python environment**
   ```bash
   # Using uv (recommended)
   uv venv .venv
   .venv/Scripts/activate  # Windows
   # or source .venv/bin/activate  # Linux/Mac
   
   # Install dependencies
   uv pip install -r requirements/base.txt -r requirements/development.txt
   ```

3. **Set up environment variables**
   ```bash
   # Copy example environment file
   cp .env.example .env
   
   # Edit .env file with your osu! OAuth credentials
   # Get them from: https://osu.ppy.sh/home/account/edit
   ```

4. **Run migrations and start server**
   ```bash
   python manage.py migrate --settings=config.settings.development
   python manage.py runserver --settings=config.settings.development
   ```

#### Development Commands

Use the included `Makefile` for common tasks:

```bash
make help          # Show all available commands
make dev           # Install development dependencies  
make run           # Start development server
make test          # Run tests
make test-cov      # Run tests with coverage
make format        # Format code with black and isort
make lint          # Run linting
make migrate       # Run database migrations
make admin         # Promote admin user
```

### Production Deployment (Fly.io)

The app uses **GitHub Actions** for automated deployment. Simply push to the `master` branch to trigger deployment.

#### Manual Setup (one-time)

1. **Install Fly CLI and authenticate**
   ```bash
   fly auth login
   ```

2. **Create LiteFS volume for distributed database**
   ```bash
   fly volumes create litefs --size 10 --region nrt --app hello-beomsan --yes
   ```

3. **Attach Consul for lease management**
   ```bash
   fly consul attach --app hello-beomsan
   ```

4. **Set up environment variables**
   ```bash
   fly secrets set OSU_CLIENT_ID="your_osu_client_id"
   fly secrets set OSU_CLIENT_SECRET="your_osu_client_secret"
   fly secrets set OSU_REDIRECT_URI="https://your-app.fly.dev/auth/callback/"
   ```

#### Automatic Deployment

The app automatically deploys via GitHub Actions when pushing to master. LiteFS handles:
- **Distributed SQLite**: Automatic replication across regions
- **Primary election**: Consul-based leader election
- **Database migrations**: Run automatically on primary node
- **Admin promotion**: "Garalulu" promoted to admin
- **Static files**: Collected and served with WhiteNoise

## Configuration

### osu! OAuth Setup

1. Go to [osu! OAuth Applications](https://osu.ppy.sh/home/account/edit)
2. Create a new OAuth application
3. Set redirect URI to: `https://your-app.fly.dev/auth/callback/`
4. Set environment variables:
   - `OSU_CLIENT_ID`
   - `OSU_CLIENT_SECRET`
   - `OSU_REDIRECT_URI`

### Google Drive Setup

For audio/image files:
1. Upload files to Google Drive
2. Set sharing to "Anyone with the link can view"
3. Use these URL formats:
   - **Audio**: `https://drive.google.com/uc?export=download&id=FILE_ID`
   - **Images**: `https://drive.google.com/uc?export=view&id=FILE_ID`

## Project Structure

```
hello-beomsan/
├── apps/                     # Django applications
│   ├── tournament/          # Main app for voting logic
│   │   ├── models.py       # Song, VotingSession, Match, Vote models
│   │   ├── views/          # Organized view modules
│   │   │   ├── __init__.py    # Re-exports all views for compatibility
│   │   │   ├── utils.py       # Validation, caching, security utilities
│   │   │   ├── public.py      # Public views (home, voting, etc.)
│   │   │   ├── stats.py       # Song statistics views
│   │   │   ├── admin_songs.py # Song management admin views
│   │   │   ├── admin_tournaments.py # Tournament management views
│   │   │   └── admin_users.py # User management admin views
│   │   ├── admin.py        # Django admin configuration
│   │   ├── urls.py         # Tournament URL patterns
│   │   ├── tests.py        # Tournament app tests
│   │   └── management/     # Custom Django commands
│   │       └── commands/   # Import songs, promote admin
│   └── accounts/           # osu! OAuth integration
│       ├── models.py       # User profile model
│       ├── views.py        # Authentication views
│       ├── urls.py         # Auth URL patterns
│       └── tests.py        # Authentication tests
├── config/                  # Configuration files
│   ├── settings/           # Environment-specific settings
│   │   ├── base.py        # Common settings
│   │   ├── development.py  # Development settings
│   │   ├── production.py   # Production settings
│   │   └── testing.py      # Test settings
│   ├── urls.py            # Root URL configuration
│   ├── wsgi.py            # WSGI application
│   └── asgi.py            # ASGI application
├── core/                   # Business logic & services
│   ├── services/          # Business logic services
│   │   ├── tournament_service.py # Tournament operations
│   │   └── accounts_service.py   # OAuth services
│   └── utils/             # Utility functions
├── templates/              # Component-based templates
│   ├── base/              # Base templates & partials
│   │   ├── base.html      # Main base template
│   │   └── partials/      # Reusable template parts
│   ├── components/        # UI components
│   │   ├── song_card.html # Reusable song card
│   │   ├── progress_bar.html # Progress component
│   │   └── pagination.html # Pagination component
│   └── pages/             # Page templates
│       ├── main/          # Main app pages
│       └── admin/         # Admin pages
├── requirements/           # Environment-specific requirements
│   ├── base.txt           # Core dependencies
│   ├── development.txt    # Dev tools & testing
│   ├── production.txt     # Production-specific
│   └── testing.txt        # Testing-only deps
├── tests/                  # Centralized testing
│   ├── test_comprehensive.py # Comprehensive test suite
│   ├── test_error_handling.py # Error handling tests
│   ├── test_models_complete.py # Model tests
│   └── test_views_complete.py # View tests
├── .github/workflows/      # GitHub Actions CI/CD
├── dev-setup.bat          # Windows development setup script
├── dev-start.bat          # Windows development start script
├── Dockerfile             # Production Docker configuration
├── Dockerfile.dev         # Development Docker configuration
├── docker-compose.yml     # Local development with Docker
├── fly.toml              # Fly.io deployment config with LiteFS
├── litefs.yml            # LiteFS configuration for distributed SQLite
├── Makefile              # Development commands
├── pyproject.toml        # Modern Python project configuration
├── manage.py             # Django management
├── .env.example          # Environment variables template
├── CLAUDE.md             # Development instructions for Claude Code
└── README.md             # This file
```

## Usage

1. **Home Page**: Start new tournament or continue existing session
2. **Voting**: Listen to two songs, choose your favorite
3. **Progress**: Automatic saving for logged-in users
4. **Statistics**: View song performance metrics
5. **Admin Features** (staff users only):
   - Add/edit/delete songs with Google Drive URL conversion
   - Upload songs via CSV with comprehensive validation
   - View active tournament sessions with real-time updates
   - Tournament history and statistics with filtering
   - User management with session counts and search functionality

## Development Features

- **Modern Django Structure**: Apps, config, core services separation for maintainability
- **Organized Views Architecture**: Views split into focused modules (public, admin, utilities) for better maintainability
- **Environment-specific Settings**: Development, production, and testing configurations with OAuth-compatible session handling
- **Service Layer Pattern**: Business logic separated from views in core services with session preference management
- **Component-based Templates**: Reusable UI components and organized template structure with enhanced result displays
- **Centralized Testing**: All tests organized in dedicated tests/ directory with comprehensive session flow testing
- **Modern Python Setup**: pyproject.toml, uv package manager, split requirements files
- **Code Quality**: Black formatting, isort imports, flake8 linting, pytest testing
- **Development Tools**: Makefile commands, automated setup scripts, .env templates
- **Comprehensive Error Handling**: Robust error handling with production-friendly session recovery
- **Logging**: Detailed logging for debugging and monitoring with OAuth state tracking
- **CSRF Protection**: Full CSRF protection on all forms and AJAX requests
- **Session Management**: Secure session handling with cross-environment persistence for anonymous and authenticated users
- **Input Sanitization**: Proper HTML entity handling for song name storage and display
- **Rate Limiting**: Tournament-aware rate limiting with velocity checks and abuse prevention
- **LiteFS Distribution**: Distributed SQLite with automatic replication and failover

## Production Features

- **LiteFS**: Distributed SQLite database with multi-region replication
- **Consul Integration**: Leader election and lease management
- **GitHub Actions**: Automated CI/CD pipeline
- **Docker**: Containerized deployment with optimized images
- **WhiteNoise**: Static file serving without external CDN
- **Error Monitoring**: Comprehensive logging and error tracking
- **Session Persistence**: Production-ready anonymous user session handling with recovery mechanisms
- **OAuth Security**: Secure osu! OAuth integration with proper state management and session cookie configuration

## Recent Improvements

### 📊 Fibonacci Ranking System
- **Intelligent Song Ranking**: Implemented two-tier fibonacci-weighted ranking system for song statistics
- **Tournament Winners First**: Champions always rank above non-winners, maintaining competitive integrity
- **Round Performance Weighted**: Later rounds worth exponentially more (Finals=13x, Semis=8x, Quarters=5x, etc.)
- **Clean Statistics UI**: Streamlined sort options to "Overall Ranking" and "Pick Rate" for better user experience
- **Database Optimized**: Added custom indexes for efficient fibonacci score calculations
- **Backward Compatible**: Works with all existing tournament data and match history

### 🎯 Session Management & User Experience
- **Fixed Anonymous User Voting**: Resolved session persistence issues preventing anonymous users from completing tournaments
- **Enhanced Session Flow**: Improved start/continue session logic with proper COMPLETED vs ACTIVE session handling
- **OAuth State Management**: Fixed OAuth login issues in production with proper session cookie SameSite configuration
- **Winner Reshuffling**: Implemented random reshuffling of winners between tournament rounds instead of traditional bracket order

### 🎨 UI/UX Enhancements
- **Enhanced Result Screen**: Added winner background images with golden borders matching voting card design
- **Centered Statistics**: Improved tournament duration display with better typography and centering
- **Fallback Design**: Beautiful gradient placeholder for songs without background images
- **Input Sanitization**: Fixed HTML entity conversion issues (&#39; to ') in song name editing
- **Static File Organization**: Moved CSS/JS from templates to proper static directory structure

### 🛠️ Admin & Management
- **User Management**: Fixed data display and search functionality in admin user management interface
- **Tournament Aware Rate Limiting**: Enhanced rate limiting system allowing tournament completion while preventing abuse
- **CSV Upload Validation**: Comprehensive validation for CSV song uploads with special character support
- **Real-time Session Monitoring**: Improved admin dashboard with live session updates and detailed statistics

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the MIT License.