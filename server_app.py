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
                 valid_cors_origins=[],
                 jinja_pipes=None,
                 jinja_functions=None,
                 extensions=None,
                 look_for_index_html=True
                 ):
        self.valid_cors_origins = valid_cors_origins
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

    def pre_controller(self, function, req, resp) -> RespBuilder | None:
        """Called once the request has been fully unpacked, but no actual processing my controllers has happened
        This is probably where you want to put your connection pooling, auth check, and other things
        in the order you want them

        Returning None continues typical processing, even if you have doctored the request or response
        Returning a ResponseBuilder skips the controller processing and jumps to post_processing
        and serving the response
        """
        return None

    def post_controller(self, function, req, resp, exception) -> RespBuilder | None:
        """Called once the controller processing has happened and a request is about to be returned,
        or an exception is about to be thrown.

        This is your change to override the response with something else

        Returning None continues moves on to returning a response or throwing an unhandled exception
        Return a ResponseBuilder serves that response blindly even if it was never completed
        """
        return None

    def pre_not_found(self, req, resp) -> RespBuilder | None:
        """
        When no controller route, and no static route were found for the request.
        When the route is a complete miss
        This is NOT the same as a controller return a 404

        :param req:
        :param resp:
        :return: returning None will result in a Page Not Found 404 response. If you want a custom 404 or other logic
        return a RespBuilder and that will be returned instead of a 404
        """

    def pre_static_file(self, req, resp, fpath) -> RespBuilder | None:
        return None

    def handle(self, req: ReqWrapper) -> RespBuilder | None:
        resp = RespBuilder(static_dir=self.static_dir,
                           template_dirs=self.template_dirs,
                           template_loader=self.template_loader,
                           static_prefix=self.static_prefix,
                           server_prefix=self.server_prefix,
                           jinja_pipes=self.jinja_pipes,
                           jinja_functions=self.jinja_functions, req=req)
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

        """apply the policy headers that should be on all responses"""
        if self.valid_cors_origins:
            # self.send_header("Access-Control-Allow-Origin", host)
            resp.headers["Access-Control-Allow-Methods"] = "*"
            resp.headers["Access-Control-Allow-Credentials"] = "true"

        """If there is a controller route that matches this path, use that first"""
        route, path_params = self.router.route(req.path, req.method)
        if not route and req.method == "HEAD":
            """A HEAD gets the same status and headers as a GET, so it runs the GET route; the hosting leaves
            out the body"""
            route, path_params = self.router.route(req.path, "GET")
        for path_param in path_params:
            req.params[path_param] = path_params[path_param]
        if route:
            """if you found a route that is registered to handle this request"""
            instance, function, auth_param = route
            req.auth_param = auth_param

            """first process middleware"""
            resp_override = self.pre_controller(function, req, resp)
            processing_error = None
            if resp_override:
                resp = resp_override
            else:
                try:
                    """then do the route action"""
                    function(req, resp)
                    """the caching or custom headers are "native" middleware 
                    TODO: Can we delete this?
                    """
                    if hasattr(function, "_headers"):
                        for header in function._headers:
                            resp.headers[header] = function._headers[header]
                except Exception as ex:
                    processing_error = ex

            resp_override = self.post_controller(function, req, resp, processing_error)
            if resp_override:
                return resp_override
            elif processing_error:
                raise processing_error
            return resp

        """There's no matching controller route, search for a matching static file"""
        if not self.static_dir:
            resp_override = self.pre_not_found(req, resp)
            if resp_override:
                return resp_override
            return resp.not_found()

        name, ext = os.path.splitext(req.path)
        """unify all paths to start with / """
        name = name.strip(" /\\")
        """if the path starts with the static pathing prefix, strip it out cause we're only looking
        at static files at this point"""
        local_prefix = self.static_prefix.lstrip("/")
        name = name[len(local_prefix):] if name.startswith(local_prefix) else name

        """attempt to serve the static file as is"""
        fpath = os.path.join(self.static_dir, name + ext)
        if os.path.isfile(fpath):
            resp_override = self.pre_static_file(req, resp, fpath)
            if resp_override:
                return resp_override
            return resp.file(fpath)

        if not ext and self.look_for_index_html:
            fpath = os.path.join(self.static_dir, name, "index.html")
            if os.path.isfile(fpath):
                resp_override = self.pre_static_file(req, resp, fpath)
                if resp_override:
                    return resp_override
                return resp.file(fpath)

        resp_override = self.pre_not_found(req, resp)
        if resp_override:
            return resp_override
        return resp.not_found()
