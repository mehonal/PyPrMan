from app.extensions import db

STATUS_CATEGORIES = ["todo", "in_progress", "done"]


class Status(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    position = db.Column(db.Integer, default=0)
    category = db.Column(db.String(20), default="todo", nullable=False)
    color = db.Column(db.String(7), default="#6b7280")
    is_default = db.Column(db.Boolean, default=False)

    project = db.relationship("Project", back_populates="statuses")
    work_items = db.relationship("WorkItem", back_populates="status")
