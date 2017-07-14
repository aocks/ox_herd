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
import hmac

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

    @classmethod
    def make_task_from_request(cls, request):
        """Make an instance of this task from a web request.
        
        :arg request:    Web request in json format (e.g., from GitHub webhook)
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:       Instance of cls designed to execute a test based
                        on information from webhook.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:   Create instance of cls based on a hit to the ox_herd/pytest
                   endpoint (which must be of type application/json). This
                   does things like validate the HMAC from github, pull out
                   the payload from the request, and configure the task.
                   After that you can call launch_raw_task on the returned
                   value if you have an OxScheduler object.
        
        """
        payload = json.loads(request.data.decode('utf8'))
        my_pr = payload['pull_request']
        my_conf = cls._get_config_info(my_pr)
        cls._validate_request(request, my_conf['secret'])
        sha = my_pr['head']['sha']
        name = 'github_pr_pytest_%s_%s' % (sha[:10], my_pr['updated_at'])
        task = RunPyTest(
            name=name, url=payload['repository']['ssh_url'], 
            pytest_cmd='--doctest-modules',
            github_info=my_pr)

        return task

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
        # Create a temporary directory with a context manager so that we
        # can safely use it inside the call and be confident it will get
        # cleaned up properly.
        with tempfile.TemporaryDirectory(suffix='.ox_pytest') as my_tmp_dir:
            url, cmd_line = cls.do_test(ox_herd_task, test_file, my_tmp_dir)
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
    def do_test(py_test_args, test_file, my_tmp_dir):
        pta = py_test_args.pytest_cmd
        if isinstance(pta, str):
            pta = shlex.split(pta)
        url = urllib.parse.urlparse(py_test_args.url)
        if url.scheme == 'file':
            cmd_line = [url.path, '--json', test_file, '-v'] + pta
        elif url.scheme == '' and url.path[:15] == 'git@github.com:':
            # If you are using github, then we need gitpython so import it
            # here so non-github users do not need it
            from git import Repo
            my_repo = Repo.clone_from(url.path, my_tmp_dir)
            if py_test_args.github_info:
                my_repo.git.checkout(py_test_args.github_info['head']['sha'])
            cmd_line = [my_tmp_dir, '--json', test_file, '-v'] + pta
        else:
            raise ValueError('URL scheme/path = "%s/%s" not handled yet.' % (
                url.scheme, url.path))
        logging.info('Running pytest with command arguments of: %s',
                     str(cmd_line))
        pytest.main(cmd_line)
        return url, cmd_line


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
        my_conf = cls._get_config_info(ox_herd_task.github_info)
        cthread = cls._prep_comment_thread(ox_herd_task, my_conf)
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
    def _get_config_info(github_info):
        """Get configuration info from OX_HERD_CONF file based on github_info.
        
        :arg github_info:    Dictionary with data about github repo.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:   A dictionary from configparser.ConfigParser pulled out of
                    OX_HERD_CONF file based on the repo in github.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:    Figure out which repo we are dealing with and extract
                    configuration from OX_HERD_CONF.
        
        """
        config_file = os.environ.get('OX_HERD_CONF', os.path.join(
            os.environ.get('HOME', ''), '.ox_herd_conf'))
        my_config = configparser.ConfigParser()
        my_config.read(config_file)
        owner, repo = github_info['head']['repo']['full_name'].split('/')
        section = 'pytest/%s/%s' % (owner, repo) 
        if section in my_config:
            my_data = my_config[section]
        else:
            my_data = my_config['pytest/DEFAULT']

        return my_data

    @staticmethod
    def _validate_request(request, secret):
        """Validate github signature on request.
        
        :arg request:   Web request of type application/json
        
        :arg secret:    Secret used for HMAC.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:  Verify the HMAC or raise ValueError.
        
        """
        header_signature = request.headers.get('X-Hub-Signature')
        if header_signature is None:
            raise ValueError(
                'No header signature provided to validate request')

        sha_name, signature = header_signature.split('=')
        if sha_name != 'sha1':
            raise ValueError('Header signature "%s" not supported.' % sha_name)
            
        request_data = request.data
        mac = hmac.new(bytes(secret, 'utf8'), request_data, digestmod='sha1')
        if not str(mac.hexdigest()) == str(signature):
            raise ValueError('Request digest does not match signature %s' % (
                str(signature)))


    @staticmethod
    def _prep_comment_thread(ox_herd_task, my_conf):
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
        user = my_conf['github_user']
        token = my_conf['github_token']
        topic = my_conf['github_issue'] if 'github_issue' in my_conf else None

        if topic is None:
            topic = ox_herd_task.github_info['title']
            thread_id = ox_herd_task.github_info['number']
        else:
            thread_id = None

        owner, repo = ox_herd_task.github_info['head']['repo'][
            'full_name'].split('/')

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

