from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.activity import ActivityLog
from app.models.project import Project, ProjectMembership
from app.models.sprint import Sprint, SprintProject
from app.models.status import Status
from app.models.work_item import WorkItem

sprints_bp = Blueprint("sprints", __name__, url_prefix="/sprints")


def _user_project_ids():
    return [
        m.project_id
        for m in ProjectMembership.query.filter_by(user_id=current_user.id).all()
    ]


@sprints_bp.route("/")
@auth_required()
def list_sprints():
    project_ids = _user_project_ids()
    sprints = (
        Sprint.query.join(SprintProject)
        .filter(SprintProject.project_id.in_(project_ids))
        .distinct()
        .options(
            db.selectinload(Sprint.sprint_projects).joinedload(SprintProject.project),
            db.selectinload(Sprint.work_items).joinedload(WorkItem.status),
        )
        .order_by(Sprint.start_date.desc().nullslast(), Sprint.id.desc())
        .all()
    )
    completed_sprints = [
        s for s in sprints if s.completed_sp_snapshot is not None
    ][:5]
    avg_velocity = None
    if completed_sprints:
        avg_velocity = round(
            sum(s.completed_sp_snapshot for s in completed_sprints)
            / len(completed_sprints)
        )
    return render_template(
        "sprints/list.html",
        sprints=sprints,
        avg_velocity=avg_velocity,
        velocity_sprint_count=len(completed_sprints),
    )


@sprints_bp.route("/project/<key>")
@auth_required()
def project_sprints(key):
    project = Project.query.filter_by(key=key.upper()).first_or_404()
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=project.id
    ).first()
    if not membership:
        abort(403)

    sprints = (
        Sprint.query.join(SprintProject)
        .filter(SprintProject.project_id == project.id)
        .options(
            db.selectinload(Sprint.sprint_projects).joinedload(SprintProject.project),
            db.selectinload(Sprint.work_items).joinedload(WorkItem.status),
        )
        .order_by(Sprint.start_date.desc().nullslast(), Sprint.id.desc())
        .all()
    )
    completed_sprints = [
        s for s in sprints if s.completed_sp_snapshot is not None
    ][:5]
    avg_velocity = None
    if completed_sprints:
        avg_velocity = round(
            sum(s.completed_sp_snapshot for s in completed_sprints)
            / len(completed_sprints)
        )
    return render_template(
        "sprints/list.html",
        sprints=sprints,
        avg_velocity=avg_velocity,
        velocity_sprint_count=len(completed_sprints),
        project=project,
    )


@sprints_bp.route("/<int:sprint_id>/detail")
@auth_required()
def sprint_detail(sprint_id):
    sprint = Sprint.query.options(
        db.selectinload(Sprint.sprint_projects),
        db.selectinload(Sprint.work_items)
        .joinedload(WorkItem.status),
        db.selectinload(Sprint.work_items)
        .joinedload(WorkItem.item_type),
        db.selectinload(Sprint.work_items)
        .joinedload(WorkItem.project),
    ).get_or_404(sprint_id)
    sprint_project_ids = [sp.project_id for sp in sprint.sprint_projects]
    membership = ProjectMembership.query.filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.project_id.in_(sprint_project_ids),
    ).first()
    if not membership:
        abort(403)

    items = sprint.work_items
    completed_items = [i for i in items if i.status.category == "done"]
    carryover_items = [i for i in items if i.status.category != "done"] if sprint.completed_at else []

    committed_sp = sum(i.story_points or 0 for i in items)
    completed_sp = sum(i.story_points or 0 for i in completed_items)

    # Scope changes: items added/removed from this sprint
    scope_changes = ActivityLog.query.filter(
        ActivityLog.work_item_id.in_([i.id for i in items]),
        ActivityLog.field_changed == "sprint",
    ).order_by(ActivityLog.created_at).all() if items else []

    return render_template(
        "sprints/detail.html",
        sprint=sprint,
        items=items,
        completed_items=completed_items,
        carryover_items=carryover_items,
        committed_sp=committed_sp,
        completed_sp=completed_sp,
        scope_changes=scope_changes,
    )


@sprints_bp.route("/new", methods=["GET", "POST"])
@auth_required()
def create_sprint():
    project_ids = _user_project_ids()
    projects = Project.query.filter(Project.id.in_(project_ids)).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        goal = request.form.get("goal", "").strip()
        start_date_str = request.form.get("start_date", "").strip()
        end_date_str = request.form.get("end_date", "").strip()
        selected_project_ids = request.form.getlist("project_ids", type=int)

        if not name:
            flash("Name is required.", "danger")
            return render_template("sprints/form.html", sprint=None, projects=projects, selected_project_ids=[])

        if not selected_project_ids:
            flash("Select at least one project.", "danger")
            return render_template("sprints/form.html", sprint=None, projects=projects, selected_project_ids=[])

        start_date = None
        end_date = None
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        sprint = Sprint(
            name=name,
            goal=goal,
            start_date=start_date,
            end_date=end_date,
            created_by=current_user,
        )
        db.session.add(sprint)

        for pid in selected_project_ids:
            if pid in project_ids:
                db.session.add(SprintProject(sprint=sprint, project_id=pid))

        db.session.commit()
        flash("Sprint created.", "success")
        return redirect(url_for("sprints.list_sprints"))

    return render_template("sprints/form.html", sprint=None, projects=projects, selected_project_ids=[])


@sprints_bp.route("/<int:sprint_id>/edit", methods=["GET", "POST"])
@auth_required()
def edit_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    sprint_project_ids = [sp.project_id for sp in sprint.sprint_projects]
    user_memberships = ProjectMembership.query.filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.project_id.in_(sprint_project_ids),
    ).all()
    if not user_memberships:
        abort(403)
    if not any(m.role in ("owner", "admin") for m in user_memberships):
        abort(403)
    project_ids = _user_project_ids()

    projects = Project.query.filter(Project.id.in_(project_ids)).all()

    if request.method == "POST":
        sprint.name = request.form.get("name", "").strip() or sprint.name
        sprint.goal = request.form.get("goal", "").strip()
        start_date_str = request.form.get("start_date", "").strip()
        end_date_str = request.form.get("end_date", "").strip()
        selected_project_ids = request.form.getlist("project_ids", type=int)

        if start_date_str:
            sprint.start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        if end_date_str:
            sprint.end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        SprintProject.query.filter_by(sprint_id=sprint.id).delete()
        for pid in selected_project_ids:
            if pid in project_ids:
                db.session.add(SprintProject(sprint=sprint, project_id=pid))

        db.session.commit()
        flash("Sprint updated.", "success")
        return redirect(url_for("sprints.list_sprints"))

    return render_template(
        "sprints/form.html",
        sprint=sprint,
        projects=projects,
        selected_project_ids=sprint_project_ids,
    )


@sprints_bp.route("/<int:sprint_id>/start", methods=["POST"])
@auth_required()
def start_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    sprint_project_ids = [sp.project_id for sp in sprint.sprint_projects]
    membership = ProjectMembership.query.filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.project_id.in_(sprint_project_ids),
    ).first()
    if not membership:
        abort(403)
    sprint.is_active = True
    db.session.commit()
    flash("Sprint started.", "success")
    return redirect(url_for("sprints.list_sprints"))


@sprints_bp.route("/<int:sprint_id>/complete", methods=["POST"])
@auth_required()
def complete_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    sprint_project_ids = [sp.project_id for sp in sprint.sprint_projects]
    membership = ProjectMembership.query.filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.project_id.in_(sprint_project_ids),
    ).first()
    if not membership:
        abort(403)
    sprint.committed_sp_snapshot = sum(
        i.story_points or 0 for i in sprint.work_items
    )
    sprint.completed_sp_snapshot = sum(
        i.story_points or 0
        for i in sprint.work_items
        if i.status.category == "done"
    )
    sprint.completed_at = datetime.utcnow()
    sprint.is_active = False
    db.session.commit()
    flash("Sprint completed.", "success")
    return redirect(url_for("sprints.list_sprints"))


@sprints_bp.route("/<int:sprint_id>/delete", methods=["POST"])
@auth_required()
def delete_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    sprint_project_ids = [sp.project_id for sp in sprint.sprint_projects]
    user_memberships = ProjectMembership.query.filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.project_id.in_(sprint_project_ids),
    ).all()
    if not user_memberships:
        abort(403)
    if not any(m.role in ("owner", "admin") for m in user_memberships):
        flash("Only project admins can delete sprints.", "danger")
        return redirect(url_for("sprints.list_sprints"))

    # Unassign all items from this sprint
    WorkItem.query.filter_by(sprint_id=sprint.id).update({"sprint_id": None})
    # Clean up sprint-project associations and the sprint itself
    SprintProject.query.filter_by(sprint_id=sprint.id).delete()
    db.session.delete(sprint)
    db.session.commit()
    flash("Sprint deleted. Items have been moved to backlog.", "success")
    return redirect(url_for("sprints.list_sprints"))
