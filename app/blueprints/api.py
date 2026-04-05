from datetime import datetime

from flask import Blueprint, abort, jsonify, request
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.activity import ActivityLog, Comment
from app.models.epic import Epic
from app.models.project import Project, ProjectMembership
from app.models.sprint import Sprint, SprintProject
from app.models.status import Status
from app.models.work_item import WorkItem
from app.validation import (
    validate_hex_color,
    validate_icon_class,
    validate_priority,
    validate_status_category,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _get_project(key):
    project = Project.query.filter_by(key=key.upper()).first_or_404()
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=project.id
    ).first()
    if not membership:
        abort(403)
    return project


def _get_item(item_id):
    item = WorkItem.query.get_or_404(item_id)
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=item.project_id
    ).first()
    if not membership:
        abort(403)
    return item


def _user_project_ids():
    return [
        m.project_id
        for m in ProjectMembership.query.filter_by(user_id=current_user.id).all()
    ]


@api_bp.route("/projects/<key>/form-options")
@auth_required()
def form_options(key):
    project = _get_project(key)
    members = ProjectMembership.query.filter_by(project_id=project.id).all()

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
            "sprints": [
                {"id": s.id, "name": s.name, "is_active": s.is_active}
                for s in sprints
            ],
            "members": [
                {"id": m.user.id, "name": m.user.display_name}
                for m in members
            ],
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
    if data.get("start_date"):
        start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
    if data.get("end_date"):
        end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date()

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
        item.sprint_id = data["sprint_id"] or None

    if "story_points" in data:
        new_sp = data["story_points"]
        if new_sp is not None:
            new_sp = int(new_sp) if str(new_sp).strip() else None
        if new_sp != item.story_points:
            old_sp = item.story_points
            changes["story_points"] = (
                str(old_sp) if old_sp is not None else "unset",
                str(new_sp) if new_sp is not None else "unset",
            )
            item.story_points = new_sp

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
