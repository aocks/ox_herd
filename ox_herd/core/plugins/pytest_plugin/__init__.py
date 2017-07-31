"""Provides pytest plugin for ox_herd.
"""

import logging

from flask import Blueprint, request
from ox_herd.core.plugins.pytest_plugin.core import (
    OxHerdPyTestPlugin, RunPyTest)
from ox_herd.core.scheduling import OxScheduler

OH_BP = Blueprint('pytest_plugin', __name__, template_folder='templates')
OxHerdPyTestPlugin.set_bp(OH_BP)


@OH_BP.route('/ox_herd/pytest', defaults={'pull_url_type': 'html'},
             methods=['GET', 'POST'])
@OH_BP.route('/ox_herd/pytest/<pull_url_type>', methods=['GET', 'POST'])
def pytest(pull_url_type='html'):
    """Route for launching pytest directly.

    This route is intended to be called by a github webhook to process
    pull requests. It uses information from the request to create an
    instance of RunPyTest and then launch that job immediately.
    """
    if request.headers['Content-Type'] != 'application/json':
        raise ValueError('Can only process application/json not %s=%s' % (
            'Content-Type', request.headers['Content-Type']))

    event = request.headers['X-Github-Event']
    if event == 'push':
        try:
            warn_task = RunPyTest.make_push_warn_task(request)
            if warn_task is not None:
                warn_job = OxScheduler.launch_raw_task(warn_task)
                msg = 'Launched warn_task %s as job %s' % (warn_task, warn_job)
                logging.debug(msg)
                return msg
        except Exception as prob:
            logging.error('Unable to make warn push task because %s', prob)
            raise

    if event != 'pull_request':
        # Only process pull_request.
        logging.debug('skipping github event %s', event)
        return 'skipped event %s' % str(event)
    if event == 'issue_comment':
        raise ValueError('Triggering on issue_comment can cause inf loop')

    try:
        task = RunPyTest.make_task_from_request(request, pull_url_type)
    except Exception as problem:
        logging.error('RunPyTest.make_task_from_request exception:\n%s\n',
                      problem)
        raise
    my_job = OxScheduler.launch_raw_task(task)
    msg = 'scheduled task from github %s as job %s' % (str(task), my_job)
    logging.debug(msg)

    return msg


def get_ox_plugin():
    """Required function for module to provide plugin.
    """
    return OxHerdPyTestPlugin()
