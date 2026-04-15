from app.extensions import db


class Watcher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    work_item_id = db.Column(
        db.Integer, db.ForeignKey("work_item.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("user_id", "work_item_id", name="uq_watcher_user_item"),
    )

    user = db.relationship("User", backref="watched_items")
    work_item = db.relationship("WorkItem", backref="watchers")
