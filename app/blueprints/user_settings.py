import uuid

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user, logout_user

from app.extensions import db
from app.models.project import ProjectMembership
from app.models.work_item import WorkItem

user_settings_bp = Blueprint("user_settings", __name__, url_prefix="/settings")


@user_settings_bp.route("/profile", methods=["GET", "POST"])
@auth_required()
def profile():
    if request.method == "POST":
        name = request.form.get("display_name", "").strip()
        if len(name) > 100:
            name = name[:100]
        current_user.display_name = name

        default_assignee = request.form.get("default_assignee", "unassigned")
        if default_assignee not in ("unassigned", "me"):
            default_assignee = "unassigned"
        current_user.default_assignee = default_assignee

        board_sprint = request.form.get("board_sprint_filter") == "on"
        current_user.board_sprint_filter = board_sprint

        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("user_settings.profile"))

    return render_template("user_settings/profile.html")


@user_settings_bp.route("/delete-account", methods=["POST"])
@auth_required()
def delete_account():
    confirmation = request.form.get("confirmation", "").strip()
    if confirmation != current_user.email:
        flash("Email confirmation did not match. Account was not deleted.", "danger")
        return redirect(url_for("user_settings.profile"))

    user = current_user._get_current_object()

    WorkItem.query.filter_by(assignee_id=user.id).update({"assignee_id": None})
    ProjectMembership.query.filter_by(user_id=user.id).delete()

    user.active = False
    user.email = f"deleted-{user.id}-{uuid.uuid4().hex[:8]}@deleted.local"
    user._display_name = "Deleted User"
    user.password = "!"
    user.fs_uniquifier = uuid.uuid4().hex

    db.session.commit()
    logout_user()
    flash("Your account has been deleted.", "success")
    return redirect(url_for("security.login"))
