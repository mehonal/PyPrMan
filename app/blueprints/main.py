from collections import defaultdict
from datetime import date, timedelta

from flask import Blueprint, redirect, render_template, url_for
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.project import Project, ProjectMembership
from app.models.sprint import Sprint, SprintProject
from app.models.status import Status
from app.models.work_item import WorkItem

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("security.login"))


@main_bp.route("/dashboard")
@auth_required()
def dashboard():
    user_project_ids = [
        m.project_id
        for m in ProjectMembership.query.filter_by(user_id=current_user.id).all()
    ]
    if not user_project_ids:
        return render_template("main/dashboard.html", empty=True)

    projects = Project.query.filter(Project.id.in_(user_project_ids)).all()

    _eager = (
        db.joinedload(WorkItem.status),
        db.joinedload(WorkItem.item_type),
        db.joinedload(WorkItem.project),
        db.joinedload(WorkItem.assignee),
    )

    # My open items
    my_items = (
        WorkItem.query.filter(
            WorkItem.assignee_id == current_user.id,
            WorkItem.project_id.in_(user_project_ids),
        )
        .join(WorkItem.status)
        .filter(Status.category != "done")
        .options(*_eager)
        .order_by(WorkItem.updated_at.desc())
        .limit(20)
        .all()
    )

    # Recent activity
    recent_items = (
        WorkItem.query.filter(WorkItem.project_id.in_(user_project_ids))
        .options(*_eager)
        .order_by(WorkItem.updated_at.desc())
        .limit(10)
        .all()
    )

    # Due soon: items due within the next 7 days (or overdue), not done
    today = date.today()
    due_soon_items = (
        WorkItem.query.filter(
            WorkItem.project_id.in_(user_project_ids),
            WorkItem.due_date.isnot(None),
            WorkItem.due_date <= today + timedelta(days=7),
        )
        .join(WorkItem.status)
        .filter(Status.category != "done")
        .options(*_eager)
        .order_by(WorkItem.due_date.asc())
        .limit(15)
        .all()
    )

    # Summary counts
    total_open = (
        WorkItem.query.filter(WorkItem.project_id.in_(user_project_ids))
        .join(WorkItem.status)
        .filter(Status.category != "done")
        .count()
    )
    my_open_count = (
        WorkItem.query.filter(
            WorkItem.assignee_id == current_user.id,
            WorkItem.project_id.in_(user_project_ids),
        )
        .join(WorkItem.status)
        .filter(Status.category != "done")
        .count()
    )
    overdue_count = (
        WorkItem.query.filter(
            WorkItem.project_id.in_(user_project_ids),
            WorkItem.due_date.isnot(None),
            WorkItem.due_date < today,
        )
        .join(WorkItem.status)
        .filter(Status.category != "done")
        .count()
    )

    # Active sprints
    active_sprints = (
        Sprint.query.join(SprintProject)
        .filter(
            SprintProject.project_id.in_(user_project_ids),
            Sprint.is_active.is_(True),
        )
        .distinct()
        .options(
            db.selectinload(Sprint.work_items).joinedload(WorkItem.status),
            db.selectinload(Sprint.sprint_projects).joinedload(SprintProject.project),
        )
        .all()
    )
    sprint_summaries = []
    for sprint in active_sprints:
        committed = sprint.committed_sp
        completed = sprint.completed_sp
        pct = round((completed / committed) * 100) if committed > 0 else 0
        sprint_summaries.append({
            "id": sprint.id,
            "name": sprint.name,
            "committed": committed,
            "completed": completed,
            "in_progress": sprint.in_progress_sp,
            "pct": pct,
            "end_date": sprint.end_date,
            "projects": [sp.project.key for sp in sprint.sprint_projects],
        })

    # Active sprint breakdowns (status category + project)
    sprint_sp_by_category = defaultdict(int)
    sp_by_project_id = defaultdict(int)
    for sprint in active_sprints:
        for item in sprint.work_items:
            sp = item.story_points or 0
            sprint_sp_by_category[item.status.category] += sp
            sp_by_project_id[item.project_id] += sp
    sprint_status_breakdown = [
        {"category": "todo", "label": "To Do", "sp": sprint_sp_by_category.get("todo", 0)},
        {"category": "in_progress", "label": "In Progress", "sp": sprint_sp_by_category.get("in_progress", 0)},
        {"category": "done", "label": "Done", "sp": sprint_sp_by_category.get("done", 0)},
    ]
    project_map = {p.id: p for p in projects}
    project_sp_breakdown = [
        {"key": project_map[pid].key, "sp": sp}
        for pid, sp in sp_by_project_id.items()
        if pid in project_map
    ]
    project_sp_breakdown.sort(key=lambda x: x["sp"], reverse=True)

    return render_template(
        "main/dashboard.html",
        empty=False,
        projects=projects,
        my_items=my_items,
        recent_items=recent_items,
        due_soon_items=due_soon_items,
        total_open=total_open,
        my_open_count=my_open_count,
        overdue_count=overdue_count,
        sprint_summaries=sprint_summaries,
        sprint_status_breakdown=sprint_status_breakdown,
        project_sp_breakdown=project_sp_breakdown,
        today=today,
    )
