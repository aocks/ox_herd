"""Module for scheduling jobs.
"""

import logging

try: # try to import rq_scheduler and redis but allow other modes if fail
    import rq
    from rq.job import Job
    from rq import get_failed_queue, Queue
    import rq_scheduler
    from redis import Redis
except Exception as problem:
    logging.error('Could not import rq_scheduler and redis because %s.\n%s',
                  str(problem), 'Continue with non-rq options.')
    

class SimpleScheduler(object):

    @classmethod
    def add_to_schedule(cls, my_ox_job, manager):
        name = 'schedule_via_%s' % manager
        func = getattr(cls, name)
        return func(my_ox_job)

    @staticmethod
    def schedule_via_instant(my_ox_job):
        return my_ox_job()
        
    @staticmethod
    def schedule_via_rq(my_ox_job):
        queue_name = my_ox_job.ox_herd_args.queue_name
        scheduler = rq_scheduler.Scheduler(
            connection=Redis(), queue_name=queue_name)
        if my_ox_job.cron_string:
            return scheduler.cron(
                my_ox_job.cron_string, func=my_ox_job,
                timeout=my_ox_job.ox_herd_args.timeout,
                queue_name=queue_name)
        else:
            raise ValueError('No scheduling method for rq task.')

    @staticmethod
    def cancel_job(job):
        scheduler = rq_scheduler.Scheduler(connection=Redis())
        return scheduler.cancel(job)

    @staticmethod
    def cleanup_job(job_id):
        conn = Redis()
        failed_queue = get_failed_queue(conn)
        failed_queue.remove(job_id)
        return 'Removed job %s' % str(job_id)


    @staticmethod
    def requeue_job(job_id):
        conn = Redis()
        failed_queue = get_failed_queue(conn)
        result = failed_queue.requeue(job_id)
        return result

    @classmethod
    def launch_job(cls, job_id):
        logging.warning('Preparing to launch job with id %s', str(job_id))
        old_job = cls.find_job(job_id)
        func = old_job.func
        ox_job = func.make_copy()
        my_queue = rq.Queue(ox_job.ox_herd_args.queue_name, connection=Redis())
        new_job = my_queue.enqueue(ox_job, kwargs={'is_ox_job': True})
        logging.warning('Launching new job with args' + str(
            ox_job.ox_herd_args))
        return new_job

    @staticmethod
    def find_job(target_job):
        scheduler = rq_scheduler.Scheduler(connection=Redis())
        job = Job.fetch(target_job, connection=scheduler.connection)
        if job:
            return job

        # FIXME: stuff below probably obsolete

        job_list = scheduler.get_jobs()
        for job in job_list:
            if job.id == target_job:
                return job
        return None

    @staticmethod
    def get_failed_jobs():
        results = []
        conn = Redis()
        failed = get_failed_queue(conn)
        failed_jobs = failed.jobs
        for item in failed_jobs:
            kwargs = getattr(item, 'kwargs', {})
            if kwargs.get('is_ox_job', False):
                results.append(item)
        return results

    @staticmethod
    def get_scheduled_jobs():
        results = []
        scheduler = rq_scheduler.Scheduler(connection=Redis())
        jobs = scheduler.get_jobs()
        for item in jobs:
            if not getattr(item, 'kwargs').get('is_ox_job', False):
                continue
            try:
                cron_string = item.meta.get('cron_string', None)
                if cron_string:
                    results.append(item)
                else:
                    logging.info('Skipping task without cron_string.'
                                 'Probably was just a one-off launch.')
            except Exception as problem:
                logging.warning(
                    'Skip job %s in get_scheduled_jobs due to exception %s',
                    str(item), problem)

        return results

    @staticmethod
    def get_queued_jobs(allowed_queues=None):
        queue = Queue(connection=Redis())
        all_jobs = queue.jobs
        if not allowed_queues:
            return all_jobs
        else:
            return [j for j in all_jobs if j.origin in allowed_queues]
