from flask import Blueprint, abort, jsonify, render_template, request
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.project import Project, ProjectMembership
from app.models.sprint import Sprint, SprintProject
from app.models.work_item import WorkItem

backlog_bp = Blueprint("backlog", __name__)


def _user_project_ids():
    return [
        m.project_id
        for m in ProjectMembership.query.filter_by(user_id=current_user.id).all()
    ]


@backlog_bp.route("/projects/<key>/backlog")
@auth_required()
def project_backlog(key):
    project = Project.query.filter_by(key=key.upper()).first_or_404()
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=project.id
    ).first()
    if not membership:
        abort(403)

    sprints = (
        Sprint.query.join(SprintProject)
        .filter(SprintProject.project_id == project.id)
        .order_by(Sprint.is_active.desc(), Sprint.start_date.asc().nullslast())
        .all()
    )

    items = (
        WorkItem.query.filter_by(project_id=project.id, parent_id=None)
        .order_by(WorkItem.position)
        .all()
    )

    sprint_items = {}
    no_sprint_items = []
    for item in items:
        if item.sprint_id:
            sprint_items.setdefault(item.sprint_id, []).append(item)
        else:
            no_sprint_items.append(item)

    return render_template(
        "backlog/list.html",
        project=project,
        sprints=sprints,
        sprint_items=sprint_items,
        no_sprint_items=no_sprint_items,
        is_aggregated=False,
    )


@backlog_bp.route("/backlog")
@auth_required()
def aggregated_backlog():
    project_ids = _user_project_ids()
    projects = Project.query.filter(Project.id.in_(project_ids)).all()

    filter_project_id = request.args.get("project_id", type=int)
    if filter_project_id and filter_project_id in project_ids:
        filtered_ids = [filter_project_id]
    else:
        filtered_ids = project_ids

    sprints = (
        Sprint.query.join(SprintProject)
        .filter(SprintProject.project_id.in_(filtered_ids))
        .distinct()
        .order_by(Sprint.is_active.desc(), Sprint.start_date.asc().nullslast())
        .all()
    )

    items = (
        WorkItem.query.filter(
            WorkItem.project_id.in_(filtered_ids), WorkItem.parent_id.is_(None)
        )
        .order_by(WorkItem.position)
        .all()
    )

    sprint_items = {}
    no_sprint_items = []
    for item in items:
        if item.sprint_id:
            sprint_items.setdefault(item.sprint_id, []).append(item)
        else:
            no_sprint_items.append(item)

    return render_template(
        "backlog/list.html",
        project=None,
        projects=projects,
        sprints=sprints,
        sprint_items=sprint_items,
        no_sprint_items=no_sprint_items,
        is_aggregated=True,
        filter_project_id=filter_project_id,
    )


@backlog_bp.route("/backlog/reorder", methods=["POST"])
@auth_required()
def reorder():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    item_id = data.get("item_id")
    new_position = data.get("position", 0)
    new_sprint_id = data.get("sprint_id")

    item = WorkItem.query.get_or_404(item_id)
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=item.project_id
    ).first()
    if not membership:
        abort(403)

    item.position = new_position
    if new_sprint_id is not None:
        item.sprint_id = new_sprint_id if new_sprint_id else None
    db.session.commit()

    return jsonify({"ok": True})
