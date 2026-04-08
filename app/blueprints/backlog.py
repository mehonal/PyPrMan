from flask import Blueprint, abort, jsonify, render_template, request
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.activity import ActivityLog
from app.models.epic import Epic
from app.models.label import Label
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

    show_completed = request.args.get("show_completed", "0") == "1"

    sprints_query = (
        Sprint.query.join(SprintProject)
        .filter(SprintProject.project_id == project.id)
    )
    if not show_completed:
        sprints_query = sprints_query.filter(Sprint.completed_at.is_(None))
    sprints = sprints_query.order_by(
        Sprint.is_active.desc(), Sprint.start_date.asc().nullslast()
    ).all()

    query = WorkItem.query.filter_by(project_id=project.id, parent_id=None)

    filter_epic_id = request.args.get("epic_id", type=int)
    if filter_epic_id:
        query = query.filter_by(epic_id=filter_epic_id)

    filter_label_id = request.args.get("label_id", type=int)
    if filter_label_id:
        query = query.filter(WorkItem.labels.any(Label.id == filter_label_id))

    items = (
        query.options(
            db.joinedload(WorkItem.status),
            db.joinedload(WorkItem.item_type),
            db.joinedload(WorkItem.epic),
            db.joinedload(WorkItem.assignee),
            db.joinedload(WorkItem.project),
        )
        .order_by(WorkItem.position)
        .all()
    )

    sprint_ids = {s.id for s in sprints}
    sprint_items = {}
    no_sprint_items = []
    for item in items:
        if item.sprint_id and item.sprint_id in sprint_ids:
            sprint_items.setdefault(item.sprint_id, []).append(item)
        elif not item.sprint_id:
            no_sprint_items.append(item)

    epics = Epic.query.filter_by(project_id=project.id).order_by(Epic.name).all()
    labels = Label.query.filter_by(project_id=project.id).order_by(Label.name).all()

    from datetime import date
    return render_template(
        "backlog/list.html",
        project=project,
        sprints=sprints,
        sprint_items=sprint_items,
        no_sprint_items=no_sprint_items,
        is_aggregated=False,
        epics=epics,
        filter_epic_id=filter_epic_id,
        labels=labels,
        filter_label_id=filter_label_id,
        show_completed=show_completed,
        today=date.today(),
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

    show_completed = request.args.get("show_completed", "0") == "1"

    sprints_query = (
        Sprint.query.join(SprintProject)
        .filter(SprintProject.project_id.in_(filtered_ids))
        .distinct()
    )
    if not show_completed:
        sprints_query = sprints_query.filter(Sprint.completed_at.is_(None))
    sprints = sprints_query.order_by(
        Sprint.is_active.desc(), Sprint.start_date.asc().nullslast()
    ).all()

    query = WorkItem.query.filter(
        WorkItem.project_id.in_(filtered_ids), WorkItem.parent_id.is_(None)
    )

    filter_epic_id = request.args.get("epic_id", type=int)
    if filter_epic_id:
        query = query.filter_by(epic_id=filter_epic_id)

    filter_label_id = request.args.get("label_id", type=int)
    if filter_label_id:
        query = query.filter(WorkItem.labels.any(Label.id == filter_label_id))

    items = (
        query.options(
            db.joinedload(WorkItem.status),
            db.joinedload(WorkItem.item_type),
            db.joinedload(WorkItem.epic),
            db.joinedload(WorkItem.assignee),
            db.joinedload(WorkItem.project),
        )
        .order_by(WorkItem.position)
        .all()
    )

    sprint_ids = {s.id for s in sprints}
    sprint_items = {}
    no_sprint_items = []
    for item in items:
        if item.sprint_id and item.sprint_id in sprint_ids:
            sprint_items.setdefault(item.sprint_id, []).append(item)
        elif not item.sprint_id:
            no_sprint_items.append(item)

    epics = (
        Epic.query.filter(Epic.project_id.in_(filtered_ids))
        .order_by(Epic.name)
        .all()
    )
    labels = (
        Label.query.filter(Label.project_id.in_(filtered_ids))
        .order_by(Label.name)
        .all()
    )

    from datetime import date
    return render_template(
        "backlog/list.html",
        project=None,
        projects=projects,
        sprints=sprints,
        sprint_items=sprint_items,
        no_sprint_items=no_sprint_items,
        is_aggregated=True,
        filter_project_id=filter_project_id,
        epics=epics,
        filter_epic_id=filter_epic_id,
        labels=labels,
        filter_label_id=filter_label_id,
        show_completed=show_completed,
        today=date.today(),
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

    # Re-index all siblings in the target group so positions are contiguous
    sibling_ids = data.get("sibling_ids")
    if sibling_ids:
        siblings = WorkItem.query.filter(
            WorkItem.id.in_(sibling_ids),
            WorkItem.project_id == item.project_id,
        ).all()
        sibling_map = {s.id: s for s in siblings}
        for idx, sid in enumerate(sibling_ids):
            if sid in sibling_map:
                sibling_map[sid].position = idx

    if new_sprint_id is not None:
        new_sid = new_sprint_id if new_sprint_id else None
        if new_sid != item.sprint_id:
            old_sprint = item.sprint
            new_sprint = Sprint.query.get(new_sid) if new_sid else None
            db.session.add(
                ActivityLog(
                    work_item=item,
                    user_id=current_user.id,
                    field_changed="sprint",
                    old_value=old_sprint.name if old_sprint else "None",
                    new_value=new_sprint.name if new_sprint else "None",
                )
            )
            item.sprint_id = new_sid
    db.session.commit()

    return jsonify({"ok": True})
