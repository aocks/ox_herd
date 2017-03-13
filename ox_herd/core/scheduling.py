"""Module for scheduling automatic testing.
"""

import copy
import os
import json
import tempfile
import logging
import datetime
import urllib.parse

import pytest

from ox_herd.file_cache import cache_utils

class TestingTask(object):

    def __call__(self, ox_test_args):
        test_file = ox_test_args.json_file if ox_test_args.json_file else (
            tempfile.mktemp())
        self.do_test(ox_test_args, test_file)
        self.make_report(ox_test_args, test_file)
        if not ox_test_args.json_file:
            logging.debug('Removing temporary json report %s', test_file)
            os.remove(test_file) # remove temp file

    @staticmethod
    def do_test(ox_test_args, test_file):
        url = urllib.parse.urlparse(ox_test_args.url)
        if url.scheme == 'file':
            logging.warning('Checking %s', url.path)
            pytest.main([url.path, '--json', test_file])
        else:
            raise ValueError('URL scheme of %s not handled yet.' % url.scheme)

    @staticmethod
    def make_report(ox_test_args, test_json):
        test_data = json.load(open(test_json))['report']
        test_time = datetime.datetime.strptime(
            test_data['created_at'].split('.')[0], '%Y-%m-%d %H:%M:%S')
        rep_name = ox_test_args.name + test_time.strftime('_%Y%m%d_%H%M%S.pkl')
        cache_utils.pickle_with_name(test_data, 'test_results/%s' % rep_name)

class SimpleScheduler(object):

    @classmethod
    def add_to_schedule(cls, args):
        name = 'schedule_via_%s' % args.manager
        func = getattr(cls, name)
        task = TestingTask(args)        
        func(args, task)

    @staticmethod
    def schedule_via_instant(args, task):
        return task(ox_test_args=args)
        
    @staticmethod
    def schedule_via_rq(args, task):
        try:
            import rq_scheduler
            from redis import Redis
        except ImportError as prob:
            msg = 'Error importing rq_scheduler and redis: %s.\n%s\n' % (
                prob, 'Install rq_scheduler and redis to use this manager.')
            logging.error(msg)
            raise
        scheduler = rq_scheduler.Scheduler(connection=Redis())
        scheduler.cron(args.cron, func=task, timeout=args.timeout,
                       kwargs={'ox_test_args' : args})

    @staticmethod
    def get_scheduled_tests():
        results = []
        try:
            import rq_scheduler
            from redis import Redis
            scheduler = rq_scheduler.Scheduler(connection=Redis())
            jobs = scheduler.get_jobs()
            for item in jobs:
                ox_test_args = item.kwargs.get('ox_test_args', None)
                if ox_test_args is not None:
                    results.append(copy.deepcopy(ox_test_args))
                    results[-1].schedule = item.meta['cron_string']
        except ImportError as prob:
            logging.debug('No python rq tasks since unable to import: %s',
                          prob)

        return results

