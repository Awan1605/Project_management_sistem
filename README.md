# Arviga Project Manager

[![Django](https://img.shields.io/badge/Django-5.x-green.svg)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-orange.svg)](https://www.mysql.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A powerful project management application inspired by Trello, built with Django. Features Kanban boards, AI-powered task prioritization, team collaboration, and real-time updates.

![Arviga Dashboard](media/branding/logo/logo-arviga.png)

## Features

### Core Project Management
- **Kanban Board**: Drag-and-drop task management with customizable lists
- **Project Organization**: Create projects with subprojects for better structure
- **Role-Based Access Control**: Admin, Member, and Viewer roles per project
- **Task Visibility**: Smart visibility - Admins see all tasks, members see only assigned tasks

### Task Management
- **Rich Tasks**: Comments, attachments, checklists, and due dates
- **Task Assignment**: Assign tasks to team members with clear ownership
- **Archive & Restore**: Archive completed projects and restore when needed
- **Activity Log**: Track all changes and activities in real-time

### AI Integration
- **AI-Powered Priority Queue**: Machine learning model analyzes and prioritizes tasks
- **Smart Recommendations**: AI suggests task priorities based on deadlines, complexity, and workload
- **AI Chat Assistant**: Built-in AI assistant for project insights

### User Experience
- **Real-time Updates**: AJAX-powered interface without page reloads
- **My Cards View**: See all your assigned tasks across projects in one place
- **Responsive Design**: Modern Bootstrap 5 UI with mobile-friendly interface
- **Google OAuth**: Easy login with Google account

## Tech Stack

- **Backend**: Django 5.x, Python 3.10+
- **Database**: MySQL 8.0+ (with UTF8MB4 support)
- **Frontend**: Bootstrap 5, jQuery, jQuery UI
- **AI/ML**: scikit-learn, Google Gemini API
- **Authentication**: Django allauth (Google OAuth)
- **Task Queue**: Django Q (optional)

## Installation

### Prerequisites
- Python 3.10 or higher
- MySQL 8.0 or higher
- Virtual environment (recommended)

### Step 1: Clone Repository
```bash
git clone https://github.com/yourusername/arviga.git
cd arviga
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
```bash
cp .env.example .env
```

Edit `.env` file with your configuration:
- Database credentials
- Secret key (generate new one for production)
- Google OAuth credentials (optional)
- Email SMTP settings
- AI API keys (optional)

### Step 5: Create Database
```sql
CREATE DATABASE arviga_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Step 6: Run Migrations
```bash
python manage.py migrate
```

### Step 7: Create Superuser
```bash
python manage.py createsuperuser
```

### Step 8: Collect Static Files (Production)
```bash
python manage.py collectstatic
```

### Step 9: Run Development Server
```bash
python manage.py runserver
```

Access the application at `http://127.0.0.1:8000`

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DEBUG` | Debug mode (True/False) | Yes |
| `SECRET_KEY` | Django secret key | Yes |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | Yes |
| `DB_NAME` | Database name | Yes |
| `DB_USER` | Database username | Yes |
| `DB_PASSWORD` | Database password | Yes |
| `DB_HOST` | Database host | Yes |
| `DB_PORT` | Database port | Yes |
| `EMAIL_HOST` | SMTP server host | No |
| `EMAIL_HOST_USER` | SMTP username | No |
| `EMAIL_HOST_PASSWORD` | SMTP password | No |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth Client ID | No |
| `GOOGLE_OAUTH_SECRET` | Google OAuth Secret | No |
| `GEMINI_API_KEY` | Google Gemini API Key | No |

### Production Deployment

1. Set `DEBUG=False` in `.env`
2. Configure `ALLOWED_HOSTS` with your domain
3. Set up HTTPS and configure `CSRF_TRUSTED_ORIGINS`
4. Use a production WSGI server (Gunicorn, uWSGI)
5. Configure a reverse proxy (Nginx, Apache)
6. Set up proper database backups

See `deploy/settings-hosting.py` for hosting-specific configurations.

## Project Structure

```
arviga/
├── arva/                   # Main application
│   ├── models.py          # Database models
│   ├── views/             # View modules (organized by domain)
│   ├── templates/         # HTML templates
│   ├── static/           # CSS, JS, images
│   ├── ai_*.py           # AI-related modules
│   └── management/       # Custom management commands
├── arviga/               # Project configuration
│   ├── settings.py       # Main settings
│   ├── urls.py          # URL routing
│   └── wsgi.py          # WSGI entry point
├── media/               # User uploads (avatars, attachments)
├── static/              # Static assets
├── templates/           # Global templates
├── scripts/             # Utility scripts
├── requirements.txt     # Python dependencies
└── .env.example        # Environment template
```

## Security Considerations

- Never commit `.env` file to version control
- Use strong `SECRET_KEY` in production (min 50 characters)
- Enable HTTPS in production (`SECURE_SSL_REDIRECT=True`)
- Regularly update dependencies
- Use environment-specific database credentials
- Keep backup of uploaded media files

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, email support@arviga.co.id or create an issue in the repository.

## Acknowledgments

- Built with [Django](https://www.djangoproject.com/)
- UI powered by [Bootstrap 5](https://getbootstrap.com/)
- Icons by [Bootstrap Icons](https://icons.getbootstrap.com/)
- AI features powered by [Google Gemini](https://ai.google.dev/)

---

**Arviga Project Manager** - Manage your projects smarter with AI assistance.
