"""Module to represent basic settings for ox_herd package.
"""

import os

# Path to your ox herd configuration file.
OX_HERD_CONF = os.environ.get('OX_HERD_CONF', os.path.join(
    os.environ.get('HOME', ''), '.ox_herd_conf'))

# Stub user database used only for testing stand alone ox_herd.
# You can either manually configure this to have keys as usernames
# and password hashes created according to the following:
#
# >>> from passlib.apps import custom_app_context as pwd_context
# >>> hash = pwd_context.hash("somepass")
#
# or provide a [STUB_USER_DB] section in OX_HERD_CONF with username
# as keys and password hashes as values
#
#                       WARNING!
#
# If you really want security, you will also need to setup SSL.
# You should probably setup SSL and some better password security
# in your app and just use ox_herd as a Flask blueprint to inherit
# proper security instead of using the login stub but it is there for
# ease of testing and local use.
STUB_USER_DB = {}

# Space separated list of queue names to show in showing scheduled tests.
# Can be changed by your own software after importing settings if you like.
# First element will be the default queue to use.
QUEUE_NAMES = 'default'

# Optional pair representing mode and string path to where we store
# database tracking job execution. Default mode is ('redis', None)
# to just use redis. You can also use 'sqlite' with
# either a path to the sqliet db or None to use a default path.
RUN_DB = ('redis', None)

# Prefix to use in things we store on redis queue for ox_herd.
REDIS_PREFIX = 'ox_herd:'

# List of names of plugins to enable. Each "name" is a string which
# can be used in a python import statement. By default we enable the
# pytest_plugin provided with ox_herd as an example.
# See ox_herd/core/plugins.py for description of how plugins work.
OX_PLUGINS = [
    'ox_herd.core.plugins.pytest_plugin',
    'ox_herd.core.plugins.pylint_plugin',
    'ox_herd.core.plugins.example_psutil_plugin',
    ]
