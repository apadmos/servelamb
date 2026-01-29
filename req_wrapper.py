import http
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
        """Sessions need to be populated by custom middleware"""
        self.session = {}

    def required_str(self, key:str):
        v = self.params.get(key)
        if not v:
            raise Exception(f"{key} is required")
        return v

    def required_int(self, key:str):
        s = self.required_str(key)
        try:
            return int(s)
        except:
            raise Exception(f"{key} must be a valid integer")

    def optional_bool(self, key:str, default:bool=False):
        return bool(self.params.get("active") or default)


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

    def _parse_cookies(self, cookies:str, url_decode=True):
        if not cookies:
            return {}
        r = {}
        for part in cookies.split("; "):
            if url_decode:
                parsed = urllib.parse.parse_qs(part)
                if parsed:
                    for k, v in parsed.items():
                        r[k] = v[0] if v else None
            else:
                parts = part.split("=")
                key = parts[0]
                """in case there is a = in the """
                val = "=".join(parts[1:])
                r[key] = val
        return r

    def cookie(self, key:str, url_decode=True) -> str:
        """
        :param key: key used to set the cookie
        :param url_decode: Cookies are URL encoded when set by the resp_builder
        :return: cookie value as string, or None
        """
        cooks = self.headers.get("cookie")
        cookies = self._parse_cookies(cooks, url_decode=url_decode)
        val = cookies.get(key)
        return val

    def _grow_array_to_fit(self, source: [], desired_index: int):
        while len(source) <= desired_index:
            source.append(None)

    """
    make sure dict is not null
    handle name[1] style array assumptions
    return possible new dictionary with assigned value or array and value
    """

    def _check_assign(self, dict: dict, key: str, default_value):
        if '[' in key and ']' in key:
            parts = key.split('[')
            key = parts[0]
            arr = dict.get(key) or []
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
            dict[key] = arr
            return arr[index]
        else:
            if dict.get(key) is None:
                dict[key] = default_value
            return dict[key]

    def _pack_objects(self, dict):
        repack = {}
        for key in dict:
            val = dict[key]
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
