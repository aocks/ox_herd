"""Module containing some plugin to run pytest.
"""

import logging
import os
import tempfile
import json
import shlex
import urllib
import urllib.parse
import urllib.request

import pytest

from ox_herd.core.plugins import base
from ox_herd.core.ox_tasks import OxHerdTask
from ox_herd.core.plugins.pytest_plugin import forms

class OxHerdPyTestPlugin(base.OxPlugin):
    """Plugin to provide pytest services for ox_herd
    """

    __blueprint = None

    @classmethod
    def set_bp(cls, my_bp):
        cls.__blueprint = my_bp
    
    def get_flask_blueprint(self):
        """Implement as required by OxPlugin."""

        return self.__class__.get_bp()

    @classmethod
    def get_bp(cls):
        return cls.__blueprint
    

    def name(self):
        """Implement as required by OxPlugin."""

        return 'pytest_plugin'

    def description(self):
        """Implement as required by OxPlugin."""

        return "Plugin to provide pytest services for ox_herd."

    def get_components(self):
        return [RunPyTest('plugin component')]

class RunPyTest(OxHerdTask, base.OxPluginComponent):

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
    def cmd_name():
        """Provide name as required by OxPluginComponent.
        """
        return 'pytest'

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

    def get_ox_task_cls(self):
        return self.__class__

    def get_flask_form(self):
        return forms.SchedJobForm

