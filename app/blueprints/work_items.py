from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.activity import ActivityLog, Comment
from app.models.epic import Epic
from app.models.project import Project, ProjectMembership
from app.models.sprint import Sprint, SprintProject
from app.models.watcher import Watcher
from app.models.work_item import WorkItem
from app.blueprints.helpers import get_project as _get_project
from app.validation import validate_priority

work_items_bp = Blueprint("work_items", __name__, url_prefix="/projects/<key>/items")


def _get_sprints_for_project(project):
    return (
        Sprint.query.join(SprintProject)
        .filter(SprintProject.project_id == project.id)
        .all()
    )


def _get_members(project):
    from app.models.user import User

    memberships = ProjectMembership.query.filter_by(project_id=project.id).all()
    if not memberships:
        return []
    user_ids = [m.user_id for m in memberships]
    return User.query.filter(User.id.in_(user_ids)).all()


def _log_change(work_item, field, old_val, new_val):
    if str(old_val) != str(new_val):
        db.session.add(
            ActivityLog(
                work_item=work_item,
                user_id=current_user.id,
                field_changed=field,
                old_value=str(old_val) if old_val else "",
                new_value=str(new_val) if new_val else "",
            )
        )


@work_items_bp.route("/new", methods=["GET", "POST"])
@auth_required()
def create_item(key):
    project = _get_project(key)
    parent_id = request.args.get("parent_id", type=int)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        item_type_id = request.form.get("item_type_id", type=int)
        status_id = request.form.get("status_id", type=int)
        priority = validate_priority(request.form.get("priority", "medium"))
        epic_id = request.form.get("epic_id", type=int) or None
        sprint_id = request.form.get("sprint_id", type=int) or None
        assignee_id = request.form.get("assignee_id", type=int) or None
        parent_id_form = request.form.get("parent_id", type=int) or None

        if not title:
            flash("Title is required.", "danger")
            return render_template(
                "work_items/form.html",
                project=project,
                item=None,
                sprints=_get_sprints_for_project(project),
                members=_get_members(project),
                parent_id=parent_id,
            )

        if not item_type_id:
            default_type = next(
                (t for t in project.item_types if t.is_default), None
            ) or project.item_types[0]
            item_type_id = default_type.id

        if not status_id:
            default_status = next(
                (s for s in project.statuses if s.is_default), None
            ) or project.statuses[0]
            status_id = default_status.id

        max_pos = (
            db.session.query(db.func.max(WorkItem.position))
            .filter_by(project_id=project.id)
            .scalar()
            or 0
        )

        item = WorkItem(
            project=project,
            item_type_id=item_type_id,
            status_id=status_id,
            epic_id=epic_id,
            sprint_id=sprint_id,
            parent_id=parent_id_form,
            assignee_id=assignee_id,
            reporter_id=current_user.id,
            title=title,
            description=description,
            priority=priority,
            story_points=request.form.get("story_points", type=int),
            position=max_pos + 1,
            item_key=project.next_item_key(),
        )
        db.session.add(item)
        db.session.flush()

        from app.notifications import add_watcher, notify_assigned
        add_watcher(current_user.id, item.id)
        if assignee_id and assignee_id != current_user.id:
            add_watcher(assignee_id, item.id)
            notify_assigned(current_user, item, assignee_id)

        db.session.commit()
        flash("Work item created.", "success")
        return redirect(
            url_for("work_items.detail", key=key, item_key=item.item_key)
        )

    return render_template(
        "work_items/form.html",
        project=project,
        item=None,
        sprints=_get_sprints_for_project(project),
        members=_get_members(project),
        parent_id=parent_id,
    )


@work_items_bp.route("/<item_key>")
@auth_required()
def detail(key, item_key):
    project = _get_project(key)
    item = WorkItem.query.filter_by(item_key=item_key.upper(), project_id=project.id).first_or_404()
    members = [m.user for m in ProjectMembership.query.filter_by(project_id=project.id).options(db.joinedload(ProjectMembership.user)).all()]
    is_watching = Watcher.query.filter_by(
        user_id=current_user.id, work_item_id=item.id
    ).first() is not None
    watcher_count = Watcher.query.filter_by(work_item_id=item.id).count()
    from datetime import date
    return render_template(
        "work_items/detail.html",
        project=project,
        item=item,
        members=members,
        sprints=_get_sprints_for_project(project),
        today=date.today(),
        is_watching=is_watching,
        watcher_count=watcher_count,
    )


@work_items_bp.route("/<item_key>/edit", methods=["GET", "POST"])
@auth_required()
def edit_item(key, item_key):
    project = _get_project(key)
    item = WorkItem.query.filter_by(item_key=item_key.upper(), project_id=project.id).first_or_404()

    if request.method == "POST":
        new_title = request.form.get("title", "").strip() or item.title
        new_description = request.form.get("description", "").strip()
        new_type_id = request.form.get("item_type_id", type=int) or item.item_type_id
        new_status_id = request.form.get("status_id", type=int) or item.status_id
        new_priority = validate_priority(request.form.get("priority", item.priority))
        new_epic_id = request.form.get("epic_id", type=int) or None
        new_sprint_id = request.form.get("sprint_id", type=int) or None
        new_assignee_id = request.form.get("assignee_id", type=int) or None
        old_assignee_id = item.assignee_id

        _log_change(item, "title", item.title, new_title)
        _log_change(item, "priority", item.priority, new_priority)
        _log_change(item, "assignee", item.assignee_id, new_assignee_id)

        if new_status_id != item.status_id:
            from app.models.status import Status
            old_status = Status.query.get(item.status_id)
            new_status = Status.query.get(new_status_id)
            _log_change(
                item,
                "status",
                old_status.name if old_status else "",
                new_status.name if new_status else "",
            )

        if new_sprint_id != item.sprint_id:
            old_sprint = item.sprint
            new_sprint = Sprint.query.get(new_sprint_id) if new_sprint_id else None
            _log_change(
                item,
                "sprint",
                old_sprint.name if old_sprint else "None",
                new_sprint.name if new_sprint else "None",
            )

        new_story_points = request.form.get("story_points", type=int)

        item.title = new_title
        item.description = new_description
        item.item_type_id = new_type_id
        item.status_id = new_status_id
        item.priority = new_priority
        item.story_points = new_story_points
        item.epic_id = new_epic_id
        item.sprint_id = new_sprint_id
        item.assignee_id = new_assignee_id

        from app.notifications import notify_assigned, notify_unassigned, notify_watchers
        if new_assignee_id != old_assignee_id:
            if new_assignee_id:
                notify_assigned(current_user, item, new_assignee_id)
            if old_assignee_id:
                notify_unassigned(current_user, item, old_assignee_id)
        notify_watchers(current_user, item, f"{current_user.display_name} updated {item.item_key}")

        db.session.commit()
        flash("Work item updated.", "success")
        return redirect(
            url_for("work_items.detail", key=key, item_key=item.item_key)
        )

    return render_template(
        "work_items/form.html",
        project=project,
        item=item,
        sprints=_get_sprints_for_project(project),
        members=_get_members(project),
        parent_id=item.parent_id,
    )


@work_items_bp.route("/<item_key>/duplicate", methods=["POST"])
@auth_required()
def duplicate_item(key, item_key):
    project = _get_project(key)
    item = WorkItem.query.filter_by(item_key=item_key.upper(), project_id=project.id).first_or_404()
    new_item = WorkItem(
        project_id=item.project_id,
        item_type_id=item.item_type_id,
        status_id=item.status_id,
        epic_id=item.epic_id,
        sprint_id=item.sprint_id,
        parent_id=item.parent_id,
        assignee_id=item.assignee_id,
        reporter_id=current_user.id,
        title="[Copy] " + item.title,
        description=item.description,
        priority=item.priority,
        story_points=item.story_points,
        item_key=project.next_item_key(),
        due_date=item.due_date,
    )
    db.session.add(new_item)
    # Copy labels
    for label in item.labels:
        new_item.labels.append(label)
    db.session.commit()
    flash("Item duplicated.", "success")
    return redirect(url_for("work_items.detail", key=key, item_key=new_item.item_key))


@work_items_bp.route("/<item_key>/delete", methods=["POST"])
@auth_required()
def delete_item(key, item_key):
    project = _get_project(key)
    item = WorkItem.query.filter_by(item_key=item_key.upper(), project_id=project.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Work item deleted.", "success")
    return redirect(url_for("backlog.project_backlog", key=key))


@work_items_bp.route("/<item_key>/comment", methods=["POST"])
@auth_required()
def add_comment(key, item_key):
    project = _get_project(key)
    item = WorkItem.query.filter_by(item_key=item_key.upper(), project_id=project.id).first_or_404()
    body = request.form.get("body", "").strip()
    if body:
        comment = Comment(work_item=item, author_id=current_user.id, body=body)
        db.session.add(comment)
        db.session.add(ActivityLog(
            work_item=item, user_id=current_user.id,
            field_changed="comment", old_value="", new_value="added",
        ))

        from app.notifications import notify_comment, notify_mentioned
        notify_comment(current_user, item, body)
        notify_mentioned(current_user, item, body)

        db.session.commit()
        flash("Comment added.", "success")
    return redirect(url_for("work_items.detail", key=key, item_key=item.item_key))


@work_items_bp.route("/<item_key>/comment/<int:comment_id>/delete", methods=["POST"])
@auth_required()
def delete_comment(key, item_key, comment_id):
    project = _get_project(key)
    item = WorkItem.query.filter_by(item_key=item_key.upper(), project_id=project.id).first_or_404()
    comment = Comment.query.get_or_404(comment_id)
    if comment.work_item_id != item.id:
        abort(404)
    if comment.author_id != current_user.id:
        abort(403)
    db.session.delete(comment)
    db.session.add(ActivityLog(
        work_item=item, user_id=current_user.id,
        field_changed="comment", old_value="", new_value="deleted",
    ))
    db.session.commit()
    flash("Comment deleted.", "success")
    return redirect(url_for("work_items.detail", key=key, item_key=item.item_key))
