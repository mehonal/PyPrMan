from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user

from app.extensions import db

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
