from flask import Blueprint, abort, jsonify, render_template, request
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.activity import ActivityLog
from app.models.epic import Epic
from app.models.label import Label
from app.models.project import Project, ProjectMembership
from app.models.sprint import Sprint, SprintProject
from app.models.status import Status
from app.models.work_item import WorkItem
from app.blueprints.helpers import user_project_ids as _user_project_ids

board_bp = Blueprint("board", __name__)


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

    sprint_filter = request.args.get("sprint_filter")
    if sprint_filter is not None:
        sprint_filter_active = sprint_filter == "1"
    else:
        sprint_filter_active = current_user.board_sprint_filter

    query = WorkItem.query.filter_by(project_id=project.id)
    active_sprint = None
    if sprint_filter_active:
        active_sprint = (
            Sprint.query.join(SprintProject)
            .filter(SprintProject.project_id == project.id, Sprint.is_active.is_(True))
            .first()
        )
        if active_sprint:
            query = query.filter_by(sprint_id=active_sprint.id)

    filter_epic_id = request.args.get("epic_id", type=int)
    if filter_epic_id:
        query = query.filter_by(epic_id=filter_epic_id)

    filter_label_id = request.args.get("label_id", type=int)
    if filter_label_id:
        query = query.filter(WorkItem.labels.any(Label.id == filter_label_id))

    items = query.options(
        db.joinedload(WorkItem.parent),
        db.joinedload(WorkItem.labels),
    ).order_by(WorkItem.position).all()

    columns = {}
    for s in statuses:
        columns[s.id] = {
            "status": s,
            "work_items": [i for i in items if i.status_id == s.id],
        }

    epics = Epic.query.filter_by(project_id=project.id).order_by(Epic.name).all()
    labels = Label.query.filter_by(project_id=project.id).order_by(Label.name).all()

    from datetime import date
    return render_template(
        "board/kanban.html",
        project=project,
        columns=columns,
        statuses=statuses,
        is_aggregated=False,
        sprint_filter_active=sprint_filter_active,
        active_sprint=active_sprint,
        epics=epics,
        filter_epic_id=filter_epic_id,
        labels=labels,
        filter_label_id=filter_label_id,
        today=date.today(),
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

    sprint_filter = request.args.get("sprint_filter")
    if sprint_filter is not None:
        sprint_filter_active = sprint_filter == "1"
    else:
        sprint_filter_active = current_user.board_sprint_filter

    query = WorkItem.query.filter(WorkItem.project_id.in_(filtered_ids))
    active_sprint = None
    if sprint_filter_active:
        active_sprints = (
            Sprint.query.join(SprintProject)
            .filter(SprintProject.project_id.in_(filtered_ids), Sprint.is_active.is_(True))
            .all()
        )
        active_sprint_ids = [s.id for s in active_sprints]
        if active_sprint_ids:
            query = query.filter(WorkItem.sprint_id.in_(active_sprint_ids))
            active_sprint = active_sprints[0] if len(active_sprints) == 1 else True

    filter_epic_id = request.args.get("epic_id", type=int)
    if filter_epic_id:
        query = query.filter_by(epic_id=filter_epic_id)

    filter_label_id = request.args.get("label_id", type=int)
    if filter_label_id:
        query = query.filter(WorkItem.labels.any(Label.id == filter_label_id))

    items = query.options(
        db.joinedload(WorkItem.parent),
        db.joinedload(WorkItem.labels),
    ).order_by(WorkItem.position).all()

    category_order = ["todo", "in_progress", "done"]
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
        "board/kanban.html",
        project=None,
        columns=sorted_columns,
        statuses=all_statuses,
        projects=projects,
        is_aggregated=True,
        filter_project_id=filter_project_id,
        sprint_filter_active=sprint_filter_active,
        active_sprint=active_sprint,
        epics=epics,
        filter_epic_id=filter_epic_id,
        labels=labels,
        filter_label_id=filter_label_id,
        today=date.today(),
    )


@board_bp.route("/projects/<key>/storymap")
@auth_required()
def story_map(key):
    project = Project.query.filter_by(key=key.upper()).first_or_404()
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=project.id
    ).first()
    if not membership:
        abort(403)

    epics = Epic.query.filter_by(project_id=project.id).order_by(Epic.position, Epic.name).all()
    labels = Label.query.filter_by(project_id=project.id).order_by(Label.name).all()
    items = (
        WorkItem.query.filter_by(project_id=project.id)
        .options(
            db.joinedload(WorkItem.labels),
            db.joinedload(WorkItem.epic),
        )
        .order_by(WorkItem.position)
        .all()
    )

    # Build grid: rows = labels (+ "Unlabeled"), columns = epics (+ "No Epic")
    # Cell key: (epic_id or 0, label_id or 0) -> [items]
    grid = {}
    for item in items:
        epic_id = item.epic_id or 0
        item_labels = item.labels if item.labels else []
        if item_labels:
            for label in item_labels:
                key_pair = (epic_id, label.id)
                grid.setdefault(key_pair, []).append(item)
        else:
            key_pair = (epic_id, 0)
            grid.setdefault(key_pair, []).append(item)

    return render_template(
        "board/storymap.html",
        project=project,
        epics=epics,
        labels=labels,
        grid=grid,
        is_aggregated=False,
    )


@board_bp.route("/storymap")
@auth_required()
def aggregated_story_map():
    project_ids = _user_project_ids()
    projects = Project.query.filter(Project.id.in_(project_ids)).all()

    filter_project_id = request.args.get("project_id", type=int)
    if filter_project_id and filter_project_id in project_ids:
        filtered_ids = [filter_project_id]
    else:
        filtered_ids = project_ids

    epics = (
        Epic.query.filter(Epic.project_id.in_(filtered_ids))
        .order_by(Epic.position, Epic.name)
        .all()
    )
    labels = (
        Label.query.filter(Label.project_id.in_(filtered_ids))
        .order_by(Label.name)
        .all()
    )
    items = (
        WorkItem.query.filter(WorkItem.project_id.in_(filtered_ids))
        .options(
            db.joinedload(WorkItem.labels),
            db.joinedload(WorkItem.epic),
            db.joinedload(WorkItem.project),
        )
        .order_by(WorkItem.position)
        .all()
    )

    grid = {}
    for item in items:
        epic_id = item.epic_id or 0
        item_labels = item.labels if item.labels else []
        if item_labels:
            for label in item_labels:
                key_pair = (epic_id, label.id)
                grid.setdefault(key_pair, []).append(item)
        else:
            key_pair = (epic_id, 0)
            grid.setdefault(key_pair, []).append(item)

    return render_template(
        "board/storymap.html",
        project=None,
        projects=projects,
        epics=epics,
        labels=labels,
        grid=grid,
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

    # Re-index all siblings in the target column so positions are contiguous
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

    db.session.commit()

    return jsonify({"ok": True})
