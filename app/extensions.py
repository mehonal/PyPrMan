from flask_mail import Mail
from flask_migrate import Migrate
from flask_security import Security
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
security = Security()
