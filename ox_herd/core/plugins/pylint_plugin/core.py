"""Module containing some plugin to run pylint.
"""

import re
import datetime
import io
import logging
import os
import urllib
import urllib.parse
import urllib.request

from pylint import lint
from pylint.reporters.text import ParseableTextReporter

from ox_herd.core.plugins import base
from ox_herd.core.ox_tasks import OxHerdTask
from ox_herd.core.plugins.pylint_plugin import forms


class OxHerdPyLintPlugin(base.OxPlugin):
    """Plugin to provide pylint services for ox_herd
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

        return 'pylint_plugin'

    def description(self):
        """Implement as required by OxPlugin."""

        return "Plugin to provide pylint services for ox_herd."

    def get_components(self):
        return [RunPyLint('plugin component')]

def make_kill_regexps():
    """Make dictionary identifying regular expressions to remove from output.

    Some of the checkers provide results that confuse pylint. So we remove
    those.
    """
    result = {
        'long_dash': r'^-+ *',
        'pylint_rating' : '^[Yy]our code has been rated.*$'
    }
    return result


class RunPyLint(OxHerdTask, base.OxPluginComponent):
    """Run pylint to analyze code quality
    """

    def __init__(self, *args, url=None, **kw):
        """Initializer.
        
        :arg *args:    Argumnets to OxHerdTask.__init__.

        :arg url:      URL representing where to run pylint on.  
        
        :arg **kw:     Keyword arguments to OxHerdTask.__init__.
        
        """
        OxHerdTask.__init__(self, *args, **kw)
        self.url = url

    @staticmethod
    def cmd_name():
        """Provide name as required by OxPluginComponent.
        """
        return 'pylint'

    @staticmethod
    def get_template_name():
        "Override to use custom template to report py lint results."

        return 'py_lint_report.html'

    @staticmethod
    def run_pylint(filename):
        """Run pylint on the given file.
        """
        args = ["-r","n"]
        pylint_output = io.StringIO()
        lint.Run([filename]+args, 
                 reporter=ParseableTextReporter(pylint_output), exit=False)
        pylint_output.seek(0)
        result = pylint_output.read()
        kill_regexps = make_kill_regexps()
        for re_name, my_re in kill_regexps.items():
            logging.debug('Cleaning output with re %s', re_name)
            result = re.sub(my_re, '', result, flags=re.M)
        return result

    @classmethod
    def main_call(cls, ox_herd_task):
        results = cls.do_lint(ox_herd_task)
        rval = 'completed lint: ' + ', '.join(['%s=%s' % (
            name, results['summary'][name]) for name in [
                'passed', 'issues', 'failures']])
        return {'return_value' : rval, 'json_blob' : results}

    @staticmethod
    def lint_results_to_dict(lint_output):
        """Take string output of lint command and return dictionary summary.
        """
        data = [line for line in lint_output.split('\n') if (
            line and line.strip() and line[:10] != ('*'*10))]
        if not data:
            return {'outcome' : 'success'}
        result = {'outcome' : 'issues', 'count' : len(data), 
                  'issues' : [line.split(':') for line in data]}
        return result

    @classmethod
    def do_lint(cls, py_lint_args):
        """Do pylint on desired URL.
        
        :arg py_lint_args:   Instance of class with arguments.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:       A list of dicts intended to be serialized into
                        JSON format outlining the results of the pylint run.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:        Analyze code quality.
        
        """
        results = {'lints' : [], 'created_at' : str(datetime.datetime.utcnow()),
                   'task_name' : py_lint_args.name, 'url' : py_lint_args.url}
        url = urllib.parse.urlparse(py_lint_args.url)
        passed = 0
        issues = 0
        failures = 0
        if url.scheme == 'file':
            for root, dummy_dirs, files in os.walk(url.path):
                for my_file in files:
                    if my_file[-3:] == '.py':
                        my_file = os.path.join(root, my_file)
                        logging.info('Checking %s.', my_file)
                        my_result = {'file' : re.sub(
                            '^%s' % url.path, '', my_file).lstrip('/')}
                        try:
                            lint_results = cls.run_pylint(my_file)
                            my_result.update(cls.lint_results_to_dict(
                                lint_results))
                            if my_result['outcome'] == 'success':
                                passed += 1
                            else:
                                assert my_result['outcome'] == 'issues'
                                issues += 1
                        except Exception as bad: #pylint: disable=broad-except
                            failures += 1
                            my_result['outcome'] = 'failed'
                            my_result['longrepr'] = str(bad)
                        results['lints'].append(my_result)
            results['summary'] = {
                'issues' : issues, 'passed' : passed, 'failures' : failures}
            return results
        else:
            raise ValueError('URL scheme of %s not handled yet.' % url.scheme)

    def get_ox_task_cls(self):
        return self.__class__

    def get_flask_form(self):
        return forms.PylintForm

