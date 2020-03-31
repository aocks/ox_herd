"""Core tools for ox_herd flask views.
"""


import logging


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
