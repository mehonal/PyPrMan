from app.extensions import db

NOTIFICATION_TYPES = [
    "assigned",
    "unassigned",
    "mentioned",
    "watched_change",
    "comment",
    "due_date_soon",
]


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    work_item_id = db.Column(
        db.Integer, db.ForeignKey("work_item.id"), nullable=True
    )
    type = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(500), default="")
    url = db.Column(db.String(500), default="")
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", foreign_keys=[user_id], backref="notifications")
    actor = db.relationship("User", foreign_keys=[actor_id])
    work_item = db.relationship("WorkItem", backref="notifications")


class NotificationPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    type = db.Column(db.String(30), nullable=False)
    in_app = db.Column(db.Boolean, default=True, nullable=False)
    email = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "type", name="uq_notif_pref_user_type"),
    )

    user = db.relationship("User", backref="notification_preferences")
