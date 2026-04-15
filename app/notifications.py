import re

from flask import current_app, url_for
from flask_mail import Message

from app.extensions import db, mail
from app.models.notification import Notification, NotificationPreference, NOTIFICATION_TYPES
from app.models.watcher import Watcher


def _batch_get_prefs(user_ids, notif_type):
    """Return dict of {user_id: (in_app, email)} for a list of users. Defaults: in_app=True, email=False."""
    if not user_ids:
        return {}
    prefs = NotificationPreference.query.filter(
        NotificationPreference.user_id.in_(user_ids),
        NotificationPreference.type == notif_type,
    ).all()
    pref_map = {p.user_id: (p.in_app, p.email) for p in prefs}
    return {uid: pref_map.get(uid, (True, False)) for uid in user_ids}


def _build_url(work_item):
    """Build the URL path for a work item."""
    if not work_item:
        return ""
    return url_for(
        "work_items.detail",
        key=work_item.project.key,
        item_key=work_item.item_key,
    )


def _send_email(recipient_email, subject, body):
    """Send an email notification. Silently fails if mail is suppressed or misconfigured."""
    try:
        msg = Message(subject=subject, recipients=[recipient_email], body=body)
        mail.send(msg)
    except Exception:
        current_app.logger.exception("Failed to send notification email to %s", recipient_email)


def _create_notification(user_id, actor_id, work_item, notif_type, title, message="",
                         pref=None):
    """Create in-app notification and/or send email based on user preferences."""
    if user_id == actor_id:
        return

    if pref is None:
        pref = _batch_get_prefs([user_id], notif_type).get(user_id, (True, False))
    in_app, send_email = pref
    if not in_app and not send_email:
        return

    url = _build_url(work_item)

    if in_app:
        db.session.add(Notification(
            user_id=user_id,
            actor_id=actor_id,
            work_item_id=work_item.id if work_item else None,
            type=notif_type,
            title=title,
            message=message,
            url=url,
        ))

    if send_email:
        from app.models.user import User
        recipient = User.query.get(user_id)
        if recipient and recipient.email:
            email_body = f"{title}\n\n{message}" if message else title
            if url:
                email_body += f"\n\nView: {url}"
            _send_email(recipient.email, f"[PyPrMan] {title}", email_body)


def notify_assigned(actor, work_item, assignee_id):
    """Notify a user they were assigned to a work item."""
    _create_notification(
        user_id=assignee_id,
        actor_id=actor.id,
        work_item=work_item,
        notif_type="assigned",
        title=f"{actor.display_name} assigned you to {work_item.item_key}",
        message=work_item.title,
    )
    add_watcher(assignee_id, work_item.id)


def notify_unassigned(actor, work_item, old_assignee_id):
    """Notify a user they were unassigned from a work item."""
    _create_notification(
        user_id=old_assignee_id,
        actor_id=actor.id,
        work_item=work_item,
        notif_type="unassigned",
        title=f"{actor.display_name} unassigned you from {work_item.item_key}",
        message=work_item.title,
    )


def notify_mentioned(actor, work_item, comment_body):
    """Parse @mentions from comment body and notify mentioned users."""
    mentions = re.findall(r"@([\w.\-]+)", comment_body)
    if not mentions:
        return

    from app.models.user import User
    from app.models.project import ProjectMembership

    member_ids = {
        m.user_id
        for m in ProjectMembership.query.filter_by(project_id=work_item.project_id).all()
    }
    if not member_ids:
        return

    members = User.query.filter(User.id.in_(member_ids)).all()
    mentioned_user_ids = []

    for mention_name in set(mentions):
        search_name = mention_name.replace(".", " ").lower()
        dotted_name = mention_name.lower()
        for user in members:
            if user.display_name.lower().replace(" ", ".") == dotted_name or \
               user.display_name.lower() == search_name:
                mentioned_user_ids.append(user.id)
                add_watcher(user.id, work_item.id)
                break

    if not mentioned_user_ids:
        return

    prefs = _batch_get_prefs(mentioned_user_ids, "mentioned")
    for uid in mentioned_user_ids:
        _create_notification(
            user_id=uid,
            actor_id=actor.id,
            work_item=work_item,
            notif_type="mentioned",
            title=f"{actor.display_name} mentioned you on {work_item.item_key}",
            message=comment_body[:200],
            pref=prefs.get(uid),
        )


def notify_watchers(actor, work_item, change_summary):
    """Notify all watchers of a work item about changes (excluding actor)."""
    watcher_ids = [
        w.user_id for w in Watcher.query.filter_by(work_item_id=work_item.id).all()
    ]
    prefs = _batch_get_prefs(watcher_ids, "watched_change")
    for uid in watcher_ids:
        _create_notification(
            user_id=uid,
            actor_id=actor.id,
            work_item=work_item,
            notif_type="watched_change",
            title=f"{actor.display_name} updated {work_item.item_key}",
            message=change_summary,
            pref=prefs.get(uid),
        )


def notify_comment(actor, work_item, comment_body):
    """Notify watchers about a new comment."""
    watcher_ids = [
        w.user_id for w in Watcher.query.filter_by(work_item_id=work_item.id).all()
    ]
    prefs = _batch_get_prefs(watcher_ids, "comment")
    preview = comment_body[:200] + ("..." if len(comment_body) > 200 else "")
    for uid in watcher_ids:
        _create_notification(
            user_id=uid,
            actor_id=actor.id,
            work_item=work_item,
            notif_type="comment",
            title=f"{actor.display_name} commented on {work_item.item_key}",
            message=preview,
            pref=prefs.get(uid),
        )


def add_watcher(user_id, work_item_id):
    """Add a watcher if not already watching."""
    existing = Watcher.query.filter_by(
        user_id=user_id, work_item_id=work_item_id
    ).first()
    if not existing:
        db.session.add(Watcher(user_id=user_id, work_item_id=work_item_id))


def remove_watcher(user_id, work_item_id):
    """Remove a watcher."""
    Watcher.query.filter_by(user_id=user_id, work_item_id=work_item_id).delete()
