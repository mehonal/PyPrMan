from app.extensions import db

PRIORITIES = ["none", "low", "medium", "high", "critical"]

PRIORITY_ICONS = {
    "none": "bi-dash",
    "low": "bi-arrow-down",
    "medium": "bi-arrow-right",
    "high": "bi-arrow-up",
    "critical": "bi-exclamation-triangle-fill",
}

PRIORITY_COLORS = {
    "none": "#6b7280",
    "low": "#3b82f6",
    "medium": "#f59e0b",
    "high": "#f97316",
    "critical": "#ef4444",
}


class WorkItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    item_type_id = db.Column(db.Integer, db.ForeignKey("item_type.id"), nullable=False)
    status_id = db.Column(db.Integer, db.ForeignKey("status.id"), nullable=False)
    epic_id = db.Column(db.Integer, db.ForeignKey("epic.id"), nullable=True)
    sprint_id = db.Column(db.Integer, db.ForeignKey("sprint.id"), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("work_item.id"), nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, default="")
    priority = db.Column(db.String(20), default="medium", nullable=False)
    story_points = db.Column(db.Integer, nullable=True)
    position = db.Column(db.Integer, default=0)
    item_key = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    project = db.relationship("Project", back_populates="work_items")
    item_type = db.relationship("ItemType", back_populates="work_items")
    status = db.relationship("Status", back_populates="work_items")
    epic = db.relationship("Epic", back_populates="work_items")
    sprint = db.relationship("Sprint", back_populates="work_items")
    assignee = db.relationship("User", foreign_keys=[assignee_id], backref="assigned_items")
    reporter = db.relationship("User", foreign_keys=[reporter_id], backref="reported_items")
    parent = db.relationship("WorkItem", remote_side=[id], backref="subtasks")
    comments = db.relationship(
        "Comment", back_populates="work_item", cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )
    activity_logs = db.relationship(
        "ActivityLog", back_populates="work_item", cascade="all, delete-orphan",
        order_by="ActivityLog.created_at.desc()",
    )

    @property
    def priority_icon(self):
        return PRIORITY_ICONS.get(self.priority, "bi-dash")

    @property
    def priority_color(self):
        return PRIORITY_COLORS.get(self.priority, "#6b7280")
