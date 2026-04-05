import re

from app.models.status import STATUS_CATEGORIES
from app.models.work_item import PRIORITIES

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ICON_CLASS_RE = re.compile(r"^bi-[a-z0-9-]+$")


def validate_priority(value):
    if value in PRIORITIES:
        return value
    return "medium"


def validate_status_category(value):
    if value in STATUS_CATEGORIES:
        return value
    return "todo"


def validate_hex_color(value, default="#6b7280"):
    if value and HEX_COLOR_RE.match(value):
        return value
    return default


def validate_icon_class(value, default="bi-circle"):
    if value and ICON_CLASS_RE.match(value):
        return value
    return default
