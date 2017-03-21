"""Module containing some simple sub-classes of OxHerdJob.
"""

import logging
import os
import tempfile
import json
import datetime
import shlex
import urllib.parse

try:
    import pytest
except ImportError as problem:
    logging.error('Unable to import pytest because:%s\n%s.',
                  str(problem), "won't be able to use RunPyTest.")


from ox_herd.file_cache import cache_utils
from ox_herd.core.ox_jobs import OxHerdJob, OxHerdArgs

class RunPyTestArgs(OxHerdArgs):

    def __init__(self, *args, **kw):
        OxHerdArgs.__init__(self, *args, **kw)
        if self.special is None:
            raise ValueError('Must provide "special" args for RunPyTestArgs')

class RunPyTest(OxHerdJob):

    def main_call(self):
        pt_args = self.py_test_args
        test_file = pt_args.json_file if pt_args.json_file else (
            tempfile.mktemp(suffix='.json'))
        url, cmd_line = self.do_test(pt_args, test_file)
        test_data = self.make_report(pt_args, test_file, url, cmd_line)
        if not pt_args.json_file:
            logging.debug('Removing temporary json report %s', test_file)
            os.remove(test_file) # remove temp file

        result = 'completed test: ' + ', '.join(['%s=%s' % (name, test_data[
            'summary'].get(name, 'unknown')) for name in [
                'failed', 'passed', 'duration']])
        return result

    @staticmethod
    def do_test(py_test_args, test_file):
        url = urllib.parse.urlparse(py_test_args.url)
        if url.scheme == 'file':
            cmd_line = [url.path, '--json', test_file, '-v']
            pta = py_test_args.pytest
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
    def make_report(py_test_args, test_json, url, cmd_line):
        test_data = json.load(open(test_json))['report']
        test_data['url'] = url
        test_data['cmd_line'] = cmd_line
        test_time = datetime.datetime.strptime(
            test_data['created_at'].split('.')[0], '%Y-%m-%d %H:%M:%S')
        rep_name = py_test_args.name + test_time.strftime('_%Y%m%d_%H%M%S.pkl')
        cache_utils.pickle_with_name(test_data, 'test_results/%s' % rep_name)
        return test_data
