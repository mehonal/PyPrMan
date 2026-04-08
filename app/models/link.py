from app.extensions import db

LINK_TYPES = {
    "relates_to": {"label": "relates to", "reverse": "relates to"},
    "blocks": {"label": "blocks", "reverse": "is blocked by"},
    "is_blocked_by": {"label": "is blocked by", "reverse": "blocks"},
    "duplicates": {"label": "duplicates", "reverse": "is duplicated by"},
    "is_duplicated_by": {"label": "is duplicated by", "reverse": "duplicates"},
}

# Pairs: creating one direction auto-creates the reverse
LINK_REVERSE = {
    "blocks": "is_blocked_by",
    "is_blocked_by": "blocks",
    "duplicates": "is_duplicated_by",
    "is_duplicated_by": "duplicates",
    "relates_to": "relates_to",
}


class WorkItemLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("work_item.id"), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey("work_item.id"), nullable=False)
    link_type = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("source_id", "target_id", "link_type"),
    )

    source = db.relationship(
        "WorkItem", foreign_keys=[source_id],
        backref=db.backref("outgoing_links", cascade="all, delete-orphan"),
    )
    target = db.relationship(
        "WorkItem", foreign_keys=[target_id],
        backref=db.backref("incoming_links", cascade="all, delete-orphan"),
    )
