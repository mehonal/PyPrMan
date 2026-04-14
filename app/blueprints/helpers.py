from flask import abort
from flask_security import current_user

from app.models.project import Project, ProjectMembership


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
