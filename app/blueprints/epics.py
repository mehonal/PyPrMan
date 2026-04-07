from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.epic import Epic
from app.models.project import Project, ProjectMembership
from app.models.work_item import WorkItem
from app.validation import validate_hex_color

epics_bp = Blueprint("epics", __name__, url_prefix="/projects/<key>/epics")


def _get_project(key):
    project = Project.query.filter_by(key=key.upper()).first_or_404()
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=project.id
    ).first()
    if not membership:
        abort(403)
    return project


def _epic_sp_stats(epic):
    total = sum(i.story_points or 0 for i in epic.work_items)
    done = sum(
        i.story_points or 0
        for i in epic.work_items
        if i.status.category == "done"
    )
    pct = round(done * 100 / total) if total else 0
    return {"total": total, "done": done, "pct": pct}


EPIC_STATUSES = ["to_do", "in_progress", "done"]


@epics_bp.route("/")
@auth_required()
def list_epics(key):
    project = _get_project(key)
    epics = (
        Epic.query.filter_by(project_id=project.id)
        .options(db.selectinload(Epic.work_items).joinedload(WorkItem.status))
        .order_by(Epic.position)
        .all()
    )
    epic_stats = {epic.id: _epic_sp_stats(epic) for epic in epics}
    return render_template(
        "epics/list.html", project=project, epics=epics, epic_stats=epic_stats
    )


@epics_bp.route("/<int:epic_id>")
@auth_required()
def detail_epic(key, epic_id):
    project = _get_project(key)
    epic = (
        Epic.query.options(
            db.selectinload(Epic.work_items).joinedload(WorkItem.status),
            db.selectinload(Epic.work_items).joinedload(WorkItem.item_type),
            db.selectinload(Epic.work_items).joinedload(WorkItem.assignee),
        )
        .get_or_404(epic_id)
    )
    if epic.project_id != project.id:
        abort(404)
    stats = _epic_sp_stats(epic)
    return render_template("epics/detail.html", project=project, epic=epic, epic_stats=stats)


@epics_bp.route("/new", methods=["GET", "POST"])
@auth_required()
def create_epic(key):
    project = _get_project(key)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        color = validate_hex_color(request.form.get("color", "#8b5cf6").strip(), "#8b5cf6")

        if not name:
            flash("Name is required.", "danger")
            return render_template("epics/form.html", project=project, epic=None)

        epic = Epic(project=project, name=name, description=description, color=color)
        db.session.add(epic)
        db.session.commit()
        flash("Epic created.", "success")
        return redirect(url_for("epics.list_epics", key=key))

    return render_template("epics/form.html", project=project, epic=None)


@epics_bp.route("/<int:epic_id>/edit", methods=["GET", "POST"])
@auth_required()
def edit_epic(key, epic_id):
    project = _get_project(key)
    epic = Epic.query.get_or_404(epic_id)
    if epic.project_id != project.id:
        abort(404)

    if request.method == "POST":
        epic.name = request.form.get("name", "").strip() or epic.name
        epic.description = request.form.get("description", "").strip()
        epic.color = validate_hex_color(request.form.get("color", epic.color).strip(), epic.color)
        new_status = request.form.get("status", epic.status)
        if new_status in EPIC_STATUSES:
            epic.status = new_status
        db.session.commit()
        flash("Epic updated.", "success")
        return redirect(url_for("epics.list_epics", key=key))

    return render_template("epics/form.html", project=project, epic=epic)


@epics_bp.route("/<int:epic_id>/delete", methods=["POST"])
@auth_required()
def delete_epic(key, epic_id):
    project = _get_project(key)
    epic = Epic.query.get_or_404(epic_id)
    if epic.project_id != project.id:
        abort(404)

    db.session.delete(epic)
    db.session.commit()
    flash("Epic deleted.", "success")
    return redirect(url_for("epics.list_epics", key=key))


@epics_bp.route("/reorder", methods=["POST"])
@auth_required()
def reorder_epic(key):
    project = _get_project(key)
    action = request.form.get("action")
    epic_id = request.form.get("epic_id", type=int)

    epics = Epic.query.filter_by(project_id=project.id).order_by(Epic.position).all()
    idx = next((i for i, e in enumerate(epics) if e.id == epic_id), None)
    if idx is not None:
        swap_idx = idx - 1 if action == "move_up" else idx + 1
        if 0 <= swap_idx < len(epics):
            epics[idx].position, epics[swap_idx].position = epics[swap_idx].position, epics[idx].position
            db.session.commit()

    return redirect(url_for("epics.list_epics", key=key))


@epics_bp.route("/board")
@auth_required()
def epic_board(key):
    project = _get_project(key)
    epics = (
        Epic.query.filter_by(project_id=project.id)
        .options(db.selectinload(Epic.work_items).joinedload(WorkItem.status))
        .order_by(Epic.position)
        .all()
    )
    columns = {
        "to_do": {"label": "To Do", "epics": []},
        "in_progress": {"label": "In Progress", "epics": []},
        "done": {"label": "Done", "epics": []},
    }
    for epic in epics:
        columns.get(epic.status, columns["to_do"])["epics"].append(epic)
    epic_stats = {e.id: _epic_sp_stats(e) for e in epics}
    return render_template(
        "epics/board.html", project=project, columns=columns, epic_stats=epic_stats
    )
