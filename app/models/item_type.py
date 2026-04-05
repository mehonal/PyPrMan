from app.extensions import db


class ItemType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(50), default="bi-circle")
    color = db.Column(db.String(7), default="#6b7280")
    is_default = db.Column(db.Boolean, default=False)

    project = db.relationship("Project", back_populates="item_types")
    work_items = db.relationship("WorkItem", back_populates="item_type")
