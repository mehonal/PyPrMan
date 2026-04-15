from collections import defaultdict
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.activity import ActivityLog
from app.models.project import Project, ProjectMembership
from app.models.sprint import Sprint, SprintProject
from app.models.status import Status
from app.models.work_item import WorkItem
from app.blueprints.helpers import user_project_ids as user_project_ids

sprints_bp = Blueprint("sprints", __name__, url_prefix="/sprints")


@sprints_bp.route("/")
@auth_required()
def list_sprints():
    project_ids = user_project_ids()
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
    done_status_names = {
        s.name for s in Status.query.filter_by(
            project_id=project.id, category="done"
        ).all()
    }

    # Per-project stats for sprint list badges
    sprint_stats = {}
    for s in sprints:
        proj_items = [i for i in s.work_items if i.project_id == project.id]
        sprint_stats[s.id] = {
            "item_count": len(proj_items),
            "committed_sp": sum(i.story_points or 0 for i in proj_items),
            "completed_sp": sum(
                i.story_points or 0 for i in proj_items
                if i.status.name in done_status_names
            ),
        }

    completed_sprints = [
        s for s in sprints if s.completed_at is not None
    ][:5]
    avg_velocity = None
    if completed_sprints:
        avg_velocity = round(
            sum(sprint_stats[s.id]["completed_sp"] for s in completed_sprints)
            / len(completed_sprints)
        )
    return render_template(
        "sprints/list.html",
        sprints=sprints,
        avg_velocity=avg_velocity,
        velocity_sprint_count=len(completed_sprints),
        project=project,
        sprint_stats=sprint_stats,
    )


@sprints_bp.route("/<int:sprint_id>/detail")
@auth_required()
def sprint_detail(sprint_id):
    sprint = Sprint.query.options(
        db.selectinload(Sprint.sprint_projects).joinedload(SprintProject.project),
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

    all_items = sprint.work_items

    # Per-project filtering
    project_key = request.args.get("project")
    project = None
    if project_key:
        project = Project.query.filter_by(key=project_key.upper()).first()
    if project:
        items = [i for i in all_items if i.project_id == project.id]
    else:
        items = all_items

    completed_items = [i for i in items if i.status.category == "done"]
    carryover_items = [i for i in items if i.status.category != "done"] if sprint.completed_at else []

    committed_sp = sum(i.story_points or 0 for i in items)
    completed_sp = sum(i.story_points or 0 for i in completed_items)

    # Project SP breakdown for multi-project sprints
    project_breakdown = []
    if len(sprint.sprint_projects) > 1:
        sp_by_project = defaultdict(int)
        for i in all_items:
            sp_by_project[i.project_id] += i.story_points or 0
        for sp_assoc in sprint.sprint_projects:
            project_breakdown.append({
                "key": sp_assoc.project.key,
                "name": sp_assoc.project.name,
                "sp": sp_by_project.get(sp_assoc.project_id, 0),
                "current": project is not None and sp_assoc.project_id == project.id,
            })

    # SP by status category
    sp_by_category = defaultdict(int)
    for i in items:
        sp_by_category[i.status.category] += i.story_points or 0
    status_breakdown = [
        {"category": "todo", "label": "To Do", "sp": sp_by_category.get("todo", 0)},
        {"category": "in_progress", "label": "In Progress", "sp": sp_by_category.get("in_progress", 0)},
        {"category": "done", "label": "Done", "sp": sp_by_category.get("done", 0)},
    ]

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
        project=project,
        project_breakdown=project_breakdown,
        status_breakdown=status_breakdown,
    )


@sprints_bp.route("/new", methods=["GET", "POST"])
@auth_required()
def create_sprint():
    project_ids = user_project_ids()
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
    project_ids = user_project_ids()

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
    sprint = Sprint.query.options(
        db.selectinload(Sprint.work_items),
    ).get_or_404(sprint_id)
    sprint_project_ids = [sp.project_id for sp in sprint.sprint_projects]
    membership = ProjectMembership.query.filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.project_id.in_(sprint_project_ids),
    ).first()
    if not membership:
        abort(403)
    sprint.initial_committed_sp = sum(
        i.story_points or 0 for i in sprint.work_items
    )
    sprint.is_active = True
    db.session.commit()
    flash("Sprint started.", "success")
    return redirect(url_for("sprints.list_sprints"))


@sprints_bp.route("/<int:sprint_id>/complete", methods=["POST"])
@auth_required()
def complete_sprint(sprint_id):
    sprint = Sprint.query.options(
        db.selectinload(Sprint.work_items).joinedload(WorkItem.status),
    ).get_or_404(sprint_id)
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
