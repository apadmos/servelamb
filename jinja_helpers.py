import datetime
import re
from zoneinfo import ZoneInfo

from jinja2 import Undefined
from markupsafe import Markup


class JinjaHelpers:

    def __init__(self, time_zone: str = "America/New_York"):

        self.LOCAL_TZ = ZoneInfo(time_zone)

    """"Generic Jinja pipe filters and functions that can be used across projects"""

    def date_format(self, d: datetime.datetime):
        if d:
            if hasattr(d, 'strftime'):
                return d.strftime("%b %d %Y")
            else:
                return d
        return ''

    def date_input_format(self, d: datetime.datetime):
        """format a date into a string that a <input type="date" /> can understand"""
        if d:
            if hasattr(d, 'strftime'):
                return d.strftime("%Y-%m-%d")
            else:
                return d
        return ''

    def words_split(self, s: str):
        parts = []
        if s:
            for word in re.split('[^a-zA-Z\\d]', s):
                parts.append(word)
        return " ".join(parts)

    def _pull_first(self, d: any, options: list[str]):
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

    def _pull_name_value(self, option: any):
        if not option:
            return None, None
        # Handle plain strings/primitives
        if isinstance(option, (str, int, bool)):
            value = str(option)
            name = self.words_split(value)
        # Handle tuples/lists: (value, name) or (value,)
        elif isinstance(option, (list, tuple)):
            value = str(option[0]) if len(option) > 0 else ""
            name = str(option[1]) if len(option) > 1 else value
        # Handle dicts
        else:
            name = self._pull_first(option, ["name", "label", "description"])
            value = self._pull_first(option, ["id", "value", "val"])
            if not value and name:
                value = name
            if not value:
                value = str(option)
            if not name and value:
                name = self.words_split(value)
        return value, name

    def render_select_options(self, options, selected=None):
        r = []
        if isinstance(selected, Undefined) or selected == "":
            selected = None
        selected_val, selected_name = self._pull_name_value(selected)
        found_selected = selected is None

        for option in options:
            value, name = self._pull_name_value(option)

            is_selected = ' selected' if selected_val == value else ''
            if is_selected:
                found_selected = True
            r.append(f"""<option value="{value}"{is_selected}>{name}</option>""")
        if not found_selected and selected is not None:
            r.append(f"""<option value="{selected_val}" selected>{selected_name}  (Not found)</option>""")
        r = "\n".join(r)
        return Markup(r)

    def localize(self, d: datetime.datetime) -> datetime.datetime:
        if not d:
            return d

        # If naive, assume UTC (based on your data model)
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)

        return d.astimezone(self.LOCAL_TZ)

    def now(self):
        return datetime.datetime.now(tz=self.LOCAL_TZ)
