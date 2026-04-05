from flask import Blueprint, abort, jsonify, render_template, request
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.activity import ActivityLog
from app.models.project import Project, ProjectMembership
from app.models.status import Status
from app.models.work_item import WorkItem

board_bp = Blueprint("board", __name__)


def _user_project_ids():
    return [
        m.project_id
        for m in ProjectMembership.query.filter_by(user_id=current_user.id).all()
    ]


@board_bp.route("/projects/<key>/board")
@auth_required()
def project_board(key):
    project = Project.query.filter_by(key=key.upper()).first_or_404()
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=project.id
    ).first()
    if not membership:
        abort(403)

    statuses = Status.query.filter_by(project_id=project.id).order_by(Status.position).all()
    items = WorkItem.query.filter_by(project_id=project.id).order_by(WorkItem.position).all()

    columns = {}
    for s in statuses:
        columns[s.id] = {
            "status": s,
            "work_items": [i for i in items if i.status_id == s.id],
        }

    return render_template(
        "board/kanban.html",
        project=project,
        columns=columns,
        statuses=statuses,
        is_aggregated=False,
    )


@board_bp.route("/board")
@auth_required()
def aggregated_board():
    project_ids = _user_project_ids()
    projects = Project.query.filter(Project.id.in_(project_ids)).all()

    filter_project_id = request.args.get("project_id", type=int)

    if filter_project_id and filter_project_id in project_ids:
        filtered_ids = [filter_project_id]
    else:
        filtered_ids = project_ids

    all_statuses = (
        Status.query.filter(Status.project_id.in_(filtered_ids))
        .order_by(Status.position)
        .all()
    )
    items = (
        WorkItem.query.filter(WorkItem.project_id.in_(filtered_ids))
        .order_by(WorkItem.position)
        .all()
    )

    category_order = ["backlog", "todo", "in_progress", "done"]
    seen_categories = {}
    columns = {}
    for s in all_statuses:
        cat = s.category
        if cat not in seen_categories:
            seen_categories[cat] = s
            columns[cat] = {
                "status": s,
                "label": s.name,
                "work_items": [],
            }
        columns[cat]["work_items"].extend([i for i in items if i.status.category == cat and i.status_id == s.id])

    sorted_columns = {k: columns[k] for k in category_order if k in columns}

    return render_template(
        "board/kanban.html",
        project=None,
        columns=sorted_columns,
        statuses=all_statuses,
        projects=projects,
        is_aggregated=True,
        filter_project_id=filter_project_id,
    )


@board_bp.route("/board/move", methods=["POST"])
@auth_required()
def move_item():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    item_id = data.get("item_id")
    new_status_id = data.get("status_id")
    new_position = data.get("position", 0)

    item = WorkItem.query.get_or_404(item_id)
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=item.project_id
    ).first()
    if not membership:
        abort(403)

    old_status = item.status
    new_status = Status.query.get_or_404(new_status_id)

    if new_status.project_id != item.project_id:
        equivalent = Status.query.filter_by(
            project_id=item.project_id, category=new_status.category
        ).order_by(Status.position).first()
        if not equivalent:
            return jsonify({"error": "No matching status category in this project"}), 400
        new_status = equivalent

    if old_status.id != new_status.id:
        db.session.add(
            ActivityLog(
                work_item=item,
                user_id=current_user.id,
                field_changed="status",
                old_value=old_status.name,
                new_value=new_status.name,
            )
        )

    item.status_id = new_status.id
    item.position = new_position
    db.session.commit()

    return jsonify({"ok": True})
