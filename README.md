# Arva - Project Management System

Trello-like project management system built with Django.

## Setup Instructions

### 1. Clone Repository
```bash
git clone <repository-url>
cd kanban
```

### 2. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env`:
```bash
copy .env.example .env  # Windows
cp .env.example .env  # Linux/Mac
```

Edit `.env` file and fill in your actual values:
- Database credentials
- Google OAuth credentials
- Email settings
- Gemini API key (for AI features)

### 5. Configure Settings

Copy `arviga/settings.example.py` to `arviga/settings.py`:
```bash
copy arviga\settings.example.py arviga\settings.py  # Windows
cp arviga/settings.example.py arviga/settings.py  # Linux/Mac
```

Update database settings if needed.

### 6. Run Migrations
```bash
python manage.py migrate
```

### 7. Create Superuser
```bash
python manage.py createsuperuser
```

### 8. Run Development Server
```bash
python manage.py runserver
```

Access the application at `http://127.0.0.1:8000/`

## Features

- **Project Management**: Create and manage projects with task boards
- **Task Management**: Kanban-style task boards with drag-and-drop
- **AI Assistant**: Chat with AI about your tasks and get priority recommendations
- **Team Collaboration**: Assign members, track progress, and collaborate
- **Google OAuth**: Login with Google account
- **Email Notifications**: Get notified about task assignments

## Security Notes

⚠️ **Never commit sensitive information!**

The following files are git-ignored for security:
- `.env` - Contains API keys and credentials
- `arviga/settings.py` - Local settings configuration
- `db.sqlite3` - Database file
- `media/` - User uploaded files

Always use environment variables for sensitive data.
