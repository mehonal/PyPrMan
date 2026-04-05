from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.project import Project, ProjectMembership
from app.models.sprint import Sprint, SprintProject

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
        .order_by(Sprint.start_date.desc().nullslast(), Sprint.id.desc())
        .all()
    )
    return render_template("sprints/list.html", sprints=sprints)


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
    sprint.is_active = False
    db.session.commit()
    flash("Sprint completed.", "success")
    return redirect(url_for("sprints.list_sprints"))
