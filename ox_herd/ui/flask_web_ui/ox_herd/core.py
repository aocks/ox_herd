"""Core tools for ox_herd flask views.
"""

import logging

from ox_herd.ui.flask_web_ui.ox_herd import OX_HERD_BP
from ox_herd import settings
from ox_herd.core.utils import ox_decs
from ox_herd.ui.flask_web_ui.ox_herd import helpers


ROLES_CHECK = None

try:
    from flask_security import roles_accepted
    ROLES_CHECK = roles_accepted
except ImportError as problem:
    logging.warning('Error on importing roles_accepted: %s; will fake it',
                    str(problem))


if not ROLES_CHECK:
    ROLES_CHECK = helpers.simple_role_check


def ox_herd_route(*args, extra_roles=(), noauth=False, **kwargs):
    """Decorator to ensure user is allowed to access ox_herd views.

    This is intended to be called instead of OX_HERD_BP.route for when
    you want a route which forces authentication + ox_herd permissions.
    Use this and **NOT** OX_HERD_BP.route.
    """
    def make_decorator(my_func):
        """Make combined decorator for given input `my_func`.

        This is a little tricky because we want to make a decorator
        that takes in my_func, applies the OX_HERD_BP.route decorator and
        makes sure all the docs are fixed up right.

        This function can then be applied as a one shot decorator to do
        the above where as if you tried to do it separately then the
        docs would be hard to get right.
        """
        if noauth:
            return OX_HERD_BP.route(*args, **kwargs)(my_func)

        if settings.OX_HERD_ROLES:
            with_role = ROLES_CHECK(*(settings.OX_HERD_ROLES + list(
                extra_roles)))(my_func)
        else:  # Do not wrap with role check
            with_role = my_func
        with_route = OX_HERD_BP.route(*args, **kwargs)(with_role)
        result = with_route
        ox_decs.fix_doc(result, OX_HERD_BP.route)
        return result
    return make_decorator


def make_form_for_task(my_args):
    """Take an ox_herd plugin instance (or something like it) and make form.

This tries to create a form to configure an ox_herd task.
    """
    # Try to get the deprecated get_flask_form first.
    # Even if they are using the preferred get_flask_form_via_cls, the
    # get_flask_form should call that. But if they are using the old
    # get_flask_form then need to go through that flow first.
    maker = getattr(my_args, 'get_flask_form', None)
    if maker is None:
        logging.warning('could not find get_flask_form method of %s',
                        str(my_args))
        maker = getattr(my_args, 'get_flask_form_via_cls', None)
    if maker is None:
        msg = ("Item %s does not inherit from OxPlugin so can't configure.\n"
               "Rewrite that class to inherit from OxPlugin or at least\n"
               "provide a get_flask_form_via_cls method.")
        raise ValueError(msg)
    my_form_cls = maker()
    my_form = my_form_cls(obj=my_args)
    return my_form
