from flask import Blueprint, abort, render_template
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.activity import ActivityLog, Comment
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.models.work_item import WorkItem

profiles_bp = Blueprint("profiles", __name__, url_prefix="/users")


@profiles_bp.route("/<int:user_id>")
@auth_required()
def profile(user_id):
    user = User.query.get_or_404(user_id)

    # Find common projects
    my_project_ids = {
        m.project_id
        for m in ProjectMembership.query.filter_by(user_id=current_user.id).all()
    }
    their_project_ids = {
        m.project_id
        for m in ProjectMembership.query.filter_by(user_id=user.id).all()
    }
    common_project_ids = my_project_ids & their_project_ids
    if not common_project_ids:
        abort(403)

    common_projects = (
        Project.query.filter(Project.id.in_(common_project_ids))
        .order_by(Project.name)
        .all()
    )

    # Recent activity on common projects
    recent_activity = (
        ActivityLog.query
        .join(WorkItem, ActivityLog.work_item_id == WorkItem.id)
        .filter(
            ActivityLog.user_id == user.id,
            WorkItem.project_id.in_(common_project_ids),
        )
        .options(
            db.joinedload(ActivityLog.work_item).joinedload(WorkItem.project),
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(30)
        .all()
    )

    # Recent comments on common projects
    recent_comments = (
        Comment.query
        .join(WorkItem, Comment.work_item_id == WorkItem.id)
        .filter(
            Comment.author_id == user.id,
            WorkItem.project_id.in_(common_project_ids),
        )
        .options(
            db.joinedload(Comment.work_item).joinedload(WorkItem.project),
        )
        .order_by(Comment.created_at.desc())
        .limit(10)
        .all()
    )

    # Items assigned to this user on common projects
    assigned_items = (
        WorkItem.query
        .filter(
            WorkItem.assignee_id == user.id,
            WorkItem.project_id.in_(common_project_ids),
        )
        .join(WorkItem.status)
        .options(
            db.joinedload(WorkItem.status),
            db.joinedload(WorkItem.item_type),
            db.joinedload(WorkItem.project),
        )
        .order_by(WorkItem.updated_at.desc())
        .limit(20)
        .all()
    )

    # Collect all members across common projects for mention resolution
    all_member_ids = {
        m.user_id
        for m in ProjectMembership.query.filter(
            ProjectMembership.project_id.in_(common_project_ids)
        ).all()
    }
    all_members = User.query.filter(User.id.in_(all_member_ids)).all()

    return render_template(
        "profiles/profile.html",
        profile_user=user,
        common_projects=common_projects,
        recent_activity=recent_activity,
        recent_comments=recent_comments,
        assigned_items=assigned_items,
        members=all_members,
    )
