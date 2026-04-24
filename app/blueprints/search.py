import re

from flask import Blueprint, render_template, request, url_for
from flask_security import auth_required, current_user

from app.extensions import db
from app.models.epic import Epic
from app.models.item_type import ItemType
from app.models.label import Label
from app.models.project import Project, ProjectMembership
from app.models.sprint import Sprint, SprintProject
from app.models.status import Status
from app.models.user import User
from app.models.work_item import WorkItem
from app.blueprints.helpers import user_project_ids


search_bp = Blueprint("search", __name__)


@search_bp.app_template_filter("merge_drop")
def merge_drop(args_dict, drop_key):
    """Return a dict copy of request.args (as multi-dict-to-dict) without the given key."""
    return {k: v for k, v in args_dict.items() if k != drop_key}


@search_bp.app_context_processor
def _inject_search_helpers():
    def toggle_url(param, value):
        """URL for /search that toggles `value` in/out of the multi-valued `param`."""
        args = request.args.to_dict(flat=False)
        current = list(args.get(param, []))
        value_s = str(value)
        if value_s in current:
            current = [v for v in current if v != value_s]
        else:
            current.append(value_s)
        args[param] = current
        return url_for("search.results_page", **args)

    return {"toggle_url": toggle_url}


FILTER_KEYS = {"project", "assignee", "label", "status", "epic", "type", "priority"}

_TOKEN_RE = re.compile(
    r'(\w+):"([^"]+)"'       # key:"quoted value"
    r"|(\w+):(\S+)"            # key:value
    r"|\S+"                    # bare word
)


def parse_query(q):
    """Return (free_text, filters_dict).

    Unknown `key:value` tokens fall back to free text. Values are lowercased
    for case-insensitive matching downstream where appropriate.
    """
    filters = {}
    free_parts = []
    for m in _TOKEN_RE.finditer(q or ""):
        qk, qv, bk, bv = m.group(1), m.group(2), m.group(3), m.group(4)
        key = qk or bk
        value = qv or bv
        if key and key.lower() in FILTER_KEYS:
            filters[key.lower()] = value
        else:
            free_parts.append(m.group(0))
    return " ".join(free_parts).strip(), filters


def _like(value):
    return f"%{value}%"


def _apply_work_item_filters(query, free_text, filters, project_ids, categories=None):
    """Apply free text + structured filters to a WorkItem query. Returns the
    modified query. Does not add ordering or limits."""

    if free_text:
        like = _like(free_text)
        query = query.filter(
            db.or_(
                WorkItem.title.ilike(like),
                WorkItem.item_key.ilike(like),
                WorkItem.description.ilike(like),
            )
        )

    if "project" in filters:
        query = query.join(Project, WorkItem.project_id == Project.id).filter(
            db.or_(
                Project.key.ilike(filters["project"]),
                Project.name.ilike(_like(filters["project"])),
            )
        )

    if "assignee" in filters:
        v = filters["assignee"]
        if v.lower() == "me":
            query = query.filter(WorkItem.assignee_id == current_user.id)
        else:
            query = query.join(User, WorkItem.assignee_id == User.id).filter(
                db.or_(
                    User._display_name.ilike(_like(v)),
                    User.email.ilike(_like(v)),
                )
            )

    if "label" in filters:
        query = query.filter(WorkItem.labels.any(Label.name.ilike(filters["label"])))

    if "status" in filters:
        v = filters["status"]
        query = query.join(Status, WorkItem.status_id == Status.id).filter(
            db.or_(
                Status.name.ilike(_like(v)),
                Status.category.ilike(v),
            )
        )

    if "epic" in filters:
        v = filters["epic"]
        if v.isdigit():
            query = query.filter(WorkItem.epic_id == int(v))
        else:
            query = query.join(Epic, WorkItem.epic_id == Epic.id).filter(
                Epic.name.ilike(_like(v))
            )

    if "type" in filters:
        query = query.join(ItemType, WorkItem.item_type_id == ItemType.id).filter(
            ItemType.name.ilike(_like(filters["type"]))
        )

    if "priority" in filters:
        query = query.filter(WorkItem.priority == filters["priority"].lower())

    if categories:
        query = query.join(Status, WorkItem.status_id == Status.id).filter(
            Status.category.in_(categories)
        )

    return query


def search_work_items(free_text, filters, project_ids, limit=8, categories=None):
    if not project_ids:
        return []
    query = WorkItem.query.filter(WorkItem.project_id.in_(project_ids))
    query = _apply_work_item_filters(query, free_text, filters, project_ids, categories)
    items = (
        query.options(
            db.joinedload(WorkItem.project),
            db.joinedload(WorkItem.status),
            db.joinedload(WorkItem.item_type),
            db.joinedload(WorkItem.assignee),
        )
        .order_by(WorkItem.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": i.id,
            "item_key": i.item_key,
            "title": i.title,
            "project_key": i.project.key,
            "status": i.status.name,
            "status_color": i.status.color,
            "type_icon": i.item_type.icon,
            "type_color": i.item_type.color,
            "assignee": i.assignee.display_name if i.assignee else None,
        }
        for i in items
    ]


def search_projects(free_text, project_ids, limit=5):
    if not free_text or not project_ids:
        return []
    like = _like(free_text)
    projects = (
        Project.query.filter(
            Project.id.in_(project_ids),
            db.or_(
                Project.name.ilike(like),
                Project.key.ilike(like),
                Project.description.ilike(like),
            ),
        )
        .order_by(Project.name.asc())
        .limit(limit)
        .all()
    )
    return [
        {"id": p.id, "key": p.key, "name": p.name}
        for p in projects
    ]


def search_epics(free_text, project_ids, limit=5):
    if not free_text or not project_ids:
        return []
    like = _like(free_text)
    epics = (
        Epic.query.filter(
            Epic.project_id.in_(project_ids),
            db.or_(Epic.name.ilike(like), Epic.description.ilike(like)),
        )
        .options(db.joinedload(Epic.project))
        .order_by(Epic.name.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "name": e.name,
            "color": e.color,
            "project_key": e.project.key,
        }
        for e in epics
    ]


def search_sprints(free_text, project_ids, limit=5):
    if not free_text or not project_ids:
        return []
    like = _like(free_text)
    sprints = (
        Sprint.query.join(SprintProject, SprintProject.sprint_id == Sprint.id)
        .filter(
            SprintProject.project_id.in_(project_ids),
            db.or_(Sprint.name.ilike(like), Sprint.goal.ilike(like)),
        )
        .order_by(Sprint.is_active.desc(), Sprint.start_date.desc().nullslast())
        .distinct()
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "name": s.name,
            "is_active": s.is_active,
            "is_completed": s.is_completed,
        }
        for s in sprints
    ]


def search_users(free_text, project_ids, limit=5):
    if not free_text or not project_ids:
        return []
    like = _like(free_text)
    users = (
        User.query.join(ProjectMembership, ProjectMembership.user_id == User.id)
        .filter(
            ProjectMembership.project_id.in_(project_ids),
            db.or_(User._display_name.ilike(like), User.email.ilike(like)),
        )
        .order_by(User._display_name.asc())
        .distinct()
        .limit(limit)
        .all()
    )
    return [
        {"id": u.id, "display_name": u.display_name, "email": u.email}
        for u in users
    ]


def search_labels(free_text, project_ids, limit=5):
    if not free_text or not project_ids:
        return []
    labels = (
        Label.query.filter(
            Label.project_id.in_(project_ids),
            Label.name.ilike(_like(free_text)),
        )
        .order_by(Label.name.asc())
        .limit(limit)
        .all()
    )
    return [
        {"id": l.id, "name": l.name, "color": l.color}
        for l in labels
    ]


STATUS_CATEGORIES_ORDER = ["todo", "in_progress", "done", "cancelled"]
STATUS_CATEGORY_LABELS = {
    "todo": "To Do",
    "in_progress": "In Progress",
    "done": "Done",
    "cancelled": "Cancelled",
}

PRIORITY_ORDER = ["critical", "high", "medium", "low", "none"]
PRIORITY_LABELS = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "none": "None",
}


@search_bp.route("/search")
@auth_required()
def results_page():
    q = request.args.get("q", "").strip()

    # Multi-valued UI filter selections.
    sel_cats = [c for c in request.args.getlist("cat") if c in STATUS_CATEGORIES_ORDER]
    sel_project_ids = request.args.getlist("project_id", type=int)
    sel_assignee_ids = request.args.getlist("assignee_id")  # ints or "unassigned"
    sel_label_ids = request.args.getlist("label_id", type=int)
    sel_epic_ids = request.args.getlist("epic_id")  # ints or "none"
    sel_type_ids = request.args.getlist("type_id", type=int)
    sel_priorities = [p for p in request.args.getlist("priority") if p in PRIORITY_ORDER]

    user_pids = user_project_ids()
    items = []
    filters = {}
    free_text = ""
    total = 0

    # Option lists for the sidebar (with counts).
    status_opts = []
    project_opts = []
    assignee_opts = []
    label_opts = []
    epic_opts = []
    type_opts = []
    priority_opts = []

    if q and user_pids:
        free_text, filters = parse_query(q)

        # Base subquery: matched ids after text + structured tokens (no UI filters).
        # This is what drives the count numbers in every sidebar section.
        base_ids_sq = (
            _apply_work_item_filters(
                WorkItem.query.filter(WorkItem.project_id.in_(user_pids)),
                free_text, filters, user_pids,
            )
            .with_entities(WorkItem.id.label("id"))
            .distinct()
            .subquery()
        )

        def _count_query(column, *join_specs):
            q_ = db.session.query(column, db.func.count(db.distinct(WorkItem.id))).select_from(WorkItem)
            for target, onclause in join_specs:
                q_ = q_.join(target, onclause)
            return q_.join(base_ids_sq, base_ids_sq.c.id == WorkItem.id).group_by(column)

        # Status category counts
        cat_counts = dict(
            _count_query(
                Status.category,
                (Status, Status.id == WorkItem.status_id),
            ).all()
        )
        status_opts = [
            {
                "value": c,
                "label": STATUS_CATEGORY_LABELS[c],
                "count": cat_counts.get(c, 0),
                "selected": c in sel_cats,
            }
            for c in STATUS_CATEGORIES_ORDER
        ]

        # Project counts
        proj_rows = (
            _count_query(
                Project.id,
                (Project, Project.id == WorkItem.project_id),
            )
            .with_entities(Project.id, Project.key, Project.name, db.func.count(db.distinct(WorkItem.id)))
            .group_by(Project.id, Project.key, Project.name)
            .order_by(Project.name)
            .all()
        )
        project_opts = [
            {"value": pid, "label": f"{pname} ({pkey})", "count": c, "selected": pid in sel_project_ids}
            for pid, pkey, pname, c in proj_rows
        ]

        # Assignee counts (including unassigned)
        assignee_rows = (
            db.session.query(
                WorkItem.assignee_id,
                db.func.count(db.distinct(WorkItem.id)),
            )
            .join(base_ids_sq, base_ids_sq.c.id == WorkItem.id)
            .group_by(WorkItem.assignee_id)
            .all()
        )
        assignee_count_map = {aid: c for aid, c in assignee_rows}
        user_ids_with_items = [aid for aid in assignee_count_map if aid is not None]
        users_by_id = {}
        if user_ids_with_items:
            users_by_id = {
                u.id: u for u in User.query.filter(User.id.in_(user_ids_with_items)).all()
            }
        unassigned_count = assignee_count_map.get(None, 0)
        assignee_opts = []
        if unassigned_count:
            assignee_opts.append({
                "value": "unassigned",
                "label": "Unassigned",
                "count": unassigned_count,
                "selected": "unassigned" in sel_assignee_ids,
            })
        for uid in sorted(user_ids_with_items, key=lambda i: (users_by_id[i].display_name or "").lower()):
            assignee_opts.append({
                "value": uid,
                "label": users_by_id[uid].display_name,
                "count": assignee_count_map[uid],
                "selected": str(uid) in sel_assignee_ids,
            })

        # Label counts
        label_rows = (
            db.session.query(
                Label.id, Label.name, Label.color,
                db.func.count(db.distinct(WorkItem.id)),
            )
            .select_from(Label)
            .join(Label.work_items)
            .join(base_ids_sq, base_ids_sq.c.id == WorkItem.id)
            .group_by(Label.id, Label.name, Label.color)
            .order_by(Label.name)
            .all()
        )
        label_opts = [
            {"value": lid, "label": lname, "color": lcolor, "count": c, "selected": lid in sel_label_ids}
            for lid, lname, lcolor, c in label_rows
        ]

        # Epic counts (including "no epic")
        epic_rows = (
            db.session.query(
                WorkItem.epic_id,
                db.func.count(db.distinct(WorkItem.id)),
            )
            .join(base_ids_sq, base_ids_sq.c.id == WorkItem.id)
            .group_by(WorkItem.epic_id)
            .all()
        )
        epic_count_map = {eid: c for eid, c in epic_rows}
        epic_ids_present = [eid for eid in epic_count_map if eid is not None]
        epics_by_id = {}
        if epic_ids_present:
            epics_by_id = {
                e.id: e for e in Epic.query.filter(Epic.id.in_(epic_ids_present)).all()
            }
        no_epic_count = epic_count_map.get(None, 0)
        epic_opts = []
        if no_epic_count:
            epic_opts.append({
                "value": "none",
                "label": "No epic",
                "count": no_epic_count,
                "selected": "none" in sel_epic_ids,
            })
        for eid in sorted(epic_ids_present, key=lambda i: (epics_by_id[i].name or "").lower()):
            epic_opts.append({
                "value": eid,
                "label": epics_by_id[eid].name,
                "color": epics_by_id[eid].color,
                "count": epic_count_map[eid],
                "selected": str(eid) in sel_epic_ids,
            })

        # Item type counts
        type_rows = (
            db.session.query(
                ItemType.id, ItemType.name, ItemType.icon, ItemType.color,
                db.func.count(db.distinct(WorkItem.id)),
            )
            .select_from(ItemType)
            .join(WorkItem, WorkItem.item_type_id == ItemType.id)
            .join(base_ids_sq, base_ids_sq.c.id == WorkItem.id)
            .group_by(ItemType.id, ItemType.name, ItemType.icon, ItemType.color)
            .order_by(ItemType.name)
            .all()
        )
        type_opts = [
            {"value": tid, "label": tname, "icon": ticon, "color": tcolor, "count": c, "selected": tid in sel_type_ids}
            for tid, tname, ticon, tcolor, c in type_rows
        ]

        # Priority counts
        prio_rows = (
            db.session.query(
                WorkItem.priority,
                db.func.count(db.distinct(WorkItem.id)),
            )
            .join(base_ids_sq, base_ids_sq.c.id == WorkItem.id)
            .group_by(WorkItem.priority)
            .all()
        )
        prio_count_map = {p: c for p, c in prio_rows}
        priority_opts = [
            {
                "value": p,
                "label": PRIORITY_LABELS[p],
                "count": prio_count_map.get(p, 0),
                "selected": p in sel_priorities,
            }
            for p in PRIORITY_ORDER
            if prio_count_map.get(p, 0) > 0 or p in sel_priorities
        ]

        # Main items query: base + UI filters.
        main_q = _apply_work_item_filters(
            WorkItem.query.filter(WorkItem.project_id.in_(user_pids)),
            free_text, filters, user_pids,
            categories=sel_cats or None,
        )
        if sel_project_ids:
            main_q = main_q.filter(WorkItem.project_id.in_(sel_project_ids))
        if sel_assignee_ids:
            clauses = []
            int_ids = [int(a) for a in sel_assignee_ids if a != "unassigned" and a.isdigit()]
            if int_ids:
                clauses.append(WorkItem.assignee_id.in_(int_ids))
            if "unassigned" in sel_assignee_ids:
                clauses.append(WorkItem.assignee_id.is_(None))
            if clauses:
                main_q = main_q.filter(db.or_(*clauses))
        if sel_label_ids:
            main_q = main_q.filter(WorkItem.labels.any(Label.id.in_(sel_label_ids)))
        if sel_epic_ids:
            clauses = []
            int_ids = [int(e) for e in sel_epic_ids if e != "none" and e.isdigit()]
            if int_ids:
                clauses.append(WorkItem.epic_id.in_(int_ids))
            if "none" in sel_epic_ids:
                clauses.append(WorkItem.epic_id.is_(None))
            if clauses:
                main_q = main_q.filter(db.or_(*clauses))
        if sel_type_ids:
            main_q = main_q.filter(WorkItem.item_type_id.in_(sel_type_ids))
        if sel_priorities:
            main_q = main_q.filter(WorkItem.priority.in_(sel_priorities))

        items = (
            main_q.options(
                db.joinedload(WorkItem.project),
                db.joinedload(WorkItem.status),
                db.joinedload(WorkItem.item_type),
                db.joinedload(WorkItem.epic),
                db.joinedload(WorkItem.assignee),
            )
            .order_by(WorkItem.updated_at.desc())
            .limit(500)
            .all()
        )
        total = sum(o["count"] for o in status_opts)

    return render_template(
        "search/results.html",
        q=q,
        free_text=free_text,
        filters=filters,
        items=items,
        total=total,
        sections=[
            {"key": "cat",         "title": "Status",   "param": "cat",         "options": status_opts,   "has_selection": bool(sel_cats)},
            {"key": "project_id",  "title": "Project",  "param": "project_id",  "options": project_opts,  "has_selection": bool(sel_project_ids)},
            {"key": "assignee_id", "title": "Assignee", "param": "assignee_id", "options": assignee_opts, "has_selection": bool(sel_assignee_ids)},
            {"key": "label_id",    "title": "Label",    "param": "label_id",    "options": label_opts,    "has_selection": bool(sel_label_ids)},
            {"key": "epic_id",     "title": "Epic",     "param": "epic_id",     "options": epic_opts,     "has_selection": bool(sel_epic_ids)},
            {"key": "type_id",     "title": "Type",     "param": "type_id",     "options": type_opts,     "has_selection": bool(sel_type_ids)},
            {"key": "priority",    "title": "Priority", "param": "priority",    "options": priority_opts, "has_selection": bool(sel_priorities)},
        ],
    )
