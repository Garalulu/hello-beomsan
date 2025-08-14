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
- **Database**: SQLite (development), PostgreSQL (production ready)
- **Authentication**: osu! OAuth 2.0
- **Frontend**: Bootstrap 5 with custom CSS/JS
- **File Storage**: Google Drive URLs
- **Deployment**: Fly.io with Docker

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd hello-beomsan
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   export OSU_CLIENT_ID="your_osu_client_id"
   export OSU_CLIENT_SECRET="your_osu_client_secret"
   export OSU_REDIRECT_URI="http://localhost:8000/auth/callback/"
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start development server**
   ```bash
   python manage.py runserver
   ```

### Production Deployment (Fly.io)

1. **Install Fly CLI and authenticate**
   ```bash
   fly auth login
   ```

2. **Deploy**
   ```bash
   fly deploy
   ```

The app will automatically:
- Run database migrations
- Promote "Garalulu" to admin (if they exist)
- Start the server

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
│   ├── services.py     # Business logic for tournaments
│   ├── views.py        # Web views and API endpoints
│   └── management/     # Custom Django commands
├── accounts/           # osu! OAuth integration
├── templates/          # HTML templates
│   ├── main/          # Voting interface templates
│   └── admin/         # Song management templates
├── static/            # CSS, JS, images
├── Dockerfile         # Docker configuration
├── fly.toml          # Fly.io deployment config
└── requirements.txt   # Python dependencies
```

## Usage

1. **Home Page**: Start new tournament or continue existing session
2. **Voting**: Listen to two songs, choose your favorite
3. **Progress**: Automatic saving for logged-in users
4. **Statistics**: View song performance metrics
5. **Admin**: Add/manage songs (staff users only)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the MIT License.