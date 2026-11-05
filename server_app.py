import os
import re
from urllib import parse

from digest import Digest
from .param_parser import ParamParser
from .req_wrapper import ReqWrapper
from .resp_builder import RespBuilder
from .router import Router


class ServerApp(object):
    """Everything after the last letter or digit of a request path: the trailing slash plus link junk"""
    TRAILING_PATH_JUNK: re.Pattern = re.compile(r"[^A-Za-z0-9]+$")

    def __init__(self,
                 controller_dir="controllers",
                 static_dir="static",
                 template_dir="templates",
                 template_loader=None,
                 static_prefix="static",
                 server_prefix="",
                 valid_cors_origins: list[str] | None = None,
                 jinja_pipes=None,
                 jinja_functions=None,
                 extensions=None,
                 look_for_index_html=True
                 ):
        """Origins (scheme, host and port, e.g. https://www.example.org) a browser may call this app from"""
        self.valid_cors_origins: list[str] = valid_cors_origins or []
        self.router = Router()
        self.router.register(controller_directory=controller_dir)
        self.extensions = extensions or []
        self.extension_roots = []
        self.template_loader = template_loader
        self.util = ParamParser()
        for extension in self.extensions:
            ext_module_prefix = f"{extension.__name__}.controllers"
            ext_root = None
            if hasattr(extension, "__path__") and extension.__path__:
                ext_root = extension.__path__[0]
            elif hasattr(extension, "__file__") and extension.__file__:
                ext_root = os.path.dirname(extension.__file__)
            if ext_root:
                self.extension_roots.append(ext_root)
            ext_controller_dir = os.path.join(str(ext_root or ""), "controllers")
            self.router.register(controller_directory=ext_controller_dir,
                                 module_prefix=ext_module_prefix)
        self.static_dir = static_dir
        self.template_dir = template_dir
        self.static_prefix = static_prefix
        self.server_prefix = server_prefix
        self.jinja_pipes = jinja_pipes or {}
        self.jinja_functions = jinja_functions or {}
        self.look_for_index_html = look_for_index_html

        cwd = os.path.abspath(os.getcwd())
        self.working_dir = cwd
        print(f"App cwd {cwd}")

        self.static_dir = os.path.abspath(self.static_dir)
        self.template_dir = os.path.abspath(self.template_dir)

        if not os.path.isdir(self.static_dir):
            print(f"Static directory does not exists!!! {self.static_dir}")
            self.static_dir = None
        else:
            print(f"The static asset path {self.static_prefix} will be linked to {self.static_dir}")

        if not os.path.isdir(self.template_dir):
            print(f"Template directory not found!!! {self.template_dir}")
            self.template_dir = None
        else:
            print(f"Templates will be served form {self.template_dir}")

        self.template_dirs = []
        if self.template_dir:
            self.template_dirs.append(self.template_dir)
        for ext_root in self.extension_roots:
            ext_template_dir = os.path.join(ext_root, "templates")
            if os.path.isdir(ext_template_dir):
                self.template_dirs.append(ext_template_dir)
        if len(self.template_dirs) > 1:
            print(f"Extension template dirs: {self.template_dirs[1:]}")

        self.static_prefix = self.static_prefix.rstrip(" /\\") + "/"
        self.server_prefix = self.server_prefix.rstrip(" /\\") + "/"
        if ':' not in self.static_prefix and not self.static_prefix.startswith("/"):
            self.static_prefix = "/" + self.static_prefix
        print(f"Server prefix: {self.server_prefix}  Static prefix: {self.static_prefix}")

    """
    Hooks, in the order they run. Each one that returns a RespBuilder replaces the response and ends the processing;
    None carries on. Override them in a subclass; none of them do anything here.
    """

    def pre_process(self, req, resp) -> RespBuilder | None:
        """First thing, before the request is unpacked or routed"""
        return None

    def pre_controller(self, function, req, resp) -> RespBuilder | None:
        """A route matched and the request is unpacked, but the controller hasn't run. This is probably where you
        want your connection pooling, auth check and other things, in the order you want them. Only routed requests
        get here, so a static file never opens a connection. A RespBuilder skips the controller"""
        return None

    def post_controller(self, function, req, resp) -> RespBuilder | None:
        """The controller ran without raising (an exception goes to pre_exception instead). This is your chance to
        change the response, or to persist what the controller left on it, like the session"""
        return None

    def pre_static_file(self, req, resp, fpath) -> RespBuilder | None:
        """No route matched and fpath is the static file about to be served"""
        return None

    def pre_not_found(self, req, resp) -> RespBuilder | None:
        """No controller route and no static file: a complete miss. This is NOT the same as a controller returning
        a 404. None sends the plain 404"""
        return None

    def pre_exception(self, req, resp, exception: Exception) -> RespBuilder | None:
        """Anything above raised, a hook or the controller. resp is whatever was built before it did, so start
        over with resp.error(...) or similar. None lets the exception go on to the hosting"""
        return None

    def post_process(self, req, resp, exception: Exception | None) -> None:
        """Always last, in a finally, so it can clean up what any other step set up (close connections) and log
        the outcome. resp is the response being sent; exception is set when one is going on to the hosting
        (pre_exception returned None). Shouldn't raise: it would replace the response or the exception"""
        return None

    def on_failure(self, title: str, details: str, req: ReqWrapper | None) -> None:
        """Not part of handle: the hosting calls it when something got past handle (a hook raised) or the request
        couldn't even be read (req is None). It has already printed it and sends a plain 500 whatever this does.
        title names the request; details are who sent it and the traceback"""
        return None

    def handle(self, req: ReqWrapper) -> RespBuilder:
        """Every return in the try sets resp first, so post_process gets the response that's actually sent"""
        resp = RespBuilder(static_dir=self.static_dir,
                           template_dirs=self.template_dirs,
                           template_loader=self.template_loader,
                           static_prefix=self.static_prefix,
                           server_prefix=self.server_prefix,
                           jinja_pipes=self.jinja_pipes,
                           jinja_functions=self.jinja_functions, req=req)
        unhandled: Exception | None = None
        try:
            resp_override = self.pre_process(req, resp)
            if resp_override is not None:
                resp = resp_override
                return resp

            req.static_dir = self.static_dir
            req.template_dir = self.template_dir
            req.static_prefix = self.static_prefix
            req.server_prefix = self.server_prefix

            """Because of how shitty the AWS Cloudfront query string support is, we need to work around it
            by using a placeholder"""
            if "~q~" in req.path and not req.query:
                parts = req.path.split("~q~", 1)
                qs = parts[1]
                req.path = parts[0]
                qs = self.util.to_param_dict(parse.parse_qs(qs, keep_blank_values=True))
                req.query = qs

            """Always copy how AWS does it: no trailing slash, whether or not there was a query string.
            Punctuation that email and chat clients glue onto the end of a link goes too, so
            /shows/show-detail/the-steel-man/) routes like /shows/show-detail/the-steel-man"""
            req.path = self.TRAILING_PATH_JUNK.sub("", req.path)

            """Now that we're doctoring paths, if it's totally blank go with /"""
            if not req.path:
                req.path = "/"

            """expand the various sources of params into one location"""
            if isinstance(req.body, list):
                req.params = Digest(body_array=req.body, **req.query)
            elif isinstance(req.body, (bytes, bytearray)):
                """A raw upload (application/octet-stream) stays in req.body: copying it byte by byte into params
                would make a dict entry per byte"""
                req.params = Digest(**req.query)
            else:
                req.params = Digest(**req.query)
                for key in req.body:
                    req.params[key] = req.body[key]

            """CORS: only an Origin in valid_cors_origins is allowed. It's echoed back rather than "*", which
            browsers refuse alongside credentials. Vary tells caches the response depends on the Origin"""
            origin: str = req.headers.get("origin") or ""
            if origin and origin in self.valid_cors_origins:
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Methods"] = "*"
                resp.headers["Access-Control-Allow-Credentials"] = "true"
                resp.headers["Vary"] = "Origin"

            """If there is a controller route that matches this path, use that first"""
            route, path_params = self.router.route(req.path, req.method)
            if not route and req.method == "HEAD":
                """A HEAD gets the same status and headers as a GET, so it runs the GET route; the hosting leaves
                out the body"""
                route, path_params = self.router.route(req.path, "GET")
            for path_param in path_params:
                req.params[path_param] = path_params[path_param]
            if route:
                _instance, function, auth_param = route
                req.auth_param = auth_param

                resp_override = self.pre_controller(function, req, resp)
                if resp_override is not None:
                    resp = resp_override
                    return resp

                function(req, resp)

                """Headers from the @header and @cache decorators, once the controller has finished without raising,
                so an error response never picks up a cache header. They're defaults: a header the controller set
                itself wins"""
                for name, value in (getattr(function, "_headers", None) or {}).items():
                    resp.headers.setdefault(name, value)

                resp_override = self.post_controller(function, req, resp)
                if resp_override is not None:
                    resp = resp_override
                return resp

            """There's no matching controller route, search for a matching static file"""
            fpath: str | None = None
            if self.static_dir:
                name, ext = os.path.splitext(req.path)
                """unify all paths to start with / """
                name = name.strip(" /\\")
                """if the path starts with the static pathing prefix, strip it out cause we're only looking
                at static files at this point"""
                local_prefix = self.static_prefix.lstrip("/")
                name = name[len(local_prefix):] if name.startswith(local_prefix) else name

                """the file as is, or a folder's index.html"""
                candidates: list[str] = [os.path.join(self.static_dir, name + ext)]
                if not ext and self.look_for_index_html:
                    candidates.append(os.path.join(self.static_dir, name, "index.html"))
                fpath = next((candidate for candidate in candidates if os.path.isfile(candidate)), None)

            if fpath:
                resp_override = self.pre_static_file(req, resp, fpath)
                resp = resp_override if resp_override is not None else resp.file(fpath)
                return resp

            resp_override = self.pre_not_found(req, resp)
            resp = resp_override if resp_override is not None else resp.not_found()
            return resp
        except Exception as exception:
            resp_override = self.pre_exception(req, resp, exception)
            if resp_override is None:
                unhandled = exception
                raise
            resp = resp_override
            return resp
        finally:
            self.post_process(req, resp, unhandled)
