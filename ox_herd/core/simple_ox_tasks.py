"""Module containing some simple sub-classes of OxHerdTask to illustate usage.
"""

import logging
import os
import tempfile
import json
import doctest
import shlex
import urllib
import urllib.parse
import urllib.request
import re

try:
    import pytest
except ImportError as problem:
    logging.error('Unable to import pytest because:%s\n%s.',
                  str(problem), "won't be able to use RunPyTest.")


from ox_herd.core.ox_tasks import OxHerdTask

class RunPyTest(OxHerdTask):

    def __init__(self, *args, url=None, pytest_cmd=None, json_file=None, **kw):
        """Initializer.
        
        :arg *args:    Argumnets to OxHerdTask.__init__.

        :arg url:      URL representing where to run pytest on.  
        
        :arg pytest_cmd: String with command line arguments for running pytest.
        
        :arg json_file=None:   Optional path for where to store json_file
                               with test results. Usually better to leave this
                               as None indicating to just use a temp file.
                               Sometimes can be useful for testing.
        
        :arg **kw:     Keyword arguments to OxHerdTask.__init__.
        
        """
        OxHerdTask.__init__(self, *args, **kw)
        self.pytest_cmd = pytest_cmd
        self.json_file = json_file
        self.url = url

    @staticmethod
    def get_template_name():
        "Override to use custom template to report py test results."

        return 'py_test_report.html'

    @classmethod
    def main_call(cls, ox_herd_task):
        test_file = ox_herd_task.json_file if ox_herd_task.json_file else (
            tempfile.mktemp(suffix='.json'))
        url, cmd_line = cls.do_test(ox_herd_task, test_file)
        test_data = cls.make_report(ox_herd_task, test_file, url, cmd_line)
        if not ox_herd_task.json_file:
            logging.debug('Removing temporary json report %s', test_file)
            os.remove(test_file) # remove temp file

        rval = 'completed test: ' + ', '.join(['%s=%s' % (name, test_data[
            'summary'].get(
                name, '0' if name == 'failed' else 'unknown')) for name in [
                    'failed', 'passed', 'duration']])
        return {'return_value' : rval, 'json_blob' : test_data}

    @staticmethod
    def do_test(py_test_args, test_file):
        url = urllib.parse.urlparse(py_test_args.url)
        if url.scheme == 'file':
            cmd_line = [url.path, '--json', test_file, '-v']
            pta = py_test_args.pytest_cmd
            if isinstance(pta, str):
                pta = shlex.split(pta)
            cmd_line.extend(pta)
            logging.info('Running pytest with command arguments of: %s',
                         str(cmd_line))
            pytest.main(cmd_line)
            return url, cmd_line
        else:
            raise ValueError('URL scheme of %s not handled yet.' % url.scheme)

    @staticmethod
    def make_report(my_task, test_json, url, cmd_line):
        test_data = json.load(open(test_json))['report']
        test_data['url'] = url
        test_data['cmd_line'] = cmd_line
        test_data['task_name'] = my_task.name

        return test_data

class ScanSite(OxHerdTask):

    def __init__(self, *args, url=None, regexp='.', encoding='utf-8', 
                 show_len=60, **kw):
        """Initializer.
        
        :arg *args:      Argumnets to OxHerdTask.__init__.

        :arg url:        URL representing where to run.
        
        :arg regexp='.': String regular expression to scan for.

        :arg encoding='utf-8':  Expected encoding of URL data.

        :arg show_len=60:  Maxium length of regexp hit to show in return val.
        
        :arg **kw:       Keyword arguments to OxHerdTask.__init__.
        
        """
        OxHerdTask.__init__(self, *args, **kw)
        self.url = url
        self.regexp = regexp
        self.encoding = encoding
        self.show_len = show_len

    @staticmethod
    def main_call(ox_herd_task):
        my_re = re.compile(ox_herd_task.regexp)
        with urllib.request.urlopen(ox_herd_task.url) as response:
            data = response.read()
            clean = data.decode(ox_herd_task.encoding, errors='ignore')
            match = my_re.search(clean)
            if match:
                result = clean[match.start():match.end()]
                msg = 'Task %s found a match (first %i chars shown):\n%s' % (
                    ox_herd_task.name, ox_herd_task.show_len, 
                    result[:ox_herd_task.show_len])
                #ox_herd_task.send_message(msg)#FIXME
                return msg

        return 'No match found for task %s' % (ox_herd_task.name)

    @staticmethod
    def _regr_test():
        """Simple test to show how task would work.

The following illustrates a simple test of how this task would work.
This is mainly a test of the ox_run_db and other infrastructure since
it does not directly use python rq.

>>> from ox_herd.core import simple_ox_tasks, ox_run_db
>>> import os, json, tempfile, datetime, time, random, imp, logging
>>> random_key = random.randint(0,10000000) # so tests do not collide
>>> print('Using random_key = %s' % str(random_key)) # doctest: +ELLIPSIS
Using random_key = ...
>>> logging.info('Switching to random test redis prefix to be isolated.')
>>> ox_run_db.ox_settings.REDIS_PREFIX += ('test_%s' % random_key)
>>> task = simple_ox_tasks.ScanSite(
...     'test_scan', url='http://google.com', regexp='[Gg]oogle')
>>> logging.info('Simulate what ox_herd would do in running the task:')
>>> task.run_ox_task(task)
>>> my_redis = ox_run_db.redis.StrictRedis()
>>> keys = my_redis.keys(ox_run_db.ox_settings.REDIS_PREFIX+'*')
>>> len(keys)
1
>>> task_json = my_redis.get(keys[0])
>>> info = json.loads(task_json.decode('utf8'))
>>> print('%s : %s : %s' % (
...     info['task_name'], info['task_status'], info['return_value']))
test_scan : finished : Task test_scan found a match (first 60 chars shown):
Google
>>> my_redis.delete(keys[0])
1
>>> my_redis.keys(ox_run_db.ox_settings.REDIS_PREFIX+'*')
[]
        """

if __name__ == '__main__':
    doctest.testmod()
    print('Tests finished.')