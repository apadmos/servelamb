import importlib
import inspect
import os
import re
from pathlib import Path


class Router(object):
    ROUTES = {}
    CONTROLLERS = []
    """Any verbs used in decorators need to be stored here for error checking"""
    RESERVED_VERBS = ["GET", "POST", "PUT", "OPTIONS", "DELETE"]

    @classmethod
    def list_controllers(cls, directory: Path, collector: set = None, module_prefix: str = None, base_dir: Path = None):
        if collector is None:
            collector = set()
        if base_dir is None:
            base_dir = directory
        for file in directory.iterdir():
            if file.name.endswith('_controller.py'):
                if module_prefix:
                    rel_dir = file.parent.relative_to(base_dir)
                    controller_path = module_prefix
                    if rel_dir.parts:
                        controller_path = f"{controller_path}.{'.'.join(rel_dir.parts)}"
                    controller_path = f"{controller_path}.{file.stem}"
                else:
                    controller_path = f'{".".join(directory.parts)}.{file.stem}'
                print(f"listing controller {controller_path} from {file.name}")
                collector.add((controller_path, file))
            elif file.is_dir():
                cls.list_controllers(file, collector, module_prefix=module_prefix, base_dir=base_dir)
        return collector

    @classmethod
    def register(cls, controller_directory, module_prefix: str = None):
        controller_directory = Path(controller_directory)

        if not os.path.isdir(controller_directory):
            print(f'{controller_directory} not found. No routes will be registered')
            return

        for module_path, file in cls.list_controllers(controller_directory, module_prefix=module_prefix):
            controller_module = importlib.import_module(module_path)
            for module in controller_module.__dict__.items():
                if str(module[0]).endswith('Controller'):
                    controller_class = module[1]
                    controller_instance = controller_class()
                    cls.CONTROLLERS.append(controller_instance)
                    for function_name in dir(controller_instance):
                        function = getattr(controller_instance, function_name)
                        if hasattr(function, 'web_method') and function.web_method:
                            auth_param = function.auth_wrapper_param if hasattr(function, 'auth_wrapper_param') else None
                            for path in function.web_paths:
                                cls.register_method(method=function.web_method,
                                                    path=path,
                                                    function=function,
                                                    instance=controller_instance,
                                                    auth_param=auth_param,
                                                    file=file)

    @classmethod
    def register_method(cls, method, path, function, instance, auth_param, file):
        # https://docs.python.org/3/library/re.html
        fn = function.__name__.upper()
        if fn in Router.RESERVED_VERBS or fn == method:
            print(f"Warning: Cannot use reserved word {method} {function}")
            raise ImportError(f"Warning: Cannot use reserved word {method} {function}")

        path = str(path).replace("{", "(?P<").replace("}", ">[^/]*)")
        key = f'{path}-{method}'
        print(f'registering {function} as {method} {path}')
        if key in cls.ROUTES:
            raise Exception(f"Attempt to register duplicate function for {key}. \n   File \"{file.absolute()}\"")
        cls.ROUTES[key] = (instance, function, auth_param)

    @classmethod
    def route(cls, path: str, method):
        key = f'{path}-{method}'
        r = cls.ROUTES.get(key)
        if not r:
            for p in cls.ROUTES:
                m = re.match(p, key)
                if m:
                    return cls.ROUTES[p], m.groupdict()
        return r, {}

    @classmethod
    def intuit_path(cls, func):
        module = inspect.getmodule(func).__name__
        if module.startswith('controllers.'):
            module = module[len('controllers'):]
        if module.endswith('_controller'):
            module = module[:-len('_controller')]
        module = module.replace('.', '/', 100)
        name = func.__name__
        return f'{module}/{name}'

    @classmethod
    def create_path_decorator(cls, path, method):
        def decorator(func):
            if not hasattr(func, "web_paths") or not func.web_paths:
                func.web_paths = []
            func.web_paths.append(path or cls.intuit_path(func))
            func.web_method = method
            return func

        return decorator


def get(path: str = None):
    return Router.create_path_decorator(path=path, method='GET')


def post(path: str = None):
    return Router.create_path_decorator(path=path, method='POST')


def delete(path: str = None):
    return Router.create_path_decorator(path=path, method='DELETE')


def put(path: str = None):
    return Router.create_path_decorator(path=path, method='PUT')


def auth(permissions):
    def auth_decorator(func):
        func.auth_wrapper_param = permissions
        return func

    return auth_decorator
