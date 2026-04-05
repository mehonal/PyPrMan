from flask import Blueprint, redirect, render_template, url_for
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.project import Project, ProjectMembership
from app.models.work_item import WorkItem

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("security.login"))


@main_bp.route("/dashboard")
@auth_required()
def dashboard():
    user_project_ids = [
        m.project_id
        for m in ProjectMembership.query.filter_by(user_id=current_user.id).all()
    ]
    projects = Project.query.filter(Project.id.in_(user_project_ids)).all()
    my_items = (
        WorkItem.query.filter(
            WorkItem.assignee_id == current_user.id,
            WorkItem.project_id.in_(user_project_ids),
        )
        .join(WorkItem.status)
        .filter(db.not_(db.literal_column("status.category").in_(["done"])))
        .order_by(WorkItem.updated_at.desc())
        .limit(20)
        .all()
    )
    recent_items = (
        WorkItem.query.filter(WorkItem.project_id.in_(user_project_ids))
        .order_by(WorkItem.updated_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "main/dashboard.html",
        projects=projects,
        my_items=my_items,
        recent_items=recent_items,
    )
