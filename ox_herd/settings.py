"""Module to represent basic settings for ox_herd package.
"""

# Stub user database used only for testing stand alone ox_herd.

STUB_USER_DB = {
    'test' : 'test_pw'
    }

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
