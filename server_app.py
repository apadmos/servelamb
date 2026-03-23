import os

from .req_wrapper import ReqWrapper
from .resp_builder import RespBuilder
from .router import Router
from .util import Digest


class ServerApp(object):

    def __init__(self,
                 controller_dir="controllers",
                 static_dir="static",
                 template_dir="templates",
                 static_prefix="static",
                 server_prefix="",
                 jinja_pipes=None,
                 jinja_functions=None,
                 middleware: list = None,
                 extensions=None):
        self.router = Router()
        self.router.register(controller_directory=controller_dir)
        self.extensions = extensions or []
        self.extension_roots = []
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
                           static_prefix=self.static_prefix,
                           server_prefix=self.server_prefix,
                           jinja_pipes=self.jinja_pipes,
                           jinja_functions=self.jinja_functions)
        req.static_dir = self.static_dir
        req.template_dir = self.template_dir
        req.static_prefix = self.static_prefix
        req.server_prefix = self.server_prefix

        """expand the various sources of params into one location"""
        if isinstance(req.body, list):
            req.params = Digest(body_array=req.body, **req.query)
        else:
            req.params = Digest(**req.query)
            for key in req.body:
                req.params[key] = req.body[key]

        """If there is a controller route that matches this path, use that first"""
        route, path_params = self.router.route(req.path, req.method)
        for path_param in path_params:
            req.params[path_param] = path_params[path_param]
        if route:
            """if you found a route that is registered to handle this request"""
            instance, function, auth_param = route
            req.auth_param = auth_param

            """first process middleware"""
            for middle in self.middleware or []:
                if hasattr(middle, "pre_process"):
                    resp_code = middle.pre_process(function, req, resp)
                    if resp_code > 0:
                        return resp

            """then do the route action"""
            function(req, resp)

            """do middleware post processing, for things like session storage etc"""
            for middle in self.middleware or []:
                if hasattr(middle, "post_process"):
                    resp = middle.post_process(function, req, resp)

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
