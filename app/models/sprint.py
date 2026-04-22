from app.extensions import db


class SprintProject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sprint_id = db.Column(db.Integer, db.ForeignKey("sprint.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)

    __table_args__ = (db.UniqueConstraint("sprint_id", "project_id"),)

    sprint = db.relationship("Sprint", back_populates="sprint_projects")
    project = db.relationship("Project")


class Sprint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    goal = db.Column(db.Text, default="")
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    completed_at = db.Column(db.DateTime)
    initial_committed_sp = db.Column(db.Integer)
    committed_sp_snapshot = db.Column(db.Integer)
    completed_sp_snapshot = db.Column(db.Integer)

    created_by = db.relationship("User", backref="created_sprints")
    sprint_projects = db.relationship(
        "SprintProject", back_populates="sprint", cascade="all, delete-orphan"
    )
    work_items = db.relationship("WorkItem", back_populates="sprint")

    @property
    def projects(self):
        return [sp.project for sp in self.sprint_projects]

    @property
    def is_completed(self):
        return self.completed_at is not None

    @property
    def committed_sp(self):
        return sum(i.story_points or 0 for i in self.work_items)

    @property
    def completed_sp(self):
        total = 0
        for i in self.work_items:
            cat = i.status.category
            if cat == "done" or (
                cat == "cancelled" and i.project.count_cancelled_as_completed
            ):
                total += i.story_points or 0
        return total

    @property
    def in_progress_sp(self):
        return sum(
            i.story_points or 0
            for i in self.work_items
            if i.status.category == "in_progress"
        )
