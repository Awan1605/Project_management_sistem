# Getting Started

<cite>
**Referenced Files in This Document**
- [README.txt](file://README.txt)
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md)
- [manage.py](file://manage.py)
- [arviga/settings.py](file://arviga/settings.py)
- [settings-hosting.py](file://settings-hosting.py)
- [arviga/urls.py](file://arviga/urls.py)
- [arviga/wsgi.py](file://arviga/wsgi.py)
- [arviga/asgi.py](file://arviga/asgi.py)
- [arva/apps.py](file://arva/apps.py)
- [arva/models.py](file://arva/models.py)
- [arva/migrations/0001_initial.py](file://arva/migrations/0001_initial.py)
- [arva/migrations/0005_project_etd_project_is_project_project_pm_assignee_and_more.py](file://arva/migrations/0005_project_etd_project_is_project_project_pm_assignee_and_more.py)
- [requirements.txt](file://requirements.txt)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Local Development Setup](#local-development-setup)
4. [Database Setup](#database-setup)
5. [Initial Configuration](#initial-configuration)
6. [Running the Application](#running-the-application)
7. [Production Deployment Considerations](#production-deployment-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Next Steps](#next-steps)

## Introduction
This guide walks you through setting up the Arva Kanban project locally and preparing it for production. It covers environment setup, database preparation, Django migrations, superuser creation, and running the development server. It also includes troubleshooting tips for common issues encountered during installation and configuration.

## Prerequisites
Before installing Arva Kanban, ensure your system meets the following requirements:
- Python 3.11 or newer
- MySQL 8.0 or newer
- pip (Python package installer)

These requirements align with the project’s use of Django and MySQL, and the documented setup procedure.

**Section sources**
- [README.txt](file://README.txt#L16-L18)
- [arviga/settings.py](file://arviga/settings.py#L58-L68)

## Local Development Setup
Follow these steps to prepare your local environment:

1) Create a virtual environment
- Create a new virtual environment using your preferred method (e.g., venv or virtualenv).
- Activate the virtual environment before proceeding.

2) Install project dependencies
- Install the required Python packages using pip with the provided requirements file.
- Command reference: [Install dependencies](file://SETUP_GUIDE.md#L71-L82)

Notes:
- The project uses Django and several third-party packages managed via pip.
- The requirements file is referenced in the setup guide.

**Section sources**
- [README.txt](file://README.txt#L16-L18)
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md#L69-L83)

## Database Setup
The project uses MySQL by default. Follow these steps to configure the database:

1) Create the database
- Create a MySQL database with the appropriate character set and collation.
- Example command: [Create database](file://README.txt#L20-L21)

2) Configure database connection
- Update the Django database settings to match your MySQL credentials.
- The default development settings specify MySQL connector and credentials.
- Reference: [Development database settings](file://arviga/settings.py#L58-L68)

3) Optional: Switch to SQLite for quick local development
- To use SQLite instead of MySQL, create a local settings override file.
- Reference: [Switch to SQLite](file://SETUP_GUIDE.md#L57-L67)

Notes:
- The project expects MySQL 8.0+ and utf8mb4 charset.
- Ensure the database host, port, user, and password match your environment.

**Section sources**
- [README.txt](file://README.txt#L20-L23)
- [arviga/settings.py](file://arviga/settings.py#L58-L68)
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md#L57-L67)

## Initial Configuration
After preparing the environment and database, apply migrations and create a superuser:

1) Apply Django migrations
- Run the migration command to create tables defined in the project models.
- Command reference: [Run migrations](file://SETUP_GUIDE.md#L69-L83)

2) Create a superuser
- Create an administrative user for the Django admin interface.
- Command reference: [Create superuser](file://SETUP_GUIDE.md#L69-L83)

Notes:
- Migrations are generated from the app’s models and applied automatically when you run the migration command.
- The superuser credentials are required to access the admin panel.

**Section sources**
- [README.txt](file://README.txt#L25-L29)
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md#L69-L83)
- [arva/models.py](file://arva/models.py#L1-L445)
- [arva/migrations/0001_initial.py](file://arva/migrations/0001_initial.py#L1-L175)
- [arva/migrations/0005_project_etd_project_is_project_project_pm_assignee_and_more.py](file://arva/migrations/0005_project_etd_project_is_project_project_pm_assignee_and_more.py#L1-L67)

## Running the Application
Start the Django development server to serve the application locally:

- Command reference: [Run server](file://SETUP_GUIDE.md#L69-L83)
- The server typically runs at http://127.0.0.1:8000.

Notes:
- The project includes URL routing for admin, app routes, and allauth social accounts.
- Static and media assets are served in debug mode.

**Section sources**
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md#L15-L17)
- [arviga/urls.py](file://arviga/urls.py#L1-L15)
- [arviga/wsgi.py](file://arviga/wsgi.py#L1-L6)
- [arviga/asgi.py](file://arviga/asgi.py#L1-L6)

## Production Deployment Considerations
When deploying to production, review the following configuration differences and requirements:

- Allowed hosts and debug settings
- Database configuration for production
- Email backend configuration
- Static and media asset serving
- WSGI/ASGI application configuration

Key references:
- Development vs hosting settings comparison: [Hosting settings](file://settings-hosting.py#L1-L133)
- Development settings: [Development settings](file://arviga/settings.py#L1-L133)
- WSGI/ASGI applications: [WSGI](file://arviga/wsgi.py#L1-L6), [ASGI](file://arviga/asgi.py#L1-L6)
- Installed apps and middleware: [Development settings](file://arviga/settings.py#L9-L35)

Notes:
- The hosting settings file demonstrates production-ready configurations for database, email, and allowed hosts.
- Ensure environment-specific overrides are applied appropriately.

**Section sources**
- [settings-hosting.py](file://settings-hosting.py#L1-L133)
- [arviga/settings.py](file://arviga/settings.py#L1-L133)
- [arviga/wsgi.py](file://arviga/wsgi.py#L1-L6)
- [arviga/asgi.py](file://arviga/asgi.py#L1-L6)

## Troubleshooting Guide
Common issues and resolutions during installation and setup:

- MySQL connection failures
  - Verify that the MySQL service is running and listening on the expected port.
  - Test connectivity using a simple script or client.
  - Reference: [MySQL troubleshooting](file://SETUP_GUIDE.md#L42-L50)

- Duplicate column errors during migration
  - If encountering duplicate column errors, you may need to fake a problematic migration before continuing.
  - Reference: [Fix duplicate column error](file://SETUP_GUIDE.md#L52-L55)

- Switching to SQLite for local development
  - Create a local settings override to use sqlite3 for faster iteration.
  - Reference: [Switch to SQLite](file://SETUP_GUIDE.md#L57-L67)

- Running commands
  - Use the documented commands for migrations, superuser creation, and server startup.
  - Reference: [Commands reference](file://SETUP_GUIDE.md#L69-L83)

**Section sources**
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md#L42-L67)
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md#L69-L83)

## Next Steps
After completing setup:
- Access the application at http://127.0.0.1:8000.
- Log in using the superuser credentials provided in the setup guide.
- Explore the admin panel and create projects, members, and tasks.
- Review the project features and customization options.

Reference:
- Application URL and default credentials: [Setup guide](file://SETUP_GUIDE.md#L15-L23)

**Section sources**
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md#L15-L23)