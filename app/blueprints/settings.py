from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.item_type import ItemType
from app.models.label import Label
from app.models.project import Project, ProjectMembership
from app.models.status import Status
from app.models.user import User
from app.validation import validate_hex_color, validate_icon_class, validate_status_category

settings_bp = Blueprint("settings", __name__, url_prefix="/projects/<key>/settings")


def _get_project_admin(key):
    project = Project.query.filter_by(key=key.upper()).first_or_404()
    membership = ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=project.id
    ).first()
    if not membership or membership.role not in ("owner", "admin"):
        abort(403)
    return project


@settings_bp.route("/statuses", methods=["GET", "POST"])
@auth_required()
def manage_statuses(key):
    project = _get_project_admin(key)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            name = request.form.get("name", "").strip()
            category = validate_status_category(request.form.get("category", "todo"))
            color = validate_hex_color(request.form.get("color", "#6b7280"))
            if name:
                max_pos = (
                    db.session.query(db.func.max(Status.position))
                    .filter_by(project_id=project.id)
                    .scalar()
                    or 0
                )
                db.session.add(
                    Status(
                        project=project,
                        name=name,
                        category=category,
                        color=color,
                        position=max_pos + 1,
                    )
                )
                db.session.commit()
                flash("Status added.", "success")

        elif action == "edit":
            status_id = request.form.get("status_id", type=int)
            status = Status.query.get_or_404(status_id)
            if status.project_id != project.id:
                abort(404)
            status.name = request.form.get("name", "").strip() or status.name
            status.category = validate_status_category(request.form.get("category", status.category))
            status.color = validate_hex_color(request.form.get("color", status.color))
            db.session.commit()
            flash("Status updated.", "success")

        elif action == "delete":
            status_id = request.form.get("status_id", type=int)
            status = Status.query.get_or_404(status_id)
            if status.project_id != project.id:
                abort(404)
            if status.work_items:
                flash("Cannot delete status with existing work items.", "danger")
            else:
                db.session.delete(status)
                db.session.commit()
                flash("Status deleted.", "success")

        elif action == "move_up" or action == "move_down":
            status_id = request.form.get("status_id", type=int)
            statuses = Status.query.filter_by(project_id=project.id).order_by(Status.position).all()
            idx = next((i for i, s in enumerate(statuses) if s.id == status_id), None)
            if idx is not None:
                swap_idx = idx - 1 if action == "move_up" else idx + 1
                if 0 <= swap_idx < len(statuses):
                    statuses[idx].position, statuses[swap_idx].position = statuses[swap_idx].position, statuses[idx].position
                    db.session.commit()

        return redirect(url_for("settings.manage_statuses", key=key))

    statuses = Status.query.filter_by(project_id=project.id).order_by(Status.position).all()
    return render_template("settings/statuses.html", project=project, statuses=statuses)


@settings_bp.route("/types", methods=["GET", "POST"])
@auth_required()
def manage_types(key):
    project = _get_project_admin(key)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            name = request.form.get("name", "").strip()
            icon = validate_icon_class(request.form.get("icon", "bi-circle").strip())
            color = validate_hex_color(request.form.get("color", "#6b7280"))
            if name:
                db.session.add(
                    ItemType(project=project, name=name, icon=icon, color=color)
                )
                db.session.commit()
                flash("Type added.", "success")

        elif action == "edit":
            type_id = request.form.get("type_id", type=int)
            item_type = ItemType.query.get_or_404(type_id)
            if item_type.project_id != project.id:
                abort(404)
            item_type.name = request.form.get("name", "").strip() or item_type.name
            item_type.icon = validate_icon_class(request.form.get("icon", item_type.icon).strip())
            item_type.color = validate_hex_color(request.form.get("color", item_type.color))
            db.session.commit()
            flash("Type updated.", "success")

        elif action == "delete":
            type_id = request.form.get("type_id", type=int)
            item_type = ItemType.query.get_or_404(type_id)
            if item_type.project_id != project.id:
                abort(404)
            if item_type.work_items:
                flash("Cannot delete type with existing work items.", "danger")
            else:
                db.session.delete(item_type)
                db.session.commit()
                flash("Type deleted.", "success")

        return redirect(url_for("settings.manage_types", key=key))

    types = ItemType.query.filter_by(project_id=project.id).all()
    return render_template("settings/types.html", project=project, types=types)


@settings_bp.route("/members", methods=["GET", "POST"])
@auth_required()
def manage_members(key):
    project = _get_project_admin(key)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            email = request.form.get("email", "").strip()
            role = request.form.get("role", "member")
            if role not in ("member", "admin"):
                role = "member"
            user = User.query.filter_by(email=email).first()
            if not user:
                flash("User not found.", "danger")
            elif ProjectMembership.query.filter_by(
                user_id=user.id, project_id=project.id
            ).first():
                flash("User is already a member.", "warning")
            else:
                db.session.add(
                    ProjectMembership(user=user, project=project, role=role)
                )
                db.session.commit()
                flash("Member added.", "success")

        elif action == "remove":
            membership_id = request.form.get("membership_id", type=int)
            membership = ProjectMembership.query.get_or_404(membership_id)
            if membership.project_id != project.id:
                abort(404)
            if membership.role == "owner" and membership.user_id == current_user.id:
                flash("Cannot remove yourself as owner.", "danger")
            else:
                db.session.delete(membership)
                db.session.commit()
                flash("Member removed.", "success")

        elif action == "change_role":
            membership_id = request.form.get("membership_id", type=int)
            new_role = request.form.get("role", "member")
            if new_role not in ("member", "admin", "owner"):
                new_role = "member"
            membership = ProjectMembership.query.get_or_404(membership_id)
            if membership.project_id != project.id:
                abort(404)
            membership.role = new_role
            db.session.commit()
            flash("Role updated.", "success")

        return redirect(url_for("settings.manage_members", key=key))

    memberships = ProjectMembership.query.filter_by(project_id=project.id).all()
    return render_template(
        "settings/members.html", project=project, memberships=memberships
    )


@settings_bp.route("/labels", methods=["GET", "POST"])
@auth_required()
def manage_labels(key):
    project = _get_project_admin(key)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            name = request.form.get("name", "").strip()
            color = validate_hex_color(request.form.get("color", "#6b7280"))
            if name:
                db.session.add(Label(project=project, name=name, color=color))
                db.session.commit()
                flash("Label added.", "success")

        elif action == "edit":
            label_id = request.form.get("label_id", type=int)
            label = Label.query.get_or_404(label_id)
            if label.project_id != project.id:
                abort(404)
            label.name = request.form.get("name", "").strip() or label.name
            label.color = validate_hex_color(request.form.get("color", label.color))
            db.session.commit()
            flash("Label updated.", "success")

        elif action == "delete":
            label_id = request.form.get("label_id", type=int)
            label = Label.query.get_or_404(label_id)
            if label.project_id != project.id:
                abort(404)
            db.session.delete(label)
            db.session.commit()
            flash("Label deleted.", "success")

        return redirect(url_for("settings.manage_labels", key=key))

    labels = Label.query.filter_by(project_id=project.id).all()
    return render_template("settings/labels.html", project=project, labels=labels)
