import datetime
import re

from markupsafe import Markup


def date_format(d: datetime.datetime):
    if d:
        if hasattr(d, 'strftime'):
            return d.strftime("%b %d %Y")
        else:
            return d
    return ''


def date_input_format(d: datetime.datetime):
    """format a date into a string that a <input type="date" /> can understand"""
    if d:
        if hasattr(d, 'strftime'):
            return d.strftime("%Y-%m-%d")
        else:
            return d
    return ''


def words_split(s: str):
    parts = []
    if s:
        for word in re.split('[^a-zA-Z\\d]', s):
            parts.append(word)
    return " ".join(parts)


def _pull_first(d: dict, options: list[str]):
    for o in options:
        if o in d:
            return d[o]
    return None


def render_select_options(selected, options):
    r = []
    for option in options:
        # Handle plain strings/primitives
        if not isinstance(option, (list, tuple, dict)):
            value = str(option)
            name = words_split(value)
        # Handle tuples/lists: (value, name) or (value,)
        elif isinstance(option, (list, tuple)):
            value = str(option[0]) if len(option) > 0 else ""
            name = str(option[1]) if len(option) > 1 else value
        # Handle dicts
        else:
            name = _pull_first(option, ["name", "label", "description"])
            value = _pull_first(option, ["value", "val", "id"])
            if not value and name:
                value = name
            if not value:
                value = str(option)
            if not name and value:
                name = words_split(value)

        is_selected = ' selected' if str(value) == str(selected) else ''
        r.append(f"""<option value="{value}"{is_selected}>{name}</option>""")
    r = "\n".join(r)
    return Markup(r)
