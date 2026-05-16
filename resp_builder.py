import datetime
import json
import mimetypes
import os
import sys
import urllib.parse
import uuid

import jinja2
from jinja2 import Environment, select_autoescape, FunctionLoader

import fancycli
from .jinja_helpers import words_split, date_format, date_input_format, render_select_options, localize
from .req_wrapper import ReqWrapper


class RespBuilder(object):

    def __init__(self, static_dir, template_dirs=None,
                 template_loader=None,
                 static_prefix: str = '',
                 server_prefix: str = '', jinja_pipes=None, jinja_functions=None, req: ReqWrapper = None):
        self._status = 200
        self._body: str = ''
        self._file: str = ''
        self.headers = {
            "Content-type": "text"
        }
        self._static_dir = static_dir
        self._template_dirs = template_dirs or []
        self._template_loader = template_loader
        self._jinja = None
        self._cache_output = False
        self._static_prefix = static_prefix
        self._server_prefix = server_prefix
        self._jinja_pipes = jinja_pipes
        self._jinja_functions = jinja_functions or {}
        self._session = {}
        self.req = req

    def session(self, session):
        self._session = session

    def serialize_helper(self, value):
        if isinstance(value, uuid.UUID):
            return value.__str__()
        if isinstance(value, datetime.datetime):
            return value.__str__()
        return value

    def json(self, body: object):
        try:
            self._body = json.dumps(body, default=self.serialize_helper)
        except TypeError as t:
            print(t, file=sys.stderr)
            print('Attempting fallback', file=sys.stderr)
            simpler = body.__dict__

            self._body = json.dumps(simpler)
        self._body = self._body
        self.headers["Content-type"] = 'application/json'
        return self

    def text(self, body: str):
        self._body = body
        self.headers["Content-type"] = 'text/plain'
        return self

    def html(self, body: str):
        self._body = body
        self.headers["Content-type"] = 'text/html'
        return self

    def static(self, relative_path):
        relative_path = os.path.join(self._static_dir, relative_path)
        return self.file(path=relative_path)

    def file(self, path, cache=True):
        self._file = path
        self._cache_output = cache
        self.headers["Content-type"] = mimetypes.guess_type(path)[0]
        return self

    def load_template(self, file_path):
        if self._template_loader:
            loaded = self._template_loader(file_path)
            if loaded:
                return loaded
        if os.path.isfile(file_path):
            with open(file_path, 'r') as file:
                return file.read()
        for template_dir in self._template_dirs:
            if not template_dir:
                continue
            candidate = os.path.join(template_dir, file_path)
            if os.path.isfile(candidate):
                with open(candidate, 'r') as file:
                    return file.read()
        return None

    def jinja(self):
        if not self._jinja:
            """May need file system loader here https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.PackageLoader"""
            self._jinja = Environment(
                loader=FunctionLoader(self.load_template),
                autoescape=select_autoescape())
            self._jinja.filters["date"] = date_format
            self._jinja.filters["input_date"] = date_input_format
            self._jinja.filters["words"] = words_split
            self._jinja.filters["words_split"] = words_split
            self._jinja.filters["localize"] = localize
            for pipe in self._jinja_pipes:
                self._jinja.filters[pipe] = self._jinja_pipes[pipe]
            for func in self._jinja_functions:
                self._jinja.globals["options"] = render_select_options
                self._jinja.globals["select_options"] = render_select_options
                self._jinja.globals[func] = self._jinja_functions[func]
        return self._jinja

    def template(self, data=None, template_path=None, template_markup=None, template_name: str = None,
                 status_code: int = None):
        if status_code:
            self._status = status_code
        if not template_markup:
            template_markup = self.load_template(file_path=template_path)

        template = self.jinja().from_string(template_markup)
        template.name = template_name

        data = data or {}
        data["SERVER_PREFIX"] = self._server_prefix
        data["STATIC_PREFIX"] = self._static_prefix
        data["SESSION"] = self._session
        try:
            rendered = template.render(data, req=self.req)
            return self.html(rendered)
        except jinja2.UndefinedError as e:
            tb = e.__traceback__
            template_frames = []
            if template_path:
                fancycli.print_error(f"Root template File \"{template_path}\"")
                print(f"File \"{template_path}\"")

            while tb is not None:
                filename = tb.tb_frame.f_code.co_filename
                # Jinja2 template frames use the template name as the filename
                if not filename.endswith(".py"):
                    template_frames.append((filename, tb.tb_lineno))
                tb = tb.tb_next

            for template_name, lineno in template_frames:
                fancycli.print_error(f"  in '{template_name}' on line {lineno}")
            raise
        except TypeError as te:
            tb = te.__traceback__
            while tb is not None:
                filename = tb.tb_frame.f_code.co_filename
                if not filename.endswith(".py"):
                    lineno = tb.tb_lineno
                    # Get the template source to extract the offending line
                    try:
                        lines = template_markup.splitlines()
                        offending_line = lines[lineno - 1].strip() if lineno <= len(lines) else "<unknown>"
                    except Exception:
                        offending_line = "<source unavailable>"
                    fancycli.print_error(
                        f"TypeError in template '{filename}' on line {lineno}: {offending_line}\n  {te}"
                    )
                tb = tb.tb_next
            raise te
        except Exception as ex:
            fancycli.print_error("Unanticipated exception type:", exception=ex)
            raise ex

    def js_redirect(self, goto: str):
        return self.html(f"""<html><body><title>Redirecting...</title>
        <script>setTimeout(function () {{ window.location.replace("{goto}");}}, 0);</script>
<a href="{goto}">Click here to continue</a></body></html>""")

    def not_found(self, message: str):
        return self.error(message=message, status_code=404)

    def redirect(self, location: str, permanent=False):
        if permanent:
            self._status = 301
        else:
            self._status = 303
        self.headers["Location"] = location
        return self

    def cookie(self, key: str, value: str,
               max_age: datetime.timedelta = datetime.timedelta(days=1),
               mode: str = "Lax", http_only: bool = True, path="/"):
        """
        :param key: User defined name
        :param value: user defined value
        :param max_age: max seconds to allow cookie to live
        :param mode: Lax (domain and subdomains), Strict (exact domain match), None (anything)
        :param http_only: Can't be accessed by JS
        :return: self
        """
        kv = dict()
        kv[key] = value
        cooks = urllib.parse.urlencode(kv)

        expiration = datetime.datetime.now(tz=datetime.timezone.utc) + max_age

        cookie_string = f"{cooks}; Path={path}; Max-Age={max_age.total_seconds()}; SameSite={mode}; Expires={expiration.strftime('%a, %d-%b-%Y %H:%M:%S GMT')}"
        if http_only:
            cookie_string += "; HttpOnly"

        current_cookie = self.headers.get("Set-Cookie")
        if current_cookie:
            raise NotImplemented(
                "Sorry, you can only set 1 cookie at a time right now. Please update the code to allow multiple")
        self.headers["Set-Cookie"] = cookie_string
        return self

    def error(self, message: str, status_code=500):
        self._body = message
        self.headers["Content-type"] = 'text/html'
        self._status = status_code
        return self

    @property
    def status(self):
        return self._status

    @property
    def content_type(self):
        return self.headers["Content-type"]

    @property
    def body(self):
        return self._body

    @property
    def file_path(self):
        return self._file

    @property
    def cache_output(self):
        return self._cache_output
