import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-not-for-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECURITY_PASSWORD_SALT = os.environ.get(
        "SECURITY_PASSWORD_SALT", "dev-only-not-for-production"
    )
    SECURITY_PASSWORD_HASH = "argon2"
    SECURITY_PASSWORD_LENGTH_MIN = 10
    SECURITY_REGISTERABLE = True
    SECURITY_SEND_REGISTER_EMAIL = False
    SECURITY_SEND_PASSWORD_CHANGE_EMAIL = False
    SECURITY_SEND_PASSWORD_RESET_EMAIL = False
    SECURITY_POST_LOGIN_VIEW = "/dashboard"
    SECURITY_POST_REGISTER_VIEW = "/dashboard"
    MAIL_SUPPRESS_SEND = True

    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "instance", "dev.db")
    SECURITY_EMAIL_VALIDATOR_ARGS = {"check_deliverability": False}


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        basedir, "instance", "test.db"
    )
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost"
    SECURITY_EMAIL_VALIDATOR_ARGS = {"check_deliverability": False}


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    MAIL_SUPPRESS_SEND = False
    SECURITY_SEND_REGISTER_EMAIL = True
    SECURITY_SEND_PASSWORD_CHANGE_EMAIL = True
    SECURITY_SEND_PASSWORD_RESET_EMAIL = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    @classmethod
    def init_app(cls, app):
        missing = [
            key
            for key in (
                "SECRET_KEY",
                "SECURITY_PASSWORD_SALT",
                "DATABASE_URL",
                "MAIL_SERVER",
                "MAIL_DEFAULT_SENDER",
            )
            if not os.environ.get(key)
        ]
        if missing:
            raise RuntimeError(
                f"Production requires these env vars: {', '.join(missing)}"
            )
        app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
        app.config["SECURITY_PASSWORD_SALT"] = os.environ["SECURITY_PASSWORD_SALT"]
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
        app.config["MAIL_SERVER"] = os.environ["MAIL_SERVER"]
        app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
        app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
        app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
        app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
        app.config["MAIL_DEFAULT_SENDER"] = os.environ["MAIL_DEFAULT_SENDER"]


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
