import os

from flask import Flask, jsonify, render_template
from flask_wtf.csrf import CSRFProtect

from config import config

csrf = CSRFProtect()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG", "default")

    app = Flask(__name__)
    config_class = config[config_name]
    app.config.from_object(config_class)
    if hasattr(config_class, "init_app"):
        config_class.init_app(app)

    csrf.init_app(app)

    from app.extensions import db, mail, migrate, security
    from app.models.user import User, Role

    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    from flask_security import SQLAlchemyUserDatastore

    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    security.init_app(app, user_datastore)
    app.user_datastore = user_datastore

    from app.blueprints.main import main_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.projects import projects_bp
    from app.blueprints.epics import epics_bp
    from app.blueprints.sprints import sprints_bp
    from app.blueprints.work_items import work_items_bp
    from app.blueprints.board import board_bp
    from app.blueprints.backlog import backlog_bp
    from app.blueprints.settings import settings_bp
    from app.blueprints.api import api_bp
    from app.blueprints.user_settings import user_settings_bp
    from app.blueprints.profiles import profiles_bp
    from app.blueprints.notifications import notifications_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(epics_bp)
    app.register_blueprint(sprints_bp)
    app.register_blueprint(work_items_bp)
    app.register_blueprint(board_bp)
    app.register_blueprint(backlog_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(user_settings_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(notifications_bp)

    @app.errorhandler(403)
    def forbidden(e):
        from flask import request as req
        if req.path.startswith("/api/"):
            return jsonify({"error": "Forbidden"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import request as req
        if req.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import request as req
        if req.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    @app.context_processor
    def inject_sidebar_data():
        from flask_security import current_user

        if current_user.is_authenticated:
            from app.models.project import Project, ProjectMembership

            memberships = ProjectMembership.query.options(
                db.joinedload(ProjectMembership.project)
            ).filter_by(
                user_id=current_user.id
            ).all()
            projects = sorted([m.project for m in memberships], key=lambda p: p.name.lower())

            active_project = None
            from flask import request

            if request.view_args and "key" in request.view_args:
                key = request.view_args["key"].upper()
                active_project = next(
                    (p for p in projects if p.key == key), None
                )

            from app.models.notification import Notification

            unread_count = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()

            return {
                "sidebar_projects": projects,
                "active_project": active_project,
                "unread_notification_count": unread_count,
            }
        return {"sidebar_projects": [], "active_project": None, "unread_notification_count": 0}

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "frame-ancestors 'self';"
        )
        return response

    _register_cli_commands(app)

    return app


def _register_cli_commands(app):
    @app.cli.command("seed")
    def seed():
        """Create default admin user."""
        from flask_security import hash_password

        from app.extensions import db

        email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            raise RuntimeError(
                "Set ADMIN_PASSWORD env var before running seed."
            )

        datastore = app.user_datastore
        if not datastore.find_user(email=email):
            datastore.create_user(
                email=email,
                password=hash_password(password),
            )
            db.session.commit()
            print(f"Admin user created: {email}")
        else:
            print("Admin user already exists.")
