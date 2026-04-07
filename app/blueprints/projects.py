from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.project import Project, ProjectMembership
from app.models.work_item import WorkItem

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


def get_user_project(key):
    project = Project.query.filter_by(key=key.upper()).first_or_404()
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=project.id
    ).first()
    if not membership:
        abort(403)
    return project, membership


@projects_bp.route("/")
@auth_required()
def list_projects():
    memberships = ProjectMembership.query.filter_by(user_id=current_user.id).all()
    projects = [m.project for m in memberships]
    return render_template("projects/list.html", projects=projects)


@projects_bp.route("/new", methods=["GET", "POST"])
@auth_required()
def create_project():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        key = request.form.get("key", "").strip().upper()
        description = request.form.get("description", "").strip()

        if not name or not key:
            flash("Name and key are required.", "danger")
            return render_template("projects/form.html", project=None)

        if len(key) > 10 or not key.isalpha():
            flash("Key must be 1-10 letters only.", "danger")
            return render_template("projects/form.html", project=None)

        if Project.query.filter_by(key=key).first():
            flash("A project with this key already exists.", "danger")
            return render_template("projects/form.html", project=None)

        project = Project(
            name=name, key=key, description=description, created_by=current_user
        )
        db.session.add(project)

        membership = ProjectMembership(
            user=current_user, project=project, role="owner"
        )
        db.session.add(membership)

        project.create_default_statuses()
        project.create_default_item_types()
        db.session.commit()

        flash("Project created.", "success")
        return redirect(url_for("projects.detail", key=project.key))

    return render_template("projects/form.html", project=None)


@projects_bp.route("/<key>")
@auth_required()
def detail(key):
    project, membership = get_user_project(key)
    recent_items = (
        WorkItem.query.filter_by(project_id=project.id)
        .options(
            db.joinedload(WorkItem.item_type),
            db.joinedload(WorkItem.status),
            db.joinedload(WorkItem.assignee),
        )
        .order_by(WorkItem.updated_at.desc())
        .limit(20)
        .all()
    )
    total_items = WorkItem.query.filter_by(project_id=project.id).count()
    return render_template(
        "projects/detail.html",
        project=project,
        membership=membership,
        recent_items=recent_items,
        total_items=total_items,
    )


@projects_bp.route("/<key>/edit", methods=["GET", "POST"])
@auth_required()
def edit_project(key):
    project, membership = get_user_project(key)
    if membership.role not in ("owner", "admin"):
        abort(403)

    if request.method == "POST":
        project.name = request.form.get("name", "").strip() or project.name
        project.description = request.form.get("description", "").strip()
        db.session.commit()
        flash("Project updated.", "success")
        return redirect(url_for("projects.detail", key=project.key))

    return render_template("projects/form.html", project=project)


@projects_bp.route("/<key>/delete", methods=["POST"])
@auth_required()
def delete_project(key):
    project, membership = get_user_project(key)
    if membership.role != "owner":
        abort(403)

    db.session.delete(project)
    db.session.commit()
    flash("Project deleted.", "success")
    return redirect(url_for("projects.list_projects"))
