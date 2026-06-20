import os
from urllib import parse

from digest import Digest
from .param_parser import ParamParser
from .req_wrapper import ReqWrapper
from .resp_builder import RespBuilder
from .router import Router


class ServerApp(object):

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
                 middleware: list = None,
                 extensions=None,
                 before_request=None,
                 before_response=None):
        self.before_request = before_request
        self.before_response = before_response

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
            ext_controller_dir = os.path.join(ext_root or "", "controllers")
            self.router.register(controller_directory=ext_controller_dir,
                                 module_prefix=ext_module_prefix)
        self.static_dir = static_dir
        self.template_dir = template_dir
        self.static_prefix = static_prefix
        self.server_prefix = server_prefix
        self.jinja_pipes = jinja_pipes or {}
        self.jinja_functions = jinja_functions or {}
        self.middleware = middleware

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

    def handle(self, req: ReqWrapper) -> RespBuilder:
        resp = RespBuilder(static_dir=self.static_dir,
                           template_dirs=self.template_dirs,
                           template_loader=self.template_loader,
                           static_prefix=self.static_prefix,
                           server_prefix=self.server_prefix,
                           jinja_pipes=self.jinja_pipes,
                           jinja_functions=self.jinja_functions, req=req)
        try:
            req.static_dir = self.static_dir
            req.template_dir = self.template_dir
            req.static_prefix = self.static_prefix
            req.server_prefix = self.server_prefix

            """Because of how shitty the AWS Cloudfront query string support is, we need to work around it
            by using a placeholder"""
            if "~q~" in req.path and not req.query:
                parts = req.path.split("~q~")
                qs = parts[1]
                req.path = parts[0]
                qs = self.util.to_param_dict(parse.parse_qs(qs, keep_blank_values=True))
                req.query = qs

            """Now that we're doctoring paths, if it's totally blank go with /"""
            if not req.path:
                req.path = "/"

            """expand the various sources of params into one location"""
            if isinstance(req.body, list):
                req.params = Digest(body_array=req.body, **req.query)
            else:
                req.params = Digest(**req.query)
                for key in req.body:
                    req.params[key] = req.body[key]

            """apply the policy headers that should be on all responses"""
            if self.valid_cors_origins:
                # self.send_header("Access-Control-Allow-Origin", host)
                resp.headers("Access-Control-Allow-Methods", "*")
                resp.headers("Access-Control-Allow-Credentials", "true")

            """If there is a controller route that matches this path, use that first"""
            route, path_params = self.router.route(req.path, req.method)
            for path_param in path_params:
                req.params[path_param] = path_params[path_param]
            if route:
                """if you found a route that is registered to handle this request"""
                if self.before_request:
                    self.before_request(req, resp)

                instance, function, auth_param = route
                req.auth_param = auth_param

                """first process middleware"""
                for middle in self.middleware or []:
                    if hasattr(middle, "pre_process"):
                        resp_code = middle.pre_process(function, req, resp)
                        if resp_code not in [0, 200]:
                            return resp

                """then do the route action"""
                function(req, resp)

                """the caching or custom headers are "native" middleware """
                if hasattr(function, "_headers"):
                    for header in function._headers:
                        resp.headers[header] = function._headers[header]

                """do middleware post processing, for things like session storage etc"""
                for middle in self.middleware or []:
                    if hasattr(middle, "post_process"):
                        middle.post_process(function, req, resp)

                return resp

            """There's no matching controller route, search for a matching static file"""
            if not self.static_dir:
                resp.not_found(f'server route {req.method} {req.path} not found and static files are not configured')
                return resp

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
                return resp.file(fpath)

            if not ext:
                fpath = os.path.join(self.static_dir, name, "index.html")
                if os.path.isfile(fpath):
                    return resp.file(fpath)

            return resp.not_found(f'route {req.method} {req.path} {fpath} not found')
        finally:
            if self.before_response:
                self.before_response(req, resp)
