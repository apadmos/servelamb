def _apply_web_method(path, method):
    def wrapper(func):
        if not hasattr(func, "web_paths") or not func.web_paths:
            func.web_paths = []
        func.web_paths.append(path)
        func.web_method = method
        return func

    return wrapper


def get(path: str = None):
    return _apply_web_method(path=path, method='GET')


def post(path: str = None):
    return _apply_web_method(path=path, method='POST')


def delete(path: str = None):
    return _apply_web_method(path=path, method='DELETE')


def put(path: str = None):
    return _apply_web_method(path=path, method='PUT')


def cache(max_age: int = 3600, stale_while_revalidate: int = 3600, stale_if_error: bool = True):
    def apply(target):
        if stale_if_error:
            stale = " stale-if-error,"
        else:
            stale = ""
        header_value = f"public,{stale} max-age={max_age}, stale-while-revalidate={stale_while_revalidate}"
        if isinstance(target, type):
            return _apply_header_to_cls(cls=target, name="Cache-Control", value=header_value)
        else:
            return _apply_header_to_func(func=target, name="Cache-Control", value=header_value)

    return apply


def header(name: str, value: str):
    def apply(target):
        if isinstance(target, type):
            return _apply_header_to_cls(cls=target, name=name, value=value)
        else:
            return _apply_header_to_func(func=target, name=name, value=value)

    return apply


def _apply_header_to_func(func, name: str, value: str):
    existing = getattr(func, "_headers", {})
    existing[name] = value
    func._headers = existing
    return func


def _apply_header_to_cls(cls, name: str, value: str):
    for attr_name in dir(cls):
        if attr_name.startswith('_'):
            continue
        attr = getattr(cls, attr_name)
        setattr(cls, attr_name, _apply_header_to_func(func=attr, name=name, value=value))
    return cls


def auth(permission: str = None,
         namespace: str = None,
         id: str = None,
         auth_redirect: str = None,
         login_redirect: str = None):
    def apply(target):
        if isinstance(target, type):
            return _appy_auth_to_cls(cls=target,
                                     permission=permission,
                                     namespace=namespace,
                                     id=id,
                                     auth_redirect=auth_redirect,
                                     login_redirect=login_redirect)
        else:
            return _apply_auth_to_func(func=target,
                                       permission=permission,
                                       namespace=namespace,
                                       id=id,
                                       auth_redirect=auth_redirect,
                                       login_redirect=login_redirect)

    return apply


def _check_assign(func, name, value):
    if not hasattr(func, name) or not getattr(func, name):
        setattr(func, name, value)


def _apply_auth_to_func(func, permission: str = None,
                        namespace: str = None,
                        id: str = None,
                        auth_redirect: str = None,
                        login_redirect: str = None,
                        ):
    _check_assign(func, "auth_permission", permission)
    _check_assign(func, "auth_namespace", namespace)
    _check_assign(func, "auth_resource_id", id)
    _check_assign(func, "auth_redirect", auth_redirect)
    _check_assign(func, "auth_login_redirect", login_redirect)
    return func


def _appy_auth_to_cls(cls, permission: str = None,
                      namespace: str = None,
                      id: str = None,
                      auth_redirect: str = None,
                      login_redirect: str = None):
    """Applies auth to every routed method on a class."""
    for attr_name in dir(cls):
        if attr_name.startswith('_'):
            continue
        attr = getattr(cls, attr_name)
        setattr(cls, attr_name, _apply_auth_to_func(func=attr,
                                                    permission=permission,
                                                    namespace=namespace,
                                                    id=id,
                                                    auth_redirect=auth_redirect,
                                                    login_redirect=login_redirect))
    return cls
