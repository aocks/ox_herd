"""Utility functions to help in file caching.
"""

import os
import pickle

from ox_herd import file_cache

def get_path(name):
    """Get path for given file name.

    :arg name:     String file name we want a full path for.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    :returns:   Full path for given name inside file cache.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    PURPOSE:    When given a base filename, figure out the full path to
                that file in the file_cache. You can just pass in '' if
                you want the root directory of the file cache.

    """
    if not isinstance(name, str):
        raise TypeError('Name %s given to get_path must be a string not %s.' % (
            str(name), str(type(name))))
    if name[-3:].lower() == '.py':
        raise ValueError('Refusing to store python file %s in cache.' % (
            name))

    root = file_cache.__file__
    path = os.path.join(os.path.dirname(root), 'data', name)
    return path

def store_with_name(data, name, mode='wb', overwrite=False):
    path = get_path(name)
    if os.path.exists(path) and not overwrite:
        raise ValueError('Refusing to overwrite existing path %s.' % path)
    with open(path, mode) as fdesc:
        fdesc.write(data)

def pickle_with_name(data, name, mode='wb', *args, **kw):
    pdata = pickle.dumps(data)
    return store_with_name(pdata, name, mode, *args, **kw)

def unpickle_name(name):
    path = get_path(name)
    result = None
    with open(path, 'rb') as fdesc:
        result = pickle.loads(fdesc.read())

    return result
