import urllib.parse
from urllib import parse


class ReqWrapper(object):

    def __init__(self):
        self.path: str = '/some/path'
        self.host: str = 'http://localhost'
        self.method: str = 'POST'
        self.static_dir = None
        self.template_dir = None
        self.auth_param = None

        self.headers = {

        }
        self.query = {
            'query_key': 'query_value'
        }
        self.body = {
            'body_key': 'body_value'
        }
        """union of body and query params"""
        self.params = {
            'query_key': 'query_value',
            'body_key': 'body_value'
        }
        self.file = {
        }
        """Parsed once from the Cookie header by the hosting layer when the request comes in"""
        self.cookies: dict[str, str] = {}

        """Sessions need to be populated by a session manager in  the middle"""
        self.session_cookie = "29cc6a41e3fd"
        self._session_cache = {}

    def required_str(self, key: str):
        v = self.params.get(key)
        if not v:
            raise Exception(f"{key} is required")
        return v

    def get_list(self, key: str):
        val = self.params.get(key)
        if not val:
            return []
        if isinstance(val, list):
            return val
        return [val]

    def required_int(self, key: str):
        s = self.required_str(key)
        try:
            return int(s)
        except:
            raise Exception(f"{key} must be a valid integer")

    def optional_bool(self, key: str, default: any = None):
        v = self.params.get(key)
        if v is None or v == '':
            return default
        return str(v).lower() == "true"

    def reconstitute_query_string(self):
        qs = "&".join([f"{parse.quote(str(key))}={parse.quote(str(val))}" for key, val in self.query.items()])
        return qs

    def read_as_complex_form(self):
        """
        pareses HTML forms that have names like data.title, data.description, data.items[0] data.items[0].order
        and converts them into objects and lists
        :return:
        """
        return self._pack_objects(self.params)

    def parse_cookie_header(self) -> dict[str, str]:
        """Cookies are URL encoded when set by the resp_builder, so values are URL decoded here"""
        cookie_header = self.headers.get("cookie")
        if not cookie_header:
            return {}
        cookies: dict[str, str] = {}
        for part in cookie_header.split(";"):
            name, _, value = part.strip().partition("=")
            if name:
                cookies[urllib.parse.unquote_plus(name)] = urllib.parse.unquote_plus(value)
        return cookies

    def cookie(self, key: str) -> str | None:
        return self.cookies.get(key)

    def session_id(self) -> str:
        sid = self.cookie(self.session_cookie)
        return sid

    def session(self) -> dict:
        return self._session_cache

    def _grow_array_to_fit(self, source: list, desired_index: int):
        while len(source) <= desired_index:
            source.append(None)

    """
    make sure dict is not null
    handle name[1] style array assumptions
    return possible new dictionary with assigned value or array and value
    """

    def _check_assign(self, d: dict, key: str, default_value):
        if '[' in key and ']' in key:
            parts = key.split('[')
            key = parts[0]
            arr = d.get(key) or []
            """Handle things like data[0][3][6]"""
            indexes = [int(i[:-1]) for i in parts[1:]]
            for index in indexes[:-1]:
                self._grow_array_to_fit(arr, index)
                arr[index] = []
                arr = arr[index]
            index = indexes[-1]
            self._grow_array_to_fit(arr, index)
            if arr[index] is None:
                arr[index] = default_value
            d[key] = arr
            return arr[index]
        else:
            if d.get(key) is None:
                d[key] = default_value
            return d[key]

    def _pack_objects(self, d: dict):
        repack = {}
        for key in d:
            val = d[key]
            key_parts = key.split('.')
            current_target = repack
            for i in range(0, len(key_parts)):
                current_part = key_parts[i]
                remainder = key_parts[i + 1:]
                if remainder:
                    current_target = self._check_assign(current_target, current_part, {})
                else:
                    self._check_assign(current_target, current_part, val)
        return repack
