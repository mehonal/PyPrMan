from flask import abort
from flask_security import current_user

from app.extensions import db
from app.models.project import Project, ProjectMembership
from app.models.status import FINAL_CATEGORIES, Status
from app.models.work_item import WorkItem


def completed_categories(project):
    """Status categories that count as "completed" for SP/velocity/burndown.

    Always includes "done". Includes "cancelled" only when the project opts into
    Jira-style behaviour via count_cancelled_as_completed.
    """
    if project.count_cancelled_as_completed:
        return ("done", "cancelled")
    return ("done",)


def get_project(key):
    project = Project.query.filter_by(key=key.upper()).first_or_404()
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=project.id
    ).first()
    if not membership:
        abort(403)
    return project


def user_project_ids():
    return [
        m.project_id
        for m in ProjectMembership.query.filter_by(user_id=current_user.id).all()
    ]


def sprint_sp_stats(sprint_ids, project_ids):
    """Compute committed/completed SP per sprint filtered by project(s).

    Returns {sprint_id: {"committed_sp": int, "completed_sp": int}}.
    """
    if not sprint_ids:
        return {}
    rows = (
        db.session.query(
            WorkItem.sprint_id,
            db.func.coalesce(db.func.sum(WorkItem.story_points), 0),
            db.func.coalesce(
                db.func.sum(
                    db.case(
                        (Status.category == "done", WorkItem.story_points),
                        (
                            db.and_(
                                Status.category == "cancelled",
                                Project.count_cancelled_as_completed.is_(True),
                            ),
                            WorkItem.story_points,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        )
        .join(Status, WorkItem.status_id == Status.id)
        .join(Project, WorkItem.project_id == Project.id)
        .filter(
            WorkItem.sprint_id.in_(sprint_ids),
            WorkItem.project_id.in_(project_ids),
        )
        .group_by(WorkItem.sprint_id)
        .all()
    )
    return {
        row[0]: {"committed_sp": row[1], "completed_sp": row[2]}
        for row in rows
    }
