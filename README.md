# Song Tournament

A Django web application for song tournament voting system inspired by piku.co.kr. Users participate in World Cup-style elimination brackets with 128 randomly selected songs.

## Features

- **World Cup Style Tournament**: 128 songs randomly seeded into elimination brackets
- **osu! OAuth Integration**: Login with osu! accounts for progress saving
- **Anonymous Play**: Play without registration (progress not saved)
- **Session-based Voting**: Each user gets randomly seeded tournaments
- **Google Drive Storage**: Audio and background images stored on Google Drive
- **Real-time Statistics**: Song win rates and pick rates tracking
- **Admin Interface**: Add and manage songs with staff privileges

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
   uv pip install -r requirements.txt -r requirements-dev.txt
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
   python manage.py migrate
   python manage.py runserver
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
├── tournament/          # Main app for voting logic
│   ├── models.py       # Song, VotingSession, Match, Vote models
│   ├── services.py     # Business logic with error handling
│   ├── views.py        # Web views and API endpoints
│   ├── admin.py        # Django admin configuration
│   ├── file_handlers.py # File upload handlers (for future use)
│   └── management/     # Custom Django commands
├── accounts/           # osu! OAuth integration
│   ├── services.py     # OAuth service with error handling
│   ├── views.py        # Authentication views
│   └── urls.py         # Auth URL patterns
├── templates/          # HTML templates
│   ├── main/          # Voting interface templates
│   └── admin/         # Song management templates
├── .github/workflows/  # GitHub Actions CI/CD
├── dev-setup.bat      # Windows development setup script
├── dev-start.bat      # Windows development start script
├── Dockerfile         # Production Docker configuration
├── Dockerfile.dev     # Development Docker configuration
├── docker-compose.yml # Local development with Docker
├── fly.toml          # Fly.io deployment config with LiteFS
├── litefs.yml        # LiteFS configuration for distributed SQLite
├── Makefile          # Development commands
├── pyproject.toml    # Modern Python project configuration
├── requirements.txt   # Production dependencies
├── requirements-dev.txt # Development dependencies
├── .env.example      # Environment variables template
├── CLAUDE.md         # Development instructions for Claude Code
└── README.md         # This file
```

## Usage

1. **Home Page**: Start new tournament or continue existing session
2. **Voting**: Listen to two songs, choose your favorite
3. **Progress**: Automatic saving for logged-in users
4. **Statistics**: View song performance metrics
5. **Admin Features** (staff users only):
   - Add/edit/delete songs
   - View active tournament sessions
   - Tournament history and statistics
   - User management

## Development Features

- **Modern Python Setup**: pyproject.toml, uv package manager, development dependencies
- **Code Quality**: Black formatting, isort imports, flake8 linting, pytest testing
- **Development Tools**: Makefile commands, automated setup scripts, .env templates
- **Comprehensive Error Handling**: Robust error handling across all components
- **Logging**: Detailed logging for debugging and monitoring
- **CSRF Protection**: Full CSRF protection on all forms and AJAX requests
- **Session Management**: Secure session handling for anonymous and authenticated users
- **LiteFS Distribution**: Distributed SQLite with automatic replication and failover

## Production Features

- **LiteFS**: Distributed SQLite database with multi-region replication
- **Consul Integration**: Leader election and lease management
- **GitHub Actions**: Automated CI/CD pipeline
- **Docker**: Containerized deployment with optimized images
- **WhiteNoise**: Static file serving without external CDN
- **Error Monitoring**: Comprehensive logging and error tracking

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the MIT License.