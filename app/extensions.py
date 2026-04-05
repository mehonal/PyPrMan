from flask_migrate import Migrate
from flask_security import Security
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
security = Security()
