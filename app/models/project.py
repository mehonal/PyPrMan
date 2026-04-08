from app.extensions import db


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    key = db.Column(db.String(10), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    item_counter = db.Column(db.Integer, default=0)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    created_by = db.relationship("User", backref="created_projects")
    memberships = db.relationship(
        "ProjectMembership", back_populates="project", cascade="all, delete-orphan"
    )
    statuses = db.relationship(
        "Status",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Status.position",
    )
    item_types = db.relationship(
        "ItemType", back_populates="project", cascade="all, delete-orphan"
    )
    epics = db.relationship(
        "Epic", back_populates="project", cascade="all, delete-orphan"
    )
    labels = db.relationship(
        "Label", back_populates="project", cascade="all, delete-orphan"
    )
    work_items = db.relationship(
        "WorkItem", back_populates="project", cascade="all, delete-orphan"
    )

    def next_item_key(self):
        self.item_counter += 1
        return f"{self.key}-{self.item_counter}"

    def create_default_statuses(self):
        from app.models.status import Status

        defaults = [
            ("To Do", "todo", "#3b82f6", 0),
            ("In Progress", "in_progress", "#f59e0b", 1),
            ("In Review", "in_progress", "#8b5cf6", 2),
            ("Done", "done", "#10b981", 3),
        ]
        for name, category, color, position in defaults:
            status = Status(
                project=self,
                name=name,
                category=category,
                color=color,
                position=position,
                is_default=(position == 1),
            )
            db.session.add(status)

    def create_default_item_types(self):
        from app.models.item_type import ItemType

        defaults = [
            ("Story", "bi-book", "#3b82f6"),
            ("Task", "bi-check-square", "#10b981"),
            ("Bug", "bi-bug", "#ef4444"),
        ]
        for name, icon, color in defaults:
            item_type = ItemType(
                project=self,
                name=name,
                icon=icon,
                color=color,
                is_default=(name == "Task"),
            )
            db.session.add(item_type)


class ProjectMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    role = db.Column(db.String(20), default="member", nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (db.UniqueConstraint("user_id", "project_id"),)

    user = db.relationship("User", backref="project_memberships")
    project = db.relationship("Project", back_populates="memberships")
