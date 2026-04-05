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

    created_by = db.relationship("User", backref="created_sprints")
    sprint_projects = db.relationship(
        "SprintProject", back_populates="sprint", cascade="all, delete-orphan"
    )
    work_items = db.relationship("WorkItem", back_populates="sprint")

    @property
    def projects(self):
        return [sp.project for sp in self.sprint_projects]
