from app.extensions import db


class Epic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    color = db.Column(db.String(7), default="#8b5cf6")
    status = db.Column(db.String(20), default="to_do", nullable=False)
    position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    project = db.relationship("Project", back_populates="epics")
    work_items = db.relationship("WorkItem", back_populates="epic")
