"""Script to schedule execution of tests automatically.
"""

import logging
import collections
import argparse

from ox_herd.core.scheduling import SimpleScheduler

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

    return parser

def run():
    parser = prepare_parser()
    args = parser.parse_args()
    sched = SimpleScheduler.add_to_schedule(args)

if __name__ == '__main__':
    run()
