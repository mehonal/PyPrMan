from app.extensions import db

work_item_labels = db.Table(
    "work_item_labels",
    db.Column(
        "work_item_id",
        db.Integer,
        db.ForeignKey("work_item.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "label_id",
        db.Integer,
        db.ForeignKey("label.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Label(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), default="#6b7280")

    project = db.relationship("Project", back_populates="labels")
    work_items = db.relationship(
        "WorkItem", secondary=work_item_labels, back_populates="labels"
    )
