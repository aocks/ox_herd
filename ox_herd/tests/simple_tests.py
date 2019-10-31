"""This module contains some simple tests for ox_herd.
"""

import doctest


def _regr_test_web_task():
    """Test basic stuff in web tasks.

>>> from ox_herd.ui.flask_web_ui.ox_herd import web_tasks
>>> class ExampleTask(web_tasks.SimpleWebTask):
...     'Example task to test a few basic things'
...     # Note that we want to test that special port handled right.
...     @classmethod
...     def make_base_url(cls):
...         'example with built-in port'
...         return 'https://foo:999'
...
>>> e = ExampleTask()
>>> e.make_url('somepath')  # verify things work if we exclude leading /
'https://foo:999/somepath'
>>> e.make_url('/somepath') # verify things work if we include leading /
'https://foo:999/somepath'
    """


if __name__ == '__main__':
    doctest.testmod()
    print('Finished Tests')
