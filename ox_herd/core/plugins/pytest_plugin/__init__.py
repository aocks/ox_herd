"""Provides pytest plugin for ox_herd.
"""

import logging
import tempfile
import json

from flask import Blueprint, request
from ox_herd.core.plugins.pytest_plugin.core import (
    OxHerdPyTestPlugin, RunPyTest)
from ox_herd.core.scheduling import OxScheduler

OH_BP = Blueprint('pytest_plugin', __name__, template_folder='templates')
OxHerdPyTestPlugin.set_bp(OH_BP)

@OH_BP.route('/ox_herd/pytest', methods=['GET', 'POST'])
def pytest():
    """Route for launching pytest directly.
    """
    try:
        logging.error('FIXME: got pytest request %s', '\n'.join(
            map(str, request.form.items())))
        event = request.headers['X-Github-Event']
        if event != 'pull_request':
            # Only process pull_request.
            logging.error('FIXME: skipping event %s', event)
            return 'skipped'
        if event == 'issue_comment':
            raise ValueError('Triggering on issue_comment can cause inf loop')
        payload = json.loads(request.form['payload'])
        my_dir = tempfile.mkdtemp(suffix='.git')
        from git import Repo
        my_repo = Repo.clone_from(payload['repository']['ssh_url'], my_dir)
        my_pr = payload['pull_request']
        sha = my_pr['head']['sha']                
        my_repo.git.checkout(sha)
        name = 'github_pr_pytest_%s_%s' % (sha[:10], my_pr['updated_at'])
        task = RunPyTest(
            name=name, url='file://%s' % my_dir, 
            pytest_cmd='--doctest-modules',
            github_info=my_pr)
        my_job = OxScheduler.launch_raw_task(task)
        logging.error('FIXME: scheduled task %s as job %s', str(task), my_job)
    except Exception as problem:
        logging.error('drop to pdb because: %s', str(problem))
        raise
    return 'FIXME: launched pytest'    

def get_ox_plugin():
    """Required function for module to provide plugin.
    """
    return OxHerdPyTestPlugin()


