from flask import Blueprint, render_template, request
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.notification import Notification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")

PER_PAGE = 30


@notifications_bp.route("/")
@auth_required()
def list_notifications():
    page = request.args.get("page", 1, type=int)
    query = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    )
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template(
        "notifications/list.html",
        notifications=pagination.items,
        pagination=pagination,
    )
