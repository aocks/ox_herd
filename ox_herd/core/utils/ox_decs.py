"""Useful decorators and decorator tools.

The `ox_decs` module contains useful decorators and related tools. See
documentation for the following for detailed information:

  - `fix_doc`
  - `withdoc`
  - `composed`

The `fix_doc` function can be used in your own decorators to make sure
your decorator adds information to the original docstring about the
decorator applied. For already existing decorators, you can use
the `withdoc` function to make the existing decorator call `fix_doc` to
update the docstring. Finally, you can use `composed` to combine
multiple decorators in a way that correctly updates the docstring with
information about the decorators whether or not they used `fix_doc`.

See docs for `withdoc` for more information.
"""

import doctest
import time
import logging
import functools


def withdoc(decorator):
    """Decorator to apply a decorator and attach its docs to a function.

    Basically, you can ust put `@withdoc` as a decorator calling your
    original (unmodified) decorator to get preserved docs.

    The following illustrates example usage:

>>> import functools
>>> from ox_decs import withdoc
>>> def withprint(func):
...     "withprint decorates a function to print result after running it."
...     @functools.wraps(func)
...     def decorated(*args, **kwargs):
...         result = func(*args, **kwargs)
...         print('Output of %s is %s' % (func.__name__, result))
...         return result
...     return decorated
...
>>> @withprint
... def add(x, y):
...    "Add inputs x and y together"
...    return x + y
...
>>> print(add.__doc__)  # Note that it does *NOT* mention decoration
Add inputs x and y together
>>> @withdoc(withprint)
... def combine(x, y):
...    "Add inputs x and y together"
...    return x + y
...
>>> print(combine.__doc__)  # Note that it *DOES* mention decoration
Add inputs x and y together
-------
Wrapped by decorator withprint:
withprint decorates a function to print result after running it.

    """
    @functools.wraps(decorator)
    def dec_with_doc(func):
        "Create decorator with doc."
        fix_doc(func, decorator)
        return decorator(func)
    return dec_with_doc


def fix_doc(func, decorator):
    """Fix a decorated function with docs about its decorator

    :param func:        Decorated function.

    :param decorator:   The decorator that decorated func.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    PURPOSE:   Modify func.__doc__ to describe the decorator.
               You can use the `fix_doc` function to make sure your
               decorator fixes docs of a decorated function when writing
               your own decorators as illustrated below.

   SEE ALSO:   See also the `withdoc` which can apply this to existing
               decorators.

>>> import ox_decs, functools
>>> def withfun(func):  # Write a decorator to illustrate how to use fix_doc
...     "Print how fun a function was after calling it."
...     @functools.wraps(func)
...     def decorated(*args, **kwargs):
...         "Function with fun"
...         result = func(*args, **kwargs)
...         name = getattr(func, '__name__', '(unknown)')
...         print('Calling %s was fun!' % name)
...         return result
...     ox_decs.fix_doc(decorated, withfun)
...     return decorated
...
>>> @withfun
... def add(x, y):
...     "Add x and y together."
...     return x + y
...
>>> print(add.__doc__)
Add x and y together.
-------
Wrapped by decorator withfun:
Print how fun a function was after calling it.

    """
    if not func.__doc__:
        func.__doc__ = 'Function %s' % func.__name__
    extra = '\n-------\nWrapped by decorator %s' % getattr(
        decorator, '__name__', '(unknown)')
    if decorator.__doc__:
        extra += ':\n%s' % decorator.__doc__
    func.__wrapdoc__ = extra
    func.__doc__ += extra
    return func


def withlog(func, logfunc=logging.info):
    "Decorate function to log output and illustrate using fix_doc."

    @functools.wraps(func)
    def decorated(*args, **kwargs):
        "Function with logging"
        result = func(*args, **kwargs)
        name = getattr(func, '__name__', '(unknown)')
        logfunc('Calling %s gives:\n%s\n', name, result)
        return result
    # To make sure that our decorated function updates docstrings of the
    # decorated function, we call fix_doc below. Note that fix_doc references
    # name of the decorator itself.
    fix_doc(decorated, withlog)

    return decorated


def withtime(func, logfunc=logging.info):
    "Decorate function to show run time after calling."

    @functools.wraps(func)
    def decorated(*args, **kwargs):
        "Function with time"
        start = time.time()
        result = func(*args, **kwargs)
        secs = time.time() - start
        name = getattr(func, '__name__', '(unknown)')
        logfunc('Calling %s took %.3f seconds' % (name, secs))
        return result
    return decorated


def composed(*decs):
    """Decorator to compose other decorators together.

>>> import functools
>>> from ox_decs import withdoc, composed, withlog, withtime
>>> def withprint(func):
...     "withprint decorates a function to print result after running it."
...     @functools.wraps(func)
...     def decorated(*args, **kwargs):
...         result = func(*args, **kwargs)
...         print('Output of %s is %s' % (func.__name__, result))
...         return result
...     return decorated
...
>>> @composed(withprint, withlog, withtime)
... def combine(x, y):
...    "Add inputs x and y together"
...    return x + y
...
>>> print(combine.__doc__)  # Note that it *DOES* mention decoration
Add inputs x and y together
-------
Wrapped by decorator withtime:
Decorate function to show run time after calling.
-------
Wrapped by decorator withlog:
Decorate function to log output and illustrate using fix_doc.
-------
Wrapped by decorator withprint:
withprint decorates a function to print result after running it.

    """
    def deco(func):
        "Composed decorator (decorator 0 applied first)"
        for dec in reversed(decs):
            orig = func
            func = dec(func)
            if orig.__doc__ == func.__doc__:
                fix_doc(func, dec)
        return func
    return deco


if __name__ == '__main__':
    doctest.testmod()
    print('Finished tests')
