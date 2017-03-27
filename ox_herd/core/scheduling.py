"""Module for scheduling jobs.
"""

import logging

try: # try to import rq_scheduler and redis but allow other modes if fail
    import rq
    from rq.job import Job, UnpickleError
    from rq import get_failed_queue, Queue
    import rq_scheduler
    from redis import Redis
except Exception as problem:
    logging.error('Could not import rq_scheduler and redis because %s.\n%s',
                  str(problem), 'Continue with non-rq options.')
    

class OxScheduler(object):

    @classmethod
    def add_to_schedule(cls, ox_herd_task, manager):
        name = 'schedule_via_%s' % manager
        sched_func = getattr(cls, name)
        return sched_func(ox_herd_task)

    @staticmethod
    def schedule_via_instant(ox_herd_task):
        return ox_herd_task.func(ox_herd_task=ox_herd_task)
        
    @staticmethod
    def schedule_via_rq(ox_herd_task):
        rq_kw = dict([(name, getattr(ox_herd_task, name)) 
                      for name in ox_herd_task.rq_fields])
        scheduler = rq_scheduler.Scheduler(
            connection=Redis(), queue_name=rq_kw.pop('queue_name'))
        if rq_kw['cron_string']:
            return scheduler.cron(
                rq_kw.pop('cron_string'), rq_kw.pop('func'),
                kwargs={'ox_herd_task' : ox_herd_task}, **rq_kw)
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
        old_args = old_job.kwargs['ox_herd_task']
        my_args = old_args.make_copy(old_args)
        rq_kw = dict([(name, getattr(my_args, name)) 
                      for name in my_args.rq_fields])
        rq_kw.pop('cron_string') # launching now so get rid of cron_string
        my_queue = rq.Queue(rq_kw.pop('queue_name'), connection=Redis())
        new_job = my_queue.enqueue(
            rq_kw.pop('func'), kwargs={'ox_herd_task' : my_args}, **rq_kw)
        logging.warning('Launching new job with args' + str(my_args))

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
            try:
                kwargs = getattr(item, 'kwargs', {})
            except UnpickleError as problem:
                logging.info('Could not unickle %s because %s; skip',
                             str(item), str(problem))
                continue
            if kwargs.get('ox_herd_task', None) is not None:
                results.append(item)
        return results

    @staticmethod
    def get_scheduled_jobs():
        results = []
        scheduler = rq_scheduler.Scheduler(connection=Redis())
        jobs = scheduler.get_jobs()
        for item in jobs:
            try:
                if not getattr(item, 'kwargs').get('ox_herd_task', None):
                    continue
            except UnpickleError as problem:
                logging.info('Could not unickle %s because %s; skip',
                             str(item), str(problem))
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
