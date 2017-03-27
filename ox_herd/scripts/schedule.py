"""Script to schedule execution of tests automatically.
"""

import logging
import collections
import argparse

from ox_herd.core.scheduling import OxScheduler

def make_manager_choices():
    "Return dictionary of manager choices and docs."

    return collections.OrderedDict([
        ('rq', 'python-rq backend for automated background runs'),
        ('instant', 'Run instantly (useful for testing).'),
    ])

def prepare_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser()

    managers = make_manager_choices()
    parser.add_argument('--url', required=True, help=(
        'Location for package to test. This can be a github URL or a file\n'
        'location.'))
    parser.add_argument('--name', default='test_', help=(
        'String name for the job you are going to schedule.'))
    parser.add_argument('--manager', required=1, choices=list(managers), help=(
        'Backend manager for automated testing. Options include:\n  '
        + '\n  '.join([
            '%s : %s' % (name, docs) for name, docs in managers.items()])))
    parser.add_argument('--json_file', help=(
        'Optional path to json file for output of test run. Usually,\n'
        'you should not provide this and a temp file will be used\n'
        'and then deleted. If you do manually specify a path, then that\n'
        'path will be used and *NOT* deleted (which can be useful\n'
        'for debugging).'))
    parser.add_argument('--timeout', type=int, default=900, help=(
        'Timeout in seconds to allow for tasks.'))
    parser.add_argument('--cron_string', help=(
        'Cron format string for when to schedule the task.\n'
        'For example, "5 1 * * 3" would be every Wednesday at 1:05 am.\n'
        'This is used for --manager choices such as rq which support cron\n'
        'scheduling. NOTE: cron_string should have 5 fields. If you try to\n'
        'use the non-standard extended cron format with 6 fields, you may get\n'
        'unexpected results.'))
    parser.add_argument('-p', '--pytest', action='append', help=(
        'Provide the given argument to pytest. For example, if you did\n'
        '-p=--ignore -p=/path/to/setup.py then you could pass an ignore\n'
        'flag to pytest.'))

    return parser

def run():
    parser = prepare_parser()
    args = parser.parse_args()
    sched = OxScheduler.add_to_schedule(args)

if __name__ == '__main__':
    run()
