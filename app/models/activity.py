from app.extensions import db


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_item_id = db.Column(
        db.Integer, db.ForeignKey("work_item.id"), nullable=False
    )
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    work_item = db.relationship("WorkItem", back_populates="comments")
    author = db.relationship("User", backref="comments")


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_item_id = db.Column(
        db.Integer, db.ForeignKey("work_item.id"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    field_changed = db.Column(db.String(50), nullable=False)
    old_value = db.Column(db.String(500), default="")
    new_value = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    work_item = db.relationship("WorkItem", back_populates="activity_logs")
    user = db.relationship("User", backref="activity_logs")
