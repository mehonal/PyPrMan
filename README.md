# PyPrMan

A web-based project management tool built with Flask. Manage projects, epics, sprints, and work items with a Kanban board, backlog views, and an activity feed.

## Features

- **Projects** -- create projects with unique keys, invite members with role-based access (Admin / Member)
- **Work Items** -- track user stories, bugs, and tasks with custom statuses and item types per project
- **Epics** -- group related work items under epics
- **Sprints** -- plan iterations, assign work items, and track progress
- **Kanban Board** -- drag-and-drop board view for each project
- **Backlog** -- prioritize and manage unscheduled work
- **Activity Log & Comments** -- per-item comment threads and activity history
- **REST API** -- JSON endpoints for work items, statuses, and sprints
- **Authentication** -- registration, login, and password management via Flask-Security (argon2 hashing)
- **PWA-ready** -- includes a service worker and web manifest

## Tech Stack

- Python 3.12, Flask 3.1
- SQLAlchemy + Flask-Migrate (Alembic) -- SQLite by default, any SQL database in production
- Flask-Security-Too -- authentication and role management
- Bootstrap 5 -- UI framework (served locally, no CDN)

## Quick Start

```bash
# Clone and enter the repo
git clone <repo-url> && cd py-project-management

# Create a virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up the database
flask db upgrade

# (Optional) seed an admin user
export ADMIN_PASSWORD='choose-a-strong-password'
flask seed

# Run the development server
flask run
```

The app will be available at `http://127.0.0.1:5000`.

## Configuration

Configuration lives in `config.py` with three profiles: **development** (default), **testing**, and **production**. Set the active profile with the `FLASK_CONFIG` environment variable.

Copy `.env.example` to `.env` and fill in the values for production use:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Flask secret key (required in production) |
| `SECURITY_PASSWORD_SALT` | Password hashing salt (required in production) |
| `DATABASE_URL` | Database connection string (defaults to SQLite) |
| `ADMIN_EMAIL` | Email for the seeded admin user |
| `ADMIN_PASSWORD` | Password for the seeded admin user |

## Project Structure

```
├── app/
│   ├── __init__.py          # App factory, security headers, CLI commands
│   ├── extensions.py        # db, migrate, security instances
│   ├── validation.py        # Shared validators
│   ├── blueprints/          # Route handlers
│   │   ├── api.py           # REST API endpoints
│   │   ├── board.py         # Kanban board
│   │   ├── backlog.py       # Backlog management
│   │   ├── epics.py         # Epic CRUD
│   │   ├── sprints.py       # Sprint CRUD
│   │   ├── work_items.py    # Work item CRUD
│   │   ├── projects.py      # Project CRUD & membership
│   │   ├── settings.py      # Project settings (statuses, types, members)
│   │   └── main.py          # Dashboard & landing page
│   ├── models/              # SQLAlchemy models
│   ├── templates/           # Jinja2 templates
│   └── static/              # CSS, JS, fonts, icons
├── migrations/              # Alembic migrations
├── config.py                # App configuration
├── wsgi.py                  # WSGI entry point
└── requirements.txt
```

## Running Tests

```bash
source venv/bin/activate
pytest
```

## License

See [LICENSE](LICENSE) for details.
