"""Module containing some plugin to run pytest.
"""

import configparser
import logging
import os
import tempfile
import json
import subprocess
import shlex
import urllib
import urllib.parse
import urllib.request
import hmac

import jinja2

import xmltodict
import yaml


from ox_herd import settings as ox_herd_settings
from ox_herd.core.plugins import base
from ox_herd.core.ox_tasks import OxHerdTask
from ox_herd.core.plugins.pytest_plugin import forms
from ox_herd.core.plugins import post_to_github_plugin

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

    def __init__(self, *args, url=None, pytest_cmd=None, xml_file=None,
                 github_info=None, **kw):
        """Initializer.

        :arg *args:    Argumnets to OxHerdTask.__init__.

        :arg url:      URL representing where to run pytest on.

        :arg pytest_cmd: String with command line arguments for running pytest.

        :arg xml_file=None:   Optional path for where to store xml_file
                              with test results. Usually better to leave this
                              as None indicating to just use a temp file.
                              Sometimes can be useful for testing.

        :arg github_info=None: Optional json object containing info about
                               github repo and issue to post comment to.

        :arg **kw:     Keyword arguments to OxHerdTask.__init__.

        """
        OxHerdTask.__init__(self, *args, **kw)
        self.pytest_cmd = pytest_cmd
        self.xml_file = xml_file
        self.url = url
        self.github_info = github_info

    @classmethod
    def make_task_from_request(cls, request, pull_url_type='html'):
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
        my_conf, dummy_my_sec = cls._get_config_info(my_pr)
        cls._validate_request(request, my_conf['github_secret'])
        sha = my_pr['head']['sha']
        name = 'github_pr_pytest_%s_%s' % (sha[:10], my_pr['updated_at'])
        task = RunPyTest(
            name=name, url=payload['repository']['%s_url' % pull_url_type],
            pytest_cmd='--doctest-modules', timeout=3000, 
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
        test_file = ox_herd_task.xml_file if ox_herd_task.xml_file else (
            tempfile.mktemp(suffix='.xml'))
        # Create a temporary directory with a context manager so that we
        # can safely use it inside the call and be confident it will get
        # cleaned up properly.
        with tempfile.TemporaryDirectory(suffix='.ox_pytest') as my_tmp_dir:
            url, cmd_line = cls.do_test(ox_herd_task, test_file, my_tmp_dir)
            test_data = cls.make_report(ox_herd_task, test_file, url, cmd_line)
            if not ox_herd_task.xml_file:
                logging.debug('Removing temporary xml report %s', test_file)
                os.remove(test_file) # remove temp file

            cls.post_results_to_github(ox_herd_task, test_data)

        rval = test_data['summary']

        return {'return_value' : rval, 'json_blob' : test_data}

    @classmethod
    def do_test(cls, py_test_args, test_file, my_tmp_dir):
        # Will force PYTHONPATH into my_env to ensure we test the
        # right thing
        my_env = os.environ.copy()
        pta = py_test_args.pytest_cmd
        clone_path = None
        if isinstance(pta, str):
            pta = shlex.split(pta)
        pta.append('--boxed')
        url = urllib.parse.urlparse(py_test_args.url)
        if url.scheme == 'file':
            cmd_line = [url.path, '--junitxml', test_file, '-v'] + pta
            my_env['PYTHONPATH'] = url.path
        elif url.scheme == '' and url.path[:15] == 'git@github.com:':
            clone_path = url.path
        elif url.scheme == 'https':
            my_conf, dummy_sec = cls._get_config_info(py_test_args.github_info)
            if 'github_token' in my_conf:
                clone_path = 'https://%s@%s%s' % (my_conf[
                    'github_token'], url.netloc, url.path)
            else:
                clone_path = url.geturl()
        else:
            raise ValueError('URL scheme/path = "%s/%s" not handled yet.' % (
                url.scheme, url.path))
        if clone_path:
            cls.prep_git_clone(py_test_args, clone_path, my_tmp_dir, my_env)
            cmd_line = [my_tmp_dir, '--junitxml', test_file, '-v'] + pta

        logging.info('Running pytest on %s with command arguments of: %s',
                     my_tmp_dir, str(cmd_line))
        subprocess.call(['py.test'] + cmd_line, env=my_env)
        return url, cmd_line

    @classmethod
    def prep_git_clone(cls, py_test_args, clone_path, my_tmp_dir, my_env):
        # If you are using github, then we need gitpython so import it
        # here so non-github users do not need it
        from git import Repo
        if py_test_args.github_info:
            sha = py_test_args.github_info['head']['sha']
            repo_name = py_test_args.github_info['head']['repo']['name']
        else:
            sha, repo_name = None, os.path.split(
                clone_path)[-1].split('.git')[0]
        my_repo = Repo.clone_from(clone_path, my_tmp_dir + '/' + repo_name)
        if sha is not None:
            my_repo.git.checkout(py_test_args.github_info['head']['sha'])
        new_repo = os.path.join(my_tmp_dir, repo_name)
        my_env['PYTHONPATH'] = '%s:%s' % (new_repo, my_tmp_dir)
        yaml_file = os.path.join(new_repo, 'ox_herd_test.yaml')
        if os.path.exists(yaml_file):
            yconfig = yaml.safe_load(open(yaml_file).read())
            my_env['PYTHONPATH'] = ':'.join([name for name in yconfig.pop(
                'prepend_pypaths', [])] + [my_env['PYTHONPATH']])
            for gname, gpath in yconfig.pop('git_clones', {}).items():
                Repo.clone_from(gpath, os.path.join(my_tmp_dir, gname))
            if yconfig:
                logging.warning('Unprocessed items in yaml file: %s', str(
                    yconfig))


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
        my_conf, dummy_sec = cls._get_config_info(ox_herd_task.github_info)
        msg = '%s\n\nTested %s:\n%s\n' % (tmsg, grepo, test_data['summary'])
        failures = int(test_data['testsuite']['@errors']) + int(
            test_data['testsuite']['@failures'])
        if failures:
            msg += '\n\n' + jinja2.Environment(loader=jinja2.FileSystemLoader(
                os.path.dirname(forms.__file__).rstrip(
                    '/') + '/templates/')).get_template(
                        'py_test_failures.html').render(
                            test_list=test_data['tests'])

        if 'github_issue' in my_conf:
            title = my_conf['github_issue']
            number = None
        else:
            title = ox_herd_task.github_info['title']
            number = ox_herd_task.github_info['number']

        full_repo = ox_herd_task.github_info['head']['repo']['full_name']

        cthread = post_to_github_plugin.PostToGitHub.prep_comment_thread(
            title, number, full_repo, my_conf)
        cthread.add_comment(msg, allow_create=True)

    @classmethod
    def _get_config_info(cls, github_info):
        """Get configuration info from OX_HERD_CONF file based on github_info.

        :arg github_info:    Dictionary with data about github repo or None
                             to use section pytest/DEFAULT

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :returns:   A dictionary from configparser.ConfigParser pulled out of
                    OX_HERD_CONF file based on the repo in github.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:    Figure out which repo we are dealing with and extract
                    configuration from OX_HERD_CONF.

        """
        config_file = cls.get_conf_file()
        my_config = configparser.ConfigParser()
        my_config.read(config_file)
        if github_info:
            owner, repo = github_info['head']['repo']['full_name'].split('/')
            section = 'pytest/%s/%s' % (owner, repo)
        else:
            section = None
        if section is not None and section in my_config:
            my_sec = section
        else:
            my_sec = 'pytest/DEFAULT'

        my_data = my_config[my_sec]

        return my_data, my_sec

    @staticmethod
    def get_conf_file():
        "Helper to deduce config file."

        return ox_herd_settings.OX_HERD_CONF


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
    def make_report(my_task, test_file, url, cmd_line):
        test_data = xmltodict.parse(open(test_file, 'rb').read(),
                                    xml_attribs=True)
        test_data['url'] = url
        test_data['cmd_line'] = cmd_line
        test_data['task_name'] = my_task.name
        summary_fields = ['errors', 'failures', 'skips', 'tests', 'time']
        test_data['summary'] = 'Test resultls: ' + ', '.join([
            '%s: %s' % (name, test_data['testsuite']['@' + name])
            for name in summary_fields])
        test_data['tests'] = test_data['testsuite']['testcase']

        return test_data

    def get_ox_task_cls(self):
        return self.__class__

    def get_flask_form(self):
        return forms.SchedJobForm

    @classmethod
    def make_push_warn_task(cls, request, warnables=('refs/heads/master',)):
        """Helper to make a task to warn about direct pushes to master.

        :arg request:    The web request from a github webhook.

        :arg warnables=('refs/heads/master',):  Tuple of strings to warn about.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :returns:  An instance of the PostToGitHub class that when run
                   will post a message to github warning about pushing
                   directly to master.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:   Support continuous integration via pull requests by
                   creating a task that will warn about direct pushes to
                   master. This is intended to be called by the pytest
                   route if a push event is seen.

        """
        payload = json.loads(request.data.decode('utf8'))
        cname = payload.get('head_commit', {}).get('committer', {}).get(
            'name', {})
        if cname == 'GitHub':  # This was a pull request merge so return None
            return None
        gh_info = {'head': {'repo': payload['repository']},
                   'title': 'push_warning', 'number': None}
        my_conf, my_sec = cls._get_config_info(gh_info)
        if payload['ref'] not in warnables:
            logging.debug('Pushing to %s not %s so not warning on push',
                          payload['ref'], str(warnables))
            return None

        full_repo = payload['repository']['full_name']
        title = 'warning_push'
        cls._validate_request(request, my_conf['github_secret'])
        msg = 'Warning: %s pushed to %s on %s' % (
            payload['sender']['login'], payload['ref'], full_repo)

        task = post_to_github_plugin.PostToGitHub(
            msg, full_repo, title, None, cls.get_conf_file(), my_sec,
            name='github_posting')

        return task
