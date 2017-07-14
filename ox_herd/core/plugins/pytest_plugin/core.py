"""Module containing some plugin to run pytest.
"""

import configparser
import logging
import os
import tempfile
import json
import shlex
import urllib
import urllib.parse
import urllib.request

import jinja2

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

    def __init__(self, *args, url=None, pytest_cmd=None, json_file=None, 
                 github_info=None, **kw):
        """Initializer.
        
        :arg *args:    Argumnets to OxHerdTask.__init__.

        :arg url:      URL representing where to run pytest on.  
        
        :arg pytest_cmd: String with command line arguments for running pytest.
        
        :arg json_file=None:   Optional path for where to store json_file
                               with test results. Usually better to leave this
                               as None indicating to just use a temp file.
                               Sometimes can be useful for testing.

        :arg github_info=None: Optional json object containing info about
                               github repo and issue to post comment to.

        :arg **kw:     Keyword arguments to OxHerdTask.__init__.
        
        """
        OxHerdTask.__init__(self, *args, **kw)
        self.pytest_cmd = pytest_cmd
        self.json_file = json_file
        self.url = url
        self.github_info = github_info

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

        cls.post_results_to_github(ox_herd_task, test_data)
            
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

    @classmethod
    def post_results_to_github(cls, ox_herd_task, test_data):
        """Helper method to post test results to github.
        
        :arg ox_herd_task:   The Ox Herd task containing data.
        
        :arg test_data:      A dictionary containing the result of running
                             tests as produced by make_report.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:  If he user has his .ox_herd_conf file setup to include
                  a [pytest/DEFAULT] section (or a section like
                  [pytest/owner/repo]) with a github_user and 
                  github_token with access to the repo in
                  ox_herd_task.github_info, then we will try
                  to post the results of the test as a comment in
                  a github issue.

                  This is a key feature in using this plugin for
                  continuous integration with github.
        """        
        if not ox_herd_task.github_info:
            return
        grepo = ox_herd_task.github_info['head']['repo']['full_name']
        grepo = grepo.strip()
        sha = ox_herd_task.github_info['head']['sha']        
        tmsg = 'Testing commit %s' % sha
        cthread = cls._prep_comment_thread(ox_herd_task)
        msg = ('%s\n\nTested %s:\n' % (tmsg, grepo)) + ', '.join(['%s=%s' % (
                name, test_data['summary'].get(
                    name, '0' if name == 'failed' else 'unknown')
                ) for name in ['failed', 'passed', 'duration']])
        failures = []
        for item in test_data['tests']:
            if item['outcome'] == 'failed':
                failures.append(item['name'])
        if failures:
            msg += '\n\n' + jinja2.Environment(loader=jinja2.FileSystemLoader(
                os.path.dirname(forms.__file__).rstrip(
                    '/') + '/templates/')).get_template(
                        'py_test_failures.html').render(
                            test_list=test_data['tests'])

        cthread.add_comment(msg, allow_create=True)

    @staticmethod
    def _prep_comment_thread(ox_herd_task):
        """Prepare a CommentThread object to use in positing comments.
        
        :arg ox_herd_task: Ox Herd task with raw data.       
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:  A GitHubCommentThread object.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:   This method reads from the OX_HERD_CONF file,
                   figures out the github parameters, and creates a
                   GitHubCommentThread we can use in posting
                   comments.
        """
        config_file = os.environ.get('OX_HERD_CONF', os.path.join(
            os.environ.get('HOME', ''), '.ox_herd_conf'))
        my_config = configparser.ConfigParser()
        my_config.read(config_file)
        owner, repo = ox_herd_task.github_info['head']['repo'][
            'full_name'].split('/')
        section = 'pytest/%s/%s' % (owner, repo) 
        if section in my_config:
            my_data = my_config[section]
        else:
            my_data = my_config['pytest/DEFAULT']
        user = my_data['github_user']
        token = my_data['github_token']
        topic = my_data['github_issue'] if 'github_issue' in my_data else None
        if topic is None:
            topic = ox_herd_task.github_info['title']
            thread_id = ox_herd_task.github_info['number']
        else:
            thread_id = None

        # FIXME: We need to handle the dependeancy on flask_yap more
        # FIXME: gracefully. Maybe make flask_yap installable via pip?
        # FIXME: For now, just import it here so if people are not using
        # FIXME: this feature it will not break.
        from flask_yap.core import github_comments

        comment_thread = github_comments.GitHubCommentThread(
            owner, repo, topic, user, token, thread_id=thread_id)

        return comment_thread        

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

