"""Helpers for flask views for ox_herd
"""

from functools import wraps

from flask import abort
from flask_login import current_user


def simple_role_check(*roles):
    """Decorator which specifies that a user must have all the specified roles.

    This is a simple hack to allow functioning if flask_security is
    not installed. If you want to do anything serious, you should
    install flask_security.
    """
    def wrapper(func):
        "Wrap view in role check"
        @wraps(func)
        def decorated_view(*args, **kwargs):
            """Decorate view with simple role check
            """
            if not roles:
                raise ValueError('Refusing to fake role check with no roles')
            user_roles = getattr(current_user, 'roles', [])
            if not set(user_roles).intersection(roles):
                abort(403, description=(
                    'User %s (roles=%s) lacks accpetable role: %s' % (
                        getattr(current_user, 'username', getattr(
                            current_user, 'id', 'unknown')),
                        str(user_roles), str(roles))))
            return func(*args, **kwargs)
        return decorated_view
    return wrapper
