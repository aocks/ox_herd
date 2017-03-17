"""Module for scheduling automatic testing.
"""

import copy
import os
import json
import tempfile
import logging
import datetime
import shlex
import urllib.parse

import pytest

from ox_herd.file_cache import cache_utils

class TestingTask(object):

    def __call__(self, ox_test_args):
        test_file = ox_test_args.json_file if ox_test_args.json_file else (
            tempfile.mktemp(suffix='.json'))
        url, cmd_line = self.do_test(ox_test_args, test_file)
        self.make_report(ox_test_args, test_file, url, cmd_line)
        if not ox_test_args.json_file:
            logging.debug('Removing temporary json report %s', test_file)
            os.remove(test_file) # remove temp file

    @staticmethod
    def do_test(ox_test_args, test_file):
        url = urllib.parse.urlparse(ox_test_args.url)
        if url.scheme == 'file':
            cmd_line = [url.path, '--json', test_file, '-v']
            pta = ox_test_args.pytest
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
    def make_report(ox_test_args, test_json, url, cmd_line):
        test_data = json.load(open(test_json))['report']
        test_data['url'] = url
        test_data['cmd_line'] = cmd_line
        test_time = datetime.datetime.strptime(
            test_data['created_at'].split('.')[0], '%Y-%m-%d %H:%M:%S')
        rep_name = ox_test_args.name + test_time.strftime('_%Y%m%d_%H%M%S.pkl')
        cache_utils.pickle_with_name(test_data, 'test_results/%s' % rep_name)


class SimpleScheduler(object):

    @classmethod
    def add_to_schedule(cls, args):
        name = 'schedule_via_%s' % args.manager
        func = getattr(cls, name)
        task = TestingTask()
        return func(args, task)

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
        if args.cron_string:
            return scheduler.cron(
                args.cron_string, func=task, timeout=args.timeout,
                kwargs={'ox_test_args' : args})
        else:
            raise ValueError('No scheduling method for rq task.')

    @staticmethod
    def cancel_job(job):
        import rq_scheduler
        from redis import Redis
        scheduler = rq_scheduler.Scheduler(connection=Redis())
        return scheduler.cancel(job)

    @staticmethod
    def launch_job(job_id):
        logging.warning('Preparing to launch job with id %s', str(job_id))
        import rq_scheduler
        from rq.job import Job
        from redis import Redis
        scheduler = rq_scheduler.Scheduler(connection=Redis())
        old_job = Job.fetch(job_id, connection=scheduler.connection)
        ox_test_args = old_job.kwargs['ox_test_args']
        my_args = copy.deepcopy(ox_test_args)
        task = TestingTask()
        new_job = scheduler.enqueue_in(
            datetime.timedelta(0), func=task, ox_test_args=my_args)
        logging.warning('Launching new job with args' + str(my_args))
        return new_job
        

    @staticmethod
    def find_job(target_job):
        import rq_scheduler
        from redis import Redis
        scheduler = rq_scheduler.Scheduler(connection=Redis())
        job_list = scheduler.get_jobs()
        for job in job_list:
            if job.id == target_job:
                return job
        return None


    @staticmethod
    def get_scheduled_tests():
        results = []
        try:
            import rq_scheduler
            from redis import Redis
            scheduler = rq_scheduler.Scheduler(connection=Redis())
            jobs = scheduler.get_jobs()
            for item in jobs:
                try:
                    ox_test_args = item.kwargs.get('ox_test_args', None)
                    if ox_test_args is not None:
                        cron_string = item.meta.get('cron_string',None)
                        if cron_string:
                            my_item = copy.deepcopy(ox_test_args)
                            my_item.schedule = item.meta.get('cron_string','')
                            my_item.jid = item.id
                            results.append(my_item)
                        else:
                            logging.info('Skipping task without cron_string.'
                                         'Probably was just a one-off launch.')
                except Exception as problem:
                    logging.warning(
                        'Skipping job %s in get_scheduled_tests due to exception %s',
                        str(item), problem)
        except ImportError as prob:
            logging.debug('No python rq tasks since unable to import: %s',
                          prob)

        return results

