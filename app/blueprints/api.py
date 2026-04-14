from datetime import datetime

from flask import Blueprint, abort, jsonify, request
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.activity import ActivityLog, Comment
from app.models.epic import Epic
from app.models.label import Label
from app.models.project import Project, ProjectMembership
from app.models.sprint import Sprint, SprintProject
from app.models.status import Status
from app.models.link import LINK_REVERSE, LINK_TYPES, WorkItemLink
from app.models.work_item import WorkItem
from app.blueprints.helpers import get_project as _get_project, user_project_ids as _user_project_ids
from app.validation import (
    validate_hex_color,
    validate_icon_class,
    validate_priority,
    validate_status_category,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _get_item(item_id):
    item = WorkItem.query.get_or_404(item_id)
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=item.project_id
    ).first()
    if not membership:
        abort(403)
    return item


@api_bp.route("/search")
@auth_required()
def search():
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify({"results": []})

    project_ids = _user_project_ids()
    if not project_ids:
        return jsonify({"results": []})

    items = (
        WorkItem.query.filter(
            WorkItem.project_id.in_(project_ids),
            db.or_(
                WorkItem.title.ilike(f"%{q}%"),
                WorkItem.item_key.ilike(f"%{q}%"),
            ),
        )
        .options(
            db.joinedload(WorkItem.project),
            db.joinedload(WorkItem.status),
            db.joinedload(WorkItem.item_type),
        )
        .order_by(WorkItem.updated_at.desc())
        .limit(10)
        .all()
    )

    return jsonify({
        "results": [
            {
                "id": item.id,
                "item_key": item.item_key,
                "title": item.title,
                "project_key": item.project.key,
                "status": item.status.name,
                "status_color": item.status.color,
                "type_icon": item.item_type.icon,
                "type_color": item.item_type.color,
            }
            for item in items
        ]
    })


@api_bp.route("/projects/<key>/form-options")
@auth_required()
def form_options(key):
    project = _get_project(key)
    members = ProjectMembership.query.filter_by(project_id=project.id).options(db.joinedload(ProjectMembership.user)).all()

    sprints = (
        Sprint.query.join(SprintProject)
        .filter(SprintProject.project_id == project.id)
        .all()
    )

    return jsonify(
        {
            "statuses": [
                {"id": s.id, "name": s.name, "color": s.color, "category": s.category, "is_default": s.is_default}
                for s in project.statuses
            ],
            "types": [
                {"id": t.id, "name": t.name, "icon": t.icon, "color": t.color, "is_default": t.is_default}
                for t in project.item_types
            ],
            "epics": [
                {"id": e.id, "name": e.name, "color": e.color}
                for e in project.epics
            ],
            "labels": [
                {"id": l.id, "name": l.name, "color": l.color}
                for l in project.labels
            ],
            "sprints": [
                {"id": s.id, "name": s.name, "is_active": s.is_active}
                for s in sprints
            ],
            "members": [
                {"id": m.user.id, "name": m.user.display_name}
                for m in members
            ],
            "default_assignee": current_user.default_assignee,
            "current_user_id": current_user.id,
        }
    )


@api_bp.route("/projects/<key>/items", methods=["POST"])
@auth_required()
def create_item(key):
    project = _get_project(key)
    data = request.get_json()
    if not data or not data.get("title", "").strip():
        return jsonify({"error": "Title is required"}), 400

    default_type = next((t for t in project.item_types if t.is_default), None) or project.item_types[0]
    default_status = next((s for s in project.statuses if s.is_default), None) or project.statuses[0]

    # When creating a subtask without explicit type, default to "Task"
    if data.get("parent_id") and not data.get("item_type_id"):
        task_type = next((t for t in project.item_types if t.name == "Task"), None)
        if task_type:
            default_type = task_type

    max_pos = (
        db.session.query(db.func.max(WorkItem.position))
        .filter_by(project_id=project.id)
        .scalar()
        or 0
    )

    item = WorkItem(
        project=project,
        item_type_id=data.get("item_type_id") or default_type.id,
        status_id=data.get("status_id") or default_status.id,
        epic_id=data.get("epic_id") or None,
        sprint_id=data.get("sprint_id") or None,
        parent_id=data.get("parent_id") or None,
        assignee_id=data.get("assignee_id") or None,
        reporter_id=current_user.id,
        title=data["title"].strip(),
        description=data.get("description", "").strip(),
        priority=validate_priority(data.get("priority", "medium")),
        story_points=int(data["story_points"]) if data.get("story_points") else None,
        position=max_pos + 1,
        item_key=project.next_item_key(),
    )
    db.session.add(item)
    db.session.commit()

    return jsonify({"ok": True, "item_key": item.item_key, "id": item.id}), 201


@api_bp.route("/projects/<key>/epics", methods=["POST"])
@auth_required()
def create_epic(key):
    project = _get_project(key)
    data = request.get_json()
    if not data or not data.get("name", "").strip():
        return jsonify({"error": "Name is required"}), 400

    epic = Epic(
        project=project,
        name=data["name"].strip(),
        description=data.get("description", "").strip(),
        color=validate_hex_color(data.get("color", "#8b5cf6")),
    )
    db.session.add(epic)
    db.session.commit()

    return jsonify({"ok": True, "id": epic.id, "name": epic.name}), 201


@api_bp.route("/sprints", methods=["POST"])
@auth_required()
def create_sprint():
    data = request.get_json()
    if not data or not data.get("name", "").strip():
        return jsonify({"error": "Name is required"}), 400

    project_ids = data.get("project_ids", [])
    user_pids = _user_project_ids()
    if not project_ids or not all(pid in user_pids for pid in project_ids):
        return jsonify({"error": "Invalid project selection"}), 400

    start_date = None
    end_date = None
    try:
        if data.get("start_date"):
            start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
        if data.get("end_date"):
            end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format, expected YYYY-MM-DD"}), 400

    sprint = Sprint(
        name=data["name"].strip(),
        goal=data.get("goal", "").strip(),
        start_date=start_date,
        end_date=end_date,
        created_by=current_user,
    )
    db.session.add(sprint)
    for pid in project_ids:
        db.session.add(SprintProject(sprint=sprint, project_id=pid))
    db.session.commit()

    return jsonify({"ok": True, "id": sprint.id}), 201


@api_bp.route("/items/<int:item_id>", methods=["PATCH"])
@auth_required()
def update_item(item_id):
    item = _get_item(item_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    changes = {}

    if "title" in data:
        new_title = data["title"].strip()
        if new_title and new_title != item.title:
            changes["title"] = (item.title, new_title)
            item.title = new_title

    if "status_id" in data:
        new_status = Status.query.get(data["status_id"])
        if new_status and new_status.project_id == item.project_id and new_status.id != item.status_id:
            old_name = item.status.name
            changes["status"] = (old_name, new_status.name)
            item.status_id = new_status.id

    if "priority" in data:
        new_priority = validate_priority(data["priority"])
        if new_priority != item.priority:
            changes["priority"] = (item.priority, new_priority)
            item.priority = new_priority

    if "assignee_id" in data:
        new_assignee_id = data["assignee_id"] or None
        if new_assignee_id != item.assignee_id:
            from app.models.user import User
            old_name = item.assignee.display_name if item.assignee else "Unassigned"
            new_user = User.query.get(new_assignee_id) if new_assignee_id else None
            new_name = new_user.display_name if new_user else "Unassigned"
            changes["assignee"] = (old_name, new_name)
            item.assignee_id = new_assignee_id

    if "item_type_id" in data:
        from app.models.item_type import ItemType
        new_type = ItemType.query.get(data["item_type_id"])
        if new_type and new_type.project_id == item.project_id and new_type.id != item.item_type_id:
            old_name = item.item_type.name
            changes["type"] = (old_name, new_type.name)
            item.item_type_id = new_type.id

    if "epic_id" in data:
        item.epic_id = data["epic_id"] or None

    if "sprint_id" in data:
        new_sprint_id = data["sprint_id"] or None
        if new_sprint_id != item.sprint_id:
            old_sprint = item.sprint
            new_sprint = Sprint.query.get(new_sprint_id) if new_sprint_id else None
            changes["sprint"] = (
                old_sprint.name if old_sprint else "None",
                new_sprint.name if new_sprint else "None",
            )
            item.sprint_id = new_sprint_id

    if "story_points" in data:
        new_sp = data["story_points"]
        if new_sp is not None:
            raw = str(new_sp).strip()
            try:
                new_sp = int(raw) if raw else None
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid story points value"}), 400
        if new_sp != item.story_points:
            old_sp = item.story_points
            changes["story_points"] = (
                str(old_sp) if old_sp is not None else "unset",
                str(new_sp) if new_sp is not None else "unset",
            )
            item.story_points = new_sp

    if "due_date" in data:
        new_due = None
        if data["due_date"]:
            new_due = datetime.strptime(data["due_date"], "%Y-%m-%d").date()
        if new_due != item.due_date:
            changes["due_date"] = (
                str(item.due_date) if item.due_date else "unset",
                str(new_due) if new_due else "unset",
            )
            item.due_date = new_due

    if "description" in data:
        new_desc = data["description"].strip()
        if new_desc != (item.description or ""):
            old_desc = item.description or ""
            old_preview = (old_desc[:50] + "...") if len(old_desc) > 50 else old_desc
            new_preview = (new_desc[:50] + "...") if len(new_desc) > 50 else new_desc
            changes["description"] = (old_preview or "(empty)", new_preview or "(empty)")
            item.description = new_desc

    for field, (old_val, new_val) in changes.items():
        db.session.add(
            ActivityLog(
                work_item=item,
                user_id=current_user.id,
                field_changed=field,
                old_value=str(old_val),
                new_value=str(new_val),
            )
        )

    db.session.commit()

    return jsonify({
        "ok": True,
        "item": {
            "id": item.id,
            "title": item.title,
            "status": {"id": item.status_id, "name": item.status.name, "color": item.status.color},
            "priority": item.priority,
            "priority_icon": item.priority_icon,
            "priority_color": item.priority_color,
            "assignee": {"id": item.assignee_id, "name": item.assignee.display_name if item.assignee else None},
            "item_type": {"id": item.item_type_id, "name": item.item_type.name, "icon": item.item_type.icon, "color": item.item_type.color},
            "story_points": item.story_points,
            "due_date": item.due_date.isoformat() if item.due_date else None,
        },
    })


@api_bp.route("/items/<int:item_id>/comments", methods=["POST"])
@auth_required()
def add_comment(item_id):
    item = _get_item(item_id)
    data = request.get_json()
    body = data.get("body", "").strip() if data else ""
    if not body:
        return jsonify({"error": "Comment body is required"}), 400

    comment = Comment(work_item=item, author_id=current_user.id, body=body)
    db.session.add(comment)
    db.session.commit()

    return jsonify({
        "ok": True,
        "comment": {
            "id": comment.id,
            "body": comment.body,
            "author": comment.author.display_name,
            "created_at": comment.created_at.strftime("%b %d, %Y %H:%M"),
            "is_mine": True,
        },
    }), 201


@api_bp.route("/items/<int:item_id>/comments/<int:comment_id>", methods=["DELETE"])
@auth_required()
def delete_comment(item_id, comment_id):
    item = _get_item(item_id)
    comment = Comment.query.get_or_404(comment_id)
    if comment.work_item_id != item.id:
        abort(404)
    if comment.author_id != current_user.id:
        abort(403)

    db.session.delete(comment)
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/sprints/<int:sprint_id>/burndown")
@auth_required()
def sprint_burndown(sprint_id):
    from datetime import date, timedelta
    sprint = Sprint.query.get_or_404(sprint_id)
    # Verify access
    sprint_project_ids = [sp.project_id for sp in sprint.sprint_projects]
    membership = ProjectMembership.query.filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.project_id.in_(sprint_project_ids),
    ).first()
    if not membership:
        abort(403)

    items = sprint.work_items
    if not items or not sprint.start_date:
        return jsonify({"dates": [], "ideal": [], "actual": []})

    end = sprint.end_date or date.today()
    if end < sprint.start_date:
        end = sprint.start_date

    total_sp = sum(i.story_points or 0 for i in items)
    item_ids = [i.id for i in items]

    # Get all status changes for these items
    status_logs = (
        ActivityLog.query.filter(
            ActivityLog.work_item_id.in_(item_ids),
            ActivityLog.field_changed == "status",
        ).order_by(ActivityLog.created_at).all()
    )

    # Build a map of item_id -> story_points
    sp_map = {i.id: (i.story_points or 0) for i in items}

    # Track which items were done on each day
    # Start: assume all items are "not done"
    done_items = set()
    log_idx = 0

    # Get all done status names from project statuses
    done_status_names = set()
    for pid in sprint_project_ids:
        from app.models.status import Status as StatusModel
        for s in StatusModel.query.filter_by(project_id=pid, category="done").all():
            done_status_names.add(s.name)

    dates = []
    ideal = []
    actual = []
    num_days = (end - sprint.start_date).days + 1
    if num_days > 365:
        num_days = 365  # safety cap

    for day_offset in range(num_days):
        current_date = sprint.start_date + timedelta(days=day_offset)
        day_end = datetime(current_date.year, current_date.month, current_date.day, 23, 59, 59)

        # Process logs up to this day
        while log_idx < len(status_logs) and status_logs[log_idx].created_at <= day_end:
            log = status_logs[log_idx]
            if log.new_value in done_status_names:
                done_items.add(log.work_item_id)
            elif log.old_value in done_status_names:
                done_items.discard(log.work_item_id)
            log_idx += 1

        done_sp = sum(sp_map.get(iid, 0) for iid in done_items)
        remaining = total_sp - done_sp

        dates.append(current_date.strftime("%b %d"))
        actual.append(remaining)

        # Ideal: linear from total_sp to 0
        if num_days > 1:
            ideal_val = total_sp - (total_sp * day_offset / (num_days - 1))
        else:
            ideal_val = 0
        ideal.append(round(ideal_val, 1))

    return jsonify({"dates": dates, "ideal": ideal, "actual": actual})


@api_bp.route("/velocity")
@auth_required()
def velocity_data():
    project_ids = _user_project_ids()
    completed_sprints = (
        Sprint.query.join(SprintProject)
        .filter(
            SprintProject.project_id.in_(project_ids),
            Sprint.completed_at.isnot(None),
        )
        .distinct()
        .order_by(Sprint.completed_at.desc())
        .limit(10)
        .all()
    )
    return jsonify({
        "sprints": [
            {
                "name": s.name,
                "initial": s.initial_committed_sp,
                "committed": s.committed_sp_snapshot or 0,
                "completed": s.completed_sp_snapshot or 0,
            }
            for s in reversed(completed_sprints)
        ]
    })


@api_bp.route("/epics/<int:epic_id>/burndown")
@auth_required()
def epic_burndown(epic_id):
    from datetime import date, timedelta
    epic = Epic.query.get_or_404(epic_id)
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=epic.project_id
    ).first()
    if not membership:
        abort(403)

    items = epic.work_items
    if not items:
        return jsonify({"dates": [], "actual": []})

    total_sp = sum(i.story_points or 0 for i in items)
    item_ids = [i.id for i in items]
    sp_map = {i.id: (i.story_points or 0) for i in items}

    status_logs = (
        ActivityLog.query.filter(
            ActivityLog.work_item_id.in_(item_ids),
            ActivityLog.field_changed == "status",
        ).order_by(ActivityLog.created_at).all()
    )

    from app.models.status import Status as StatusModel
    done_status_names = set()
    for s in StatusModel.query.filter_by(project_id=epic.project_id, category="done").all():
        done_status_names.add(s.name)

    if not status_logs:
        today = date.today()
        return jsonify({
            "dates": [today.strftime("%b %d")],
            "actual": [total_sp - sum(sp_map.get(i.id, 0) for i in items if i.status.category == "done")],
        })

    start = status_logs[0].created_at.date()
    end = date.today()
    done_items = set()
    log_idx = 0
    dates = []
    actual = []

    num_days = (end - start).days + 1
    if num_days > 365:
        num_days = 365

    for day_offset in range(num_days):
        current_date = start + timedelta(days=day_offset)
        day_end = datetime(current_date.year, current_date.month, current_date.day, 23, 59, 59)

        while log_idx < len(status_logs) and status_logs[log_idx].created_at <= day_end:
            log = status_logs[log_idx]
            if log.new_value in done_status_names:
                done_items.add(log.work_item_id)
            elif log.old_value in done_status_names:
                done_items.discard(log.work_item_id)
            log_idx += 1

        done_sp = sum(sp_map.get(iid, 0) for iid in done_items)
        dates.append(current_date.strftime("%b %d"))
        actual.append(total_sp - done_sp)

    return jsonify({"dates": dates, "actual": actual})


@api_bp.route("/epics/<int:epic_id>", methods=["PATCH"])
@auth_required()
def update_epic(epic_id):
    epic = Epic.query.get_or_404(epic_id)
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=epic.project_id
    ).first()
    if not membership:
        abort(403)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    if "status" in data and data["status"] in ("to_do", "in_progress", "done"):
        epic.status = data["status"]
    if "position" in data:
        try:
            epic.position = int(data["position"])
        except (ValueError, TypeError):
            return jsonify({"error": "position must be an integer"}), 400
    db.session.commit()
    return jsonify({"ok": True, "status": epic.status, "position": epic.position})


@api_bp.route("/projects/<key>/labels", methods=["POST"])
@auth_required()
def create_label(key):
    project = _get_project(key)
    data = request.get_json()
    if not data or not data.get("name", "").strip():
        return jsonify({"error": "Name is required"}), 400
    name = data["name"].strip()
    color = validate_hex_color(data.get("color", "#6b7280"))
    existing = Label.query.filter_by(project_id=project.id, name=name).first()
    if existing:
        return jsonify({"ok": True, "label": {"id": existing.id, "name": existing.name, "color": existing.color}})
    label = Label(project=project, name=name, color=color)
    db.session.add(label)
    db.session.commit()
    return jsonify({"ok": True, "label": {"id": label.id, "name": label.name, "color": label.color}}), 201


@api_bp.route("/items/<int:item_id>/labels", methods=["POST"])
@auth_required()
def add_label(item_id):
    item = _get_item(item_id)
    data = request.get_json()
    label_id = data.get("label_id") if data else None
    if not label_id:
        return jsonify({"error": "label_id required"}), 400
    label = Label.query.get_or_404(label_id)
    if label.project_id != item.project_id:
        abort(400)
    if label not in item.labels:
        item.labels.append(label)
        db.session.commit()
    return jsonify({"ok": True, "label": {"id": label.id, "name": label.name, "color": label.color}})


@api_bp.route("/items/<int:item_id>/labels/<int:label_id>", methods=["DELETE"])
@auth_required()
def remove_label(item_id, label_id):
    item = _get_item(item_id)
    label = Label.query.get_or_404(label_id)
    if label in item.labels:
        item.labels.remove(label)
        db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/items/bulk", methods=["PATCH"])
@auth_required()
def bulk_update():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    item_ids = data.get("item_ids", [])
    changes = data.get("changes", {})
    if not item_ids or not changes:
        return jsonify({"error": "item_ids and changes required"}), 400

    items = (
        WorkItem.query.filter(WorkItem.id.in_(item_ids))
        .options(db.joinedload(WorkItem.status), db.joinedload(WorkItem.assignee))
        .all()
    )
    user_pids = set(_user_project_ids())

    # Pre-fetch status-by-name lookup per project if cross-project status change
    status_name = changes.get("status_name")
    project_status_map = {}
    if status_name:
        statuses = Status.query.filter(
            Status.name == status_name,
            Status.project_id.in_(user_pids),
        ).all()
        for s in statuses:
            project_status_map[s.project_id] = s

    # Pre-validate sprint belongs to each item's project
    new_sprint_id = None
    sprint_project_ids = set()
    if "sprint_id" in changes:
        new_sprint_id = changes["sprint_id"] or None
        if new_sprint_id:
            sprint_project_ids = {
                sp.project_id
                for sp in SprintProject.query.filter_by(sprint_id=new_sprint_id).all()
            }

    # Pre-validate assignee membership per project
    new_aid = None
    assignee_project_ids = set()
    new_assignee_name = None
    if "assignee_id" in changes:
        new_aid = changes["assignee_id"] or None
        if new_aid:
            assignee_project_ids = {
                m.project_id
                for m in ProjectMembership.query.filter_by(user_id=new_aid).all()
            }
            from app.models.user import User
            new_user = User.query.get(new_aid)
            new_assignee_name = new_user.display_name if new_user else "Unassigned"

    # Pre-fetch status by id (single-project path)
    status_by_id = None
    if "status_id" in changes:
        status_by_id = Status.query.get(changes["status_id"])

    updated = 0
    skipped = 0
    for item in items:
        if item.project_id not in user_pids:
            continue

        if status_by_id is not None:
            new_status = status_by_id
            if new_status.project_id == item.project_id and new_status.id != item.status_id:
                db.session.add(ActivityLog(
                    work_item=item, user_id=current_user.id,
                    field_changed="status",
                    old_value=item.status.name, new_value=new_status.name,
                ))
                item.status_id = new_status.id
        elif status_name:
            new_status = project_status_map.get(item.project_id)
            if new_status and new_status.id != item.status_id:
                db.session.add(ActivityLog(
                    work_item=item, user_id=current_user.id,
                    field_changed="status",
                    old_value=item.status.name, new_value=new_status.name,
                ))
                item.status_id = new_status.id
            elif not new_status:
                skipped += 1
                continue

        if "sprint_id" in changes:
            if new_sprint_id is None:
                item.sprint_id = None
            elif item.project_id in sprint_project_ids:
                item.sprint_id = new_sprint_id
            # else: sprint not linked to this project, skip silently

        if "assignee_id" in changes:
            if new_aid is None:
                if item.assignee_id is not None:
                    old_name = item.assignee.display_name if item.assignee else "Unassigned"
                    db.session.add(ActivityLog(
                        work_item=item, user_id=current_user.id,
                        field_changed="assignee",
                        old_value=old_name, new_value="Unassigned",
                    ))
                    item.assignee_id = None
            elif item.project_id in assignee_project_ids:
                if new_aid != item.assignee_id:
                    old_name = item.assignee.display_name if item.assignee else "Unassigned"
                    db.session.add(ActivityLog(
                        work_item=item, user_id=current_user.id,
                        field_changed="assignee",
                        old_value=old_name, new_value=new_assignee_name,
                    ))
                    item.assignee_id = new_aid
            # else: assignee not a member of this project, skip silently

        if "priority" in changes:
            new_p = validate_priority(changes["priority"])
            if new_p != item.priority:
                db.session.add(ActivityLog(
                    work_item=item, user_id=current_user.id,
                    field_changed="priority",
                    old_value=item.priority, new_value=new_p,
                ))
                item.priority = new_p

        updated += 1

    db.session.commit()
    return jsonify({"ok": True, "updated": updated, "skipped": skipped})


@api_bp.route("/items/bulk", methods=["DELETE"])
@auth_required()
def bulk_delete():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    item_ids = data.get("item_ids", [])
    if not item_ids:
        return jsonify({"error": "item_ids required"}), 400

    items = WorkItem.query.filter(WorkItem.id.in_(item_ids)).all()
    user_pids = set(_user_project_ids())
    deleted = 0
    for item in items:
        if item.project_id in user_pids:
            db.session.delete(item)
            deleted += 1

    db.session.commit()
    return jsonify({"ok": True, "deleted": deleted})


# ---- Links / Relations ----

@api_bp.route("/items/<int:item_id>/links", methods=["GET"])
@auth_required()
def get_links(item_id):
    from sqlalchemy.orm import joinedload, selectinload
    item = WorkItem.query.options(
        selectinload(WorkItem.outgoing_links).joinedload(WorkItemLink.target).joinedload(WorkItem.project),
        selectinload(WorkItem.incoming_links).joinedload(WorkItemLink.source).joinedload(WorkItem.project),
    ).get_or_404(item_id)
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=item.project_id
    ).first()
    if not membership:
        abort(403)
    links = []
    for link in item.outgoing_links:
        links.append({
            "id": link.id,
            "direction": "outgoing",
            "link_type": link.link_type,
            "label": LINK_TYPES.get(link.link_type, {}).get("label", link.link_type),
            "item": {
                "id": link.target.id,
                "item_key": link.target.item_key,
                "title": link.target.title,
                "project_key": link.target.project.key,
            },
        })
    for link in item.incoming_links:
        reverse_type = LINK_REVERSE.get(link.link_type, link.link_type)
        links.append({
            "id": link.id,
            "direction": "incoming",
            "link_type": reverse_type,
            "label": LINK_TYPES.get(reverse_type, {}).get("label", reverse_type),
            "item": {
                "id": link.source.id,
                "item_key": link.source.item_key,
                "title": link.source.title,
                "project_key": link.source.project.key,
            },
        })
    return jsonify({"links": links})


@api_bp.route("/items/<int:item_id>/links", methods=["POST"])
@auth_required()
def add_link(item_id):
    item = _get_item(item_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    link_type = data.get("link_type")
    target_key = data.get("target_key", "").strip().upper()

    if link_type not in LINK_TYPES:
        return jsonify({"error": "Invalid link type"}), 400

    target = WorkItem.query.filter_by(item_key=target_key).first()
    if not target:
        return jsonify({"error": "Item not found: " + target_key}), 404
    if target.id == item.id:
        return jsonify({"error": "Cannot link item to itself"}), 400

    # Check for existing link
    existing = WorkItemLink.query.filter_by(
        source_id=item.id, target_id=target.id, link_type=link_type
    ).first()
    if existing:
        return jsonify({"error": "Link already exists"}), 409

    link = WorkItemLink(source_id=item.id, target_id=target.id, link_type=link_type)
    db.session.add(link)
    db.session.commit()

    return jsonify({
        "ok": True,
        "link": {
            "id": link.id,
            "direction": "outgoing",
            "link_type": link.link_type,
            "label": LINK_TYPES[link.link_type]["label"],
            "item": {
                "id": target.id,
                "item_key": target.item_key,
                "title": target.title,
                "project_key": target.project.key,
            },
        },
    })


@api_bp.route("/items/<int:item_id>/links/<int:link_id>", methods=["DELETE"])
@auth_required()
def delete_link(item_id, link_id):
    _get_item(item_id)
    link = WorkItemLink.query.get_or_404(link_id)
    if link.source_id != item_id and link.target_id != item_id:
        abort(404)
    db.session.delete(link)
    db.session.commit()
    return jsonify({"ok": True})
