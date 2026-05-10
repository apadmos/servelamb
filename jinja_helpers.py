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


def _pull_first(d: any, options: list[str]):
    try:
        for o in options:
            if o in d:
                return d[o]
    except TypeError:
        pass
    try:
        for o in options:
            if hasattr(d, o):
                return getattr(d, o)
    except TypeError:
        pass
    return None


def _pull_name_value(option: any):
    if option is None:
        return None, None
    # Handle plain strings/primitives
    if isinstance(option, (str, int, bool)):
        value = str(option)
        name = words_split(value)
    # Handle tuples/lists: (value, name) or (value,)
    elif isinstance(option, (list, tuple)):
        value = str(option[0]) if len(option) > 0 else ""
        name = str(option[1]) if len(option) > 1 else value
    # Handle dicts
    else:
        name = _pull_first(option, ["name", "label", "description"])
        value = _pull_first(option, ["id", "value", "val"])
        if not value and name:
            value = name
        if not value:
            value = str(option)
        if not name and value:
            name = words_split(value)
    return value, name


def render_select_options(options, selected=None):
    r = []
    selected_val, selected_name = _pull_name_value(selected)
    found_selected = selected is None

    for option in options:
        value, name = _pull_name_value(option)

        is_selected = ' selected' if selected_val == value else ''
        if is_selected:
            found_selected = True
        r.append(f"""<option value="{value}"{is_selected}>{name}</option>""")
    if not found_selected and selected is not None:
        r.append(f"""<option value="{selected_val}" selected>{selected_name}  (Not found)</option>""")
    r = "\n".join(r)
    return Markup(r)
